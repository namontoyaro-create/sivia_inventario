from fastapi.testclient import TestClient

from sivia_inventario.web import app


def test_inicio_muestra_resumen_simulado():
    with TestClient(app) as cliente:
        respuesta = cliente.get("/")

    assert respuesta.status_code == 200
    assert "SIVIA" in respuesta.text
    assert "Datos de prueba" in respuesta.text
    assert "Productos registrados" in respuesta.text
