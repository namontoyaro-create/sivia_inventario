"""Pruebas de seguridad del modo PostgreSQL; no usan DATABASE_URL de producción."""
import os
from uuid import uuid4

import pytest

from sivia_inventario import base_datos
from sivia_inventario.migraciones_postgres import VERSION_ACTUAL, aplicar_migraciones_postgres
from sivia_inventario.postgres import _traducir, base_pruebas_postgres_autorizada, es_url_postgres, url_postgres_configurada


def test_database_url_se_toma_solo_del_entorno_y_valida_protocolo(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert url_postgres_configurada() is None
    monkeypatch.setenv("DATABASE_URL", "mysql://no-autorizado")
    with pytest.raises(RuntimeError, match="PostgreSQL"):
        url_postgres_configurada()


def test_sqlite_se_conserva_sin_database_url(monkeypatch, tmp_path):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    ruta = tmp_path / "local.db"
    base_datos.inicializar_base_datos(ruta)
    assert ruta.is_file()


def test_url_postgres_explicita_solo_ejecuta_migrador_controlado(monkeypatch):
    llamadas = []
    monkeypatch.setattr(base_datos, "aplicar_migraciones_postgres", lambda url: llamadas.append(url))
    url = "postgresql://usuario:secreto@host-pruebas/base_pruebas?sslmode=require"
    assert base_datos.inicializar_base_datos(url) is None
    assert llamadas == [url]


def test_traduccion_postgres_cubre_parametros_conflictos_y_codigos():
    assert "%s" in _traducir("SELECT * FROM productos WHERE id=?")
    assert "ON CONFLICT DO NOTHING" in _traducir("INSERT OR IGNORE INTO productos(id) VALUES (?)")
    assert "LPAD" in _traducir("SELECT printf('VER-%04d', s.id) FROM sesiones_verificacion s")
    assert es_url_postgres("postgresql://host/base")
    assert not es_url_postgres("sqlite:///local.db")


def test_insercion_postgres_recupera_el_identificador_devuelto():
    """La compatibilidad ``lastrowid`` es necesaria para usuarios y movimientos."""
    class Cursor:
        rowcount = 1

        def execute(self, texto, parametros):
            self.texto, self.parametros = texto, parametros

        def fetchone(self):
            return {"id": 42}

    class Conexion:
        def cursor(self):
            return Cursor()

    from sivia_inventario.postgres import ConexionPostgres

    resultado = ConexionPostgres(Conexion()).execute(
        "INSERT INTO usuarios(usuario,nombre,rol,password_hash,password_salt) VALUES (?,?,?,?,?)",
        ("prueba", "Prueba", "operador", "hash", "sal"),
    )
    assert resultado.lastrowid == 42


def test_valores_de_ejemplo_no_autorizan_pruebas_postgres(monkeypatch):
    monkeypatch.setenv("TEST_DATABASE_URL", "postgresql://USUARIO:CLAVE@HOST_DE_SIVIA_PRUEBAS/neondb?sslmode=require")
    monkeypatch.setenv("SIVIA_TEST_NEON_HOST", "host_de_sivia_pruebas")
    assert not base_pruebas_postgres_autorizada()


@pytest.mark.skipif(not base_pruebas_postgres_autorizada(), reason="Requiere TEST_DATABASE_URL y SIVIA_TEST_NEON_HOST coincidentes")
def test_migracion_postgres_aislada_no_usa_database_url_de_produccion():
    """Solo se activa con TEST_DATABASE_URL, nunca con DATABASE_URL."""
    assert aplicar_migraciones_postgres(os.environ["TEST_DATABASE_URL"]) == VERSION_ACTUAL


@pytest.mark.skipif(not base_pruebas_postgres_autorizada(), reason="Requiere TEST_DATABASE_URL y SIVIA_TEST_NEON_HOST coincidentes")
def test_operaciones_y_autenticacion_postgres_aisladas():
    """Prueba real que sólo puede usar TEST_DATABASE_URL, nunca producción."""
    from sivia_inventario.autenticacion import autenticar, crear_usuario
    from sivia_inventario.repositorio_inventario import confirmar_movimiento, crear_producto, crear_solicitud_movimiento

    url = os.environ["TEST_DATABASE_URL"]
    sufijo = uuid4().hex[:10]
    producto, usuario = f"TP{sufijo}", f"prueba.{sufijo}"
    aplicar_migraciones_postgres(url)
    try:
        crear_producto(producto, "Producto PostgreSQL", "Pruebas", "candado", "Unidad", 3, url)
        crear_usuario(usuario, "Usuario PostgreSQL", "operador", "ClaveSegura10", url)
        assert autenticar(usuario, "ClaveSegura10", url)
        solicitud = crear_solicitud_movimiento("Entrada de prueba", "entrada", 2, producto, url)
        assert confirmar_movimiento(solicitud["token"], url)["stock_resultante"] == 5
    finally:
        from sivia_inventario.base_datos import conectar
        with conectar(url) as conexion:
            conexion.execute("DELETE FROM movimientos_inventario WHERE producto_id=?", (producto,))
            conexion.execute("DELETE FROM solicitudes_voz WHERE producto_id=?", (producto,))
            conexion.execute("DELETE FROM productos WHERE id=?", (producto,))
            conexion.execute("DELETE FROM usuarios WHERE usuario=?", (usuario,))
