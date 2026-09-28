"""Comparación de cantidades de un producto, sin modificar existencias."""

from dataclasses import dataclass

from sivia_inventario.categorias import CATALOGO, ProductoCatalogo


@dataclass(frozen=True)
class ComparacionStock:
    """Compara cantidades ya asociadas al mismo producto y alcance.

    Ambas cantidades deben usar la misma unidad de inventario. Esta clase
    no resuelve ambigüedades de detección ni verifica la cobertura de una
    imagen; esas condiciones deben comprobarse antes de la comparación.
    """

    producto: ProductoCatalogo
    stock_registrado: int
    stock_detectado: int

    def __post_init__(self) -> None:
        for campo in ("stock_registrado", "stock_detectado"):
            cantidad = getattr(self, campo)
            if (
                not isinstance(cantidad, int)
                or isinstance(cantidad, bool)
                or cantidad < 0
            ):
                raise ValueError(f"{campo} debe ser un entero no negativo.")

    @property
    def diferencia(self) -> int:
        return self.stock_detectado - self.stock_registrado

    @property
    def estado(self) -> str:
        if self.diferencia < 0:
            return "faltante"
        if self.diferencia > 0:
            return "sobrante"
        return "coincide"


if __name__ == "__main__":
    print("SIVIA - Comparación simulada; no analiza imágenes ni modifica stock.")
    candado = next(p for p in CATALOGO if p.id == "P003")
    resultado = ComparacionStock(
        producto=candado,
        stock_registrado=20,
        stock_detectado=18,
    )

    print(f"Producto: {resultado.producto.producto}")
    print(f"Presentación: {resultado.producto.presentacion}")
    print(f"Stock registrado: {resultado.stock_registrado}")
    print(f"Stock detectado (simulado): {resultado.stock_detectado}")
    print(f"Diferencia: {resultado.diferencia}")
    print(f"Estado: {resultado.estado}")
