# SIVIA

Sistema Inteligente de Visión Artificial para Inventarios.

## Proyecto académico

**Título:** “Sistema de automatización de inventario mediante visión artificial en Distribuidora Atencio, Santa Anita-Ate, 2026.”

**Curso:** Sistemas Inteligentes.

## Objetivo

Identificar y contar unidades visibles de productos de ferretería en imágenes para apoyar la verificación del inventario.

## Arquitectura prevista

1. **Entrada:** recibir la imagen.
2. **Procesamiento:** cargar y preparar la imagen.
3. **Detección:** localizar objetos y asignarles una clase mediante IA.
4. **Conteo:** sumar las detecciones por clase.
5. **Catálogo:** relacionar las clases con los productos registrados.
6. **Inventario:** comparar el conteo con el stock registrado.
7. **Resultado:** presentar cantidades y diferencias.

Estos componentes estarán separados para poder cambiar el detector sin modificar el catálogo ni las reglas del inventario.

## Modos previstos

- **Catálogo / inventario:** detección de productos registrados de la empresa.
- **Prueba libre:** búsqueda experimental de objetos mediante texto, utilizando posteriormente un detector de vocabulario abierto.

El modo libre no dependerá del catálogo y sus resultados no modificarán automáticamente el inventario. Ambos modos de detección están pendientes de implementación. La prueba técnica con el modelo general preentrenado no es detección de vocabulario abierto.

## Catálogo inicial

| Clase IA | Unidad de conteo |
|---|---|
| `bolsa_clavos` | Cada bolsa visible |
| `caja_clavos` | Cada caja visible |
| `candado` | Cada candado visible |
| `cerradura_sobreponer` | Cada cerradura visible |
| `tuberia_pvc` | Cada tubo visible |
| `bolsa_cemento` | Cada bolsa visible |
| `disco_corte` | Cada disco visible |
| `caja_discos_corte` | Cada caja visible |

No se cuentan los clavos contenidos dentro de bolsas o cajas. El sistema no inferirá unidades ocultas.

Cada registro contiene identificador, producto, familia, presentación, unidad de conteo y clase de IA. También admite marca, modelo, tamaño y código del producto como datos opcionales.

El catálogo inicial se define en `src/sivia_inventario/categorias.py` y puede ampliarse. Agregar un registro no enseña automáticamente al detector a reconocerlo: la capacidad del modelo deberá validarse por separado.

## Relación con el inventario

El identificador del catálogo es independiente del índice de clase del detector.

Una clase general puede corresponder a varios productos comerciales. Detectar un candado no determina por sí solo su marca, modelo o tamaño. La comparación por código de producto requerirá resolver esa relación.

El stock detectado pertenecerá a una verificación concreta. La comparación requerirá la misma unidad de conteo y el mismo alcance del stock registrado; una fotografía parcial no demuestra por sí sola un faltante en todo el almacén.

La diferencia se calculará como:

```text
diferencia = stock detectado - stock registrado
```

Por ejemplo, 18 unidades detectadas frente a 20 registradas producen una diferencia de -2.

## Estado actual

Implementado:

- Entorno Python administrado con Poetry.
- Dependencias para detección instaladas: Ultralytics y PyTorch/Torchvision para CPU.
- Comando de prueba de detección real con YOLO26n preentrenado, conteo por clase e imagen anotada. Sus clases generales no se relacionan automáticamente con el catálogo de ferretería.
- Carga y visualización de imágenes con OpenCV.
- Pruebas de carga de imágenes, catálogo, conteo y comparación de stock con Pytest.
- Catálogo estructurado de siete productos.
- Validación de campos obligatorios e identificadores únicos del catálogo.
- Comando de inicio del sistema.
- Conteo por clase a partir de etiquetas, comprobado con datos simulados.
- Relación del conteo con el catálogo, conservando coincidencias ambiguas y clases sin correspondencia.
- Comparación de stock por producto con estados de faltante, sobrante o coincidencia, comprobada con datos simulados.
- Archivo JSON de stock de referencia simulado para los siete productos, conectado con la comparación por producto.
- Lectura del stock desde JSON, con validación de cantidades, identificadores y claves duplicadas. Los productos omitidos conservan stock desconocido.

Pendiente:

- Adaptación y validación del detector para las siete clases de ferretería.
- Gestión de movimientos de inventario y conexión de la comparación con resultados de detección verificados.
- Interfaz y modo de prueba libre.

## Entorno para detección con YOLO

El proyecto usa Python 3.13 y Poetry. Desde la raíz del repositorio se pueden instalar las versiones registradas en `poetry.lock`:

```bash
poetry install
```

PyTorch y Torchvision se obtienen del repositorio oficial para CPU, configurado como fuente explícita en `pyproject.toml`. No se necesita CUDA para esta etapa.

Versiones comprobadas en Windows de 64 bits:

| Dependencia | Versión |
|---|---|
| PyTorch | 2.14.1+cpu |
| Torchvision | 0.29.1+cpu |
| Ultralytics | 8.4.171 |
| OpenCV | 5.0.0 |

Para comprobar la importación:

```bash
poetry run python -c "import torch; from ultralytics import YOLO; print('YOLO disponible'); print('PyTorch:', torch.__version__); print('CUDA disponible:', torch.cuda.is_available())"
```

En esta instalación para CPU, `CUDA disponible: False` es el resultado esperado. Esta comprobación no descarga pesos ni ejecuta detección. Las configuraciones locales que Ultralytics genere en la carpeta `Ultralytics/` están excluidas de Git.

Instalar estas dependencias no entrena el modelo ni le enseña las clases del catálogo de SIVIA. Su adaptación al catálogo se realizará en pasos posteriores.

## Primera prueba de detección real

Desde la raíz del proyecto:

```bash
poetry run python -m sivia_inventario.deteccion datos/imagenes/productos.jpg
```

La primera ejecución descarga los pesos oficiales de `yolo26n.pt` en `modelos/` y requiere conexión a Internet. La predicción se realiza localmente en CPU, con un umbral de confianza de 0.50. La fotografía se carga desde el disco, sin enviarla a un servicio de detección.

El comando cuenta las clases devueltas por el modelo y guarda una copia con las detecciones en `resultados/deteccion/`, con fecha y hora en el nombre. El original se conserva. Las carpetas de resultados y los pesos descargados están excluidos de Git.

YOLO26n preentrenado utiliza las 80 clases generales de COCO, no las siete clases de ferretería. Puede no detectar la bolsa o la caja de clavos, o asignarles una categoría incorrecta. Una salida sin detecciones no demuestra ausencia de productos y no se interpreta como stock cero. Este comando no compara ni modifica inventario.

Referencia del modelo: [documentación oficial de YOLO26](https://docs.ultralytics.com/models/yolo26/).

## Dataset de ferretería

Las fotos originales se conservan en `datos/imagenes/`, organizadas por clase. El manifiesto `datos/anotaciones/ferreteria.json` registra sus dimensiones, huellas SHA-256, cajas y particiones.

Para añadir propuestas de anotación para nuevas imágenes y generar una galería de revisión:

```bash
poetry run python -m sivia_inventario.dataset --proponer --revision
```

La galería se crea en `resultados/revision_anotaciones/index.html`. Las cajas con estado `propuesta_automatica` son aproximaciones y quedan bloqueadas para entrenamiento. Una propuesta debe revisarse y corregirse antes de marcarse como `revisada_usuario`.

El dataset actual sirve para probar el flujo, pero no valida conteo de inventario: contiene fotografías comerciales, no tiene un conjunto de prueba independiente y todavía incluye propuestas pendientes de revisión.

Cuando todas las cajas estén revisadas, el comando de exportación genera copias para YOLO sin modificar los originales:

```bash
poetry run python -m sivia_inventario.dataset --exportar --salida datos/dataset_yolo_v2
```

La exportación se detiene si encuentra una propuesta automática, una imagen duplicada, una caja inválida o una fuga entre entrenamiento y validación.

El primer piloto revisado se documenta en [`datos/anotaciones/INFORME_PILOTO.md`](datos/anotaciones/INFORME_PILOTO.md). Sus pesos se guardan localmente dentro de `modelos/` y no se suben a GitHub, ya que se pueden regenerar desde las anotaciones.

## Interfaz local

La interfaz permite elegir una imagen y revisar el resultado de un modelo local:

```bash
poetry run python -m sivia_inventario.interfaz
```

El resultado incluye una imagen anotada y un informe JSON en `resultados/deteccion/`. Los modelos actuales son experimentales, por lo que SIVIA bloquea la comparación con stock aunque se seleccione un archivo JSON. No modifica existencias.

La interfaz necesita que la instalación de Python incluya Tcl/Tk. Si el equipo no lo tiene, se puede usar el comando de detección descrito abajo y abrir la imagen e informe generados.

## Ejecutar la visualización

Desde la raíz del proyecto, con el entorno de Poetry instalado y una fotografía disponible en la ruta indicada:

```bash
poetry run python -m sivia_inventario datos/imagenes/productos.jpg --mostrar
```

Presiona una tecla dentro de la ventana para cerrarla. Sin `--mostrar`, el comando carga la imagen y muestra sus dimensiones en la terminal.

La fotografía de prueba está incluida en Git. Se puede sustituir la ruta por otra imagen local; si contiene espacios, debe escribirse entre comillas.

## Consultar el catálogo

```bash
poetry run python -m sivia_inventario.categorias
```

## Comprobar el conteo con etiquetas simuladas

```bash
poetry run python -m sivia_inventario.conteo
```

Este ejemplo contiene cinco etiquetas `bolsa_clavos`, dos `caja_clavos` y tres `candado`, para un total de diez unidades. No lee imágenes ni ejecuta IA.

La función de conteo recibe una etiqueta por objeto y no depende del catálogo. La eliminación de detecciones duplicadas corresponderá a la etapa de detección.

## Comprobar la relación entre conteo y catálogo

```bash
poetry run python -m sivia_inventario.resumen
```

El ejemplo simulado muestra el identificador, el producto, la presentación y la cantidad. No analiza imágenes ni modifica stock.

Una clase con varios productos candidatos se marca como ambigua y su cantidad se conserva una sola vez. Una clase ajena al catálogo también conserva su cantidad, con estado sin coincidencia. Las clases ausentes del conteo no se interpretan como stock cero.

## Comprobar la comparación de stock

```bash
poetry run python -m sivia_inventario.inventario
```

Este ejemplo lee el stock registrado de `P003` desde `datos/inventario/stock_prueba.json` y lo compara con un conteo simulado de 18 candados. Con las 20 unidades de referencia del archivo de prueba, produce una diferencia de -2 y estado `faltante`. No lee imágenes ni guarda cambios de inventario.

Se puede indicar otro archivo de referencia:

```bash
poetry run python -m sivia_inventario.inventario --stock datos/inventario/stock_prueba.json
```

La salida identifica el archivo utilizado y el tipo de datos de referencia. El conteo de 18 unidades sigue siendo simulado. Si el producto no tiene stock registrado, el comando muestra un error en lugar de asumir cero.

La comparación recibe explícitamente un producto y dos cantidades enteras no negativas. Ambas deben corresponder a la misma unidad y alcance. No resuelve clases ambiguas ni verifica por sí sola que una fotografía cubra todas las existencias.

## Stock de referencia de prueba

El archivo `datos/inventario/stock_prueba.json` contiene cantidades ficticias, marcadas con `tipo_datos: simulados`. No representa las existencias reales de Distribuidora Atencio ni un conteo obtenido de una imagen.

Las claves de `stock_por_producto` son identificadores del catálogo, no índices ni nombres de clase del detector. Cada cantidad usa la presentación del producto correspondiente:

| ID | Producto y presentación | Stock simulado |
|---|---|---|
| P001 | Clavos — bolsa | 30 |
| P002 | Clavos — caja | 8 |
| P003 | Candado — unidad | 20 |
| P004 | Cerradura de sobreponer — unidad | 12 |
| P005 | Tubería PVC — tubo | 25 |
| P006 | Cemento — bolsa | 15 |
| P007 | Disco de corte — unidad | 40 |

Para visualizar y comprobar la sintaxis JSON:

```bash
poetry run python -m json.tool datos/inventario/stock_prueba.json
```

Para leerlo con las validaciones de SIVIA y mostrar los nombres del catálogo:

```bash
poetry run python -m sivia_inventario.stock datos/inventario/stock_prueba.json
```

La lectura conserva el tipo de datos (`simulados` o `reales`) declarado en el archivo y no modifica sus cantidades. Esta etiqueta describe el origen declarado; el sistema no certifica que los datos sean reales. Un producto omitido se muestra con stock desconocido, distinto de un cero explícito.

El módulo de comparación utiliza estas cantidades por identificador de producto mediante `comparar_con_referencia`. La identificación del producto y el alcance del conteo deben resolverse antes de llamar a esta función.

## Ejecutar las pruebas

```bash
poetry run pytest -q
```

Si Windows bloquea el acceso a las carpetas temporales o a la caché, esta alternativa comprobada en Git Bash crea una carpeta temporal nueva y desactiva la caché:

```bash
poetry run pytest -q -p no:cacheprovider --basetemp="$(mktemp -d)/sivia"
```
