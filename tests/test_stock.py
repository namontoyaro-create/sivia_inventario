import json

import pytest

from sivia_inventario.categorias import CATALOGO
from sivia_inventario.stock import cargar_stock_referencia


@pytest.fixture
def datos():
    return {
        "tipo_datos": "simulados",
        "descripcion": "Inventario ficticio de prueba",
        "stock_por_producto": {"P003": 20},
    }


def guardar_json(tmp_path, datos):
    ruta = tmp_path / "datos" / "inventario" / "stock.json"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    return ruta


def test_carga_stock_y_conserva_origen_sin_modificar_archivo(tmp_path, datos):
    ruta = guardar_json(tmp_path, datos)
    contenido_original = ruta.read_bytes()

    referencia = cargar_stock_referencia(ruta, CATALOGO, tmp_path)

    assert referencia.tipo_datos == "simulados"
    assert referencia.descripcion == datos["descripcion"]
    assert referencia.stock_por_producto == {"P003": 20}
    assert ruta.read_bytes() == contenido_original


def test_distingue_cero_de_stock_desconocido(tmp_path, datos):
    datos["stock_por_producto"] = {"P003": 0}

    referencia = cargar_stock_referencia(guardar_json(tmp_path, datos), CATALOGO, tmp_path)

    assert referencia.stock_por_producto["P003"] == 0
    assert "P001" not in referencia.stock_por_producto


def test_rechaza_id_ajeno_al_catalogo(tmp_path, datos):
    datos["stock_por_producto"] = {"P999": 10}

    with pytest.raises(ValueError, match="Producto no registrado.*P999"):
        cargar_stock_referencia(guardar_json(tmp_path, datos), CATALOGO, tmp_path)


@pytest.mark.parametrize("cantidad", [-1, 2.5, True, "20", None])
def test_rechaza_cantidad_invalida(tmp_path, datos, cantidad):
    datos["stock_por_producto"]["P003"] = cantidad

    with pytest.raises(ValueError, match="entero no negativo"):
        cargar_stock_referencia(guardar_json(tmp_path, datos), CATALOGO, tmp_path)


@pytest.mark.parametrize(
    "campo, valor",
    [
        ("tipo_datos", None),
        ("tipo_datos", "sin_definir"),
        ("descripcion", "   "),
        ("stock_por_producto", []),
        ("stock_por_producto", None),
    ],
)
def test_rechaza_estructura_invalida(tmp_path, datos, campo, valor):
    datos[campo] = valor

    with pytest.raises(ValueError, match=campo):
        cargar_stock_referencia(guardar_json(tmp_path, datos), CATALOGO, tmp_path)


def test_rechaza_raiz_que_no_es_objeto(tmp_path):
    with pytest.raises(ValueError, match="objeto JSON"):
        cargar_stock_referencia(guardar_json(tmp_path, []), CATALOGO, tmp_path)


def test_rechaza_stock_duplicado_sin_sobrescribir_silenciosamente(tmp_path):
    ruta = tmp_path / "datos" / "inventario" / "duplicado.json"
    ruta.parent.mkdir(parents=True)
    ruta.write_text(
        '{"tipo_datos":"simulados","descripcion":"Prueba",'
        '"stock_por_producto":{"P003":20,"P003":99}}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Clave duplicada.*P003"):
        cargar_stock_referencia(ruta, CATALOGO, tmp_path)


def test_rechaza_json_mal_formado(tmp_path):
    ruta = tmp_path / "datos" / "inventario" / "invalido.json"
    ruta.parent.mkdir(parents=True)
    ruta.write_text('{"stock_por_producto":', encoding="utf-8")

    with pytest.raises(ValueError, match="JSON inválido"):
        cargar_stock_referencia(ruta, CATALOGO, tmp_path)


def test_archivo_inexistente(tmp_path):
    with pytest.raises(ValueError, match="no existe"):
        cargar_stock_referencia(tmp_path / "datos" / "no_existe.json", CATALOGO, tmp_path)


def test_stock_rechaza_escape_de_directorio(tmp_path):
    (tmp_path / "secreto.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="secuencias '..'"):
        cargar_stock_referencia("../secreto.json", CATALOGO, tmp_path)
