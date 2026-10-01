"""Consultas de inventario usadas por la aplicación web."""

from dataclasses import dataclass
from pathlib import Path

from sivia_inventario.base_datos import RUTA_BASE_DATOS, conectar


@dataclass(frozen=True)
class ProductoInventario:
    id: str
    producto: str
    familia: str
    presentacion: str
    clase_ia: str
    stock_registrado: int
    origen_stock: str


def listar_productos(ruta: Path = RUTA_BASE_DATOS) -> list[ProductoInventario]:
    with conectar(ruta) as conexion:
        filas = conexion.execute(
            """
            SELECT id, producto, familia, presentacion, clase_ia,
                   stock_registrado, origen_stock
            FROM productos WHERE activo = 1
            ORDER BY id
            """
        ).fetchall()
    return [ProductoInventario(**dict(fila)) for fila in filas]


def resumen_dashboard(ruta: Path = RUTA_BASE_DATOS) -> dict[str, int]:
    with conectar(ruta) as conexion:
        productos = conexion.execute("SELECT COUNT(*) FROM productos WHERE activo = 1").fetchone()[0]
        stock = conexion.execute("SELECT COALESCE(SUM(stock_registrado), 0) FROM productos WHERE activo = 1").fetchone()[0]
        verificaciones = conexion.execute("SELECT COUNT(*) FROM verificaciones").fetchone()[0]
        diferencias = conexion.execute(
            "SELECT COUNT(*) FROM verificaciones WHERE estado = 'requiere_revision'"
        ).fetchone()[0]
    return {
        "productos_registrados": productos,
        "stock_registrado": stock,
        "verificaciones": verificaciones,
        "diferencias": diferencias,
    }
