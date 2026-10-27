from pathlib import Path

import cv2
import numpy as np


MAXIMO_PIXELES_IMAGEN = 25_000_000


def validar_contenido_imagen(contenido: bytes) -> None:
    """Comprueba que una carga sea una imagen decodificable y razonable."""
    datos = np.frombuffer(contenido, dtype=np.uint8)
    imagen = cv2.imdecode(datos, cv2.IMREAD_COLOR) if datos.size else None
    if imagen is None:
        raise ValueError("El archivo no contiene una imagen válida.")
    alto, ancho = imagen.shape[:2]
    if alto * ancho > MAXIMO_PIXELES_IMAGEN:
        raise ValueError("La imagen supera el límite seguro de resolución.")


def cargar_imagen(ruta: str | Path) -> np.ndarray:
    """Carga una imagen en formato BGR de OpenCV."""
    archivo = Path(ruta)

    if not archivo.is_file():
        raise FileNotFoundError(f"No existe el archivo: {archivo}")

    datos = np.frombuffer(archivo.read_bytes(), dtype=np.uint8)

    if datos.size == 0:
        raise ValueError(f"El archivo está vacío: {archivo}")

    imagen = cv2.imdecode(datos, cv2.IMREAD_COLOR)

    if imagen is None:
        raise ValueError(f"No se pudo leer como imagen: {archivo}")

    return imagen
