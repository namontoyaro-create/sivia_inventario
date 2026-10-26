"""Interpretación determinista de instrucciones de voz de SIVIA.

No ejecuta operaciones ni usa un modelo generativo. Sólo prepara una solicitud
para que la persona revise y confirme el movimiento.
"""

from dataclasses import dataclass
import re
import unicodedata


NUMEROS = {
    "cero": 0, "un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3,
    "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8,
    "nueve": 9, "diez": 10, "once": 11, "doce": 12, "trece": 13,
    "catorce": 14, "quince": 15, "dieciseis": 16, "diecisiete": 17,
    "dieciocho": 18, "diecinueve": 19, "veinte": 20,
}
MARCAS_ENTRADA = ("entrada", "ingresar", "ingreso", "agregar", "anadir", "añadir")
MARCAS_SALIDA = ("salida", "retirar", "retiro", "descontar", "sacar")
MARCAS_CONSULTA = ("cuanto", "cuanta", "cuantos", "cuantas", "consultar", "existencia", "existencias", "stock", "tenemos")


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto.lower())
    texto = "".join(caracter for caracter in texto if unicodedata.category(caracter) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", texto)).strip()


@dataclass(frozen=True)
class InterpretacionVoz:
    tipo: str  # consulta, movimiento o aclaracion
    operacion: str | None = None
    cantidad: int | None = None
    termino_producto: str | None = None
    mensaje: str = ""


def extraer_cantidad(texto: str) -> tuple[int | None, str | None]:
    encontrados: list[int] = []
    for token in normalizar(texto).split():
        if token.isdigit():
            encontrados.append(int(token))
        elif token in NUMEROS:
            encontrados.append(NUMEROS[token])
    if not encontrados:
        return None, "Indica una cantidad positiva para continuar."
    if len(set(encontrados)) != 1 or len(encontrados) > 1:
        return None, "La cantidad es ambigua. Indica un único número positivo."
    if encontrados[0] <= 0:
        return None, "La cantidad debe ser mayor que cero."
    return encontrados[0], None


def interpretar_instruccion(texto: str) -> InterpretacionVoz:
    limpio = normalizar(texto)
    if not limpio:
        return InterpretacionVoz("aclaracion", mensaje="Escribe o dicta una instrucción para continuar.")
    entrada = any(marca in limpio.split() for marca in MARCAS_ENTRADA)
    salida = any(marca in limpio.split() for marca in MARCAS_SALIDA)
    if entrada and salida:
        return InterpretacionVoz("aclaracion", mensaje="La instrucción contiene entrada y salida. Indica sólo una operación.")
    if entrada or salida:
        cantidad, error = extraer_cantidad(limpio)
        if error:
            return InterpretacionVoz("aclaracion", mensaje=error)
        return InterpretacionVoz("movimiento", "entrada" if entrada else "salida", cantidad, limpio)
    if any(marca in limpio.split() for marca in MARCAS_CONSULTA):
        return InterpretacionVoz("consulta", termino_producto=limpio)
    return InterpretacionVoz("aclaracion", mensaje="No se identificó una consulta, entrada o salida. Indica claramente la operación.")


def coincide_producto(termino: str, producto) -> bool:
    """Relaciona texto con productos registrados sin asumir un producto exacto."""
    texto = normalizar(termino)
    candidatos = {normalizar(producto.producto), normalizar(producto.clase_ia.replace("_", " "))}
    if producto.codigo_producto:
        candidatos.add(normalizar(producto.codigo_producto))
    candidatos.add(normalizar(producto.id))
    palabras_texto = {palabra.rstrip("s") for palabra in texto.split() if len(palabra) > 3}
    for candidato in candidatos:
        if candidato and (candidato in texto or texto in candidato):
            return True
        palabras = [palabra.rstrip("s") for palabra in candidato.split() if len(palabra) > 3]
        if palabras and all(palabra in palabras_texto for palabra in palabras):
            return True
        if len(palabras) == 1 and palabras[0] in palabras_texto:
            return True
    return False
