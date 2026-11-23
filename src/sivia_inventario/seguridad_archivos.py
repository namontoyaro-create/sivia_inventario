"""Primitivas centralizadas para acceder a archivos del proyecto de forma segura."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path


RAIZ_PROYECTO = Path(__file__).resolve().parents[2]
ERROR_RUTA_CONTROLADA = "La ruta solicitada no es válida."
REGISTRO = logging.getLogger(__name__)


def _rechazar_ruta_controlada(motivo: str) -> None:
    """Registra el motivo interno sin convertirlo en información para el cliente."""
    REGISTRO.warning("Rechazo de ruta controlada: %s", motivo)
    raise ValueError(ERROR_RUTA_CONTROLADA)


def resolver_ruta_controlada(
    ruta: str | Path,
    raiz: Path = RAIZ_PROYECTO,
    directorio_autorizado: str | Path = ".",
    *,
    extensiones: set[str] | None = None,
    requiere_archivo: bool = True,
) -> Path:
    """Normaliza una ruta dentro de un único directorio permitido.

    Todo rechazo externo devuelve el mismo mensaje para no revelar estado,
    ubicación ni tipo de archivo. ``requiere_archivo=False`` se reserva para
    rutas internas de salida que todavía no existen.
    """
    base = Path(raiz).resolve()
    permitido = (base / directorio_autorizado).resolve()
    try:
        entrada = Path(ruta)
    except (TypeError, ValueError):
        _rechazar_ruta_controlada("entrada inválida")
    if ".." in entrada.parts:
        _rechazar_ruta_controlada("secuencia de ascenso")
    candidata_sin_resolver = entrada if entrada.is_absolute() else base / entrada
    try:
        candidata_absoluta = candidata_sin_resolver.absolute()
        candidata_absoluta.relative_to(permitido)
    except (OSError, ValueError):
        _rechazar_ruta_controlada("fuera del directorio autorizado")
    try:
        candidata = candidata_sin_resolver.resolve(strict=False)
    except OSError:
        _rechazar_ruta_controlada("fallo al resolver ruta")
    if not candidata.is_relative_to(permitido):
        _rechazar_ruta_controlada("enlace simbólico o resolución externa")
    if extensiones is not None and candidata.suffix.lower() not in extensiones:
        _rechazar_ruta_controlada("extensión no permitida")
    if requiere_archivo and not candidata.is_file():
        _rechazar_ruta_controlada("archivo inexistente o no regular")
    return candidata


def leer_archivo_controlado(
    ruta: str | Path, raiz: Path, directorio_autorizado: str | Path, *,
    extensiones: set[str] | None = None,
) -> tuple[Path, bytes]:
    """Valida una ruta y devuelve su contenido sin abrir rutas no verificadas."""
    archivo = resolver_ruta_controlada(ruta, raiz, directorio_autorizado, extensiones=extensiones)
    try:
        contenido = archivo.read_bytes()
    except OSError:
        _rechazar_ruta_controlada("fallo de lectura")
    return archivo, contenido


def sha256_archivo_controlado(
    ruta: str | Path, raiz: Path, directorio_autorizado: str | Path, *,
    extensiones: set[str] | None = None,
) -> str:
    """Calcula una huella únicamente después de validar la ubicación del archivo."""
    _, contenido = leer_archivo_controlado(ruta, raiz, directorio_autorizado, extensiones=extensiones)
    return hashlib.sha256(contenido).hexdigest()
