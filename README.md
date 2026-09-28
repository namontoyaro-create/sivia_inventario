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

El modo libre no dependerá del catálogo y sus resultados no modificarán automáticamente el inventario. Ambos modos de detección están pendientes de implementación.

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
- Carga y visualización de imágenes con OpenCV.
- Pruebas de carga de imágenes, catálogo, conteo y comparación de stock con Pytest.
- Catálogo estructurado de siete productos.
- Validación de campos obligatorios e identificadores únicos del catálogo.
- Comando de inicio del sistema.
- Conteo por clase a partir de etiquetas, comprobado con datos simulados.
- Relación del conteo con el catálogo, conservando coincidencias ambiguas y clases sin correspondencia.
- Comparación de stock por producto con estados de faltante, sobrante o coincidencia, comprobada con datos simulados.

Pendiente:

- Detección mediante IA y conexión con el conteo para analizar imágenes.
- Registro persistente de existencias y conexión de la comparación con resultados de detección verificados.
- Interfaz y modo de prueba libre.

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

Este ejemplo simula 20 candados registrados y 18 contados: diferencia de -2 y estado `faltante`. No lee imágenes ni guarda cambios de inventario.

La comparación recibe explícitamente un producto y dos cantidades enteras no negativas. Ambas deben corresponder a la misma unidad y alcance. No resuelve clases ambiguas ni verifica por sí sola que una fotografía cubra todas las existencias.

## Ejecutar las pruebas

```bash
poetry run pytest -q
```

Si Windows bloquea el acceso a las carpetas temporales o a la caché, esta alternativa comprobada en Git Bash crea una carpeta temporal nueva y desactiva la caché:

```bash
poetry run pytest -q -p no:cacheprovider --basetemp="$(mktemp -d)/sivia"
```
