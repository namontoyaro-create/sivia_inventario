from dataclasses import replace

import pytest

from sivia_inventario.categorias import CATALOGO, ProductoCatalogo
from sivia_inventario.resumen import relacionar_con_catalogo


def test_relaciona_bolsa_y_caja_por_separado():
    resumen = relacionar_con_catalogo(
        {"bolsa_clavos": 5, "caja_clavos": 2}, CATALOGO
    )

    assert len(resumen) == 2
    bolsa, caja = resumen
    assert bolsa.candidatos[0].presentacion == "Bolsa"
    assert caja.candidatos[0].presentacion == "Caja"
    assert bolsa.candidatos[0].id != caja.candidatos[0].id
    assert (bolsa.cantidad, caja.cantidad) == (5, 2)
    assert all(fila.estado == "coincidencia_unica" for fila in resumen)


def test_conserva_clase_sin_coincidencia():
    fila, = relacionar_con_catalogo({"botella": 4}, CATALOGO)

    assert fila.clase_ia == "botella"
    assert fila.cantidad == 4
    assert fila.candidatos == ()
    assert fila.estado == "sin_coincidencia"


def test_ambiguedad_no_duplica_ni_asigna_el_conteo_a_una_marca():
    primero = ProductoCatalogo(
        id="PRUEBA001",
        producto="Candado",
        familia="Cerrajería",
        presentacion="Unidad",
        unidad_conteo="Cada candado visible",
        clase_ia="candado",
        marca="Marca A",
    )
    segundo = replace(primero, id="PRUEBA002", marca="Marca B")

    resumen = relacionar_con_catalogo({"candado": 3}, (primero, segundo))

    assert len(resumen) == 1
    assert resumen[0].estado == "ambiguo"
    assert resumen[0].candidatos == (primero, segundo)
    assert sum(fila.cantidad for fila in resumen) == 3


def test_conteo_vacio_no_inventa_stock_cero():
    assert relacionar_con_catalogo({}, CATALOGO) == ()


@pytest.mark.parametrize("cantidad", [-1, 1.5, True, "3"])
def test_rechaza_cantidades_invalidas(cantidad):
    with pytest.raises(ValueError, match="entero no negativo"):
        relacionar_con_catalogo({"candado": cantidad}, CATALOGO)


def test_rechaza_clase_vacia():
    with pytest.raises(ValueError, match="texto no vacío"):
        relacionar_con_catalogo({"": 2}, CATALOGO)
