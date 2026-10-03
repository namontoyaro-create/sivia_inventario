from fastapi.testclient import TestClient

from sivia_inventario.web import app


def test_inicio_muestra_resumen_simulado():
    with TestClient(app) as cliente:
        respuesta = cliente.get("/")

    assert respuesta.status_code == 200
    assert "SIVIA" in respuesta.text
    assert "Datos de prueba" in respuesta.text
    assert "Productos registrados" in respuesta.text


def test_paginas_principales_no_muestran_anotaciones_del_dataset():
    with TestClient(app) as cliente:
        for ruta, texto in [("/inventario", "Categoría IA"), ("/verificar", "Cámara lista"), ("/historial", "No hay verificaciones"), ("/alertas", "No hay alertas")]:
            respuesta = cliente.get(ruta)
            assert respuesta.status_code == 200
            assert texto in respuesta.text
            assert "Anotaciones experimentales" not in respuesta.text
