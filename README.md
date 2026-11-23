# SIVIA

Sistema Inteligente de Visión Artificial para Inventarios.

## Proyecto académico

**Título:** “Sistema de automatización de inventario mediante visión artificial en Distribuidora Atencio, Santa Anita-Ate, 2026.”

**Curso:** Sistemas Inteligentes.

## Objetivo

Identificar y contar unidades visibles de productos de ferretería en imágenes para apoyar la verificación del inventario, sin modificar las existencias de forma automática.

## Principios de diseño

- **La IA propone, la persona confirma.** Una detección nunca actualiza el stock. Solo los movimientos confirmados lo cambian.
- **Trazabilidad.** Cada movimiento registra usuario, fecha, producto, tipo, cantidad y stock resultante.
- **Honestidad sobre los límites.** El detector actual es experimental y sus resultados se presentan como tales.
- **Alcance explícito.** Una fotografía parcial no demuestra por sí sola un faltante en todo el almacén.

## Tecnologías

| Componente | Tecnología |
|---|---|
| Backend y web | Python 3.13, FastAPI, Jinja2 |
| Base de datos local | SQLite (`datos/sivia.db`) |
| Base de datos de despliegue | PostgreSQL / Neon (opcional, vía `DATABASE_URL`) |
| Visión artificial | YOLO (Ultralytics), PyTorch CPU, OpenCV |
| Voz | Faster-Whisper (transcripción local en español, CPU) |
| Pruebas | Pytest |
| Dependencias | Poetry |

## Arquitectura

1. **Entrada:** se recibe una fotografía (archivo o cámara del navegador).
2. **Procesamiento:** se valida y prepara la imagen.
3. **Detección:** YOLO localiza objetos y les asigna una clase.
4. **Conteo:** se suman las detecciones por clase.
5. **Catálogo:** las clases se relacionan con los productos registrados.
6. **Revisión humana:** la persona corrige, confirma o agrega productos.
7. **Resultado:** se guarda la verificación como evidencia; el stock no cambia.

Los componentes están separados para poder cambiar el detector sin modificar el catálogo ni las reglas del inventario.

## Clases del catálogo

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

No se cuentan los clavos contenidos dentro de bolsas o cajas. El sistema no infiere unidades ocultas.

Una clase general puede corresponder a varios productos comerciales. Detectar un candado no determina por sí solo su marca, modelo o tamaño; la persona selecciona el producto exacto durante la revisión. Agregar un producto al catálogo no enseña automáticamente al detector a reconocerlo: eso requiere fotografías, anotaciones y reentrenamiento.

## Funciones principales

### Inventario y catálogo
- Productos con código interno/SKU, código de barras, categoría, presentación, clase IA, proveedor, marca, modelo, tamaño, precios, stock mínimo, unidad de medida, estado y fotografía.
- Búsqueda global, filtros y ordenamiento.
- Desactivación lógica de productos (no se borran datos).
- El stock no se edita desde “Editar producto”: se gestiona mediante movimientos auditables.
- Los productos sin fotografía muestran “Sin imagen”.

### Movimientos de inventario
- Entradas, salidas y ajustes controlados, con historial.
- Las salidas no pueden superar el stock disponible.
- Requieren confirmación explícita y tienen protección contra envíos duplicados.

### Verificación con YOLO
- Fotografía subida o cámara del navegador (laptop o celular).
- Recuadros reales, clase IA, confianza y cantidad por clase.
- Revisión humana: corregir detecciones, elegir el producto exacto, indicar la cantidad confirmada y agregar productos que YOLO omitió.
- Se diferencia entre conteo automático, conteo confirmado, detección dudosa y producto no detectado.
- Si ninguna detección supera el umbral, se informa que no se reconoció ninguna clase entrenada, sin afirmar que el producto sea desconocido.
- Reanálisis focalizado de cajas de clavos agrupadas: si YOLO detecta una sola caja grande, se vuelve a analizar la imagen en cuatro zonas con el mismo modelo. No se inventan conteos.

### Asistente de voz
- Grabación desde el navegador o carga de audio.
- Transcripción local con Faster-Whisper (modelo base, CPU, int8). Los audios temporales se eliminan tras procesarse.
- La transcripción es editable antes de interpretarla.
- Interpretación determinista de consultas, entradas y salidas (no usa IA generativa para mover stock).
- Antes de cualquier movimiento se muestra: instrucción, operación, producto, cantidad, stock actual y stock resultante previsto. Solo se actualiza tras la confirmación de un administrador.

Ejemplos: “¿Cuántos candados tenemos?”, “Registrar entrada de cinco candados”, “Registrar salida de dos cerraduras”.

### Historial y alertas
- Historial de verificaciones con evidencia, conteo YOLO, conteo confirmado y alcance revisado.
- Alertas diferenciadas: stock bajo, producto agotado, detección dudosa, diferencia observada en una fotografía y discrepancia real (solo cuando el alcance fue confirmado).

### Entrenamiento IA (revisión de dataset)
- Revisión de fotografías y anotaciones pendientes, procedencia, duplicados y estado de aprobación.
- Nada se incorpora al entrenamiento sin aprobación humana.

## Usuarios, roles y seguridad

| Rol | Acceso |
|---|---|
| Administrador | Usuarios, entrenamiento IA, confirmación de movimientos, configuración |
| Operador | Inventario y verificación operativa, sin administración |
| Auditor | Solo consulta |

Medidas implementadas: contraseñas con hash seguro, sesiones firmadas, protección CSRF, límite de intentos de inicio de sesión, recuperación local de acceso con código temporal de un solo uso, solicitud de cuenta separada y validación centralizada de rutas de archivos (protege contra `../` y rutas externas).

En la primera apertura SIVIA solicita crear la cuenta de administradora. No existen contraseñas predeterminadas.

## Estado del modelo y limitaciones

El detector activo es **YOLO piloto v2**, de carácter **experimental**. Sirve para demostración, pero **no representa una evaluación final de precisión en un almacén real**.

Limitaciones conocidas (según la auditoría técnica del 22 de noviembre de 2026):

- Dataset pequeño: 48 imágenes de entrenamiento y 21 de validación.
- **No existe un conjunto de prueba independiente** (0 imágenes de test).
- `caja_clavos` cuenta con pocos ejemplos (8 objetos), lo que explica la dificultad histórica para contar cajas agrupadas.
- Faltan escenas reales con varios productos mezclados, distintos fondos e iluminación.
- Las fotografías de entrenamiento no deben usarse como prueba definitiva.
- Un entrenamiento v3 experimental no se activó porque no demostró mejora suficiente en pruebas reales.
- El historial real de movimientos es corto, por lo que aún no es posible estimar demanda ni reposición con datos reales.

Trabajo futuro: conjunto de test independiente con métricas (precisión, recall, mAP y matriz de confusión), ampliación del dataset, reutilización de las correcciones humanas como datos candidatos de entrenamiento (con aprobación), alertas de anomalías y sugerencia de reposición cuando exista historial suficiente.

## Instalación y ejecución

Requiere Python 3.13 y Poetry. Desde la raíz del repositorio:

```bash
poetry install
```

PyTorch y Torchvision se obtienen del repositorio oficial para CPU, configurado como fuente explícita en `pyproject.toml`. No se necesita CUDA.

Versiones comprobadas en Windows de 64 bits:

| Dependencia | Versión |
|---|---|
| PyTorch | 2.14.1+cpu |
| Torchvision | 0.29.1+cpu |
| Ultralytics | 8.4.171 |
| OpenCV | 5.0.0 |

Para iniciar la aplicación web:

```bash
poetry run uvicorn sivia_inventario.web:app --reload
```

Abre `http://127.0.0.1:8000` en el navegador. Para usarla desde un celular, ambos dispositivos deben estar en la misma red.

La primera apertura crea `datos/sivia.db`, carga los ocho productos del catálogo y marca las cantidades como **simuladas**. La base local no se sube a GitHub.

### Datos de demostración

Los precios y los códigos EAN-13 de prueba del catálogo académico son datos de demostración. No representan precios ni códigos comerciales verificados de Distribuidora Atencio; se pueden editar desde la ficha autorizada de cada producto.

### Advertencia

La variable de entorno `SIVIA_SIN_AUTENTICACION=1` desactiva el inicio de sesión y existe solo para pruebas automáticas (`tests/conftest.py`). No debe definirse en demostraciones ni en producción.

## Base de datos

SQLite es la opción predeterminada de desarrollo y demostración local (`datos/sivia.db`). Almacena usuarios y roles, productos, stock, precios, movimientos, verificaciones, historial y solicitudes de cuenta.

Antes de cambios estructurales se crea un respaldo verificable en `datos/respaldos/`.

### PostgreSQL en Render / Neon

Para una instancia persistente de Render, configura `DATABASE_URL` exclusivamente como secreto del servicio; nunca copies una URL real a `.env`, GitHub o documentación. Al existir esta variable, SIVIA utiliza PostgreSQL y exige un esquema previamente migrado. La migración es explícita y no se ejecuta al iniciar FastAPI:

```powershell
$env:DATABASE_URL = "postgresql://..." # URL de una base autorizada
poetry run python -m sivia_inventario.migrar_postgres
```

Primero usa una base o rama Neon de pruebas y define `TEST_DATABASE_URL` para las pruebas PostgreSQL. El comando no importa datos de `datos/sivia.db`; una migración de datos requiere respaldo y autorización independiente.

En Render Free el almacenamiento local no es persistente tras reinicios, por lo que SQLite no es adecuado allí.

## Dataset de ferretería

Las fotos originales se conservan en `datos/imagenes/`, organizadas por clase. El manifiesto `datos/anotaciones/ferreteria.json` registra sus dimensiones, huellas SHA-256, cajas y particiones.

Para revisar las fotos nuevas agregadas a `datos/imagenes/` y generar una galería de propuestas:

```bash
poetry run python -m sivia_inventario.preparacion_v2 --galeria
```

La galería se crea en `resultados/revision_anotaciones_pendientes/index.html`. Las cajas son propuestas y quedan bloqueadas para entrenamiento hasta su revisión y aprobación humana.

Cuando todas las cajas estén revisadas, la exportación genera copias en formato YOLO sin modificar los originales:

```bash
poetry run python -m sivia_inventario.dataset --exportar --salida datos/entrenamiento/experimental/nuevo_dataset
```

La exportación se detiene si encuentra una propuesta automática, una imagen duplicada, una caja inválida o una fuga entre entrenamiento y validación. El `data.yaml` generado usa rutas relativas.

El primer piloto revisado se documenta en [`datos/anotaciones/INFORME_PILOTO.md`](datos/anotaciones/INFORME_PILOTO.md). Los pesos se guardan localmente en `modelos/` y no se suben a GitHub, ya que se pueden regenerar desde las anotaciones.

## Detección desde la línea de comandos

```bash
poetry run python -m sivia_inventario.deteccion datos/imagenes/productos.jpg
```

La primera ejecución puede descargar los pesos oficiales de `yolo26n.pt` en `modelos/` y requiere conexión a Internet. La predicción se realiza localmente en CPU. El comando cuenta las clases devueltas y guarda una copia anotada en `resultados/deteccion/`. YOLO26n preentrenado usa las 80 clases generales de COCO, no las ocho clases de ferretería, y este comando no modifica inventario.

Para comprobar la instalación de YOLO sin descargar pesos:

```bash
poetry run python -c "import torch; from ultralytics import YOLO; print('YOLO disponible'); print('PyTorch:', torch.__version__); print('CUDA disponible:', torch.cuda.is_available())"
```

En esta instalación para CPU, `CUDA disponible: False` es lo esperado.

## Interfaz local de escritorio

```bash
poetry run python -m sivia_inventario.interfaz
```

Permite elegir una imagen y revisar el resultado de un modelo local. Necesita que la instalación de Python incluya Tcl/Tk. Los modelos son experimentales, por lo que SIVIA bloquea la comparación con stock y no modifica existencias.

## Comandos de comprobación del núcleo

Visualizar una imagen (presiona una tecla para cerrar la ventana):

```bash
poetry run python -m sivia_inventario datos/imagenes/productos.jpg --mostrar
```

Consultar el catálogo:

```bash
poetry run python -m sivia_inventario.categorias
```

Conteo con etiquetas simuladas (no lee imágenes ni ejecuta IA):

```bash
poetry run python -m sivia_inventario.conteo
```

Relación entre conteo y catálogo (una clase con varios productos candidatos se marca como ambigua; una clase ajena al catálogo se marca sin coincidencia; una clase ausente no se interpreta como stock cero):

```bash
poetry run python -m sivia_inventario.resumen
```

Comparación de stock con el archivo de referencia simulado:

```bash
poetry run python -m sivia_inventario.inventario
poetry run python -m sivia_inventario.inventario --stock datos/inventario/stock_prueba.json
```

La diferencia se calcula como `diferencia = stock detectado - stock registrado`. Por ejemplo, 18 unidades detectadas frente a 20 registradas dan -2. La comparación exige la misma unidad y el mismo alcance; no verifica por sí sola que una fotografía cubra todas las existencias.

### Stock de referencia de prueba

`datos/inventario/stock_prueba.json` contiene cantidades ficticias, marcadas como `tipo_datos: simulados`. No representan las existencias reales de Distribuidora Atencio. Las claves son identificadores del catálogo, no índices del detector. Un producto omitido se muestra con stock desconocido, distinto de un cero explícito.

```bash
poetry run python -m json.tool datos/inventario/stock_prueba.json
poetry run python -m sivia_inventario.stock datos/inventario/stock_prueba.json
```

## Ejecutar las pruebas

```bash
poetry run pytest -q
```

Si Windows bloquea el acceso a las carpetas temporales o a la caché, esta alternativa (Git Bash) crea una carpeta temporal nueva y desactiva la caché:

```bash
poetry run pytest -q -p no:cacheprovider --basetemp="$(mktemp -d)/sivia"
```

## Estructura del proyecto

```text
sivia_inventario/
├── datos/            # base SQLite, imágenes, anotaciones, evidencias, respaldos
├── modelos/          # pesos YOLO locales (no se suben a GitHub)
├── resultados/       # salidas de detección, entrenamiento y revisión
├── src/sivia_inventario/
│   ├── plantillas/   # HTML (Jinja2)
│   ├── estaticos/    # CSS, JavaScript e iconos
│   └── *.py          # web, detección, voz, repositorio, autenticación, seguridad
└── tests/            # pruebas automáticas
```

## Archivos que no deben subirse a GitHub

`datos/sivia.db`, `datos/.sivia_sesion_secreta`, `.env`, contraseñas y tokens, fotografías privadas y evidencias, pesos YOLO y datasets pesados.