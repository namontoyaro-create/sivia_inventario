import cv2
import numpy as np
import pytest

from sivia_inventario.imagenes import cargar_imagen, validar_contenido_imagen


def test_cargar_imagen_valida(tmp_path):
    ruta = tmp_path / "datos" / "imagenes" / "candado" / "producto.png"
    ruta.parent.mkdir(parents=True)
    original = np.full((20, 30, 3), 150, dtype=np.uint8)
    assert cv2.imwrite(str(ruta), original)

    resultado = cargar_imagen(ruta, raiz=tmp_path)

    np.testing.assert_array_equal(resultado, original)


def test_archivo_inexistente(tmp_path):
    ruta = tmp_path / "datos" / "imagenes" / "candado" / "no_existe.jpg"
    ruta.parent.mkdir(parents=True)
    with pytest.raises(ValueError, match="No se pudo leer"):
        cargar_imagen(ruta, raiz=tmp_path)


def test_archivo_vacio(tmp_path):
    ruta = tmp_path / "datos" / "imagenes" / "candado" / "vacio.jpg"
    ruta.parent.mkdir(parents=True)
    ruta.write_bytes(b"")

    with pytest.raises(ValueError, match="vacío"):
        cargar_imagen(ruta, raiz=tmp_path)


def test_archivo_invalido(tmp_path):
    ruta = tmp_path / "datos" / "imagenes" / "candado" / "invalido.jpg"
    ruta.parent.mkdir(parents=True)
    ruta.write_bytes(b"Esto no es una imagen")

    with pytest.raises(ValueError, match="No se pudo leer"):
        cargar_imagen(ruta, raiz=tmp_path)


def test_validar_contenido_imagen_rechaza_archivo_disfrazado():
    with pytest.raises(ValueError, match="imagen válida"):
        validar_contenido_imagen(b"no es una imagen aunque tenga extension jpg")


def test_validar_contenido_imagen_acepta_jpeg_real():
    imagen = np.full((20, 30, 3), 150, dtype=np.uint8)
    ok, codificada = cv2.imencode(".jpg", imagen)
    assert ok

    validar_contenido_imagen(codificada.tobytes())


def test_cargar_imagen_rechaza_escape_de_directorio(tmp_path):
    (tmp_path / "secreto.jpg").write_bytes(b"no importa")

    with pytest.raises(ValueError, match="secuencias '..'"):
        cargar_imagen("../secreto.jpg", raiz=tmp_path)
