"""Adaptador PostgreSQL opcional; SQLite sigue siendo el valor local."""
from __future__ import annotations

from contextlib import contextmanager
import os
import re
import hmac
from typing import Any, Iterator
from urllib.parse import urlsplit

from psycopg import connect
from psycopg.rows import dict_row


class ErrorEsquemaPostgres(RuntimeError):
    """El esquema PostgreSQL no se preparó con la migración controlada."""


def url_postgres_configurada() -> str | None:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        return None
    if not url.startswith(("postgresql://", "postgres://")):
        raise RuntimeError("DATABASE_URL debe usar PostgreSQL.")
    return url


def usa_postgres() -> bool:
    return url_postgres_configurada() is not None


def es_url_postgres(valor: object) -> bool:
    return isinstance(valor, str) and valor.startswith(("postgresql://", "postgres://"))


def host_postgres(url: str) -> str:
    """Obtiene el host sin revelar usuario, contraseña ni parámetros."""
    try:
        host = urlsplit(url).hostname
    except ValueError as error:
        raise RuntimeError("La URL PostgreSQL no tiene un formato válido.") from error
    if not host:
        raise RuntimeError("La URL PostgreSQL no contiene un host.")
    return host.lower()


def base_pruebas_postgres_autorizada() -> bool:
    """Exige que el host de pruebas sea declarado explícitamente en el entorno.

    Evita que una prueba que escribe datos use por accidente ``DATABASE_URL`` o
    una URL de Neon distinta a la rama aislada seleccionada por la persona que
    administra el proyecto.
    """
    url = os.getenv("TEST_DATABASE_URL", "").strip()
    host_esperado = os.getenv("SIVIA_TEST_NEON_HOST", "").strip().lower()
    if not url or not host_esperado:
        return False
    try:
        host = host_postgres(url)
        return host.endswith(".neon.tech") and hmac.compare_digest(host, host_esperado)
    except RuntimeError:
        return False


class Fila(dict):
    """Fila compatible con accesos por nombre o índice de sqlite3.Row."""
    def __getitem__(self, clave: str | int) -> Any:
        return list(self.values())[clave] if isinstance(clave, int) else super().__getitem__(clave)


class Resultado:
    def __init__(self, cursor, lastrowid: int | None = None):
        self._cursor, self.lastrowid, self.rowcount = cursor, lastrowid, cursor.rowcount

    def fetchone(self):
        fila = self._cursor.fetchone()
        return Fila(fila) if fila is not None else None

    def fetchall(self):
        return [Fila(fila) for fila in self._cursor.fetchall()]


_TABLAS_ID = {"sesiones_verificacion", "capturas_verificacion", "verificaciones", "movimientos_inventario", "usuarios", "recuperaciones_contrasena", "solicitudes_cuenta"}


def _traducir(sql: str) -> str:
    texto = sql.strip()
    if texto.upper() == "BEGIN IMMEDIATE":
        return ""
    ignorar = bool(re.search(r"\bINSERT\s+OR\s+IGNORE\b", texto, re.I))
    texto = re.sub(r"\bINSERT\s+OR\s+IGNORE\s+INTO\b", "INSERT INTO", texto, flags=re.I)
    encontrada = re.match(r"^INSERT\s+INTO\s+([a-z_]+)", texto, re.I)
    if ignorar:
        texto += " ON CONFLICT DO NOTHING"
    elif encontrada and encontrada.group(1).lower() in _TABLAS_ID and "RETURNING" not in texto.upper():
        texto += " RETURNING id"
    texto = re.sub(r"\s+COLLATE\s+NOCASE", "", texto, flags=re.I)
    texto = texto.replace("printf('VER-%04d', s.id)", "'VER-' || LPAD(s.id::text, 4, '0')")
    return texto.replace("?", "%s")


class ConexionPostgres:
    def __init__(self, conexion): self._conexion = conexion

    def execute(self, sql: str, parametros: tuple | list = ()) -> Resultado:
        texto = _traducir(sql)
        cursor = self._conexion.cursor()
        if not texto:
            return Resultado(cursor)
        cursor.execute(texto, parametros)
        ultimo = None
        # ``_traducir`` agrega ``RETURNING id`` a las tablas con claves
        # seriales.  Comparar contra la versión ya normalizada evita que la
        # diferencia de mayúsculas deje ``lastrowid`` en ``None``.
        if " RETURNING ID" in texto.upper():
            ultimo = int(cursor.fetchone()["id"])
        return Resultado(cursor, ultimo)


@contextmanager
def conectar_postgres(url: str | None = None) -> Iterator[ConexionPostgres]:
    configurada = url or url_postgres_configurada()
    if not configurada:
        raise RuntimeError("DATABASE_URL no está configurada.")
    with connect(configurada, row_factory=dict_row) as conexion:
        try:
            yield ConexionPostgres(conexion)
            conexion.commit()
        except Exception:
            conexion.rollback()
            raise
