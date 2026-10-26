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



def test_migracion_respalda_base_existente_y_conserva_productos(tmp_path):
    from sivia_inventario.base_datos import conectar
    ruta = tmp_path / "sivia.db"
    # Base previa a la etapa 1, deliberadamente sin las nuevas columnas.
    with conectar(ruta) as conexion:
        conexion.execute("""CREATE TABLE productos (
            id TEXT PRIMARY KEY, producto TEXT NOT NULL, familia TEXT NOT NULL,
            presentacion TEXT NOT NULL, unidad_conteo TEXT NOT NULL, clase_ia TEXT NOT NULL,
            marca TEXT, modelo TEXT, tamano TEXT, codigo_producto TEXT,
            stock_registrado INTEGER NOT NULL, origen_stock TEXT NOT NULL,
            activo INTEGER NOT NULL DEFAULT 1, creado_en TEXT, actualizado_en TEXT
        )""")
        conexion.execute("""INSERT INTO productos VALUES
            ('P900','Producto legado','Prueba','Unidad','Cada unidad','candado',NULL,NULL,NULL,NULL,12,'real',1,'2026-01-01','2026-01-01')""")

    respaldo = inicializar_base_datos(ruta)
    assert respaldo is not None and respaldo.is_file()
    with conectar(respaldo) as conexion:
        assert conexion.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conexion.execute("SELECT stock_registrado FROM productos WHERE id='P900'").fetchone()[0] == 12
    with conectar(ruta) as conexion:
        columnas = {fila[1] for fila in conexion.execute("PRAGMA table_info(productos)")}
        versiones = [fila[0] for fila in conexion.execute("SELECT version FROM versiones_esquema ORDER BY version")]
    assert {"sku", "codigo_barras", "proveedor", "precio_compra", "precio_venta", "stock_minimo", "unidad_medida", "estado_producto"}.issubset(columnas)
    assert versiones == [1, 2]
    assert [p.stock_registrado for p in listar_productos(ruta) if p.id == "P900"] == [12]
    assert inicializar_base_datos(ruta) is None
