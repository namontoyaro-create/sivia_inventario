"""Auditoría segura de imágenes nuevas para una futura mejora de YOLO.

No modifica anotaciones aprobadas, no exporta datasets ni entrena modelos.
"""

from __future__ import annotations

import html
import json
from collections import Counter
from pathlib import Path

import cv2

from sivia_inventario.categorias import CATALOGO
from sivia_inventario.dataset import EXTENSIONES_IMAGEN, MANIFIESTO, RAIZ, cargar_imagen, sha256


PREPARACION = RAIZ / "datos" / "anotaciones" / "preparacion_v2.json"
REGISTRO_NUEVAS = RAIZ / "datos" / "anotaciones" / "registro_procedencia_nuevas.json"
PROPUESTAS_PENDIENTES = RAIZ / "datos" / "anotaciones" / "propuestas_anotaciones_pendientes.json"
GALERIA_PENDIENTES = RAIZ / "resultados" / "revision_anotaciones_pendientes"
ORIGENES_VALIDOS = {"internet", "prueba_fisica", "distribuidora_atencio"}
SPLITS_VALIDOS = {"train", "val", "test"}
CLASES = {producto.clase_ia for producto in CATALOGO}
SPLITS_APROBACIONES = {
    "datos/imagenes/candado/candado1.jpg": "train",
    "datos/imagenes/candado/candado3.jpg": "train",
    "datos/imagenes/candado/candado5.jpg": "val",
    "datos/imagenes/tuberia_pvc/tuvo1.jpg": "train",
    "datos/imagenes/tuberia_pvc/tuvo6.jpg": "train",
    "datos/imagenes/tuberia_pvc/tuvo7.jpg": "val",
    "datos/imagenes/candado/Candado2.jpg": "train",
    "datos/imagenes/candado/candado4.jpg": "val",
    "datos/imagenes/tuberia_pvc/tuvo2.jpg": "val",
}

# Metas mínimas para un siguiente piloto más diverso. No sustituyen una
# evaluación real y no aprueban imágenes ni generan etiquetas por sí mismas.
METAS_V3 = {"train": 20, "val": 6, "test": 5}


def cargar_json(ruta: Path) -> dict:
    return json.loads(ruta.read_text(encoding="utf-8"))


def auditar_imagenes_nuevas(
    manifiesto: Path = MANIFIESTO,
    registro: Path = REGISTRO_NUEVAS,
    raiz: Path = RAIZ,
) -> dict:
    """Informa imágenes nuevas sin moverlas ni modificar su anotación."""
    raiz = Path(raiz)
    base = cargar_json(Path(manifiesto))
    existentes = {entrada["archivo"] for entrada in base["imagenes"]}
    hashes_existentes = {entrada["sha256"] for entrada in base["imagenes"]}
    por_archivo = {entrada["archivo"]: entrada for entrada in cargar_json(Path(registro)).get("imagenes", [])}
    nuevas, duplicados = [], []
    for clase in sorted(CLASES):
        carpeta = raiz / "datos" / "imagenes" / clase
        for ruta in sorted(carpeta.iterdir() if carpeta.exists() else []):
            if not ruta.is_file() or ruta.suffix.lower() not in EXTENSIONES_IMAGEN:
                continue
            archivo = ruta.relative_to(raiz).as_posix()
            if archivo in existentes:
                continue
            registro_imagen = por_archivo.get(archivo, {})
            if sha256(ruta) in hashes_existentes:
                duplicados.append({"archivo": archivo, "motivo": "Duplicado exacto del manifiesto aprobado."})
                continue
            nuevas.append({
                "archivo": archivo,
                "clase_ia": clase,
                "origen": registro_imagen.get("origen", "origen_no_confirmado"),
                "grupo_escena": registro_imagen.get("grupo_escena", "pendiente_declarar"),
                "split_propuesto": registro_imagen.get("split_propuesto", "sin_reservar"),
                "estado": "pendiente_revision_visual",
            })
    return {
        "estado": "preparacion_sivia_sin_exportar",
        "nuevas_pendientes_revision": nuevas,
        "duplicados_exactos": duplicados,
        "nota": "No se modifica el manifiesto, el dataset, el modelo ni el inventario.",
    }


def plan_mejora_dataset(manifiesto: Path = MANIFIESTO) -> list[dict]:
    """Resume cobertura y faltantes sin alterar el manifiesto ni las fotos."""
    datos = cargar_json(Path(manifiesto))
    resultado = []
    for clase in datos["clases"]:
        fila = {"clase": clase, "splits": {}, "escenas_multiples": 0, "excluidas": 0}
        for split, meta in METAS_V3.items():
            imagenes = [
                entrada for entrada in datos["imagenes"]
                if entrada.get("estado") != "excluida" and entrada.get("split") == split
                and any(objeto.get("clase") == clase for objeto in entrada.get("objetos", []))
            ]
            fila["splits"][split] = {"actual": len(imagenes), "meta": meta, "faltan": max(0, meta - len(imagenes))}
            fila["escenas_multiples"] += sum(len(entrada.get("objetos", [])) > 1 for entrada in imagenes)
        fila["excluidas"] = sum(
            entrada.get("estado") == "excluida" and clase in Path(entrada["archivo"]).parts
            for entrada in datos["imagenes"]
        )
        fila["prioridad"] = "alta" if clase in {"candado", "tuberia_pvc", "bolsa_cemento", "disco_corte", "caja_discos_corte"} else "media"
        resultado.append(fila)
    return resultado


def registrar_procedencia_imagen(
    archivo: str,
    origen: str,
    grupo_escena: str,
    split_propuesto: str,
    registro: Path = REGISTRO_NUEVAS,
    raiz: Path = RAIZ,
) -> None:
    """Registra la procedencia y destino sin aprobar ni anotar la imagen."""
    if origen not in ORIGENES_VALIDOS or split_propuesto not in SPLITS_VALIDOS:
        raise ValueError("El origen o el destino propuesto no son válidos.")
    ruta = (Path(raiz) / archivo).resolve()
    imagenes_raiz = (Path(raiz) / "datos" / "imagenes").resolve()
    if imagenes_raiz not in ruta.parents or not ruta.is_file() or ruta.suffix.lower() not in EXTENSIONES_IMAGEN:
        raise ValueError("La fotografía debe existir dentro de datos/imagenes.")
    clase = Path(archivo).parent.name
    if clase not in CLASES:
        raise ValueError("La carpeta de la fotografía no corresponde a una clase de SIVIA.")
    grupo = grupo_escena.strip()
    if not grupo:
        raise ValueError("Indica un grupo de escena para evitar fugas entre conjuntos.")
    datos = cargar_json(Path(registro))
    nueva = {
        "archivo": archivo,
        "clase_ia": clase,
        "origen": origen,
        "grupo_escena": grupo,
        "split_propuesto": split_propuesto,
    }
    imagenes = datos.setdefault("imagenes", [])
    for indice, existente in enumerate(imagenes):
        if existente.get("archivo") == archivo:
            imagenes[indice] = {**existente, **nueva}
            break
    else:
        imagenes.append(nueva)
    Path(registro).write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def resumen_clases(objetos: list[dict]) -> str:
    """Resume las clases declaradas en la propuesta, sin inferirlas del archivo."""
    conteos = Counter(objeto["clase"] for objeto in objetos)
    return ", ".join(f"{cantidad} {clase}" for clase, cantidad in sorted(conteos.items()))


def propuestas_pendientes(ruta: Path = PROPUESTAS_PENDIENTES) -> list[dict]:
    """Obtiene solo las propuestas que aún esperan una decisión humana."""
    return [
        propuesta for propuesta in cargar_json(Path(ruta)).get("imagenes", [])
        if propuesta.get("estado", "pendiente_revision_visual") == "pendiente_revision_visual"
    ]


def actualizar_rectangulos_propuesta(
    archivo: str,
    objetos: list[dict],
    ruta: Path = PROPUESTAS_PENDIENTES,
) -> None:
    """Actualiza una propuesta pendiente desde la interfaz, nunca el manifiesto."""
    from sivia_inventario.dataset import validar_caja

    if not objetos or any(objeto.get("clase") not in CLASES for objeto in objetos):
        raise ValueError("La propuesta debe conservar objetos de clases válidas.")
    for objeto in objetos:
        validar_caja(objeto.get("xyxy"))
    datos = cargar_json(Path(ruta))
    for propuesta in datos.get("imagenes", []):
        if propuesta["archivo"] == archivo and propuesta.get("estado", "pendiente_revision_visual") == "pendiente_revision_visual":
            propuesta["objetos"] = objetos
            propuesta["nota_revision"] = "Rectángulos ajustados manualmente desde Entrenamiento IA; pendiente de aprobación."
            Path(ruta).write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return
    raise ValueError("No se encontró una propuesta pendiente para actualizar.")


def rechazar_propuesta(archivo: str, motivo: str, ruta: Path = PROPUESTAS_PENDIENTES) -> None:
    """Conserva una propuesta rechazada como historial, sin tocar imágenes."""
    datos = cargar_json(Path(ruta))
    for propuesta in datos.get("imagenes", []):
        if propuesta["archivo"] == archivo and propuesta.get("estado", "pendiente_revision_visual") == "pendiente_revision_visual":
            propuesta["estado"] = "rechazada_usuario"
            propuesta["motivo_rechazo"] = motivo.strip() or "Rechazada desde Entrenamiento IA."
            Path(ruta).write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return
    raise ValueError("No se encontró una propuesta pendiente para rechazar.")


def registrar_aprobaciones(
    archivos: set[str],
    manifiesto: Path = MANIFIESTO,
    propuestas: Path = PROPUESTAS_PENDIENTES,
    raiz: Path = RAIZ,
) -> dict[str, int]:
    """Incorpora únicamente propuestas aprobadas explícitamente por la persona usuaria."""
    datos_manifiesto = cargar_json(Path(manifiesto))
    datos_propuestas = cargar_json(Path(propuestas))
    existentes = {entrada["archivo"] for entrada in datos_manifiesto["imagenes"]}
    nuevas, pendientes = [], []
    objetos_aprobados = 0
    for propuesta in datos_propuestas.get("imagenes", []):
        archivo = propuesta["archivo"]
        if archivo not in archivos:
            pendientes.append(propuesta)
            continue
        if archivo in existentes:
            raise ValueError(f"La imagen ya está registrada en el manifiesto: {archivo}")
        # La propuesta registra su destino antes de la revisión. La lista
        # histórica se mantiene únicamente como respaldo de propuestas antiguas.
        split = SPLITS_APROBACIONES.get(archivo, propuesta.get("split_propuesto"))
        if split not in SPLITS_VALIDOS:
            raise ValueError(f"No hay una asignación de split segura para: {archivo}")
        objetos = propuesta.get("objetos", [])
        if not objetos or any(objeto.get("clase") not in CLASES for objeto in objetos):
            raise ValueError(f"La propuesta no tiene clases válidas: {archivo}")
        ruta_imagen = Path(raiz) / archivo
        imagen = cargar_imagen(ruta_imagen)
        alto, ancho = imagen.shape[:2]
        origen = propuesta.get("origen", "origen_no_confirmado")
        nuevas.append({
            "archivo": archivo,
            "sha256": sha256(ruta_imagen),
            "ancho": ancho,
            "alto": alto,
            "origen": origen,
            "procedencia_documentada": origen != "origen_no_confirmado",
            "estado": "revisada_usuario",
            "tipo_fuente": "apoyo_comercial" if origen == "internet" else "origen_no_confirmado",
            "split": split,
            "grupo": propuesta["grupo_escena"],
            "objetos": objetos,
            "motivo": "Rectángulos aprobados explícitamente para preparación del siguiente entrenamiento.",
        })
        objetos_aprobados += len(objetos)
    if len(nuevas) != len(archivos):
        faltantes = archivos - {entrada["archivo"] for entrada in nuevas}
        raise ValueError(f"No se encontraron propuestas para: {', '.join(sorted(faltantes))}")
    datos_manifiesto["imagenes"].extend(nuevas)
    datos_propuestas["imagenes"] = pendientes
    datos_propuestas["descripcion"] = "Solo conserva propuestas pendientes de revisión y aprobación humana."
    Path(manifiesto).write_text(json.dumps(datos_manifiesto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    Path(propuestas).write_text(json.dumps(datos_propuestas, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"imagenes_aprobadas": len(nuevas), "objetos_aprobados": objetos_aprobados, "pendientes": len(pendientes)}


def generar_galeria_pendiente(
    propuestas: Path = PROPUESTAS_PENDIENTES,
    salida: Path = GALERIA_PENDIENTES,
) -> Path:
    """Renderiza propuestas visuales que permanecen pendientes de aprobación."""
    datos = cargar_json(Path(propuestas))
    salida = Path(salida)
    salida.mkdir(parents=True, exist_ok=True)
    tarjetas = []
    for indice, entrada in enumerate(datos.get("imagenes", [])):
        imagen = cargar_imagen(RAIZ / entrada["archivo"])
        alto, ancho = imagen.shape[:2]
        for numero, objeto in enumerate(entrada["objetos"], start=1):
            x1, y1, x2, y2 = objeto["xyxy"]
            inicio = (round(x1 * ancho), round(y1 * alto))
            fin = (round(x2 * ancho), round(y2 * alto))
            cv2.rectangle(imagen, inicio, fin, (0, 0, 255), max(2, ancho // 250))
            etiqueta = f"{objeto['clase']} #{numero}"
            cv2.putText(imagen, etiqueta, (inicio[0], max(24, inicio[1] - 8)), cv2.FONT_HERSHEY_SIMPLEX, max(0.45, ancho / 1700), (0, 0, 255), max(1, ancho // 600))
        nombre = f"propuesta_{indice:03d}.jpg"
        if not cv2.imwrite(str(salida / nombre), imagen):
            raise ValueError(f"No se pudo escribir {nombre}")
        tarjetas.append(
            f"<article><h2>{html.escape(Path(entrada['archivo']).name)}</h2>"
            f"<p>Origen: {html.escape(entrada['origen'])} · "
            f"{html.escape(resumen_clases(entrada['objetos']))} propuesto(s) · pendiente de aprobación</p>"
            f"<a href=\"{nombre}\"><img src=\"{nombre}\" alt=\"Propuesta de anotación\"></a></article>"
        )
    pagina = """<!doctype html><html lang="es"><meta charset="utf-8"><title>SIVIA · Propuestas pendientes</title><style>body{font:16px system-ui;background:#eef2f5;padding:24px;color:#102a43}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:20px}article{background:#fff;padding:16px;border-radius:12px;box-shadow:0 2px 8px #0001}img{width:100%;height:420px;object-fit:contain}h2{font-size:18px;margin:0 0 8px}p{color:#526b84}</style><h1>SIVIA · Propuestas de anotación pendientes</h1><p>Los rectángulos rojos son propuestas de revisión. No están aprobados, no se exportan al dataset y no provienen de YOLO.</p><main>""" + "".join(tarjetas) + "</main></html>"
    ruta = salida / "index.html"
    ruta.write_text(pagina, encoding="utf-8")
    return ruta


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Revisar fotos nuevas de SIVIA sin entrenar YOLO")
    parser.add_argument("--galeria", action="store_true")
    args = parser.parse_args()
    print(json.dumps(auditar_imagenes_nuevas(), ensure_ascii=False, indent=2))
    if args.galeria:
        print(f"Galería: {generar_galeria_pendiente()}")


if __name__ == "__main__":
    main()
