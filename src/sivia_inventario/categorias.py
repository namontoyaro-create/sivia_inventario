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


def validar_catalogo(catalogo: tuple[ProductoCatalogo, ...]) -> None:
    """Rechaza campos obligatorios vacíos e identificadores duplicados.

    Varios productos pueden compartir una clase de IA.
    """
    identificadores: set[str] = set()
    campos_obligatorios = (
        "id", "producto", "familia", "presentacion", "unidad_conteo", "clase_ia"
    )

    for producto in catalogo:
        for campo in campos_obligatorios:
            valor = getattr(producto, campo)
            if not isinstance(valor, str) or not valor.strip():
                raise ValueError(
                    f"El campo '{campo}' debe contener texto en el producto "
                    f"{producto.id!r}."
                )

        if producto.id in identificadores:
            raise ValueError(f"Identificador duplicado: {producto.id}")
        identificadores.add(producto.id)


if __name__ == "__main__":
    validar_catalogo(CATALOGO)
    print("Catálogo validado correctamente.")
    print(f"SIVIA - Catálogo inicial: {len(CATALOGO)} productos\n")

    for producto in CATALOGO:
        print(
            f"{producto.id} | {producto.producto} | "
            f"{producto.presentacion} | {producto.clase_ia} | "
            f"{producto.unidad_conteo}"
        )
