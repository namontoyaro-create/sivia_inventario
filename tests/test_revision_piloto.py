import json

import pytest

from sivia_inventario.revision_piloto import aplicar_revision


def test_revision_confirma_propuesta_y_excluye_escena_ambigua(tmp_path):
    ruta = tmp_path / "datos" / "anotaciones" / "anotaciones.json"
    ruta.parent.mkdir(parents=True)
    ruta.write_text(json.dumps({"imagenes": [
        {"archivo": "datos/imagenes/candado/candado_05.jpg", "estado": "propuesta_automatica"},
        {"archivo": "datos/imagenes/candado/candado_04.jpg", "estado": "propuesta_automatica"},
    ]}), encoding="utf-8")

    resumen = aplicar_revision(ruta, tmp_path)
    datos = json.loads(ruta.read_text(encoding="utf-8"))

    assert resumen == {"confirmadas": 1, "excluidas": 1, "splits_corregidos": 0}
    assert datos["imagenes"][0]["estado"] == "revisada_asistente"
    assert datos["imagenes"][1]["estado"] == "excluida"


def test_revision_rechaza_un_manifiesto_fuera_de_anotaciones(tmp_path):
    externo = tmp_path / "externo.json"
    externo.write_text('{"imagenes": []}', encoding="utf-8")

    with pytest.raises(ValueError, match="fuera del directorio autorizado"):
        aplicar_revision(externo, tmp_path)
