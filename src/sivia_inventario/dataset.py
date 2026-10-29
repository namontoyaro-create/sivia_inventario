"""Audita anotaciones y exporta copias en formato YOLO, sin tocar originales."""

import argparse
from collections import Counter
import html
import json
import math
from pathlib import Path
import shutil

import cv2

from sivia_inventario.categorias import CATALOGO
from sivia_inventario.imagenes import cargar_imagen
from sivia_inventario.seguridad_archivos import (
    leer_archivo_controlado,
    resolver_ruta_controlada,
    sha256_archivo_controlado,
)

RAIZ = Path(__file__).resolve().parents[2]
MANIFIESTO = RAIZ / "datos/anotaciones/ferreteria.json"
EXTENSIONES_IMAGEN = {".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}


def ruta_manifiesto_controlada(manifiesto: str | Path, raiz: Path = RAIZ) -> Path:
    ruta = resolver_ruta_controlada(manifiesto, raiz, "datos", extensiones={".json"})
    raiz_resuelta = Path(raiz).resolve()
    permitidos = (
        (raiz_resuelta / "datos/anotaciones").resolve(),
        (raiz_resuelta / "datos/entrenamiento").resolve(),
    )
    if not any(ruta.is_relative_to(directorio) for directorio in permitidos):
        raise ValueError("El manifiesto debe estar en datos/anotaciones o datos/entrenamiento.")
    return ruta


def ruta_imagen_controlada(archivo: object, raiz: Path = RAIZ) -> Path:
    if not isinstance(archivo, str) or not archivo.strip():
        raise ValueError("Cada imagen debe indicar una ruta relativa válida.")
    return resolver_ruta_controlada(
        archivo, raiz, "datos/imagenes", extensiones=EXTENSIONES_IMAGEN
    )


def sha256(
    ruta: str | Path,
    raiz: Path = RAIZ,
    directorio_autorizado: str | Path = "datos",
) -> str:
    """Compatibilidad: calcula una huella solo tras validar la ubicación."""
    return sha256_archivo_controlado(ruta, raiz, directorio_autorizado)


def cargar_manifiesto_controlado(ruta: str | Path, raiz: Path = RAIZ) -> dict:
    """Lee JSON de manifiestos mediante la única primitiva de lectura segura."""
    _, contenido = leer_archivo_controlado(ruta, raiz, "datos", extensiones={".json"})
    try:
        datos = json.loads(contenido.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("El manifiesto de SIVIA no contiene JSON UTF-8 válido.") from error
    if not isinstance(datos, dict):
        raise ValueError("El manifiesto de SIVIA debe contener un objeto JSON.")
    return datos


def validar_caja(caja: list) -> tuple[float, float, float, float]:
    if not isinstance(caja, list) or len(caja) != 4:
        raise ValueError("Cada caja xyxy debe tener cuatro coordenadas.")
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in caja):
        raise ValueError("Las coordenadas deben ser números finitos.")
    x1, y1, x2, y2 = caja
    if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
        raise ValueError("Caja fuera de límites o sin área; use xyxy normalizado.")
    return (x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1


def proponer_caja(imagen) -> list[float]:
    """Propone una caja amplia para una imagen de producto.

    Es una ayuda de etiquetado, nunca una anotación confirmada. Para fondos
    complejos devuelve una caja amplia que debe corregirse visualmente.
    """
    alto, ancho = imagen.shape[:2]
    gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
    mascara = cv2.inRange(gris, 0, 245)
    mascara = cv2.morphologyEx(mascara, cv2.MORPH_CLOSE, (3, 3))
    contornos, _ = cv2.findContours(mascara, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contornos:
        return [0.02, 0.02, 0.98, 0.98]
    x, y, ancho_caja, alto_caja = cv2.boundingRect(max(contornos, key=cv2.contourArea))
    if ancho_caja * alto_caja < alto * ancho * 0.03:
        return [0.02, 0.02, 0.98, 0.98]
    margen_x = max(2, round(ancho * 0.01))
    margen_y = max(2, round(alto * 0.01))
    return [
        max(0, (x - margen_x) / ancho),
        max(0, (y - margen_y) / alto),
        min(1, (x + ancho_caja + margen_x) / ancho),
        min(1, (y + alto_caja + margen_y) / alto),
    ]


def proponer_anotaciones() -> int:
    """Añade propuestas al manifiesto principal interno, sin cambiar anotadas.

    No recibe rutas desde CLI: la única escritura se limita al manifiesto
    oficial ``datos/anotaciones/ferreteria.json``.
    """
    raiz = RAIZ
    ruta_manifiesto = MANIFIESTO
    datos = cargar_manifiesto_controlado(ruta_manifiesto, raiz)
    clases = [producto.clase_ia for producto in CATALOGO]
    existentes = {entrada["archivo"] for entrada in datos["imagenes"]}
    grupos = {}
    for entrada in datos["imagenes"]:
        if entrada.get("estado") != "excluida" and entrada.get("grupo"):
            grupos.setdefault(entrada["grupo"], entrada.get("split"))
    agregadas = 0

    for clase in clases:
        carpeta = raiz / "datos" / "imagenes" / clase
        for imagen_path in sorted(carpeta.iterdir() if carpeta.is_dir() else []):
            if not imagen_path.is_file() or imagen_path.suffix.lower() not in EXTENSIONES_IMAGEN:
                continue
            ruta_relativa = imagen_path.relative_to(raiz).as_posix()
            if ruta_relativa in existentes:
                continue
            imagen = cargar_imagen(
                ruta_relativa, raiz=raiz, directorio_autorizado="datos/imagenes"
            )
            alto, ancho = imagen.shape[:2]
            numero = sum(1 for entrada in datos["imagenes"] if entrada.get("objetos") and entrada["objetos"][0].get("clase") == clase)
            grupo = f"{clase}_{imagen_path.stem}"
            split = grupos.get(grupo, "val" if numero % 5 == 4 else "train")
            grupos[grupo] = split
            datos["imagenes"].append(
                {
                    "archivo": ruta_relativa,
                    "sha256": sha256(ruta_relativa, raiz, "datos/imagenes"),
                    "ancho": ancho,
                    "alto": alto,
                    "origen": "aportada_por_usuario",
                    "procedencia_documentada": False,
                    "estado": "propuesta_automatica",
                    "split": split,
                    "grupo": grupo,
                    "objetos": [{"clase": clase, "xyxy": proponer_caja(imagen)}],
                }
            )
            agregadas += 1
    cambios_split = normalizar_splits_por_grupo(datos)
    duplicadas = excluir_duplicados_por_hash(datos)
    if agregadas or cambios_split or duplicadas:
        datos["descripcion"] = (
            "Incluye propuestas automáticas de cajas para las imágenes nuevas. "
            "Las propuestas requieren revisión visual antes del entrenamiento definitivo."
        )
        ruta_manifiesto.write_text(
            json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return agregadas


def normalizar_splits_por_grupo(datos: dict) -> int:
    """Mantiene todas las variantes de una escena en la misma partición."""
    destino_por_grupo = {}
    for entrada in datos["imagenes"]:
        if entrada.get("estado") == "excluida" or not entrada.get("grupo"):
            continue
        grupo = entrada["grupo"]
        if grupo not in destino_por_grupo:
            destino_por_grupo[grupo] = entrada.get("split")
    cambios = 0
    for entrada in datos["imagenes"]:
        grupo = entrada.get("grupo")
        if grupo in destino_por_grupo and entrada.get("split") != destino_por_grupo[grupo]:
            entrada["split"] = destino_por_grupo[grupo]
            cambios += 1
    return cambios


def excluir_duplicados_por_hash(datos: dict) -> int:
    """Excluye copias exactas sin borrar ninguna imagen del proyecto."""
    vistas = set()
    cambios = 0
    for entrada in datos["imagenes"]:
        if entrada.get("estado") == "excluida":
            continue
        huella = entrada.get("sha256")
        if huella in vistas:
            entrada["estado"] = "excluida"
            entrada["motivo"] = "Copia idéntica de otra imagen del manifiesto; se conserva, pero no se duplica en entrenamiento."
            cambios += 1
        else:
            vistas.add(huella)
    return cambios


def auditar(
    manifiesto: Path = MANIFIESTO,
    raiz: Path = RAIZ,
    permitir_propuestas: bool = False,
) -> tuple[dict, dict]:
    raiz = Path(raiz).resolve()
    ruta_manifiesto = ruta_manifiesto_controlada(manifiesto, raiz)
    datos = cargar_manifiesto_controlado(ruta_manifiesto, raiz)
    clases = [p.clase_ia for p in CATALOGO]
    if datos.get("version") != 1 or datos.get("clases") != clases:
        raise ValueError("Versión o clases del manifiesto incompatibles con el catálogo.")
    if not isinstance(datos.get("imagenes"), list) or not datos["imagenes"]:
        raise ValueError("El manifiesto no contiene imágenes.")
    rutas, hashes, grupos = set(), {}, {}
    conteos = {s: Counter() for s in ("train", "val", "test")}
    numero_imagenes = Counter()
    excluidas = []
    propuestas = []
    for e in datos["imagenes"]:
        ruta = ruta_imagen_controlada(e.get("archivo"), raiz)
        if ruta in rutas:
            raise ValueError("Ruta fuera del proyecto o repetida.")
        rutas.add(ruta)
        if sha256(ruta, raiz, "datos/imagenes") != e.get("sha256"):
            raise ValueError(f"La imagen cambió desde su anotación: {e['archivo']}")
        imagen = cargar_imagen(ruta, raiz=raiz, directorio_autorizado="datos/imagenes")
        if imagen.shape[:2] != (e.get("alto"), e.get("ancho")):
            raise ValueError(f"Dimensiones incorrectas: {e['archivo']}")
        if e.get("estado") == "excluida":
            if not e.get("motivo"):
                raise ValueError("Toda exclusión necesita un motivo.")
            excluidas.append({"archivo": e["archivo"], "motivo": e["motivo"]})
            continue
        if e.get("estado") == "propuesta_automatica":
            propuestas.append(e["archivo"])
            if not permitir_propuestas:
                raise ValueError(
                    "Hay propuestas automáticas pendientes de revisión: "
                    f"{e['archivo']}."
                )
        elif e.get("estado") not in ("revisada_asistente", "revisada_usuario"):
            raise ValueError(f"Anotación pendiente de revisión: {e['archivo']}")
        split = e.get("split")
        if split not in conteos or not isinstance(e.get("grupo"), str) or not e["grupo"].strip():
            raise ValueError("Cada imagen necesita split y grupo de escena.")
        if e["sha256"] in hashes:
            raise ValueError("Imagen duplicada por contenido; no debe repetirse en el dataset.")
        hashes[e["sha256"]] = split
        if e["grupo"] in grupos and grupos[e["grupo"]] != split:
            raise ValueError("Fuga de datos: un grupo de escena aparece en distintos splits.")
        grupos[e["grupo"]] = split
        objetos = e.get("objetos")
        if not isinstance(objetos, list) or (not objetos and e.get("negativa") is not True):
            raise ValueError("Una imagen sin objetos debe declararse negativa explícitamente.")
        for objeto in objetos:
            if objeto.get("clase") not in clases:
                raise ValueError(f"Clase desconocida: {objeto.get('clase')}")
            validar_caja(objeto.get("xyxy"))
            conteos[split][objeto["clase"]] += 1
        numero_imagenes[split] += 1
    if not numero_imagenes["train"] or not numero_imagenes["val"]:
        raise ValueError("Se necesitan imágenes diferentes para train y val.")
    ausentes_train = [c for c in clases if not conteos["train"][c]]
    if ausentes_train:
        raise ValueError(f"Clases sin ejemplos de entrenamiento: {ausentes_train}")
    avisos = ["Dataset piloto: no acredita precisión ni conteo fiable en un almacén."]
    sin_val = [c for c in clases if not conteos["val"][c]]
    if sin_val:
        avisos.append(f"Sin ejemplos independientes de validación: {', '.join(sin_val)}.")
    if not numero_imagenes["test"]:
        avisos.append("No existe conjunto de prueba independiente.")
    if propuestas:
        avisos.append(
            f"Hay {len(propuestas)} propuestas automáticas pendientes; no se exportarán para entrenamiento."
        )
    avisos.append("Revisar procedencia de imágenes y añadir escenas reales, variadas y mezcladas.")
    informe = {
        "experimental": True,
        "imagenes": dict(numero_imagenes),
        "objetos": {s: {c: conteos[s][c] for c in clases} for s in conteos},
        "excluidas": excluidas,
        "propuestas_pendientes": propuestas,
        "advertencias": avisos,
        "sha256_manifiesto": sha256(ruta_manifiesto, raiz, "datos"),
    }
    return datos, informe


def exportar(manifiesto: Path, salida: Path, raiz: Path = RAIZ) -> Path:
    raiz = Path(raiz).resolve()
    datos, informe = auditar(manifiesto, raiz)
    ruta_manifiesto = ruta_manifiesto_controlada(manifiesto, raiz)
    salida = resolver_ruta_controlada(salida, raiz, "datos/entrenamiento")
    if salida.exists():
        raise FileExistsError("La salida ya existe. Use --salida con una carpeta nueva; no se borrará nada.")
    salida.mkdir(parents=True)
    for split in ("train", "val", "test"):
        (salida / "images" / split).mkdir(parents=True)
        (salida / "labels" / split).mkdir(parents=True)
    for e in datos["imagenes"]:
        if e["estado"] == "excluida":
            continue
        origen = ruta_imagen_controlada(e["archivo"], raiz)
        nombre = f"{e['sha256'][:12]}_{origen.stem}"
        destino = salida / "images" / e["split"] / (nombre + origen.suffix.lower())
        shutil.copy2(origen, destino)
        if sha256_archivo_controlado(destino, raiz, "datos/entrenamiento") != e["sha256"]:
            raise ValueError("La copia de la imagen no coincide con el original.")
        lineas = []
        for obj in e["objetos"]:
            coordenadas = validar_caja(obj["xyxy"])
            lineas.append(str(datos["clases"].index(obj["clase"])) + " " + " ".join(f"{v:.8f}" for v in coordenadas))
        (salida / "labels" / e["split"] / f"{nombre}.txt").write_text("\n".join(lineas) + ("\n" if lineas else ""), encoding="utf-8")
    config = {"path": salida.as_posix(), "train": "images/train", "val": "images/val", "names": datos["clases"]}
    if informe["imagenes"].get("test"):
        config["test"] = "images/test"
    # JSON es un subconjunto de YAML: evita otra dependencia directa.
    (salida / "data.yaml").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    (salida / "informe.json").write_text(json.dumps(informe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    shutil.copy2(ruta_manifiesto, salida / "anotaciones.json")
    return salida / "data.yaml"


def generar_revision(manifiesto: Path, salida: Path, raiz: Path = RAIZ) -> Path:
    raiz = Path(raiz).resolve()
    datos, informe = auditar(manifiesto, raiz, permitir_propuestas=True)
    salida = resolver_ruta_controlada(salida, raiz, "resultados")
    salida.mkdir(parents=True, exist_ok=True)
    tarjetas = []
    for i, e in enumerate(datos["imagenes"]):
        imagen = cargar_imagen(e["archivo"], raiz=raiz, directorio_autorizado="datos/imagenes")
        h, w = imagen.shape[:2]
        for obj in e["objetos"]:
            x1, y1, x2, y2 = obj["xyxy"]
            a, b = (round(x1*w), round(y1*h)), (round(x2*w), round(y2*h))
            cv2.rectangle(imagen, a, b, (0, 0, 255), max(2, w//250))
            cv2.putText(imagen, obj["clase"], (a[0], max(20, a[1]-5)), cv2.FONT_HERSHEY_SIMPLEX, max(.5, w/1500), (0,0,255), max(1,w//500))
        ok, contenido = cv2.imencode(".jpg", imagen)
        if not ok:
            raise ValueError("No se pudo generar la revisión.")
        nombre = f"revision_{i:03d}.jpg"
        (salida / nombre).write_bytes(contenido.tobytes())
        estado = e.get("motivo", f"{e.get('estado')} · {e.get('split')} · {len(e['objetos'])} objetos")
        tarjetas.append(f'<article><h2>{html.escape(Path(e["archivo"]).name)}</h2><p>{html.escape(estado)}</p><a href="{nombre}"><img src="{nombre}" alt="Anotaciones"></a></article>')
    documento = '<!doctype html><html lang="es"><meta charset="utf-8"><title>SIVIA · Revisión</title><style>body{font:16px system-ui;background:#eef2f5;padding:24px}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:20px}article{background:white;padding:16px;border-radius:12px}img{width:100%;height:360px;object-fit:contain}h2{font-size:16px}</style><h1>SIVIA · Anotaciones experimentales</h1><p>Rectángulos revisados por el asistente; requieren revisión del responsable del proyecto. No representan detecciones del modelo.</p><main>' + ''.join(tarjetas) + '</main></html>'
    ruta = salida / "index.html"
    ruta.write_text(documento, encoding="utf-8")
    return ruta


def main() -> None:
    parser = argparse.ArgumentParser(description="Auditar y preparar imágenes etiquetadas para YOLO")
    parser.add_argument("--manifiesto", type=Path, default=MANIFIESTO)
    parser.add_argument("--exportar", action="store_true")
    parser.add_argument("--proponer", action="store_true")
    parser.add_argument("--salida", type=Path, default=RAIZ / "datos/entrenamiento/experimental/dataset_yolo")
    parser.add_argument("--revision", action="store_true")
    args = parser.parse_args()
    try:
        if args.proponer:
            print(f"Propuestas agregadas: {proponer_anotaciones()}")
        _, informe = auditar(
            args.manifiesto,
            permitir_propuestas=args.revision and not args.exportar,
        )
        print(json.dumps(informe, ensure_ascii=False, indent=2))
        if args.exportar:
            print("Dataset:", exportar(args.manifiesto, args.salida))
        if args.revision:
            print("Revisión:", generar_revision(args.manifiesto, RAIZ / "resultados/revision_anotaciones"))
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
