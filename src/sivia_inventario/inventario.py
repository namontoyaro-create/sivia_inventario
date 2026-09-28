"""Comparación de cantidades de un producto, sin modificar existencias."""

import argparse
from dataclasses import dataclass

from sivia_inventario.categorias import CATALOGO, ProductoCatalogo
from sivia_inventario.stock import StockReferencia, cargar_stock_referencia


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


def comparar_con_referencia(
    producto: ProductoCatalogo,
    stock_detectado: int,
    referencia: StockReferencia,
) -> ComparacionStock:
    """Compara un conteo ya asociado a un producto con su stock registrado.

    El producto y el alcance del conteo deben estar resueltos previamente.
    Si falta la referencia, no se genera una comparación con cero.
    """
    if producto.id not in referencia.stock_por_producto:
        raise ValueError(f"Stock registrado desconocido para {producto.id}.")

    return ComparacionStock(
        producto=producto,
        stock_registrado=referencia.stock_por_producto[producto.id],
        stock_detectado=stock_detectado,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="SIVIA - Comparar stock de referencia con un conteo simulado"
    )
    parser.add_argument(
        "--stock",
        default="datos/inventario/stock_prueba.json",
        help="Ruta del JSON de stock registrado",
    )
    args = parser.parse_args()
    candado = next(p for p in CATALOGO if p.id == "P003")

    try:
        referencia = cargar_stock_referencia(args.stock, CATALOGO)
        resultado = comparar_con_referencia(
            producto=candado,
            stock_detectado=18,
            referencia=referencia,
        )
    except (OSError, ValueError) as error:
        parser.error(str(error))

    print("SIVIA - Conteo simulado; no analiza imágenes ni modifica stock.")
    print(f"Archivo de referencia: {args.stock}")
    print(f"Stock de referencia: datos {referencia.tipo_datos}")
    print(f"Producto: {resultado.producto.producto}")
    print(f"Presentación: {resultado.producto.presentacion}")
    print(f"Stock registrado: {resultado.stock_registrado}")
    print(f"Stock detectado (simulado): {resultado.stock_detectado}")
    print(f"Diferencia: {resultado.diferencia}")
    print(f"Estado: {resultado.estado}")
