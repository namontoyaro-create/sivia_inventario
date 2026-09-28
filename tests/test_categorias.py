from dataclasses import replace

import pytest

from sivia_inventario.categorias import (
    CATALOGO,
    ProductoCatalogo,
    validar_catalogo,
)


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


def test_catalogo_inicial_es_valido():
    validar_catalogo(CATALOGO)


def test_rechaza_identificador_duplicado(candado):
    otro = replace(candado, marca="Otra marca")

    with pytest.raises(ValueError, match="Identificador duplicado: PRUEBA001"):
        validar_catalogo((candado, otro))


@pytest.mark.parametrize(
    "campo",
    ["id", "producto", "familia", "presentacion", "unidad_conteo", "clase_ia"],
)
@pytest.mark.parametrize("valor", ["", "   "])
def test_rechaza_campo_obligatorio_vacio(candado, campo, valor):
    incompleto = replace(candado, **{campo: valor})

    with pytest.raises(ValueError, match=f"El campo '{campo}'"):
        validar_catalogo((incompleto,))


def test_permite_productos_distintos_con_misma_clase_ia(candado):
    otro = replace(candado, id="PRUEBA002", marca="Otra marca", tamano="40 mm")

    validar_catalogo((candado, otro))
