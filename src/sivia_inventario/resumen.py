"""Relaciona conteos por clase con el catálogo, sin modificar el inventario."""

from collections.abc import Mapping
from dataclasses import dataclass

from sivia_inventario.categorias import (
    CATALOGO,
    ProductoCatalogo,
    validar_catalogo,
)
from sivia_inventario.conteo import contar_por_clase


@dataclass(frozen=True)
class ConteoCatalogo:
    clase_ia: str
    cantidad: int
    candidatos: tuple[ProductoCatalogo, ...]

    @property
    def estado(self) -> str:
        if not self.candidatos:
            return "sin_coincidencia"
        if len(self.candidatos) == 1:
            return "coincidencia_unica"
        return "ambiguo"


def relacionar_con_catalogo(
    conteos: Mapping[str, int],
    catalogo: tuple[ProductoCatalogo, ...],
) -> tuple[ConteoCatalogo, ...]:
    """Conserva un resultado por clase, incluso sin coincidencia o con varias.

    No distribuye ni repite la cantidad entre productos candidatos.
    Las clases ausentes del conteo no se convierten en stock cero.
    Una coincidencia indica una relación con el catálogo, no una
    verificación visual de marca, modelo o tamaño.
    """
    validar_catalogo(catalogo)
    resultados = []

    for clase, cantidad in conteos.items():
        if not isinstance(clase, str) or not clase.strip():
            raise ValueError("Cada clase debe ser un texto no vacío.")
        if (
            not isinstance(cantidad, int)
            or isinstance(cantidad, bool)
            or cantidad < 0
        ):
            raise ValueError("Cada cantidad debe ser un entero no negativo.")

        candidatos = tuple(p for p in catalogo if p.clase_ia == clase)
        resultados.append(ConteoCatalogo(clase, cantidad, candidatos))

    return tuple(resultados)


if __name__ == "__main__":
    print("SIVIA - Resumen simulado; no analiza imágenes ni modifica stock.")
    etiquetas_ejemplo = (
        ["bolsa_clavos"] * 5
        + ["caja_clavos"] * 2
        + ["candado"] * 3
    )
    resumen = relacionar_con_catalogo(
        contar_por_clase(etiquetas_ejemplo), CATALOGO
    )

    for fila in resumen:
        if fila.estado == "coincidencia_unica":
            producto = fila.candidatos[0]
            print(
                f"{producto.id} | {producto.producto} | "
                f"{producto.presentacion}: {fila.cantidad} unidades"
            )
        else:
            print(f"{fila.clase_ia}: {fila.cantidad} unidades ({fila.estado})")

    print(f"Total: {sum(fila.cantidad for fila in resumen)} unidades")
