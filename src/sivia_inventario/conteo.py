"""Conteo por clase a partir de etiquetas; no realiza detección de imágenes."""

from collections import Counter
from collections.abc import Iterable


def contar_por_clase(clases: Iterable[str]) -> dict[str, int]:
    """Cuenta una unidad por etiqueta recibida, sin depender del catálogo.

    La entrada debe contener una etiqueta por objeto. El detector futuro
    deberá filtrar las detecciones duplicadas antes de llamar esta función.
    Una entrada vacía devuelve un diccionario vacío.
    """
    if isinstance(clases, (str, bytes)):
        raise TypeError("Se requiere una colección de etiquetas, no un texto único.")

    conteos: Counter[str] = Counter()
    for clase in clases:
        if not isinstance(clase, str) or not clase.strip():
            raise ValueError("Cada etiqueta debe ser un texto no vacío.")
        conteos[clase] += 1

    return dict(conteos)


if __name__ == "__main__":
    print("SIVIA - Ejemplo simulado de conteo; no analiza imágenes.")
    etiquetas_ejemplo = (
        ["bolsa_clavos"] * 5
        + ["caja_clavos"] * 2
        + ["candado"] * 3
    )
    resultado = contar_por_clase(etiquetas_ejemplo)

    for clase, cantidad in resultado.items():
        print(f"{clase}: {cantidad} unidades")
    print(f"Total: {sum(resultado.values())} unidades")
