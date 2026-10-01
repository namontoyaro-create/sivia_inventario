"""Inferencia local, conteo por clase y exportación de resultados revisables."""

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import uuid

import cv2

from sivia_inventario.categorias import CATALOGO
from sivia_inventario.conteo import contar_por_clase
from sivia_inventario.dataset import RAIZ, sha256
from sivia_inventario.imagenes import cargar_imagen
from sivia_inventario.stock import cargar_stock_referencia
from sivia_inventario.verificacion import comparar_conteos

MODELO_GENERAL = RAIZ / "modelos/yolo26n.pt"


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
    imagen = cargar_imagen(imagen_path)
    modelo_path = Path(modelo_path).resolve()
    referencia = cargar_stock_referencia(stock_path, CATALOGO) if stock_path else None
    if not modelo_path.is_file() and modelo_path != MODELO_GENERAL:
        raise FileNotFoundError(f"No existe el modelo: {modelo_path}")
    modelo_path.parent.mkdir(parents=True, exist_ok=True)
    ficha = modelo_path.with_suffix(".json")
    metadata = {}
    if ficha.is_file():
        metadata = json.loads(ficha.read_text(encoding="utf-8"))
        if metadata.get("sha256_modelo") != sha256(modelo_path):
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
    detecciones = [
        {"clase": resultado.names[int(clase)], "confianza": float(puntuacion), "xyxy": [float(v) for v in caja]}
        for clase, puntuacion, caja in zip(resultado.boxes.cls.cpu().tolist(), resultado.boxes.conf.cpu().tolist(), resultado.boxes.xyxy.cpu().tolist())
    ]
    conteos = contar_por_clase(d["clase"] for d in detecciones)
    reporte = {
        "imagen": str(Path(imagen_path).resolve()), "sha256_imagen": sha256(Path(imagen_path)),
        "modelo": str(modelo_path), "sha256_modelo": sha256(modelo_path),
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
            sha256_stock=sha256(Path(stock_path)),
            alcance_confirmado=True,
            comparaciones=comparar_conteos(conteos, referencia),
        )
    nombre = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
    carpeta = Path(salida) / nombre
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
