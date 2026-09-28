"""Catálogo inicial de productos de ferretería de SIVIA."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ProductoCatalogo:
    """Describe un producto; no representa una detección ni su stock."""

    id: str
    producto: str
    familia: str
    presentacion: str
    unidad_conteo: str
    clase_ia: str

    marca: str | None = None
    modelo: str | None = None
    tamano: str | None = None
    codigo_producto: str | None = None


CATALOGO: tuple[ProductoCatalogo, ...] = (
    ProductoCatalogo(
        id="P001",
        producto="Clavos",
        familia="Fijaciones",
        presentacion="Bolsa",
        unidad_conteo="Cada bolsa visible",
        clase_ia="bolsa_clavos",
    ),
    ProductoCatalogo(
        id="P002",
        producto="Clavos",
        familia="Fijaciones",
        presentacion="Caja",
        unidad_conteo="Cada caja visible",
        clase_ia="caja_clavos",
    ),
    ProductoCatalogo(
        id="P003",
        producto="Candado",
        familia="Cerrajería",
        presentacion="Unidad",
        unidad_conteo="Cada candado visible",
        clase_ia="candado",
    ),
    ProductoCatalogo(
        id="P004",
        producto="Cerradura de sobreponer",
        familia="Cerrajería",
        presentacion="Unidad",
        unidad_conteo="Cada cerradura visible",
        clase_ia="cerradura_sobreponer",
    ),
    ProductoCatalogo(
        id="P005",
        producto="Tubería PVC",
        familia="Tuberías",
        presentacion="Tubo",
        unidad_conteo="Cada tubo visible",
        clase_ia="tuberia_pvc",
    ),
    ProductoCatalogo(
        id="P006",
        producto="Cemento",
        familia="Materiales de construcción",
        presentacion="Bolsa",
        unidad_conteo="Cada bolsa visible",
        clase_ia="bolsa_cemento",
    ),
    ProductoCatalogo(
        id="P007",
        producto="Disco de corte",
        familia="Abrasivos",
        presentacion="Unidad",
        unidad_conteo="Cada disco visible",
        clase_ia="disco_corte",
    ),
)


if __name__ == "__main__":
    print(f"SIVIA - Catálogo inicial: {len(CATALOGO)} productos\n")

    for producto in CATALOGO:
        print(
            f"{producto.id} | {producto.producto} | "
            f"{producto.presentacion} | {producto.clase_ia} | "
            f"{producto.unidad_conteo}"
        )
