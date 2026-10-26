import pytest
from sivia_inventario.base_datos import inicializar_base_datos
from sivia_inventario.repositorio_inventario import (MovimientoNoDisponible, actualizar_producto, confirmar_movimiento, crear_producto, crear_solicitud_movimiento, guardar_verificacion, listar_movimientos, listar_sesiones_verificacion, obtener_producto, obtener_sesion_verificacion)

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
