import json

import cv2
import numpy as np
import pytest

from sivia_inventario.categorias import CATALOGO
from sivia_inventario.dataset import auditar, proponer_caja


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
                "sha256": sha256(imagen_path),
                "ancho": 20,
                "alto": 20,
                "estado": "propuesta_automatica",
                "split": "train",
                "grupo": "ejemplo",
                "objetos": [{"clase": "candado", "xyxy": [0.1, 0.1, 0.9, 0.9]}],
            }
        ],
    }
    ruta = raiz / "manifiesto.json"
    ruta.write_text(json.dumps(manifiesto), encoding="utf-8")

    with pytest.raises(ValueError, match="propuestas automáticas"):
        auditar(ruta, raiz)
