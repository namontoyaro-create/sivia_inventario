import json

from sivia_inventario.revision_piloto import aplicar_revision


def test_revision_confirma_propuesta_y_excluye_escena_ambigua(tmp_path):
    ruta = tmp_path / "anotaciones.json"
    ruta.write_text(json.dumps({"imagenes": [
        {"archivo": "datos/imagenes/candado/candado_05.jpg", "estado": "propuesta_automatica"},
        {"archivo": "datos/imagenes/candado/candado_04.jpg", "estado": "propuesta_automatica"},
    ]}), encoding="utf-8")

    resumen = aplicar_revision(ruta)
    datos = json.loads(ruta.read_text(encoding="utf-8"))

    assert resumen == {"confirmadas": 1, "excluidas": 1, "splits_corregidos": 0}
    assert datos["imagenes"][0]["estado"] == "revisada_asistente"
    assert datos["imagenes"][1]["estado"] == "excluida"
