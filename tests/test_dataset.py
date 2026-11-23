import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from sivia_inventario.categorias import CATALOGO
from sivia_inventario.dataset import auditar, proponer_caja, resolver_ruta_controlada
from sivia_inventario.entrenamiento import (
    configuracion_ultralytics_temporal,
    ruta_configuracion_entrenamiento,
    ruta_dataset_declarada,
)


def test_proponer_caja_encierra_un_objeto_oscuro_sobre_fondo_claro():
    imagen = np.full((100, 200, 3), 255, dtype=np.uint8)
    imagen[20:80, 50:150] = 20

    x1, y1, x2, y2 = proponer_caja(imagen)

    assert x1 < 0.3 < x2
    assert y1 < 0.5 < y2
    assert x1 < x2 and y1 < y2


def test_auditar_rechaza_propuestas_automaticas_sin_revision(tmp_path):
    raiz = tmp_path
    imagen_path = raiz / "datos" / "imagenes" / "candado" / "ejemplo.jpg"
    imagen_path.parent.mkdir(parents=True)
    assert cv2.imwrite(str(imagen_path), np.full((20, 20, 3), 100, dtype=np.uint8))
    from sivia_inventario.dataset import sha256

    manifiesto = {
        "version": 1,
        "clases": [producto.clase_ia for producto in CATALOGO],
        "imagenes": [
            {
                "archivo": "datos/imagenes/candado/ejemplo.jpg",
                "sha256": sha256(imagen_path, raiz, "datos/imagenes"),
                "ancho": 20,
                "alto": 20,
                "estado": "propuesta_automatica",
                "split": "train",
                "grupo": "ejemplo",
                "objetos": [{"clase": "candado", "xyxy": [0.1, 0.1, 0.9, 0.9]}],
            }
        ],
    }
    ruta = raiz / "datos" / "anotaciones" / "manifiesto.json"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(manifiesto), encoding="utf-8")

    with pytest.raises(ValueError, match="propuestas automáticas"):
        auditar(ruta, raiz)


def test_resolver_ruta_controlada_acepta_archivo_normal_en_directorio_autorizado(tmp_path):
    archivo = tmp_path / "datos" / "anotaciones" / "ferreteria.json"
    archivo.parent.mkdir(parents=True)
    archivo.write_text("{}", encoding="utf-8")

    resuelta = resolver_ruta_controlada(
        archivo, tmp_path, "datos/anotaciones", extensiones={".json"}
    )

    assert resuelta == archivo.resolve()


@pytest.mark.parametrize("ruta", ["../secreto.json", "datos/anotaciones/../../secreto.json"])
def test_resolver_ruta_controlada_rechaza_secuencias_de_escape(tmp_path, ruta):
    (tmp_path / "secreto.json").write_text("secreto", encoding="utf-8")

    with pytest.raises(ValueError, match="secuencias '..'"):
        resolver_ruta_controlada(ruta, tmp_path, "datos/anotaciones", extensiones={".json"})


def test_resolver_ruta_controlada_rechaza_ruta_absoluta_externa(tmp_path):
    externo = tmp_path / "secreto.json"
    externo.write_text("secreto", encoding="utf-8")

    with pytest.raises(ValueError, match="fuera del directorio autorizado"):
        resolver_ruta_controlada(externo, tmp_path, "datos/anotaciones", extensiones={".json"})


def test_auditar_rechaza_archivo_del_manifiesto_fuera_de_imagenes(tmp_path):
    manifiesto = {
        "version": 1,
        "clases": [producto.clase_ia for producto in CATALOGO],
        "imagenes": [{
            "archivo": "../secreto.jpg", "sha256": "no-importa", "ancho": 1, "alto": 1,
            "estado": "revisada_usuario", "split": "train", "grupo": "escape",
            "objetos": [{"clase": "candado", "xyxy": [0.1, 0.1, 0.9, 0.9]}],
        }],
    }
    ruta = tmp_path / "datos" / "anotaciones" / "manifiesto.json"
    ruta.parent.mkdir(parents=True)
    ruta.write_text(json.dumps(manifiesto), encoding="utf-8")

    with pytest.raises(ValueError, match="secuencias '..'"):
        auditar(ruta, tmp_path)


def test_resolver_ruta_controlada_rechaza_enlace_simbolico(tmp_path):
    externo = tmp_path / "externo.jpg"
    assert cv2.imwrite(str(externo), np.full((10, 10, 3), 100, dtype=np.uint8))
    enlace = tmp_path / "datos" / "imagenes" / "candado" / "enlace.jpg"
    enlace.parent.mkdir(parents=True)
    try:
        enlace.symlink_to(externo)
    except OSError:
        pytest.skip("El entorno no permite crear enlaces simbólicos.")

    with pytest.raises(ValueError, match="ruta resuelta está fuera del directorio autorizado"):
        resolver_ruta_controlada(
            "datos/imagenes/candado/enlace.jpg", tmp_path, "datos/imagenes",
            extensiones={".jpg"},
        )


def test_configuracion_entrenamiento_rechaza_archivo_fuera_de_datos(tmp_path):
    externo = tmp_path / "data.yaml"
    externo.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="fuera del directorio autorizado"):
        ruta_configuracion_entrenamiento(externo)


def test_ruta_dataset_relativa_se_resuelve_desde_carpeta_del_yaml(tmp_path):
    configuracion = tmp_path / "exportado" / "data.yaml"
    configuracion.parent.mkdir()

    assert ruta_dataset_declarada(configuracion, {"path": "."}) == configuracion.parent.resolve()


def test_ruta_dataset_absoluta_se_mantiene_compatible(tmp_path):
    configuracion = tmp_path / "configuracion" / "data.yaml"
    configuracion.parent.mkdir()
    dataset = tmp_path / "dataset" / "exportado"
    dataset.mkdir(parents=True)

    assert ruta_dataset_declarada(configuracion, {"path": str(dataset)}) == dataset.resolve()


def test_yaml_temporal_para_ultralytics_se_elimina_si_falla(tmp_path):
    configuracion = tmp_path / "exportado" / "data.yaml"
    configuracion.parent.mkdir()
    directorio_temporal = None

    with pytest.raises(RuntimeError, match="fallo de entrenamiento"):
        with configuracion_ultralytics_temporal(configuracion, {"path": ".", "names": ["candado"]}) as yaml_yolo:
            directorio_temporal = yaml_yolo.parent
            datos = json.loads(yaml_yolo.read_text(encoding="utf-8"))
            assert Path(datos["path"]) == configuracion.parent.resolve()
            raise RuntimeError("fallo de entrenamiento")

    assert directorio_temporal is not None
    assert not directorio_temporal.exists()
