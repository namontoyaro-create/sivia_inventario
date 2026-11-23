from sivia_inventario.deteccion import (
    filtrar_detecciones,
    requiere_reanalisis_caja_clavos,
)


def test_marca_recuadro_que_cubre_casi_toda_la_imagen_sin_descartarlo():
    detecciones = filtrar_detecciones(
        [{"clase": "caja_clavos", "confianza": 0.68, "xyxy": [0, 10, 100, 100]}],
        (100, 100),
    )

    assert len(detecciones) == 1
    assert detecciones[0]["recuadro_anormal"] is True
    assert detecciones[0]["dudosa"] is True
    assert detecciones[0]["cobertura_imagen"] == 0.9


def test_elimina_solo_duplicados_de_la_misma_clase():
    detecciones = filtrar_detecciones([
        {"clase": "candado", "confianza": 0.80, "xyxy": [10, 10, 90, 90]},
        {"clase": "candado", "confianza": 0.60, "xyxy": [11, 11, 89, 89]},
        {"clase": "caja_clavos", "confianza": 0.70, "xyxy": [10, 10, 90, 90]},
    ])

    assert [item["clase"] for item in detecciones] == ["candado", "caja_clavos"]
    assert detecciones[0]["conflicto"] is True
    assert detecciones[1]["conflicto"] is True


def test_reanaliza_una_unica_caja_clavos_grande_sin_afectar_otras_clases():
    assert requiere_reanalisis_caja_clavos(
        [{"clase": "caja_clavos", "confianza": 0.9, "xyxy": [0, 0, 80, 80]}],
        100,
        100,
    ) is True
    assert requiere_reanalisis_caja_clavos(
        [{"clase": "candado", "confianza": 0.9, "xyxy": [0, 0, 90, 90]}],
        100,
        100,
    ) is False
    assert requiere_reanalisis_caja_clavos(
        [
            {"clase": "caja_clavos", "confianza": 0.9, "xyxy": [0, 0, 30, 30]},
            {"clase": "caja_clavos", "confianza": 0.8, "xyxy": [50, 50, 80, 80]},
        ],
        100,
        100,
    ) is False
