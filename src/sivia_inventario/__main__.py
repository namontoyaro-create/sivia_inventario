import argparse

import cv2

from sivia_inventario.imagenes import cargar_imagen


def main():
    parser = argparse.ArgumentParser(
        description="SIVIA - Carga y visualización de imágenes"
    )
    parser.add_argument("imagen", help="Ruta de la imagen de productos")
    parser.add_argument(
        "--mostrar",
        action="store_true",
        help="Abre una ventana con la imagen",
    )
    args = parser.parse_args()

    try:
        imagen = cargar_imagen(args.imagen)
    except (OSError, ValueError) as error:
        parser.error(str(error))

    alto, ancho = imagen.shape[:2]
    print(f"SIVIA - Imagen cargada: {ancho} x {alto} píxeles")

    if args.mostrar:
        cv2.imshow("SIVIA - Imagen de productos", imagen)
        cv2.waitKey(0)
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
