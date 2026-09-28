import json

import pytest

from sivia_inventario.categorias import ProductoCatalogo
from sivia_inventario.inventario import ComparacionStock, comparar_con_referencia
from sivia_inventario.stock import StockReferencia, cargar_stock_referencia


@pytest.fixture
def candado():
    return ProductoCatalogo(
        id="PRUEBA001",
        producto="Candado",
        familia="Cerrajería",
        presentacion="Unidad",
        unidad_conteo="Cada candado visible",
        clase_ia="candado",
    )


@pytest.mark.parametrize(
    "registrado, detectado, diferencia, estado",
    [
        (20, 18, -2, "faltante"),
        (20, 23, 3, "sobrante"),
        (20, 20, 0, "coincide"),
        (0, 0, 0, "coincide"),
        (20, 0, -20, "faltante"),
    ],
)
def test_compara_stock(candado, registrado, detectado, diferencia, estado):
    resultado = ComparacionStock(candado, registrado, detectado)

    assert resultado.producto == candado
    assert resultado.stock_registrado == registrado
    assert resultado.stock_detectado == detectado
    assert resultado.diferencia == diferencia
    assert resultado.estado == estado


@pytest.mark.parametrize("campo", ["stock_registrado", "stock_detectado"])
@pytest.mark.parametrize("valor", [-1, 2.5, True, "20"])
def test_rechaza_stock_invalido(candado, campo, valor):
    cantidades = {"stock_registrado": 20, "stock_detectado": 18}
    cantidades[campo] = valor

    with pytest.raises(ValueError, match=f"{campo} debe ser un entero no negativo"):
        ComparacionStock(producto=candado, **cantidades)


@pytest.mark.parametrize("registrado, diferencia", [(20, -2), (25, -7)])
def test_comparacion_usa_la_cantidad_del_json(tmp_path, candado, registrado, diferencia):
    ruta = tmp_path / "stock.json"
    ruta.write_text(
        json.dumps({
            "tipo_datos": "simulados",
            "descripcion": "Stock de prueba",
            "stock_por_producto": {candado.id: registrado},
        }),
        encoding="utf-8",
    )
    referencia = cargar_stock_referencia(ruta, (candado,))

    resultado = comparar_con_referencia(candado, 18, referencia)

    assert resultado.stock_registrado == registrado
    assert resultado.diferencia == diferencia
    assert resultado.estado == "faltante"
    assert referencia.stock_por_producto[candado.id] == registrado


def test_referencia_ausente_no_se_convierte_en_cero(candado):
    referencia = StockReferencia("simulados", "Sin stock informado", {})

    with pytest.raises(ValueError, match="Stock registrado desconocido.*PRUEBA001"):
        comparar_con_referencia(candado, 18, referencia)


def test_referencia_con_cero_explicito_permite_comparar(candado):
    referencia = StockReferencia("simulados", "Stock cero", {candado.id: 0})

    resultado = comparar_con_referencia(candado, 3, referencia)

    assert resultado.stock_registrado == 0
    assert resultado.diferencia == 3
    assert resultado.estado == "sobrante"
