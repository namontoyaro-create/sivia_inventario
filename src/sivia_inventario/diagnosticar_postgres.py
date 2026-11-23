"""Diagnóstico local seguro de una conexión PostgreSQL de pruebas.

No imprime la URL, contraseña ni otros secretos. No modifica el esquema ni
datos. Las pruebas de escritura siguen requiriendo SIVIA_TEST_NEON_HOST.
"""

from __future__ import annotations

import os
from urllib.parse import parse_qs, urlsplit

from psycopg import connect

from sivia_inventario.postgres import base_pruebas_postgres_autorizada, host_postgres


def _error(mensaje: str) -> None:
    print(f"ERROR: {mensaje}")


def main() -> int:
    url = os.getenv("TEST_DATABASE_URL", "").strip()
    if not url:
        _error("TEST_DATABASE_URL no está configurada en esta terminal.")
        return 2
    try:
        partes = urlsplit(url)
        parametros = parse_qs(partes.query, strict_parsing=True)
        host = host_postgres(url)
    except ValueError:
        _error("Los parámetros de la URL están mal formados.")
        return 2
    except RuntimeError as error:
        _error(str(error))
        return 2
    if partes.scheme not in {"postgresql", "postgres"}:
        _error("La URL debe iniciar con postgresql://.")
        return 2
    if not partes.username or partes.password is None or not partes.path.strip("/"):
        _error("Falta usuario, contraseña, host o nombre de base en la URL.")
        return 2
    if not host.endswith(".neon.tech"):
        _error("El host no parece pertenecer a Neon; no se realizará conexión.")
        return 2
    if parametros.get("sslmode", [None])[0] != "require":
        _error("La URL debe incluir sslmode=require.")
        return 2
    if any(len(valores) != 1 for valores in parametros.values()):
        _error("La URL contiene parámetros repetidos; genera una URL nueva desde Neon.")
        return 2
    print("FORMATO_URL=correcto")
    print(f"HOST_NEON={host}")
    print(f"BASE={partes.path.strip('/')}")
    print(f"HOST_PRUEBAS_CONFIRMADO={base_pruebas_postgres_autorizada()}")
    try:
        with connect(url, connect_timeout=10) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT current_database(), current_user, version()")
                base, usuario, version = cursor.fetchone()
    except Exception as error:
        _error(f"No se pudo conectar: {type(error).__name__}.")
        return 3
    print("CONEXION=correcta")
    print(f"BASE_CONECTADA={base}")
    print(f"USUARIO_CONECTADO={usuario}")
    print("SERVIDOR_POSTGRES=confirmado")
    if not base_pruebas_postgres_autorizada():
        _error("No se confirma la rama de pruebas: configura SIVIA_TEST_NEON_HOST antes de ejecutar pytest.")
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
