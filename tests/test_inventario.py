import pytest

from sivia_inventario.categorias import ProductoCatalogo
from sivia_inventario.inventario import ComparacionStock


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
