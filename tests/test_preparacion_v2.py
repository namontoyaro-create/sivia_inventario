import json

import cv2
import numpy as np

from sivia_inventario.preparacion_v2 import (
    SPLITS_APROBACIONES,
    auditar_imagenes_nuevas,
    registrar_procedencia_imagen,
    registrar_aprobaciones,
    plan_mejora_dataset,
    resumen_clases,
)


def test_registrar_procedencia_conserva_reserva_test(tmp_path):
    imagen = tmp_path / "datos" / "imagenes" / "disco_corte" / "nuevo.jpg"
    imagen.parent.mkdir(parents=True)
    imagen.write_bytes(b"imagen")
    registro = tmp_path / "registro.json"
    registro.write_text('{"imagenes": []}', encoding="utf-8")

    registrar_procedencia_imagen(
        "datos/imagenes/disco_corte/nuevo.jpg", "prueba_fisica", "disco_real_01", "test", registro, tmp_path
    )

    datos = json.loads(registro.read_text(encoding="utf-8"))
    assert datos["imagenes"][0]["split_propuesto"] == "test"
    assert datos["imagenes"][0]["grupo_escena"] == "disco_real_01"


def test_auditar_imagenes_nuevas_detecta_una_foto_sin_modificar_el_manifiesto(tmp_path):
    raiz = tmp_path
    imagen = raiz / "datos" / "imagenes" / "candado" / "nuevo.jpg"
    imagen.parent.mkdir(parents=True)
    assert cv2.imwrite(str(imagen), np.full((20, 20, 3), 100, dtype=np.uint8))

    registro = raiz / "registro.json"
    registro.write_text(json.dumps({"imagenes": [{
        "archivo": "datos/imagenes/candado/nuevo.jpg",
        "clase_ia": "candado",
        "origen": "prueba_fisica",
        "grupo_escena": "escena_01",
    }]}), encoding="utf-8")
    manifiesto = raiz / "manifiesto.json"
    manifiesto.write_text(json.dumps({"imagenes": []}), encoding="utf-8")

    informe = auditar_imagenes_nuevas(manifiesto, registro, raiz)

    assert informe["estado"] == "preparacion_sivia_sin_exportar"
    assert informe["nuevas_pendientes_revision"][0]["estado"] == "pendiente_revision_visual"
    assert not informe["duplicados_exactos"]


def test_resumen_clases_mantiene_la_clase_real_de_la_propuesta():
    assert resumen_clases([{"clase": "tuberia_pvc"}] * 4) == "4 tuberia_pvc"


def test_plan_de_mejora_indica_faltantes_sin_cambiar_anotaciones(tmp_path):
    manifiesto = tmp_path / "manifiesto.json"
    manifiesto.write_text(json.dumps({
        "clases": ["candado"],
        "imagenes": [{"archivo": "datos/imagenes/candado/a.jpg", "estado": "revisada_usuario", "split": "train", "objetos": [{"clase": "candado"}]}],
    }), encoding="utf-8")

    plan = plan_mejora_dataset(manifiesto)

    assert plan[0]["splits"]["train"] == {"actual": 1, "meta": 20, "faltan": 19}
    assert plan[0]["splits"]["test"]["faltan"] == 5


def test_registrar_aprobaciones_conserva_clase_y_procedencia(tmp_path, monkeypatch):
    archivo = "datos/imagenes/candado/candado1.jpg"
    imagen = tmp_path / archivo
    imagen.parent.mkdir(parents=True)
    assert cv2.imwrite(str(imagen), np.full((20, 30, 3), 100, dtype=np.uint8))
    manifiesto = tmp_path / "manifiesto.json"
    manifiesto.write_text(json.dumps({"imagenes": []}), encoding="utf-8")
    propuestas = tmp_path / "propuestas.json"
    propuestas.write_text(json.dumps({"imagenes": [{
        "archivo": archivo, "origen": "internet", "grupo_escena": "escena",
        "objetos": [{"clase": "candado", "xyxy": [0.1, 0.1, 0.9, 0.9]}],
    }]}), encoding="utf-8")
    monkeypatch.setitem(SPLITS_APROBACIONES, archivo, "train")

    resumen = registrar_aprobaciones({archivo}, manifiesto, propuestas, tmp_path)
    registrado = json.loads(manifiesto.read_text(encoding="utf-8"))["imagenes"][0]

    assert resumen == {"imagenes_aprobadas": 1, "objetos_aprobados": 1, "pendientes": 0}
    assert registrado["estado"] == "revisada_usuario"
    assert registrado["origen"] == "internet"
    assert registrado["objetos"][0]["clase"] == "candado"
