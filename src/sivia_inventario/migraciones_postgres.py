"""Migraciones PostgreSQL controladas. Nunca se ejecutan al iniciar FastAPI."""
from __future__ import annotations
from contextlib import closing
from psycopg import connect
from sivia_inventario.postgres import ErrorEsquemaPostgres, url_postgres_configurada

VERSION_ACTUAL = 1
ESQUEMA_V1 = """
CREATE TABLE IF NOT EXISTS versiones_esquema(version INTEGER PRIMARY KEY,nombre TEXT NOT NULL,aplicada_en TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::text);
CREATE TABLE IF NOT EXISTS productos(id TEXT PRIMARY KEY,producto TEXT NOT NULL,familia TEXT NOT NULL,presentacion TEXT NOT NULL,unidad_conteo TEXT NOT NULL,clase_ia TEXT NOT NULL,marca TEXT,modelo TEXT,tamano TEXT,codigo_producto TEXT,stock_registrado INTEGER NOT NULL CHECK(stock_registrado>=0),origen_stock TEXT NOT NULL CHECK(origen_stock IN ('simulado','real')),activo SMALLINT NOT NULL DEFAULT 1 CHECK(activo IN(0,1)),creado_en TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::text,actualizado_en TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::text,sku TEXT,codigo_barras TEXT,proveedor TEXT,precio_compra DOUBLE PRECISION NOT NULL DEFAULT 0 CHECK(precio_compra>=0),precio_venta DOUBLE PRECISION NOT NULL DEFAULT 0 CHECK(precio_venta>=0),stock_minimo INTEGER NOT NULL DEFAULT 0 CHECK(stock_minimo>=0),unidad_medida TEXT NOT NULL DEFAULT 'unidad',estado_producto TEXT NOT NULL DEFAULT 'activo' CHECK(estado_producto IN('activo','inactivo','descontinuado')),descripcion TEXT NOT NULL DEFAULT '',imagen_ruta TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS idx_productos_sku_unico ON productos(sku) WHERE sku IS NOT NULL AND btrim(sku)<>'';
CREATE UNIQUE INDEX IF NOT EXISTS idx_productos_barras_unico ON productos(codigo_barras) WHERE codigo_barras IS NOT NULL AND btrim(codigo_barras)<>'';
CREATE TABLE IF NOT EXISTS sesiones_verificacion(id BIGSERIAL PRIMARY KEY,codigo_verificacion TEXT,nombre TEXT NOT NULL,alcance TEXT NOT NULL,estado TEXT NOT NULL DEFAULT 'abierta' CHECK(estado IN('abierta','finalizada','cancelada')),detector TEXT NOT NULL DEFAULT 'manual',alcance_confirmado SMALLINT NOT NULL DEFAULT 0 CHECK(alcance_confirmado IN(0,1)),creada_en TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::text,finalizada_en TEXT);
CREATE TABLE IF NOT EXISTS capturas_verificacion(id BIGSERIAL PRIMARY KEY,sesion_id BIGINT NOT NULL REFERENCES sesiones_verificacion(id),hash_imagen TEXT NOT NULL,ruta_evidencia TEXT NOT NULL,ruta_resultado TEXT,procedencia TEXT NOT NULL DEFAULT 'no_confirmada',creada_en TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::text,UNIQUE(sesion_id,hash_imagen));
CREATE TABLE IF NOT EXISTS verificaciones(id BIGSERIAL PRIMARY KEY,sesion_id BIGINT NOT NULL REFERENCES sesiones_verificacion(id),captura_id BIGINT REFERENCES capturas_verificacion(id),producto_id TEXT NOT NULL REFERENCES productos(id),stock_registrado INTEGER NOT NULL CHECK(stock_registrado>=0),cantidad_detectada INTEGER NOT NULL CHECK(cantidad_detectada>=0),cantidad_yolo INTEGER,diferencia INTEGER NOT NULL,estado TEXT NOT NULL CHECK(estado IN('stock_coincide','requiere_revision','no_concluyente')),confianza_promedio DOUBLE PRECISION CHECK(confianza_promedio>=0 AND confianza_promedio<=1),guardada_en TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::text);
CREATE TABLE IF NOT EXISTS solicitudes_voz(token TEXT PRIMARY KEY,transcripcion TEXT NOT NULL,operacion TEXT NOT NULL CHECK(operacion IN('entrada','salida')),cantidad INTEGER NOT NULL CHECK(cantidad>0),producto_id TEXT NOT NULL REFERENCES productos(id),estado TEXT NOT NULL DEFAULT 'pendiente' CHECK(estado IN('pendiente','confirmada','cancelada')),creada_en TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::text,confirmada_en TEXT);
CREATE TABLE IF NOT EXISTS movimientos_inventario(id BIGSERIAL PRIMARY KEY,codigo_movimiento TEXT UNIQUE,solicitud_token TEXT NOT NULL UNIQUE REFERENCES solicitudes_voz(token),producto_id TEXT NOT NULL REFERENCES productos(id),operacion TEXT NOT NULL CHECK(operacion IN('entrada','salida')),cantidad INTEGER NOT NULL CHECK(cantidad>0),stock_anterior INTEGER NOT NULL CHECK(stock_anterior>=0),stock_resultante INTEGER NOT NULL CHECK(stock_resultante>=0),transcripcion TEXT NOT NULL,confirmado_en TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::text);
CREATE TABLE IF NOT EXISTS usuarios(id BIGSERIAL PRIMARY KEY,usuario TEXT NOT NULL UNIQUE,nombre TEXT NOT NULL,rol TEXT NOT NULL CHECK(rol IN('administrador','operador','auditor')),password_hash TEXT NOT NULL,password_salt TEXT NOT NULL,activo SMALLINT NOT NULL DEFAULT 1 CHECK(activo IN(0,1)),creado_en TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::text,actualizado_en TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::text);
CREATE UNIQUE INDEX IF NOT EXISTS idx_usuarios_casefold ON usuarios(lower(usuario));
CREATE TABLE IF NOT EXISTS recuperaciones_contrasena(id BIGSERIAL PRIMARY KEY,usuario_id BIGINT NOT NULL REFERENCES usuarios(id),codigo_hash TEXT NOT NULL UNIQUE,creada_en TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::text,vence_en TEXT NOT NULL,usada_en TEXT,creada_localmente SMALLINT NOT NULL DEFAULT 1 CHECK(creada_localmente IN(0,1)));
CREATE INDEX IF NOT EXISTS idx_recuperaciones_usuario_vigente ON recuperaciones_contrasena(usuario_id,usada_en,vence_en);
CREATE TABLE IF NOT EXISTS solicitudes_cuenta(id BIGSERIAL PRIMARY KEY,usuario_solicitado TEXT NOT NULL,nombre TEXT NOT NULL,motivo TEXT NOT NULL DEFAULT '',estado TEXT NOT NULL DEFAULT 'pendiente' CHECK(estado IN('pendiente','revisada','rechazada')),creada_en TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::text,revisada_en TEXT,revisada_por BIGINT REFERENCES usuarios(id));
CREATE UNIQUE INDEX IF NOT EXISTS idx_solicitudes_casefold ON solicitudes_cuenta(lower(usuario_solicitado));
CREATE INDEX IF NOT EXISTS idx_solicitudes_estado ON solicitudes_cuenta(estado,creada_en);
"""

def version_esquema_postgres(url: str | None = None) -> int:
    configurada=url or url_postgres_configurada()
    if not configurada:return 0
    try:
        with connect(configurada) as db, closing(db.cursor()) as cur:
            cur.execute("SELECT to_regclass('public.versiones_esquema')")
            if cur.fetchone()[0] is None:return 0
            cur.execute("SELECT COALESCE(MAX(version),0) FROM versiones_esquema")
            return int(cur.fetchone()[0])
    except Exception as error: raise ErrorEsquemaPostgres("No se pudo verificar el esquema PostgreSQL.") from error

def aplicar_migraciones_postgres(url: str | None = None) -> int:
    configurada=url or url_postgres_configurada()
    if not configurada: raise RuntimeError("DATABASE_URL no está configurada.")
    with connect(configurada) as db, closing(db.cursor()) as cur:
        cur.execute("SELECT pg_advisory_xact_lock(87421035)")
        # psycopg ejecuta una sentencia por llamada; el esquema no contiene
        # bloques procedurales, por lo que separar por punto y coma es seguro.
        for sentencia in (item.strip() for item in ESQUEMA_V1.split(";")):
            if sentencia:
                cur.execute(sentencia)
        cur.execute("INSERT INTO versiones_esquema(version,nombre) VALUES(%s,%s) ON CONFLICT(version) DO NOTHING",(VERSION_ACTUAL,"esquema_inicial_sivia_postgresql"))
    return VERSION_ACTUAL

def exigir_esquema_postgres_actualizado(url: str | None = None) -> None:
    if version_esquema_postgres(url)!=VERSION_ACTUAL: raise ErrorEsquemaPostgres("El esquema PostgreSQL no está listo. Ejecuta la migración controlada antes de iniciar SIVIA.")
