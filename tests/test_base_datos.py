from sivia_inventario.base_datos import inicializar_base_datos
from sivia_inventario.repositorio_inventario import listar_productos, resumen_dashboard


def test_inicializa_catalogo_y_stock_simulado(tmp_path):
    ruta = tmp_path / "sivia.db"
    inicializar_base_datos(ruta)

    productos = listar_productos(ruta)
    resumen = resumen_dashboard(ruta)

    assert len(productos) == 8
    assert productos[2].id == "P003"
    assert productos[2].clase_ia == "candado"
    assert productos[2].stock_registrado == 20
    assert productos[2].origen_stock == "simulado"
    assert resumen == {
        "productos_registrados": 8,
        "stock_registrado": 156,
        "verificaciones": 0,
        "diferencias": 0,
    }


def test_inicializar_no_sobrescribe_stock_existente(tmp_path):
    ruta = tmp_path / "sivia.db"
    inicializar_base_datos(ruta)
    from sivia_inventario.base_datos import conectar

    with conectar(ruta) as conexion:
        conexion.execute("UPDATE productos SET stock_registrado = 99 WHERE id = 'P003'")
    inicializar_base_datos(ruta)

    assert [p.stock_registrado for p in listar_productos(ruta) if p.id == "P003"] == [99]
