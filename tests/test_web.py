from fastapi.testclient import TestClient

from sivia_inventario.web import app


def test_recuperacion_contrasena_es_publica_y_exige_codigo_local():
    with TestClient(app) as cliente:
        pagina_login = cliente.get("/login")
        pagina_recuperacion = cliente.get("/recuperar-acceso")
        intento = cliente.post("/recuperar-acceso", data={
            "codigo_recuperacion": "codigo-invalido",
            "nueva_contrasena": "ClaveSegura12",
            "confirmar_contrasena": "ClaveSegura12",
        })

    assert pagina_login.status_code == 200
    assert "Olvidaste" in pagina_login.text
    assert pagina_recuperacion.status_code == 200
    assert "Recuperar acceso a SIVIA" in pagina_recuperacion.text
    assert "Olvid" in pagina_recuperacion.text
    assert "usuario" in pagina_recuperacion.text
    assert intento.status_code == 400
    assert "No se pudo validar" in intento.text


def test_inicio_muestra_resumen_simulado():
    with TestClient(app) as cliente:
        respuesta = cliente.get("/")

    assert respuesta.status_code == 200
    assert "SIVIA" in respuesta.text
    assert "Dashboard" in respuesta.text
    assert "Productos registrados" in respuesta.text


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


def test_entrenamiento_ia_muestra_propuestas_pendientes():
    with TestClient(app) as cliente:
        respuesta = cliente.get("/entrenamiento-ia")

    assert respuesta.status_code == 200
    assert "Entrenamiento IA" in respuesta.text
    assert "No hay propuestas pendientes" in respuesta.text
