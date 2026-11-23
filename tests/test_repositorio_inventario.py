import pytest
from sivia_inventario.base_datos import inicializar_base_datos
from sivia_inventario.repositorio_inventario import (MovimientoNoDisponible, actualizar_producto, buscar_productos_global, confirmar_movimiento, crear_producto, crear_solicitud_movimiento, eliminar_producto, es_ean13_valido, guardar_verificacion, listar_alertas, listar_alertas_discrepancia_recurrente_ia, listar_alertas_salida_inusual, listar_movimientos, listar_sesiones_verificacion, obtener_producto, obtener_sesion_verificacion, resumen_dashboard)

def test_crea_y_actualiza_producto_persistente(tmp_path):
    ruta=tmp_path/"sivia.db"; inicializar_base_datos(ruta)
    crear_producto("P900","Producto demo","Prueba","candado","Unidad",7,ruta)
    actualizar_producto("P900","Producto editado","Prueba","candado","Caja",7,ruta, sku="CAD-900", codigo_barras="12345678", proveedor="Proveedor demo", precio_compra=4.5, precio_venta=7.9, stock_minimo=2, unidad_medida="unidad")
    p=obtener_producto("P900",ruta)
    assert (p.producto,p.presentacion,p.stock_registrado)==("Producto editado","Caja",7)
    assert (p.sku,p.codigo_barras,p.proveedor,p.precio_compra,p.precio_venta,p.stock_minimo)==("CAD-900","12345678","Proveedor demo",4.5,7.9,2)
    with pytest.raises(ValueError, match="movimiento"):
        actualizar_producto("P900","Producto editado","Prueba","candado","Caja",11,ruta)

def test_rechaza_codigo_duplicado_y_stock_invalido(tmp_path):
    ruta=tmp_path/"sivia.db"; inicializar_base_datos(ruta)
    with pytest.raises(ValueError,match="Ya existe"):crear_producto("P001","Otro","Prueba","candado","Unidad",1,ruta)
    with pytest.raises(ValueError,match="entero"):crear_producto("P900","Otro","Prueba","candado","Unidad",-1,ruta)


def test_guarda_una_sesion_solo_con_productos_confirmados(tmp_path):
    raiz = tmp_path / "proyecto"; ruta = raiz / "datos" / "sivia.db"
    evidencia = raiz / "datos" / "evidencias" / "captura.jpg"
    evidencia.parent.mkdir(parents=True); evidencia.write_bytes(b"evidencia")
    inicializar_base_datos(ruta)
    codigo = guardar_verificacion("Prueba", "datos/evidencias/captura.jpg", {"candado": 2, "bolsa_clavos": 0}, ruta=ruta)
    assert codigo == "VER-0001"
    sesiones = listar_sesiones_verificacion(ruta)
    assert sesiones[0]["productos_detectados"] == 1
    assert sesiones[0]["objetos_yolo"] == 0
    assert sesiones[0]["objetos_confirmados"] == 2
    detalle = obtener_sesion_verificacion(codigo, ruta)
    assert [(p["clase_ia"], p["cantidad_detectada"]) for p in detalle["productos"]] == [("candado", 2)]


def test_conserva_conteo_yolo_confirmado_y_stock_sin_cambios(tmp_path):
    raiz = tmp_path / "proyecto"; ruta = raiz / "datos" / "sivia.db"
    evidencia = raiz / "datos" / "evidencias" / "captura.jpg"
    evidencia.parent.mkdir(parents=True); evidencia.write_bytes(b"evidencia")
    inicializar_base_datos(ruta)
    stock_inicial = obtener_producto("P003", ruta).stock_registrado
    codigo = guardar_verificacion(
        "Piloto", "datos/evidencias/captura.jpg", {"candado": 1},
        {"candado": 0.61}, ruta, conteos_yolo={"candado": 2},
        detector="piloto_sivia", alcance="Estante de candados", alcance_confirmado=False,
    )
    detalle = obtener_sesion_verificacion(codigo, ruta)
    fila = detalle["productos"][0]
    assert fila["cantidad_yolo"] == 2
    assert fila["cantidad_detectada"] == 1
    assert fila["estado"] == "no_concluyente"
    assert detalle["alcance_confirmado"] == 0
    assert listar_sesiones_verificacion(ruta)[0]["objetos_yolo"] == 2
    assert listar_sesiones_verificacion(ruta)[0]["objetos_confirmados"] == 1
    assert obtener_producto("P003", ruta).stock_registrado == stock_inicial


def test_prediccion_rechazada_se_conserva_sin_generar_diferencia_de_stock(tmp_path):
    raiz = tmp_path / "proyecto"; ruta = raiz / "datos" / "sivia.db"
    evidencia = raiz / "datos" / "evidencias" / "captura.jpg"
    evidencia.parent.mkdir(parents=True); evidencia.write_bytes(b"evidencia")
    inicializar_base_datos(ruta)

    codigo = guardar_verificacion(
        "Correccion humana", "datos/evidencias/captura.jpg", {"P003": 1}, ruta=ruta,
        conteos_yolo={"P002": 1}, alcance_confirmado=True,
    )

    detalle = obtener_sesion_verificacion(codigo, ruta)
    por_codigo = {fila["codigo"]: fila for fila in detalle["productos"]}
    assert por_codigo["P002"]["cantidad_detectada"] == 0
    assert por_codigo["P002"]["cantidad_yolo"] == 1
    assert por_codigo["P002"]["diferencia"] == 0
    assert por_codigo["P002"]["estado"] == "no_concluyente"
    assert por_codigo["P003"]["cantidad_detectada"] == 1


def test_guarda_productos_de_la_misma_clase_y_procedencia_internet(tmp_path):
    raiz = tmp_path / "proyecto"; ruta = raiz / "datos" / "sivia.db"
    evidencia = raiz / "datos" / "evidencias" / "captura.jpg"
    evidencia.parent.mkdir(parents=True); evidencia.write_bytes(b"evidencia")
    inicializar_base_datos(ruta)
    crear_producto("P901", "Candado alternativo", "Cerrajería", "candado", "Unidad", 4, ruta)
    stock_inicial = obtener_producto("P003", ruta).stock_registrado
    codigo = guardar_verificacion(
        "Prueba internet", "datos/evidencias/captura.jpg", {"P003": 1, "P901": 1},
        {"P003": 0.80, "P901": 0.70}, ruta, conteos_yolo={"P003": 1, "P901": 1},
        alcance_confirmado=True, procedencia="internet",
    )
    detalle = obtener_sesion_verificacion(codigo, ruta)
    assert {fila["codigo"] for fila in detalle["productos"]} == {"P003", "P901"}
    assert detalle["procedencia"] == "internet"
    assert detalle["alcance_confirmado"] == 0
    assert obtener_producto("P003", ruta).stock_registrado == stock_inicial


def test_movimiento_confirmado_actualiza_stock_una_sola_vez(tmp_path):
    ruta = tmp_path / "sivia.db"; inicializar_base_datos(ruta)
    solicitud = crear_solicitud_movimiento("Registrar entrada de cinco candados", "entrada", 5, "P003", ruta)
    comprobante = confirmar_movimiento(solicitud["token"], ruta)
    repetido = confirmar_movimiento(solicitud["token"], ruta)
    assert comprobante["codigo_movimiento"] == "MOV-0001"
    assert comprobante["stock_resultante"] == 25
    assert repetido["duplicado"] is True
    assert obtener_producto("P003", ruta).stock_registrado == 25
    assert len(listar_movimientos(ruta)) == 1


def test_bloquea_salida_mayor_al_stock(tmp_path):
    ruta = tmp_path / "sivia.db"; inicializar_base_datos(ruta)
    with pytest.raises(MovimientoNoDisponible, match="suficientes"):
        crear_solicitud_movimiento("Registrar salida de 21 candados", "salida", 21, "P003", ruta)
    assert obtener_producto("P003", ruta).stock_registrado == 20



def test_rechaza_sku_barra_precio_y_stock_minimo_invalidos(tmp_path):
    ruta = tmp_path / "sivia.db"; inicializar_base_datos(ruta)
    with pytest.raises(ValueError, match="SKU"):
        crear_producto("P902", "Demo", "Prueba", "candado", "Unidad", 0, ruta, sku="x")
    with pytest.raises(ValueError, match="barras"):
        crear_producto("P902", "Demo", "Prueba", "candado", "Unidad", 0, ruta, codigo_barras="ABC")
    with pytest.raises(ValueError, match="precio"):
        crear_producto("P902", "Demo", "Prueba", "candado", "Unidad", 0, ruta, precio_venta=-1)
    with pytest.raises(ValueError, match="m?nimo"):
        crear_producto("P902", "Demo", "Prueba", "candado", "Unidad", 0, ruta, stock_minimo=-1)


def test_rechaza_sku_y_codigo_barras_duplicados(tmp_path):
    ruta = tmp_path / "sivia.db"; inicializar_base_datos(ruta)
    crear_producto("P902", "Demo", "Prueba", "candado", "Unidad", 0, ruta, sku="SKU-902", codigo_barras="12345678")
    with pytest.raises(ValueError, match="SKU"):
        crear_producto("P903", "Demo 2", "Prueba", "candado", "Unidad", 0, ruta, sku="SKU-902")
    with pytest.raises(ValueError, match="barras"):
        crear_producto("P903", "Demo 2", "Prueba", "candado", "Unidad", 0, ruta, codigo_barras="12345678")


def test_valida_digito_verificador_ean13_y_no_impide_ean8_o_upc():
    assert es_ean13_valido("2000000000015")
    assert not es_ean13_valido("2000000000014")


def test_rechaza_ean13_con_digito_verificador_invalido(tmp_path):
    ruta = tmp_path / "sivia.db"; inicializar_base_datos(ruta)
    with pytest.raises(ValueError, match="EAN-13"):
        crear_producto("P906", "Demo", "Prueba", "candado", "Unidad", 0, ruta, codigo_barras="2000000000014")


def test_eliminacion_logica_conserva_registro_en_la_base(tmp_path):
    ruta = tmp_path / "sivia.db"; inicializar_base_datos(ruta)
    eliminar_producto("P003", ruta)

    assert obtener_producto("P003", ruta) is None
    from sivia_inventario.base_datos import conectar
    with conectar(ruta) as conexion:
        fila = conexion.execute("SELECT id, activo FROM productos WHERE id='P003'").fetchone()
    assert dict(fila) == {"id": "P003", "activo": 0}


def test_persiste_campos_comerciales_al_crear_y_editar(tmp_path):
    ruta = tmp_path / "sivia.db"; inicializar_base_datos(ruta)
    crear_producto(
        "P904", "Candado comercial", "Cerrajería", "candado", "Unidad", 7, ruta,
        marca="Forte", modelo="Serie Pro", tamano="50 mm", codigo_producto="FOR-50-PRO",
    )
    creado = obtener_producto("P904", ruta)
    assert (creado.marca, creado.modelo, creado.tamano, creado.codigo_producto) == (
        "Forte", "Serie Pro", "50 mm", "FOR-50-PRO",
    )
    actualizar_producto(
        "P904", "Candado comercial", "Cerrajería", "candado", "Unidad", 7, ruta,
        marca="Forte", modelo="Serie Ultra", tamano="60 mm", codigo_producto="FOR-60-ULTRA",
    )
    editado = obtener_producto("P904", ruta)
    assert (editado.marca, editado.modelo, editado.tamano, editado.codigo_producto) == (
        "Forte", "Serie Ultra", "60 mm", "FOR-60-ULTRA",
    )
    assert editado.stock_registrado == 7


def test_rechaza_clase_ia_fuera_del_catalogo_oficial(tmp_path):
    ruta = tmp_path / "sivia.db"; inicializar_base_datos(ruta)
    with pytest.raises(ValueError, match="clases oficiales"):
        crear_producto("P905", "Producto", "Prueba", "clase_inventada", "Unidad", 0, ruta)
    with pytest.raises(ValueError, match="clases oficiales"):
        actualizar_producto("P003", "Candado", "Cerrajería", "clase_inventada", "Unidad", 20, ruta)



def test_vincula_fotografias_locales_revisadas_sin_tocar_stock(tmp_path):
    from sivia_inventario.repositorio_inventario import vincular_fotografias_catalogo, listar_productos
    ruta = tmp_path / "sivia.db"; inicializar_base_datos(ruta)
    stock_inicial = {producto.id: producto.stock_registrado for producto in listar_productos(ruta)}
    resultado = vincular_fotografias_catalogo(ruta)
    productos = {producto.id: producto for producto in listar_productos(ruta)}
    assert set(resultado["vinculados"]) == set(productos)
    assert all(producto.imagen_ruta and producto.imagen_ruta.startswith("datos/imagenes/") for producto in productos.values())
    assert {producto.id: producto.stock_registrado for producto in productos.values()} == stock_inicial


def test_dashboard_cuenta_sesiones_y_filtros_del_historial_sin_tocar_stock(tmp_path):
    raiz = tmp_path / "proyecto"
    ruta = raiz / "datos" / "sivia.db"
    evidencia = raiz / "datos" / "evidencias" / "captura.jpg"
    evidencia.parent.mkdir(parents=True)
    evidencia.write_bytes(b"evidencia")
    inicializar_base_datos(ruta)
    stock_inicial = obtener_producto("P003", ruta).stock_registrado

    guardar_verificacion(
        "Prueba", "datos/evidencias/captura.jpg", {"P003": 1, "P004": 2}, ruta=ruta,
        conteos_yolo={"P003": 1, "P004": 2}, alcance_confirmado=True,
    )

    assert resumen_dashboard(ruta)["verificaciones"] == 1
    assert len(listar_sesiones_verificacion(ruta, producto_id="P003")) == 1
    assert not listar_sesiones_verificacion(ruta, producto_id="P005")
    assert obtener_producto("P003", ruta).stock_registrado == stock_inicial


def test_busqueda_global_encuentra_nombre_codigo_sku_y_barras(tmp_path):
    ruta = tmp_path / "sivia.db"
    inicializar_base_datos(ruta)
    crear_producto(
        "P910", "Candado de búsqueda", "Cerrajería", "candado", "Unidad", 3, ruta,
        sku="CAN-910", codigo_barras="12345678",
    )

    for termino in ("candado de búsqueda", "P910", "can-910", "12345678"):
        assert [producto.id for producto in buscar_productos_global(termino, ruta)] == ["P910"]
    assert buscar_productos_global("sin coincidencia", ruta) == []


def _ruta_con_evidencia(tmp_path):
    raiz = tmp_path / "proyecto"
    ruta = raiz / "datos" / "sivia.db"
    evidencia = raiz / "datos" / "evidencias" / "captura.jpg"
    evidencia.parent.mkdir(parents=True)
    evidencia.write_bytes(b"evidencia de alertas")
    inicializar_base_datos(ruta)
    return ruta


def test_alerta_calidad_ia_aparece_con_tres_discrepancias_y_omite_yolo_nulo(tmp_path):
    ruta = _ruta_con_evidencia(tmp_path)
    stock_antes = obtener_producto("P003", ruta).stock_registrado
    for _ in range(3):
        guardar_verificacion(
            "Prueba IA", "datos/evidencias/captura.jpg", {"P003": 1}, ruta=ruta,
            conteos_yolo={"P003": 2}, alcance_confirmado=False,
        )
    guardar_verificacion("Registro antiguo", "datos/evidencias/captura.jpg", {"P003": 1}, ruta=ruta)

    alertas = listar_alertas_discrepancia_recurrente_ia(ruta)

    assert len(alertas) == 1
    assert alertas[0]["codigo"] == "P003"
    assert alertas[0]["verificaciones_con_diferencia"] == 3
    assert obtener_producto("P003", ruta).stock_registrado == stock_antes


def test_alerta_calidad_ia_no_aparece_con_dos_discrepancias(tmp_path):
    ruta = _ruta_con_evidencia(tmp_path)
    for _ in range(2):
        guardar_verificacion(
            "Prueba IA", "datos/evidencias/captura.jpg", {"P003": 1}, ruta=ruta,
            conteos_yolo={"P003": 2}, alcance_confirmado=False,
        )

    assert listar_alertas_discrepancia_recurrente_ia(ruta) == []


def _confirmar_salidas(ruta, cantidades):
    for cantidad in cantidades:
        solicitud = crear_solicitud_movimiento(f"Salida de prueba {cantidad}", "salida", cantidad, "P003", ruta)
        confirmar_movimiento(solicitud["token"], ruta)


def test_alerta_salida_inusual_requiere_cinco_salidas_previas_y_no_modifica_stock(tmp_path):
    ruta = tmp_path / "sivia.db"
    inicializar_base_datos(ruta)
    _confirmar_salidas(ruta, [1, 1, 1, 1, 1, 10])
    stock_antes_consulta = obtener_producto("P003", ruta).stock_registrado

    alertas = listar_alertas_salida_inusual(ruta)

    assert len(alertas) == 1
    assert alertas[0]["cantidad"] == 10
    assert alertas[0]["promedio_salidas"] == 1
    assert obtener_producto("P003", ruta).stock_registrado == stock_antes_consulta


def test_alerta_salida_inusual_omite_salidas_normales_o_con_historial_insuficiente(tmp_path):
    ruta_normal = tmp_path / "normal.db"
    inicializar_base_datos(ruta_normal)
    _confirmar_salidas(ruta_normal, [1, 1, 1, 1, 1, 1])
    assert listar_alertas_salida_inusual(ruta_normal) == []

    ruta_corta = tmp_path / "corta.db"
    inicializar_base_datos(ruta_corta)
    _confirmar_salidas(ruta_corta, [1, 1, 1, 1, 10])
    assert listar_alertas_salida_inusual(ruta_corta) == []


def test_alertas_de_stock_no_muestran_diferencia_de_captura_sin_alcance_confirmado(tmp_path):
    ruta = _ruta_con_evidencia(tmp_path)
    codigo = guardar_verificacion(
        "Captura parcial", "datos/evidencias/captura.jpg", {"P003": 1}, ruta=ruta,
        conteos_yolo={"P003": 2}, alcance_confirmado=False,
    )
    from sivia_inventario.base_datos import conectar
    with conectar(ruta) as conexion:
        sesion = conexion.execute("SELECT id FROM sesiones_verificacion WHERE codigo_verificacion=?", (codigo,)).fetchone()
        conexion.execute("UPDATE verificaciones SET estado='requiere_revision' WHERE sesion_id=?", (sesion["id"],))

    assert listar_alertas(ruta) == []
