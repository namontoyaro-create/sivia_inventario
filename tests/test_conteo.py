import pytest

from sivia_inventario.conteo import contar_por_clase


def test_cuenta_clases_mezcladas_y_separa_presentaciones():
    etiquetas = [
        "bolsa_clavos", "candado", "caja_clavos",
        "bolsa_clavos", "candado", "bolsa_clavos",
    ]

    assert contar_por_clase(etiquetas) == {
        "bolsa_clavos": 3,
        "candado": 2,
        "caja_clavos": 1,
    }


def test_sin_objetos_devuelve_conteo_vacio():
    assert contar_por_clase([]) == {}


def test_admite_etiquetas_ajenas_al_catalogo():
    assert contar_por_clase(["botella", "galleta", "botella"]) == {
        "botella": 2,
        "galleta": 1,
    }


@pytest.mark.parametrize("etiqueta", ["", "   ", None])
def test_rechaza_etiqueta_invalida(etiqueta):
    with pytest.raises(ValueError, match="texto no vacío"):
        contar_por_clase(["candado", etiqueta])


def test_rechaza_texto_unico_para_no_contar_caracteres():
    with pytest.raises(TypeError, match="colección de etiquetas"):
        contar_por_clase("candado")
