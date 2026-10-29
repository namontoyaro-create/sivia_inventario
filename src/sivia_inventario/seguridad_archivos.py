"""Primitivas centralizadas para acceder a archivos del proyecto de forma segura."""

from __future__ import annotations

import hashlib
from pathlib import Path


RAIZ_PROYECTO = Path(__file__).resolve().parents[2]


def resolver_ruta_controlada(
    ruta: str | Path,
    raiz: Path = RAIZ_PROYECTO,
    directorio_autorizado: str | Path = ".",
    *,
    extensiones: set[str] | None = None,
) -> Path:
    """Normaliza una ruta dentro de un único directorio permitido.

    La función no consulta si el archivo existe. Eso evita revelar el estado
    del sistema de archivos a partir de una entrada externa. Las operaciones
    de lectura usan :func:`leer_archivo_controlado`, que devuelve el mismo
    error genérico ante archivos ausentes, directorios o permisos insuficientes.
    """
    base = Path(raiz).resolve()
    permitido = (base / directorio_autorizado).resolve()
    entrada = Path(ruta)
    if ".." in entrada.parts:
        raise ValueError("No se permiten secuencias '..' en rutas de SIVIA.")
    candidata_sin_resolver = entrada if entrada.is_absolute() else base / entrada
    try:
        candidata_absoluta = candidata_sin_resolver.absolute()
        relativa = candidata_absoluta.relative_to(permitido)
    except ValueError as error:
        raise ValueError("La ruta está fuera del directorio autorizado de SIVIA.") from error
    try:
        candidata = candidata_sin_resolver.resolve(strict=False)
    except OSError as error:
        raise ValueError("No se pudo resolver la ruta solicitada.") from error
    if not candidata.is_relative_to(permitido):
        raise ValueError("La ruta resuelta está fuera del directorio autorizado de SIVIA.")
    if extensiones is not None and candidata.suffix.lower() not in extensiones:
        raise ValueError("La extensión del archivo no está permitida.")
    return candidata


def leer_archivo_controlado(
    ruta: str | Path, raiz: Path, directorio_autorizado: str | Path, *,
    extensiones: set[str] | None = None,
) -> tuple[Path, bytes]:
    """Valida una ruta y devuelve su contenido sin abrir rutas no verificadas."""
    archivo = resolver_ruta_controlada(ruta, raiz, directorio_autorizado, extensiones=extensiones)
    try:
        contenido = archivo.read_bytes()
    except OSError as error:
        raise ValueError("No se pudo leer un archivo autorizado de SIVIA.") from error
    return archivo, contenido


def sha256_archivo_controlado(
    ruta: str | Path, raiz: Path, directorio_autorizado: str | Path, *,
    extensiones: set[str] | None = None,
) -> str:
    """Calcula una huella únicamente después de validar la ubicación del archivo."""
    _, contenido = leer_archivo_controlado(ruta, raiz, directorio_autorizado, extensiones=extensiones)
    return hashlib.sha256(contenido).hexdigest()
