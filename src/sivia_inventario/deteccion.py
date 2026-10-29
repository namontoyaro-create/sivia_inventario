"""Inferencia local, conteo por clase y exportación de resultados revisables."""

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import uuid

import cv2

from sivia_inventario.categorias import CATALOGO
from sivia_inventario.conteo import contar_por_clase
from sivia_inventario.dataset import RAIZ
from sivia_inventario.imagenes import cargar_imagen
from sivia_inventario.seguridad_archivos import resolver_ruta_controlada, sha256_archivo_controlado
from sivia_inventario.stock import cargar_stock_referencia
from sivia_inventario.verificacion import comparar_conteos

MODELO_GENERAL = RAIZ / "modelos/yolo26n.pt"
MODELO_PILOTO = RAIZ / "runs/detect/resultados/entrenamiento_yolo/piloto_v1/weights/best.pt"
MODELO_PILOTO_V2 = RAIZ / "modelos/ferreteria_v2_20261013_021350_326502.pt"
# La interfaz normal no expone esta elección. Para activar un futuro v3 se
# configura SIVIA_DETECTOR_ACTIVO o se actualiza este valor, sin rediseñar UI.
DETECTOR_ACTIVO_PREDETERMINADO = os.getenv("SIVIA_DETECTOR_ACTIVO", "piloto_sivia_v2")


def detectores_disponibles() -> dict[str, dict]:
    """Describe detectores locales sin sustituir el modelo general existente."""
    return {
        "general": {
            "nombre": "YOLO general",
            "ruta": MODELO_GENERAL,
            "experimental": False,
            "descripcion": "Modelo general; sus clases no equivalen necesariamente al catálogo.",
        },
        "piloto_sivia": {
            "nombre": "YOLO piloto SIVIA (best.pt)",
            "ruta": MODELO_PILOTO,
            "experimental": True,
            "descripcion": "Piloto entrenado con referencias comerciales; requiere revisión humana.",
        },
        "piloto_sivia_v2": {
            "nombre": "YOLO piloto SIVIA v2 (best.pt)",
            "ruta": MODELO_PILOTO_V2,
            "experimental": True,
            "descripcion": "Versión v2 experimental; no reemplaza el piloto v1 ni valida inventario físico.",
        },
    }


def detector_activo() -> tuple[str, dict]:
    """Obtiene un único detector para el flujo normal, con respaldo local."""
    detectores = detectores_disponibles()
    for identificador in (DETECTOR_ACTIVO_PREDETERMINADO, "piloto_sivia", "general"):
        datos = detectores.get(identificador)
        if datos and datos["ruta"].is_file():
            return identificador, datos
    raise FileNotFoundError("No hay un modelo YOLO local disponible para SIVIA.")


def ruta_modelo_controlada(ruta: str | Path) -> Path:
    """Acepta pesos locales solo desde las carpetas internas de SIVIA."""
    for directorio in ("modelos", "runs/detect"):
        try:
            return resolver_ruta_controlada(ruta, RAIZ, directorio, extensiones={".pt"})
        except ValueError:
            continue
    raise ValueError("El modelo debe estar en una carpeta interna autorizada de SIVIA.")


def cargar_imagen_verificacion(ruta: str | Path):
    """Carga únicamente evidencia o imágenes del catálogo de SIVIA."""
    for directorio in ("datos/evidencias", "datos/imagenes"):
        try:
            archivo = resolver_ruta_controlada(ruta, RAIZ, directorio)
            return cargar_imagen(archivo, raiz=RAIZ, directorio_autorizado=directorio), archivo, directorio
        except ValueError:
            continue
    raise ValueError("La imagen debe estar en una carpeta autorizada de SIVIA.")


def _iou(caja_a: list[float], caja_b: list[float]) -> float:
    izquierda, arriba = max(caja_a[0], caja_b[0]), max(caja_a[1], caja_b[1])
    derecha, abajo = min(caja_a[2], caja_b[2]), min(caja_a[3], caja_b[3])
    interseccion = max(0.0, derecha - izquierda) * max(0.0, abajo - arriba)
    area_a = max(0.0, caja_a[2] - caja_a[0]) * max(0.0, caja_a[3] - caja_a[1])
    area_b = max(0.0, caja_b[2] - caja_b[0]) * max(0.0, caja_b[3] - caja_b[1])
    union = area_a + area_b - interseccion
    return interseccion / union if union else 0.0


def filtrar_detecciones(detecciones: list[dict]) -> list[dict]:
    """Elimina solo duplicados de la misma clase y marca conflictos entre clases.

    Nunca elimina dos clases distintas: podrían ser objetos físicos diferentes
    superpuestos. Esas predicciones quedan disponibles para revisión humana.
    """
    ordenadas = sorted(detecciones, key=lambda item: item["confianza"], reverse=True)
    conservadas: list[dict] = []
    for deteccion in ordenadas:
        if any(
            previa["clase"] == deteccion["clase"]
            and _iou(previa["xyxy"], deteccion["xyxy"]) >= 0.85
            for previa in conservadas
        ):
            continue
        deteccion["dudosa"] = deteccion["confianza"] < 0.55
        deteccion["conflicto"] = False
        conservadas.append(deteccion)
    for indice, deteccion in enumerate(conservadas):
        for otra in conservadas[indice + 1:]:
            if deteccion["clase"] != otra["clase"] and _iou(deteccion["xyxy"], otra["xyxy"]) >= 0.65:
                deteccion["conflicto"] = otra["conflicto"] = True
                deteccion["dudosa"] = otra["dudosa"] = True
    return conservadas


def procesar_imagen(
    imagen_path: str | Path,
    modelo_path: str | Path = MODELO_GENERAL,
    confianza: float = 0.5,
    salida: Path = RAIZ / "resultados/deteccion",
    stock_path: str | Path | None = None,
    mismo_alcance: bool = False,
) -> dict:
    if isinstance(confianza, bool) or not isinstance(confianza, (float, int)) or not math.isfinite(confianza) or not 0 < confianza <= 1:
        raise ValueError("La confianza debe estar entre 0 (excluido) y 1.")
    if stock_path and not mismo_alcance:
        raise ValueError("Para comparar debe confirmar la misma unidad y alcance con --mismo-alcance.")
    imagen, imagen_path_segura, directorio_imagen = cargar_imagen_verificacion(imagen_path)
    modelo_path = ruta_modelo_controlada(modelo_path)
    referencia = cargar_stock_referencia(stock_path, CATALOGO, RAIZ) if stock_path else None
    ficha = modelo_path.with_suffix(".json")
    metadata = {}
    if ficha.is_file():
        metadata = json.loads(ficha.read_text(encoding="utf-8"))
        if metadata.get("sha256_modelo") != sha256_archivo_controlado(modelo_path, RAIZ, modelo_path.parent.relative_to(RAIZ)):
            raise ValueError("Los pesos no coinciden con la ficha del modelo.")
    from ultralytics import YOLO
    modelo = YOLO(str(modelo_path))
    if modelo.task != "detect":
        raise ValueError("Se requiere un modelo de detección de objetos.")
    compatible = set(modelo.names.values()) == {p.clase_ia for p in CATALOGO}
    if referencia and not compatible:
        raise ValueError("El modelo no tiene las clases del catálogo; no se comparará con inventario.")
    if referencia and not metadata.get("validado_para_inventario", False):
        raise ValueError(
            "El modelo es experimental y no está validado para inventario; "
            "analice la imagen sin stock hasta completar la validación."
        )
    tamano = metadata.get("tamano", 640)
    if type(tamano) is not int or not 32 <= tamano <= 1280 or tamano % 32:
        raise ValueError("Tamaño de inferencia inválido en la ficha del modelo.")
    resultado = modelo.predict(source=imagen, device="cpu", conf=confianza, imgsz=tamano, save=False, verbose=False)[0]
    detecciones = filtrar_detecciones([
        {"clase": resultado.names[int(clase)], "confianza": float(puntuacion), "xyxy": [float(v) for v in caja]}
        for clase, puntuacion, caja in zip(resultado.boxes.cls.cpu().tolist(), resultado.boxes.conf.cpu().tolist(), resultado.boxes.xyxy.cpu().tolist())
    ])
    conteos = contar_por_clase(d["clase"] for d in detecciones)
    reporte = {
        "imagen": str(imagen_path_segura),
        "sha256_imagen": sha256_archivo_controlado(imagen_path_segura, RAIZ, directorio_imagen),
        "modelo": str(modelo_path),
        "sha256_modelo": sha256_archivo_controlado(modelo_path, RAIZ, modelo_path.parent.relative_to(RAIZ)),
        "fecha_utc": datetime.now(timezone.utc).isoformat(),
        "modo": "catalogo_experimental" if compatible else "general",
        "validado_para_inventario": bool(metadata.get("validado_para_inventario", False)),
        "umbral": confianza, "tamano": tamano,
        "detecciones": detecciones, "conteos": conteos, "total": sum(conteos.values()),
        "advertencia": "Predicciones experimentales. Sin detección no significa stock cero. Revise visualmente los resultados; no se modifican existencias.",
    }
    if referencia:
        reporte.update(
            tipo_stock=referencia.tipo_datos,
            stock_archivo=str(Path(stock_path).resolve()),
            sha256_stock=sha256_archivo_controlado(stock_path, RAIZ, "datos"),
            alcance_confirmado=True,
            comparaciones=comparar_conteos(conteos, referencia),
        )
    nombre = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
    salida = resolver_ruta_controlada(salida, RAIZ, "resultados", debe_existir=False)
    carpeta = salida / nombre
    carpeta.mkdir(parents=True, exist_ok=False)
    imagen_salida = carpeta / "detecciones.jpg"
    ok, contenido = cv2.imencode(".jpg", resultado.plot())
    if not ok:
        raise ValueError("No se pudo generar la imagen de resultado.")
    imagen_salida.write_bytes(contenido.tobytes())
    reporte["imagen_resultado"] = str(imagen_salida.resolve())
    reporte["informe"] = str((carpeta / "resultado.json").resolve())
    (carpeta / "resultado.json").write_text(json.dumps(reporte, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return reporte


def main() -> None:
    parser = argparse.ArgumentParser(description="SIVIA - Detección y conteo local")
    parser.add_argument("imagen", type=Path)
    parser.add_argument("--modelo", type=Path, default=MODELO_GENERAL)
    parser.add_argument("--confianza", type=float, default=0.5)
    parser.add_argument("--stock", type=Path)
    parser.add_argument("--mismo-alcance", action="store_true")
    args = parser.parse_args()
    print("SIVIA - Predicciones experimentales; no modifica existencias.", flush=True)
    try:
        reporte = procesar_imagen(args.imagen, args.modelo, args.confianza, stock_path=args.stock, mismo_alcance=args.mismo_alcance)
    except (OSError, ValueError, RuntimeError) as error:
        parser.error(str(error))
    print("Modo:", reporte["modo"])
    for clase, cantidad in reporte["conteos"].items():
        print(f"{clase}: {cantidad}")
    if not reporte["conteos"]:
        print("Sin detecciones por encima del umbral; no significa ausencia de productos.")
    print("Total detectado:", reporte["total"])
    for comparacion in reporte.get("comparaciones", []):
        print(json.dumps(comparacion, ensure_ascii=False))
    print("Imagen:", reporte["imagen_resultado"])
    print("Informe JSON:", reporte["informe"])


if __name__ == "__main__":
    main()
