"""Lectura y validación del stock de referencia almacenado en JSON."""

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from sivia_inventario.categorias import CATALOGO, ProductoCatalogo, validar_catalogo
from sivia_inventario.seguridad_archivos import resolver_ruta_controlada


RAIZ = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class StockReferencia:
    tipo_datos: str
    descripcion: str
    stock_por_producto: dict[str, int]


def _objeto_sin_duplicados(pares: list[tuple[str, object]]) -> dict[str, object]:
    resultado = {}
    for clave, valor in pares:
        if clave in resultado:
            raise ValueError(f"Clave duplicada en el JSON: {clave}")
        resultado[clave] = valor
    return resultado


def cargar_stock_referencia(
    ruta: str | Path,
    catalogo: tuple[ProductoCatalogo, ...],
    raiz: Path = RAIZ,
) -> StockReferencia:
    """Lee cantidades por ID del catálogo sin completar registros ausentes.

    Un producto omitido tiene stock desconocido; cero debe ser explícito.
    La lectura no modifica el archivo, el catálogo ni las existencias.
    """
    validar_catalogo(catalogo)
    archivo = resolver_ruta_controlada(ruta, raiz, "datos", extensiones={".json"})
    texto = archivo.read_text(encoding="utf-8-sig")
    try:
        datos = json.loads(texto, object_pairs_hook=_objeto_sin_duplicados)
    except json.JSONDecodeError as error:
        raise ValueError(f"JSON inválido: {error.msg}") from error

    if not isinstance(datos, dict):
        raise ValueError("El archivo de stock debe contener un objeto JSON.")

    tipo_datos = datos.get("tipo_datos")
    if tipo_datos not in ("simulados", "reales"):
        raise ValueError("tipo_datos debe ser 'simulados' o 'reales'.")

    descripcion = datos.get("descripcion")
    if not isinstance(descripcion, str) or not descripcion.strip():
        raise ValueError("descripcion debe contener texto.")

    stock = datos.get("stock_por_producto")
    if not isinstance(stock, dict):
        raise ValueError("stock_por_producto debe ser un objeto JSON.")

    ids_conocidos = {producto.id for producto in catalogo}
    for producto_id, cantidad in stock.items():
        if producto_id not in ids_conocidos:
            raise ValueError(f"Producto no registrado en el catálogo: {producto_id}")
        if type(cantidad) is not int or cantidad < 0:
            raise ValueError(
                f"El stock de {producto_id} debe ser un entero no negativo."
            )

    return StockReferencia(tipo_datos, descripcion, stock)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SIVIA - Consultar stock de referencia")
    parser.add_argument("archivo", help="Ruta del archivo JSON de stock")
    args = parser.parse_args()

    try:
        referencia = cargar_stock_referencia(args.archivo, CATALOGO)
    except (OSError, ValueError) as error:
        parser.error(str(error))

    print(f"SIVIA - Stock de referencia: datos {referencia.tipo_datos}")
    print(referencia.descripcion)
    for producto in CATALOGO:
        cantidad = referencia.stock_por_producto.get(producto.id)
        stock_texto = "desconocido" if cantidad is None else str(cantidad)
        print(
            f"{producto.id} | {producto.producto} | "
            f"{producto.presentacion} | Stock: {stock_texto}"
        )
