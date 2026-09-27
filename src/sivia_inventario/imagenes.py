from pathlib import Path

import cv2
import numpy as np


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
