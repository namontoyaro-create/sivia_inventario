from fastapi.testclient import TestClient
from pathlib import Path
import json
import pytest
import re

from sivia_inventario.web import (ESTATICOS, PLANTILLAS, app, crear_audio_temporal,
                                  eliminar_audio_temporal, preparar_directorios_web,
                                  secreto_sesion, configuracion_cookies_sesion, csrf_login_valido,
                                  _leer_o_crear_secreto_local)


def test_url_imagen_valida_rutas_autorizadas_y_omite_rutas_no_validas(tmp_path, monkeypatch):
    import sivia_inventario.web as web

    monkeypatch.setattr(web, "RAIZ", tmp_path)
    imagen = tmp_path / "datos" / "imagenes" / "candado" / "ejemplo.jpg"
    producto = tmp_path / "datos" / "productos" / "producto.png"
    imagen.parent.mkdir(parents=True)
    producto.parent.mkdir(parents=True)
    imagen.write_bytes(b"imagen")
    producto.write_bytes(b"producto")

    assert web.url_imagen("datos/imagenes/candado/ejemplo.jpg") == "/imagenes/candado/ejemplo.jpg"
    assert web.url_imagen("datos/productos/producto.png") == "/productos/producto.png"
    assert web.url_imagen("datos/imagenes/candado/inexistente.jpg") is None
    assert web.url_imagen("") is None
    assert web.url_imagen(None) is None
    assert web.url_imagen("datos/imagenes/../secreto.jpg") is None

    externo = tmp_path / "externo.jpg"
    enlace = imagen.parent / "enlace.jpg"
    externo.write_bytes(b"externo")
    try:
        enlace.symlink_to(externo)
    except OSError:
        pytest.skip("El entorno no permite crear enlaces simbólicos.")
    assert web.url_imagen("datos/imagenes/candado/enlace.jpg") is None


def _configurar_verificacion_temporal(monkeypatch, tmp_path):
    import sivia_inventario.preparacion_v2 as preparacion
    import sivia_inventario.repositorio_inventario as repositorio
    import sivia_inventario.web as web
    from sivia_inventario.base_datos import inicializar_base_datos

    base = tmp_path / "datos" / "sivia.db"
    base.parent.mkdir()
    inicializar_base_datos(base)
    evidencia = tmp_path / "datos" / "evidencias" / "captura.jpg"
    evidencia.parent.mkdir()
    evidencia.write_bytes(b"evidencia de prueba")
    anotaciones = tmp_path / "datos" / "anotaciones"
    anotaciones.mkdir()
    propuestas = anotaciones / "propuestas.json"
    registro = anotaciones / "registro.json"
    propuestas.write_text(json.dumps({"version": 1, "imagenes": []}), encoding="utf-8")
    registro.write_text(json.dumps({"version": 1, "imagenes": []}), encoding="utf-8")
    monkeypatch.setattr(preparacion, "RAIZ", tmp_path)
    monkeypatch.setattr(preparacion, "PROPUESTAS_PENDIENTES", propuestas)
    monkeypatch.setattr(preparacion, "REGISTRO_NUEVAS", registro)
    monkeypatch.setattr(web, "RAIZ", tmp_path)
    monkeypatch.setattr(web, "CARPETA_EVIDENCIAS", evidencia.parent)
    monkeypatch.setattr(web, "inicializar_base_datos", lambda: inicializar_base_datos(base))
    monkeypatch.setattr(web, "guardar_verificacion", lambda *args, **kwargs: repositorio.guardar_verificacion(*args, ruta=base, **kwargs))
    monkeypatch.setattr(web, "obtener_producto", lambda codigo: repositorio.obtener_producto(codigo, base))
    monkeypatch.setattr(web, "listar_productos_por_clase", lambda clase: repositorio.listar_productos_por_clase(clase, base))
    web.REVISIONES_PENDIENTES.clear()
    token = web.crear_revision_pendiente(
        "datos/evidencias/captura.jpg",
        "",
        "prueba",
        "prueba_fisica",
    )
    return base, propuestas, registro, token


def _formulario_verificacion(revision_token, *, manual=False):
    datos = {
        "revision_token": revision_token,
        "alcance": "captura de prueba",
        "deteccion_id": "1",
        "clase_1": "candado",
        "confianza_1": "0.80",
        "producto_1": "P003",
    }
    if manual:
        datos |= {"producto_manual": "P003", "cantidad_manual": "1"}
    return datos


def test_verificacion_corregida_crea_propuesta_sin_cambiar_stock_ni_duplicar(tmp_path, monkeypatch):
    import sivia_inventario.repositorio_inventario as repositorio
    import sivia_inventario.web as web

    base, propuestas, registro, revision_token = _configurar_verificacion_temporal(monkeypatch, tmp_path)
    stock_antes = repositorio.obtener_producto("P003", base).stock_registrado
    with TestClient(app) as cliente:
        primera = cliente.post("/verificar/guardar", data=_formulario_verificacion(revision_token, manual=True), follow_redirects=False)
        segundo_token = web.crear_revision_pendiente("datos/evidencias/captura.jpg", "", "prueba", "prueba_fisica")
        segunda = cliente.post("/verificar/guardar", data=_formulario_verificacion(segundo_token, manual=True), follow_redirects=False)

    pendientes = json.loads(propuestas.read_text(encoding="utf-8"))["imagenes"]
    procedencias = json.loads(registro.read_text(encoding="utf-8"))["imagenes"]
    assert primera.status_code == 303
    assert segunda.status_code == 303
    assert len(pendientes) == 1
    assert pendientes[0]["estado"] == "requiere_anotacion_manual"
    assert pendientes[0]["objetos"] == []
    assert procedencias[0]["origen"] == "correccion_usuario"
    assert repositorio.obtener_producto("P003", base).stock_registrado == stock_antes


def test_verificacion_sin_correccion_no_crea_propuesta(tmp_path, monkeypatch):
    _base, propuestas, registro, revision_token = _configurar_verificacion_temporal(monkeypatch, tmp_path)
    with TestClient(app) as cliente:
        respuesta = cliente.post("/verificar/guardar", data=_formulario_verificacion(revision_token), follow_redirects=False)

    assert respuesta.status_code == 303
    assert json.loads(propuestas.read_text(encoding="utf-8"))["imagenes"] == []
    assert json.loads(registro.read_text(encoding="utf-8"))["imagenes"] == []


def test_error_al_enviar_correccion_no_impide_guardar_verificacion(tmp_path, monkeypatch):
    import sivia_inventario.web as web
    import sivia_inventario.repositorio_inventario as repositorio

    base, _propuestas, _registro, revision_token = _configurar_verificacion_temporal(monkeypatch, tmp_path)
    monkeypatch.setattr(web, "registrar_correccion_verificacion", lambda *_args: (_ for _ in ()).throw(OSError("fallo simulado")))
    with TestClient(app) as cliente:
        respuesta = cliente.post("/verificar/guardar", data=_formulario_verificacion(revision_token, manual=True), follow_redirects=False)

    assert respuesta.status_code == 303
    assert len(repositorio.listar_sesiones_verificacion(base)) == 1


@pytest.mark.parametrize("ruta_manipulada", ["../fuera.jpg", "C:/Windows/system32/archivo.jpg", "datos/productos/otro.jpg"])
def test_guardar_revision_ignora_rutas_manipuladas_del_formulario(tmp_path, monkeypatch, ruta_manipulada):
    import sivia_inventario.repositorio_inventario as repositorio

    base, _propuestas, _registro, revision_token = _configurar_verificacion_temporal(monkeypatch, tmp_path)
    stock_antes = repositorio.obtener_producto("P003", base).stock_registrado
    formulario = _formulario_verificacion(revision_token)
    formulario |= {
        "evidencia_ruta": ruta_manipulada,
        "resultado_ruta": ruta_manipulada,
        "detector": "manipulado",
        "procedencia": "internet",
    }
    with TestClient(app) as cliente:
        respuesta = cliente.post("/verificar/guardar", data=formulario, follow_redirects=False)

    assert respuesta.status_code == 303
    assert ruta_manipulada not in respuesta.text
    assert repositorio.obtener_producto("P003", base).stock_registrado == stock_antes


def test_guardar_revision_rechaza_token_manipulado_sin_exponer_rutas(tmp_path, monkeypatch):
    _base, _propuestas, _registro, _revision_token = _configurar_verificacion_temporal(monkeypatch, tmp_path)
    with TestClient(app) as cliente:
        respuesta = cliente.post(
            "/verificar/guardar",
            data={"revision_token": "../datos/evidencias/captura.jpg"},
            follow_redirects=False,
        )

    assert respuesta.status_code == 400
    assert "datos/evidencias" not in respuesta.text
    assert "La revisión ya no está disponible" in respuesta.text


def test_revision_verificacion_no_reenvia_rutas_internas():
    plantilla = (PLANTILLAS / "revision_verificacion.html").read_text(encoding="utf-8")

    assert 'name="revision_token"' in plantilla
    assert 'name="evidencia_ruta"' not in plantilla
    assert 'name="resultado_ruta"' not in plantilla


def test_produccion_exige_secreto_de_sesion(monkeypatch):
    monkeypatch.delenv("SIVIA_SESION_SECRETA", raising=False)
    monkeypatch.setenv("SIVIA_ENTORNO", "produccion")

    with pytest.raises(RuntimeError, match="SIVIA_SESION_SECRETA"):
        secreto_sesion()


def test_secreto_local_se_conserva_entre_reinicios_simulados(tmp_path):
    ruta = tmp_path / ".sivia_sesion_secreta"

    primero = _leer_o_crear_secreto_local(ruta)
    segundo = _leer_o_crear_secreto_local(ruta)

    assert primero == segundo
    assert len(primero) >= 32


def test_cookies_locales_usan_http_aunque_exista_opcion_https(monkeypatch):
    monkeypatch.setenv("SIVIA_ENTORNO", "local")
    monkeypatch.setenv("SIVIA_HTTPS_ONLY", "1")

    configuracion = configuracion_cookies_sesion()

    assert configuracion["https_only"] is False
    assert configuracion["same_site"] == "lax"


def test_cookies_produccion_usan_https_si_se_configura(monkeypatch):
    monkeypatch.setenv("SIVIA_ENTORNO", "produccion")
    monkeypatch.setenv("SIVIA_HTTPS_ONLY", "1")

    assert configuracion_cookies_sesion()["https_only"] is True


def test_recuperacion_contrasena_es_publica_y_exige_codigo_local():
    with TestClient(app) as cliente:
        pagina_login = cliente.get("/login")
        pagina_recuperacion = cliente.get("/recuperar-acceso")
        token = re.search(r'name="csrf_token" value="([^"]+)"', pagina_recuperacion.text).group(1)
        intento = cliente.post("/recuperar-acceso", data={
            "codigo_recuperacion": "codigo-invalido",
            "nueva_contrasena": "ClaveSegura12",
            "confirmar_contrasena": "ClaveSegura12",
            "csrf_token": token,
        })

    assert pagina_login.status_code == 200
    assert "Olvidaste" in pagina_login.text
    assert pagina_recuperacion.status_code == 200
    assert "Recuperar acceso a SIVIA" in pagina_recuperacion.text
    assert "Olvid" in pagina_recuperacion.text
    assert "usuario" in pagina_recuperacion.text
    assert intento.status_code == 400
    assert "No se pudo validar" in intento.text


def test_login_permanece_publico_y_la_configuracion_inicial_exige_token(monkeypatch):
    import sivia_inventario.web as web

    monkeypatch.setattr(web, "existen_usuarios", lambda: False)
    monkeypatch.setenv("SIVIA_BOOTSTRAP_TOKEN", "codigo-bootstrap-prueba")
    with TestClient(app) as cliente:
        pagina_login = cliente.get("/login")
        pagina_configuracion = cliente.get("/configurar-acceso")
        token = re.search(r'name="csrf_token" value="([^"]+)"', pagina_configuracion.text).group(1)
        rechazo = cliente.post("/configurar-acceso", data={
            "csrf_token": token, "codigo_configuracion": "incorrecto", "nombre": "Admin Prueba",
            "usuario": "admin.prueba", "contrasena": "ClaveSegura10", "confirmar_contrasena": "ClaveSegura10",
        })

    assert pagina_login.status_code == 200
    assert "Configuración inicial autorizada" in pagina_login.text
    assert rechazo.status_code == 403


def test_solicitar_cuenta_exige_csrf_y_no_asigna_rol(monkeypatch):
    import sivia_inventario.web as web

    llamadas = []
    monkeypatch.setattr(web, "solicitar_cuenta", lambda usuario, nombre, motivo: llamadas.append((usuario, nombre, motivo)))
    with TestClient(app) as cliente:
        pagina = cliente.get("/solicitar-cuenta")
        token = re.search(r'name="csrf_token" value="([^"]+)"', pagina.text).group(1)
        respuesta = cliente.post("/solicitar-cuenta", data={
            "csrf_token": token, "usuario": "nuevo.operador", "nombre": "Nuevo Operador", "motivo": "Prácticas",
        })

    assert respuesta.status_code == 200
    assert llamadas == [("nuevo.operador", "Nuevo Operador", "Prácticas")]


def test_prepara_carpetas_operativas_para_un_despliegue_limpio(tmp_path):
    rutas = preparar_directorios_web(tmp_path)

    assert {ruta.relative_to(tmp_path).as_posix() for ruta in rutas} == {
        "datos/productos",
        "datos/evidencias",
        "datos/imagenes",
        "resultados/revision_anotaciones_pendientes",
    }
    assert all(ruta.is_dir() for ruta in rutas)


def test_formularios_de_acceso_no_fuerzan_autofoco():
    for nombre in ("login.html", "recuperar_acceso.html", "recuperar_contrasena.html"):
        plantilla = (PLANTILLAS / nombre).read_text(encoding="utf-8")
        assert "autofocus" not in plantilla


def test_revision_verificacion_asocia_selector_de_producto_a_etiqueta():
    plantilla = (PLANTILLAS / "revision_verificacion.html").read_text(encoding="utf-8")
    assert 'for="producto_{{ deteccion.id }}"' in plantilla
    assert 'id="producto_{{ deteccion.id }}"' in plantilla
    assert 'name="producto_manual"' in plantilla
    assert "No confirmar / falso positivo" in plantilla


def test_registro_de_audio_no_usa_metadatos_del_archivo_del_cliente():
    codigo = (PLANTILLAS.parent / "web.py").read_text(encoding="utf-8")
    assert 'REGISTRO.info("Audio recibido para transcripción: bytes=%d", len(contenido))' in codigo
    assert "extension=%s" not in codigo


def test_base_usa_iconos_svg_locales_y_dashboard_no_tiene_textos_danados():
    base = (PLANTILLAS / "base.html").read_text(encoding="utf-8")
    inicio = (PLANTILLAS / "inicio.html").read_text(encoding="utf-8")

    assert '/static/iconos.svg#inicio' in base
    assert '/static/iconos.svg#microfono' in base
    assert 'Informaci?n' not in inicio
    assert 'cat?logo' not in inicio
    assert 'categor?a' not in inicio
    assert '>?</' not in inicio

    with TestClient(app) as cliente:
        iconos = cliente.get("/static/iconos.svg")
        estilos = cliente.get("/static/fundacion-visual.css")

    assert iconos.status_code == 200
    assert 'id="inventario"' in iconos.text
    assert estilos.status_code == 200
    assert ".icono-sistema" in estilos.text


def test_inicio_muestra_resumen_simulado():
    with TestClient(app) as cliente:
        respuesta = cliente.get("/")

    assert respuesta.status_code == 200
    assert "SIVIA" in respuesta.text
    assert "Dashboard" in respuesta.text
    assert "Productos registrados" in respuesta.text


def test_busqueda_global_muestra_resultados_y_estado_vacio():
    with TestClient(app) as cliente:
        resultado = cliente.get("/buscar?q=candado")
        vacio = cliente.get("/buscar?q=zzzzzz")

    assert resultado.status_code == 200
    assert "Resultados de b" in resultado.text
    assert 'href="/inventario/P003"' in resultado.text
    assert vacio.status_code == 200
    assert "Sin resultados" in vacio.text


def test_base_habilita_busqueda_global_y_carga_su_script():
    base = (PLANTILLAS / "base.html").read_text(encoding="utf-8")
    script = (PLANTILLAS.parent / "estaticos" / "busqueda-global.js").read_text(encoding="utf-8")

    assert 'id="busqueda-global"' in base
    assert "readonly" not in base
    assert 'name="q"' in base
    assert 'maxlength="100"' in base
    assert '/static/busqueda-global.js' in base
    assert "campo.focus()" in script


def test_historial_ofrece_filtros_y_alertas_enlazan_a_su_detalle(monkeypatch):
    import sivia_inventario.web as web

    sesiones = [{
        "codigo": "VER-0001", "finalizada_en": "2026-10-15 12:00", "ruta_evidencia": None,
        "productos_detectados": 1, "objetos_yolo": 1, "objetos_confirmados": 1,
        "alcance_confirmado": 0, "diferencias": 0,
    }]
    alertas_demo = [{
        "codigo_verificacion": "VER-0001", "guardada_en": "2026-10-15 12:00", "codigo": "P003",
        "producto": "Candado", "stock_registrado": 20, "cantidad_detectada": 18, "diferencia": -2,
    }]
    monkeypatch.setattr(web, "listar_sesiones_verificacion", lambda **_filtros: sesiones)
    monkeypatch.setattr(web, "listar_alertas", lambda: alertas_demo)
    monkeypatch.setattr(web, "listar_alertas_discrepancia_recurrente_ia", lambda: [])
    monkeypatch.setattr(web, "listar_alertas_salida_inusual", lambda: [])
    with TestClient(app) as cliente:
        historial = cliente.get("/historial?fecha_desde=2026-01-01&fecha_hasta=2026-12-31&producto_id=P003")
        alertas = cliente.get("/alertas")

    assert historial.status_code == 200
    assert 'name="fecha_desde"' in historial.text
    assert 'name="producto_id"' in historial.text
    assert "captura parcial o de prueba" in historial.text
    assert alertas.status_code == 200
    plantilla = (PLANTILLAS / "alertas.html").read_text(encoding="utf-8")
    assert 'href="/historial/{{ alerta.codigo_verificacion }}"' in plantilla


def test_ficha_comercial_y_detalle_de_producto_estan_disponibles():
    with TestClient(app) as cliente:
        formulario = cliente.get("/inventario/P003/editar")
        detalle = cliente.get("/inventario/P003")

    assert formulario.status_code == 200
    for campo in ("marca", "modelo", "tamano", "codigo_producto"):
        assert f'name="{campo}"' in formulario.text
    assert 'name="stock_registrado"' in formulario.text
    assert "readonly" in formulario.text
    assert detalle.status_code == 200
    assert "Información comercial" in detalle.text
    assert "Código comercial" in detalle.text


def test_datos_de_demostracion_no_ocupan_las_vistas_de_inventario():
    with TestClient(app) as cliente:
        inventario = cliente.get("/inventario")
        detalle = cliente.get("/inventario/P003")
        edicion = cliente.get("/inventario/P003/editar")

    assert inventario.status_code == detalle.status_code == edicion.status_code == 200
    assert "Precios referenciales" not in inventario.text
    assert "Precios referenciales" not in detalle.text
    assert "Precios referenciales" not in edicion.text
    assert "Datos de demostraci" in Path("README.md").read_text(encoding="utf-8")


def test_inventario_compacto_muestra_columnas_acciones_y_ean_simulado(monkeypatch):
    from dataclasses import replace
    import sivia_inventario.web as web

    productos = web.listar_productos()
    monkeypatch.setattr(web, "listar_productos", lambda: [replace(productos[0], codigo_barras="2000000000015"), *productos[1:]])
    with TestClient(app) as cliente:
        respuesta = cliente.get("/inventario")

    assert respuesta.status_code == 200
    for columna in (
        "N.&ordm;", "Foto", "C&#243;digo interno / SKU", "C&#243;digo de barras",
        "Nombre del producto", "Presentaci&#243;n", "Stock actual", "Precio de venta", "Acciones",
    ):
        assert columna in respuesta.text
    assert "Categor&#237;a</th>" not in respuesta.text
    assert "Stock m&#237;nimo</th>" not in respuesta.text
    assert "Precio de compra</th>" not in respuesta.text
    assert "Estado</th>" not in respuesta.text
    assert "Editar" in respuesta.text
    assert "Eliminar" in respuesta.text
    assert 'title="2000000000015"' in respuesta.text


def test_confirmacion_de_eliminacion_nombra_producto_y_preserva_historial():
    with TestClient(app) as cliente:
        respuesta = cliente.get("/inventario/P003/eliminar")

    assert respuesta.status_code == 200
    assert "P003" in respuesta.text
    assert "No se borrar&#225;n su historial, movimientos" in respuesta.text
    assert 'action="/inventario/P003/eliminar"' in respuesta.text


def test_estilos_inventario_compacto_se_sirven_y_contemplan_movil():
    with TestClient(app) as cliente:
        respuesta = cliente.get("/static/inventario-compacto.css")

    assert respuesta.status_code == 200
    assert ".tabla-inventario-compacta" in respuesta.text
    assert "max-width: 700px" in respuesta.text


def test_paginas_principales_no_muestran_anotaciones_del_dataset():
    with TestClient(app) as cliente:
        paginas = [
                ("/inventario", "Inventario de productos"),
            ("/verificar", "Analizar imagen"),
            ("/historial", "Historial de verificaciones"),
            ("/alertas", "Alertas"),
        ]
        for ruta, texto in paginas:
            respuesta = cliente.get(ruta)
            assert respuesta.status_code == 200
            assert texto in respuesta.text
            assert "Anotaciones experimentales" not in respuesta.text


def test_verificar_usa_modelo_activo_sin_selector_manual():
    with TestClient(app) as cliente:
        respuesta = cliente.get("/verificar")

    assert respuesta.status_code == 200
    assert "YOLO piloto SIVIA v2" in respuesta.text
    assert "Procedencia de la evidencia" in respuesta.text
    assert 'name="detector"' not in respuesta.text
    assert "Comparar YOLO piloto SIVIA v1 y v2" not in respuesta.text
    assert "Analizando imagen con IA" in respuesta.text


def test_verificar_carga_con_aviso_si_render_no_tiene_pesos_yolo(monkeypatch):
    def sin_detector():
        raise FileNotFoundError("No hay un modelo YOLO local disponible para SIVIA.")

    monkeypatch.setattr("sivia_inventario.web.detector_activo_contexto", sin_detector)

    with TestClient(app) as cliente:
        pagina = cliente.get("/verificar")
        analisis = cliente.post("/verificar/analizar")

    assert pagina.status_code == 200
    assert "Detector no disponible" in pagina.text
    assert "no se analizar" in pagina.text
    assert analisis.status_code == 503
    assert "Detector no disponible" in analisis.text


def test_verificar_muestra_solo_captura_y_resultados_sin_tabla_de_catalogo():
    with TestClient(app) as cliente:
        respuesta = cliente.get("/verificar")

    assert respuesta.status_code == 200
    assert "Captura de productos" in respuesta.text
    assert "Resultados de detecci" in respuesta.text
    assert "Procedencia de la evidencia" in respuesta.text
    assert "YOLO experimental" in respuesta.text
    assert "Inventario de productos</h2>" not in respuesta.text
    assert "/inventario/nuevo" not in respuesta.text


def test_verificar_limita_el_tamano_visual_y_adapta_los_paneles_a_movil():
    estilos = (ESTATICOS / "verificar_activo.css").read_text(encoding="utf-8")

    assert "max-height:360px" in estilos
    assert "object-fit:contain" in estilos
    assert "@media(max-width:980px)" in estilos
    assert ".verificacion-ia{grid-template-columns:1fr}" in estilos


def test_javascript_de_verificar_conserva_camara_captura_y_limpieza():
    script = (ESTATICOS / "verificar.js").read_text(encoding="utf-8")

    assert "navigator.mediaDevices.getUserMedia" in script
    assert "lienzo.toBlob" in script
    assert "formulario.requestSubmit()" in script
    assert "detenerCamara" in script


def test_pruebas_tecnicas_conservan_selector_y_comparacion():
    with TestClient(app) as cliente:
        respuesta = cliente.get("/verificar/tecnico")

    assert respuesta.status_code == 200
    assert "YOLO general" in respuesta.text
    assert "YOLO piloto SIVIA" in respuesta.text
    assert "YOLO piloto SIVIA v2" in respuesta.text
    assert "Comparar YOLO piloto SIVIA v1 y v2" in respuesta.text
    assert 'name="modo_tecnico" value="si"' in respuesta.text


def test_estilos_del_resultado_de_deteccion_se_sirven():
    with TestClient(app) as cliente:
        respuesta = cliente.get("/static/resultado_deteccion.css")

    assert respuesta.status_code == 200
    assert ".resumen-deteccion" in respuesta.text


def test_resultado_baja_confianza_no_afirma_producto_desconocido():
    from sivia_inventario.web import plantillas

    pagina = plantillas.get_template("revision_verificacion.html").render(
        pagina="verificar", detector_nombre="Piloto", aviso="Prueba", procedencia="prueba_fisica",
        comparacion_modelos=[], resumen_yolo=[], detectados=[], estado_resultado="baja_confianza",
        detecciones_bajas=[{"clase": "bolsa_cemento", "confianza": 0.196, "xyxy": [1, 2, 3, 4]}],
        evidencia_url="/evidencias/a.jpg", resultado_url="/evidencias/r.jpg",
    )

    assert "No se reconocieron productos de las clases entrenadas" in pagina
    assert "no confirma que el objeto sea desconocido" in pagina
    assert "Revisar o registrar producto" in pagina
    assert "19.6%" in pagina


def test_entrenamiento_ia_muestra_pantalla_de_revision():
    with TestClient(app) as cliente:
        respuesta = cliente.get("/entrenamiento-ia")

    assert respuesta.status_code == 200
    assert "Entrenamiento IA" in respuesta.text
    assert "Plan de mejora del dataset" in respuesta.text


def test_audio_temporal_se_puede_eliminar_despues_de_procesarlo():
    ruta = crear_audio_temporal(b"audio de prueba", ".webm")
    try:
        assert ruta.is_file()
        assert ruta.read_bytes() == b"audio de prueba"
    finally:
        eliminar_audio_temporal(ruta)

    assert not ruta.exists()


def test_javascript_de_voz_maneja_promesas_de_transcripcion():
    script = (ESTATICOS / "asistente-voz.js").read_text(encoding="utf-8")

    assert "void transcribir(archivo).catch" in script


def test_asistente_voz_muestra_paneles_estados_y_historial_compacto(monkeypatch):
    import sivia_inventario.web as web

    monkeypatch.setattr(web, "listar_movimientos", lambda: [{
        "codigo_movimiento": "MOV-0001", "confirmado_en": "2026-10-15 12:00",
        "codigo_producto": "P003", "producto": "Candado", "operacion": "entrada",
        "cantidad": 1, "stock_anterior": 20, "stock_resultante": 21,
    }])
    with TestClient(app) as cliente:
        respuesta = cliente.get("/asistente-voz")

    assert respuesta.status_code == 200
    assert "Instrucci" in respuesta.text
    assert "Operaci" in respuesta.text
    assert 'id="insignia-estado-voz"' in respuesta.text
    assert "Movimientos recientes por voz" in respuesta.text
    assert "Confirmar operaci" not in respuesta.text


def test_login_rechaza_formularios_sin_csrf_y_aplica_limite_de_intentos(monkeypatch):
    import sivia_inventario.web as web

    web.INTENTOS_LOGIN.clear()
    monkeypatch.setattr(web, "existen_usuarios", lambda: True)
    monkeypatch.setattr(web, "autenticar", lambda *_args: None)
    monkeypatch.setattr(web, "MAXIMO_INTENTOS_LOGIN", 1)
    with TestClient(app) as cliente:
        sin_token = cliente.post("/login", data={"usuario": "admin", "contrasena": "invalida"})
        pagina = cliente.get("/login")
        token = re.search(r'name="csrf_token" value="([^"]+)"', pagina.text).group(1)
        primer_error = cliente.post("/login", data={"usuario": "admin", "contrasena": "invalida", "csrf_token": token})
        bloqueado = cliente.post("/login", data={"usuario": "admin", "contrasena": "invalida", "csrf_token": token})

    assert sin_token.status_code == 403
    assert primer_error.status_code == 401
    assert bloqueado.status_code == 429
    web.INTENTOS_LOGIN.clear()


def test_login_recien_abierto_acepta_csrf_y_conserva_cookie_de_sesion(monkeypatch):
    """Una página nueva debe poder iniciar sesión sin requerir recarga extra."""
    import sivia_inventario.web as web
    from sivia_inventario.autenticacion import Usuario

    cuenta = Usuario(7, "operador.prueba", "Operador de prueba", "operador", True)
    monkeypatch.setattr(web, "existen_usuarios", lambda: True)
    monkeypatch.setattr(web, "autenticar", lambda *_args: cuenta)
    web.INTENTOS_LOGIN.clear()
    with TestClient(app) as cliente:
        pagina = cliente.get("/login")
        token = re.search(r'name="csrf_token" value="([^"]+)"', pagina.text).group(1)
        respuesta = cliente.post("/login", data={
            "usuario": "operador.prueba", "contrasena": "ClaveSegura10", "csrf_token": token,
        }, follow_redirects=False)
        pagina_actualizada = cliente.get("/login")

    assert respuesta.status_code == 303
    assert "sivia_sesion" in cliente.cookies
    assert pagina_actualizada.status_code == 200
    assert "csrf_token" in pagina_actualizada.text


def test_error_de_credenciales_devuelve_un_nuevo_token_csrf_de_login(monkeypatch):
    import sivia_inventario.web as web

    monkeypatch.setattr(web, "existen_usuarios", lambda: True)
    monkeypatch.setattr(web, "autenticar", lambda *_args: None)
    with TestClient(app) as cliente:
        pagina = cliente.get("/login")
        token = re.search(r'name="csrf_token" value="([^"]+)"', pagina.text).group(1)
        error = cliente.post("/login", data={
            "usuario": "admin", "contrasena": "invalida", "csrf_token": token,
        })
        nuevo = re.search(r'name="csrf_token" value="([^"]+)"', error.text)

    assert error.status_code == 401
    assert nuevo and len(nuevo.group(1)) > 32
    assert error.headers["cache-control"] == "no-store, max-age=0"


def test_login_rechaza_token_csrf_firmado_manipulado(monkeypatch):
    import sivia_inventario.web as web

    monkeypatch.setattr(web, "existen_usuarios", lambda: True)
    with TestClient(app) as cliente:
        respuesta = cliente.post("/login", data={
            "usuario": "admin", "contrasena": "invalida", "csrf_token": "token-manipulado",
        })

    assert respuesta.status_code == 403


def test_estilos_de_voz_son_responsivos_y_no_sustituyen_confirmacion():
    estilos = (ESTATICOS / "asistente-voz.css").read_text(encoding="utf-8")

    assert ".voz-diseno{display:grid" in estilos
    assert ".estado-grabando" in estilos
    assert "@media(max-width:620px)" in estilos
    assert ".acciones-operacion" in estilos


def test_javascript_de_voz_conserva_grabacion_y_transcripcion_automatica():
    script = (ESTATICOS / "asistente-voz.js").read_text(encoding="utf-8")

    assert "navigator.mediaDevices.getUserMedia" in script
    assert "grabador.ondataavailable" in script
    assert "grabador.onstop" in script
    assert "iniciarTranscripcion" in script
    assert "fetch('/asistente-voz/transcribir'" in script
