import cv2
import numpy as np
import pytest

from sivia_inventario.imagenes import cargar_imagen


def test_cargar_imagen_valida(tmp_path):
    ruta = tmp_path / "producto.png"
    original = np.full((20, 30, 3), 150, dtype=np.uint8)
    assert cv2.imwrite(str(ruta), original)

    resultado = cargar_imagen(ruta)

    np.testing.assert_array_equal(resultado, original)


def test_archivo_inexistente(tmp_path):
    with pytest.raises(FileNotFoundError):
        cargar_imagen(tmp_path / "no_existe.jpg")


def test_archivo_vacio(tmp_path):
    ruta = tmp_path / "vacio.jpg"
    ruta.write_bytes(b"")

    with pytest.raises(ValueError, match="vacío"):
        cargar_imagen(ruta)


def test_archivo_invalido(tmp_path):
    ruta = tmp_path / "invalido.jpg"
    ruta.write_bytes(b"Esto no es una imagen")

    with pytest.raises(ValueError, match="No se pudo leer"):
        cargar_imagen(ruta)
