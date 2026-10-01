"""Primera prueba de detección real con un modelo general preentrenado."""

import argparse
from datetime import datetime
from pathlib import Path

import cv2
from ultralytics import YOLO

from sivia_inventario.conteo import contar_por_clase
from sivia_inventario.imagenes import cargar_imagen


MODELO_GENERAL = Path("modelos/yolo26n.pt")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="SIVIA - Prueba de detección general, sin comparar inventario"
    )
    parser.add_argument("imagen", type=Path, help="Ruta de la imagen de prueba")
    args = parser.parse_args()

    print("SIVIA - Detección real con modelo general YOLO26n.", flush=True)
    print(
        "Prueba técnica: las clases de este modelo no son el catálogo de SIVIA.\n"
        "Los resultados no se usan para comparar ni modificar inventario.",
        flush=True,
    )

    try:
        imagen = cargar_imagen(args.imagen)
        MODELO_GENERAL.parent.mkdir(parents=True, exist_ok=True)
        if not MODELO_GENERAL.is_file():
            print("Descargando modelo preentrenado de Ultralytics...", flush=True)
        modelo = YOLO(str(MODELO_GENERAL))
        resultado = modelo.predict(
            source=imagen,
            device="cpu",
            conf=0.5,
            imgsz=640,
            save=False,
            verbose=False,
        )[0]

        etiquetas = [
            resultado.names[int(clase)]
            for clase in resultado.boxes.cls.cpu().tolist()
        ]
        conteos = contar_por_clase(etiquetas)
        imagen_anotada = resultado.plot()
        correcto, contenido = cv2.imencode(".jpg", imagen_anotada)
        if not correcto:
            raise ValueError("No se pudo generar la imagen con las detecciones.")

        carpeta_salida = Path("resultados/deteccion")
        carpeta_salida.mkdir(parents=True, exist_ok=True)
        instante = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        salida = carpeta_salida / f"{args.imagen.stem}_{instante}.jpg"
        salida.write_bytes(contenido.tobytes())
    except (OSError, ValueError, RuntimeError) as error:
        parser.error(str(error))

    print("Umbral de confianza: 0.50")
    if conteos:
        for clase, cantidad in conteos.items():
            print(f"{clase}: {cantidad}")
    else:
        print("Sin detecciones por encima del umbral; no significa que la imagen esté vacía.")
    print(f"Total de objetos detectados por el modelo general: {sum(conteos.values())}")
    print(f"Imagen de resultado: {salida}")


if __name__ == "__main__":
    main()
