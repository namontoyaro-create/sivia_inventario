# Informe del primer piloto YOLO

Fecha: 1 de octubre de 2026.

El dataset revisado contiene 38 imágenes para entrenamiento y 17 para validación. Se conservaron únicamente ejemplos donde una unidad puede delimitarse de forma razonable. Las fotografías con múltiples unidades sin cajas individuales, collages o duplicados se mantienen en `datos/imagenes/`, pero están excluidas del manifiesto con su motivo.

El primer entrenamiento experimental usó YOLO26n en CPU, tamaño de imagen 320, lote 4 y un máximo de 100 épocas. La detención temprana terminó el proceso en la época 62. El mejor peso local se guardó como `modelos/ferreteria_piloto_20261001_184825_574143.pt`; no se versiona en Git porque es un archivo generado.

En la imagen independiente `datos/imagenes/candado/candado_03.jpg`, el modelo detectó un `candado` con confianza 0.9746 y conteo 1 usando umbral 0.50. La imagen anotada y su informe se guardaron en `resultados/deteccion/20261001_191941_16dd5f4d/`.

Este resultado solo demuestra que el flujo de detección funciona con una imagen de validación. El modelo no está validado para inventario: faltan imágenes reales de almacén, escenas con productos mezclados, varias unidades por imagen y un conjunto de prueba independiente. Por ello SIVIA mantiene bloqueada la comparación con stock.
