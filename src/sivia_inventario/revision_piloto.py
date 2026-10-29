"""Registra la revisión visual conservadora del dataset piloto de SIVIA.

No crea cajas nuevas ni borra fotografías. Solo confirma propuestas que muestran
una unidad claramente delimitada y excluye escenas donde el conteo por unidad no
puede verificarse con la imagen disponible.
"""

import argparse
import json
from pathlib import Path

from sivia_inventario.dataset import MANIFIESTO, RAIZ, ruta_manifiesto_controlada


EXCLUSIONES: dict[str, str] = {
    "datos/imagenes/bolsa_cemento/bolsa_cemento_05.jpg": "Pila de bolsas: las unidades individuales no están delimitadas.",
    "datos/imagenes/bolsa_cemento/bolsa_cemento_06.jpg": "Pallet con múltiples bolsas: no permite verificar el conteo por unidad.",
    "datos/imagenes/bolsa_cemento/bolsa_cemento_07.jpg": "Pila de bolsas parcialmente ocluidas; no hay cajas fiables por unidad.",
    "datos/imagenes/bolsa_cemento/bolsa_cemento_08.jpg": "Varias bolsas superpuestas: el conteo individual no se puede confirmar.",
    "datos/imagenes/bolsa_cemento/bolsa_cemento_10.jpg": "Grupo de bolsas superpuestas: faltan límites verificables por unidad.",
    "datos/imagenes/caja_clavos/caja_clavos_06.jpg": "Composición de varias cajas; una sola caja no representa las unidades visibles.",
    "datos/imagenes/caja_clavos/caja_clavos_09.jpg": "Fotografía de estantería con varias cajas pequeñas y ocluidas.",
    "datos/imagenes/candado/candado_04.jpg": "Muestra varios candados; las cajas propuestas no cubren todas las unidades.",
    "datos/imagenes/cerradura_sobreponer/cerradura_sobreponer_09.jpg": "Infografía de producto; no se delimitó la cerradura física de forma fiable.",
    "datos/imagenes/cerradura_sobreponer/cerradura_sobreponer_10.jpg": "Herrajes de puerta, no una cerradura de sobreponer identificable.",
    "datos/imagenes/disco_corte/disco_corte_05.jpg": "Pila de discos: faltan cajas individuales para el conteo.",
    "datos/imagenes/disco_corte/disco_corte_06.jpg": "Conjunto de discos superpuestos; no hay conteo verificable por unidad.",
    "datos/imagenes/disco_corte/disco_corte_07.jpg": "Catálogo con varios discos diferentes; no se anotaron todas las unidades.",
    "datos/imagenes/disco_corte/disco_corte_08.jpg": "Infografía con múltiples discos; no es una escena de conteo anotable.",
    "datos/imagenes/disco_corte/disco_corte_10.jpg": "Dos columnas de varios discos; no están delimitados individualmente.",
    "datos/imagenes/caja_discos_corte/caja_discos_corte_06.jpg": "Maletín y discos sueltos: la presentación caja de discos es ambigua.",
    "datos/imagenes/caja_discos_corte/caja_discos_corte_11.jpg": "Varias presentaciones de cajas en una composición; no se anotaron por unidad.",
    "datos/imagenes/tuberia_pvc/tuberia_pvc_04.jpg": "Collage de tuberías y accesorios; no permite contar tubos individualmente.",
    "datos/imagenes/tuberia_pvc/tuberia_pvc_05.jpg": "Atados de muchos tubos: faltan límites individuales verificables.",
    "datos/imagenes/tuberia_pvc/tuberia_pvc_06.jpg": "Grupo de tubos superpuestos; el conteo individual no es fiable.",
    "datos/imagenes/tuberia_pvc/tuberia_pvc_07.jpg": "Estantería con numerosos tubos; requiere anotación especializada por unidad.",
    "datos/imagenes/tuberia_pvc/tuberia_pvc_08.jpg": "Collage de estanterías con múltiples tubos.",
    "datos/imagenes/tuberia_pvc/tuberia_pvc_09.jpg": "Almacén con numerosos tubos y oclusiones.",
    "datos/imagenes/tuberia_pvc/tuberia_pvc_10.jpg": "Pallet con numerosos tubos; no se delimitan unidades individuales.",
}

# Las dos fotografías individuales de tubería representan la misma escena de
# catálogo. Se mantienen en entrenamiento y la auditoría advertirá que falta
# una imagen independiente de validación para esta clase.
SPLITS_CORREGIDOS = {
    "datos/imagenes/tuberia_pvc/tuberia_pvc_03.jpg": "train",
}


def aplicar_revision(manifiesto: Path = MANIFIESTO, raiz: Path = RAIZ) -> dict[str, int]:
    """Aplica únicamente reglas internas a un manifiesto autorizado."""
    ruta = ruta_manifiesto_controlada(manifiesto, raiz)
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    confirmadas = excluidas = splits = 0
    for entrada in datos["imagenes"]:
        archivo = entrada["archivo"]
        if archivo in EXCLUSIONES:
            if entrada.get("estado") != "excluida" or entrada.get("motivo") != EXCLUSIONES[archivo]:
                entrada["estado"] = "excluida"
                entrada["motivo"] = EXCLUSIONES[archivo]
                excluidas += 1
            continue
        if entrada.get("estado") == "propuesta_automatica":
            entrada["estado"] = "revisada_asistente"
            entrada.pop("motivo", None)
            confirmadas += 1
        if archivo in SPLITS_CORREGIDOS and entrada.get("split") != SPLITS_CORREGIDOS[archivo]:
            entrada["split"] = SPLITS_CORREGIDOS[archivo]
            splits += 1
    datos["descripcion"] = (
        "Dataset piloto revisado visualmente de forma conservadora. "
        "Solo conserva ejemplos con una unidad claramente delimitada; las escenas "
        "con múltiples unidades sin cajas individuales quedan excluidas."
    )
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"confirmadas": confirmadas, "excluidas": excluidas, "splits_corregidos": splits}


def main() -> None:
    parser = argparse.ArgumentParser(description="Aplicar la revisión visual conservadora del dataset piloto")
    parser.add_argument("--manifiesto", type=Path, default=MANIFIESTO)
    args = parser.parse_args()
    print(json.dumps(aplicar_revision(args.manifiesto), ensure_ascii=False))


if __name__ == "__main__":
    main()
