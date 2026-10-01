from sivia_inventario.categorias import ProductoCatalogo
from sivia_inventario.stock import StockReferencia
from sivia_inventario.verificacion import comparar_conteos


def producto(producto_id: str, clase: str) -> ProductoCatalogo:
    return ProductoCatalogo(
        id=producto_id,
        producto=clase.replace("_", " "),
        familia="Prueba",
        presentacion="Unidad",
        unidad_conteo="Cada unidad visible",
        clase_ia=clase,
    )


def test_comparar_conteos_no_convierte_ausencias_en_cero():
    catalogo = (producto("P001", "candado"), producto("P002", "disco_corte"))
    referencia = StockReferencia("simulados", "Prueba", {"P001": 20, "P002": 30})

    filas = comparar_conteos({"candado": 18}, referencia, catalogo)

    assert filas[0]["estado"] == "faltante"
    assert filas[0]["diferencia"] == -2
    assert filas[1] == {
        "producto_id": "P002",
        "clase": "disco_corte",
        "detectado": None,
        "estado": "sin_deteccion_no_concluyente",
    }


def test_comparar_conteos_con_stock_ausente_indica_desconocido():
    catalogo = (producto("P001", "candado"),)
    referencia = StockReferencia("simulados", "Prueba", {})

    filas = comparar_conteos({"candado": 2}, referencia, catalogo)

    assert filas[0]["estado"] == "stock_desconocido"
