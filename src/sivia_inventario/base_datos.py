"""Base SQLite local de SIVIA.

La base almacena inventario y verificaciones. La detección nunca modifica el
stock registrado por sí sola.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from sivia_inventario.categorias import CATALOGO

RAIZ = Path(__file__).resolve().parents[2]
RUTA_BASE_DATOS = RAIZ / "datos" / "sivia.db"
CARPETA_RESPALDOS = RAIZ / "datos" / "respaldos"

STOCK_SIMULADO_INICIAL = {
    "P001": 30,
    "P002": 8,
    "P003": 20,
    "P004": 12,
    "P005": 25,
    "P006": 15,
    "P007": 40,
    "P008": 6,
}

ESQUEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS productos (
    id TEXT PRIMARY KEY,
    producto TEXT NOT NULL,
    familia TEXT NOT NULL,
    presentacion TEXT NOT NULL,
    unidad_conteo TEXT NOT NULL,
    clase_ia TEXT NOT NULL,
    marca TEXT,
    modelo TEXT,
    tamano TEXT,
    codigo_producto TEXT,
    stock_registrado INTEGER NOT NULL CHECK (stock_registrado >= 0),
    origen_stock TEXT NOT NULL CHECK (origen_stock IN ('simulado', 'real')),
    activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
    creado_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    ,sku TEXT
    ,codigo_barras TEXT
    ,proveedor TEXT
    ,precio_compra REAL NOT NULL DEFAULT 0 CHECK (precio_compra >= 0)
    ,precio_venta REAL NOT NULL DEFAULT 0 CHECK (precio_venta >= 0)
    ,stock_minimo INTEGER NOT NULL DEFAULT 0 CHECK (stock_minimo >= 0)
    ,unidad_medida TEXT NOT NULL DEFAULT 'unidad'
    ,estado_producto TEXT NOT NULL DEFAULT 'activo' CHECK (estado_producto IN ('activo', 'inactivo', 'descontinuado'))
);

CREATE TABLE IF NOT EXISTS versiones_esquema (
    version INTEGER PRIMARY KEY,
    nombre TEXT NOT NULL,
    aplicada_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sesiones_verificacion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    alcance TEXT NOT NULL,
    estado TEXT NOT NULL DEFAULT 'abierta' CHECK (estado IN ('abierta', 'finalizada', 'cancelada')),
    detector TEXT NOT NULL DEFAULT 'manual',
    alcance_confirmado INTEGER NOT NULL DEFAULT 0 CHECK (alcance_confirmado IN (0, 1)),
    creada_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finalizada_en TEXT
);

CREATE TABLE IF NOT EXISTS capturas_verificacion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sesion_id INTEGER NOT NULL REFERENCES sesiones_verificacion(id),
    hash_imagen TEXT NOT NULL,
    ruta_evidencia TEXT NOT NULL,
    ruta_resultado TEXT,
    procedencia TEXT NOT NULL DEFAULT 'no_confirmada',
    creada_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(sesion_id, hash_imagen)
);

CREATE TABLE IF NOT EXISTS verificaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sesion_id INTEGER NOT NULL REFERENCES sesiones_verificacion(id),
    captura_id INTEGER REFERENCES capturas_verificacion(id),
    producto_id TEXT NOT NULL REFERENCES productos(id),
    stock_registrado INTEGER NOT NULL CHECK (stock_registrado >= 0),
    cantidad_detectada INTEGER NOT NULL CHECK (cantidad_detectada >= 0),
    cantidad_yolo INTEGER,
    diferencia INTEGER NOT NULL,
    estado TEXT NOT NULL CHECK (estado IN ('stock_coincide', 'requiere_revision', 'no_concluyente')),
    confianza_promedio REAL CHECK (confianza_promedio >= 0 AND confianza_promedio <= 1),
    guardada_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS solicitudes_voz (
    token TEXT PRIMARY KEY,
    transcripcion TEXT NOT NULL,
    operacion TEXT NOT NULL CHECK (operacion IN ('entrada', 'salida')),
    cantidad INTEGER NOT NULL CHECK (cantidad > 0),
    producto_id TEXT NOT NULL REFERENCES productos(id),
    estado TEXT NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente', 'confirmada', 'cancelada')),
    creada_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    confirmada_en TEXT
);

CREATE TABLE IF NOT EXISTS movimientos_inventario (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo_movimiento TEXT UNIQUE,
    solicitud_token TEXT NOT NULL UNIQUE REFERENCES solicitudes_voz(token),
    producto_id TEXT NOT NULL REFERENCES productos(id),
    operacion TEXT NOT NULL CHECK (operacion IN ('entrada', 'salida')),
    cantidad INTEGER NOT NULL CHECK (cantidad > 0),
    stock_anterior INTEGER NOT NULL CHECK (stock_anterior >= 0),
    stock_resultante INTEGER NOT NULL CHECK (stock_resultante >= 0),
    transcripcion TEXT NOT NULL,
    confirmado_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario TEXT NOT NULL UNIQUE COLLATE NOCASE,
    nombre TEXT NOT NULL,
    rol TEXT NOT NULL CHECK (rol IN ('administrador', 'operador', 'auditor')),
    password_hash TEXT NOT NULL,
    password_salt TEXT NOT NULL,
    activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
    creado_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS recuperaciones_contrasena (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    codigo_hash TEXT NOT NULL UNIQUE,
    creada_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    vence_en TEXT NOT NULL,
    usada_en TEXT,
    creada_localmente INTEGER NOT NULL DEFAULT 1 CHECK (creada_localmente IN (0, 1))
);

CREATE INDEX IF NOT EXISTS idx_recuperaciones_usuario_vigente
ON recuperaciones_contrasena(usuario_id, usada_en, vence_en);
"""


@contextmanager
def conectar(ruta: Path = RUTA_BASE_DATOS):
    """Abre una conexión SQLite con claves foráneas activas."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    conexion = sqlite3.connect(ruta)
    conexion.row_factory = sqlite3.Row
    conexion.execute("PRAGMA foreign_keys = ON")
    try:
        yield conexion
        conexion.commit()
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()


def _tablas_y_columnas(ruta: Path) -> tuple[set[str], set[str]]:
    """Inspecciona SQLite sin modificarlo, para saber si hace falta migrar."""
    if not ruta.is_file() or ruta.stat().st_size == 0:
        return set(), set()
    conexion = sqlite3.connect(ruta)
    try:
        tablas = {fila[0] for fila in conexion.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        columnas = ({fila[1] for fila in conexion.execute("PRAGMA table_info(productos)")}
                    if "productos" in tablas else set())
        return tablas, columnas
    finally:
        conexion.close()


def _respaldo_valido(ruta: Path) -> bool:
    """Comprueba que un respaldo SQLite se puede abrir e integrar."""
    conexion = sqlite3.connect(ruta)
    try:
        return conexion.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        conexion.close()


def crear_respaldo_antes_migracion(ruta: Path = RUTA_BASE_DATOS) -> Path | None:
    """Copia una base existente mediante la API SQLite y verifica su integridad."""
    ruta = Path(ruta)
    if not ruta.is_file() or ruta.stat().st_size == 0:
        return None
    carpeta = CARPETA_RESPALDOS if ruta.resolve() == RUTA_BASE_DATOS.resolve() else ruta.parent / "respaldos"
    carpeta.mkdir(parents=True, exist_ok=True)
    sello = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destino = carpeta / f"{ruta.stem}_antes_migracion_{sello}.db"
    origen = sqlite3.connect(ruta)
    copia = sqlite3.connect(destino)
    try:
        origen.backup(copia)
    finally:
        copia.close()
        origen.close()
    if not _respaldo_valido(destino):
        destino.unlink(missing_ok=True)
        raise RuntimeError("El respaldo SQLite no super? la verificaci?n de integridad.")
    return destino


def _agregar_columna_si_falta(conexion: sqlite3.Connection, tabla: str, nombre: str, definicion: str) -> bool:
    columnas = {fila["name"] for fila in conexion.execute(f"PRAGMA table_info({tabla})").fetchall()}
    if nombre not in columnas:
        conexion.execute(f"ALTER TABLE {tabla} ADD COLUMN {definicion}")
        return True
    return False


def _registrar_migracion(conexion: sqlite3.Connection, version: int, nombre: str) -> None:
    conexion.execute(
        "INSERT OR IGNORE INTO versiones_esquema(version, nombre) VALUES (?, ?)",
        (version, nombre),
    )


def _aplicar_migraciones(conexion: sqlite3.Connection) -> None:
    """Aplica cambios idempotentes y deja una traza de cada versi?n."""
    # Versi?n 1 documenta las columnas que ya exist?an en las bases del piloto.
    _agregar_columna_si_falta(conexion, "productos", "descripcion", "descripcion TEXT NOT NULL DEFAULT ''")
    _agregar_columna_si_falta(conexion, "productos", "imagen_ruta", "imagen_ruta TEXT")
    _agregar_columna_si_falta(conexion, "sesiones_verificacion", "codigo_verificacion", "codigo_verificacion TEXT")
    _agregar_columna_si_falta(conexion, "sesiones_verificacion", "detector", "detector TEXT NOT NULL DEFAULT 'manual'")
    _agregar_columna_si_falta(conexion, "sesiones_verificacion", "alcance_confirmado", "alcance_confirmado INTEGER NOT NULL DEFAULT 0")
    _agregar_columna_si_falta(conexion, "capturas_verificacion", "ruta_resultado", "ruta_resultado TEXT")
    _agregar_columna_si_falta(conexion, "capturas_verificacion", "procedencia", "procedencia TEXT NOT NULL DEFAULT 'no_confirmada'")
    _agregar_columna_si_falta(conexion, "verificaciones", "cantidad_yolo", "cantidad_yolo INTEGER")
    _registrar_migracion(conexion, 1, "compatibilidad_piloto_yolo")

    # Versi?n 2: datos comerciales. No altera stock ni elimina registros.
    _agregar_columna_si_falta(conexion, "productos", "sku", "sku TEXT")
    _agregar_columna_si_falta(conexion, "productos", "codigo_barras", "codigo_barras TEXT")
    _agregar_columna_si_falta(conexion, "productos", "proveedor", "proveedor TEXT")
    _agregar_columna_si_falta(conexion, "productos", "precio_compra", "precio_compra REAL NOT NULL DEFAULT 0")
    _agregar_columna_si_falta(conexion, "productos", "precio_venta", "precio_venta REAL NOT NULL DEFAULT 0")
    stock_minimo_agregado = _agregar_columna_si_falta(conexion, "productos", "stock_minimo", "stock_minimo INTEGER NOT NULL DEFAULT 0")
    _agregar_columna_si_falta(conexion, "productos", "unidad_medida", "unidad_medida TEXT NOT NULL DEFAULT 'unidad'")
    _agregar_columna_si_falta(conexion, "productos", "estado_producto", "estado_producto TEXT NOT NULL DEFAULT 'activo'")
    # Las pantallas anteriores ya utilizaban 10 unidades como umbral de alerta.
    # Se conserva ese criterio solo al migrar registros que aún no tenían campo.
    if stock_minimo_agregado:
        conexion.execute("UPDATE productos SET stock_minimo=10 WHERE stock_minimo=0")
    conexion.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_productos_sku_unico ON productos(sku) WHERE sku IS NOT NULL AND trim(sku) <> ''")
    conexion.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_productos_codigo_barras_unico ON productos(codigo_barras) WHERE codigo_barras IS NOT NULL AND trim(codigo_barras) <> ''")
    _registrar_migracion(conexion, 2, "datos_comerciales_producto")

    # Versi\u00f3n 3: recuperaci\u00f3n local de credenciales. Los c\u00f3digos nunca se
    # almacenan en texto plano y no afecta productos ni existencias.
    conexion.execute(
        """
        CREATE TABLE IF NOT EXISTS recuperaciones_contrasena (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
            codigo_hash TEXT NOT NULL UNIQUE,
            creada_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            vence_en TEXT NOT NULL,
            usada_en TEXT,
            creada_localmente INTEGER NOT NULL DEFAULT 1 CHECK (creada_localmente IN (0, 1))
        )
        """
    )
    conexion.execute(
        "CREATE INDEX IF NOT EXISTS idx_recuperaciones_usuario_vigente "
        "ON recuperaciones_contrasena(usuario_id, usada_en, vence_en)"
    )
    _registrar_migracion(conexion, 3, "recuperacion_local_contrasena")


def inicializar_base_datos(ruta: Path = RUTA_BASE_DATOS) -> Path | None:
    """Inicializa SIVIA y respalda una base existente antes de migrarla.

    Devuelve la ruta del respaldo cuando se aplic? una migraci?n estructural.
    """
    ruta = Path(ruta)
    tablas, columnas = _tablas_y_columnas(ruta)
    campos_v2 = {"sku", "codigo_barras", "proveedor", "precio_compra", "precio_venta", "stock_minimo", "unidad_medida", "estado_producto"}
    requiere_migracion = bool(tablas) and (
        "versiones_esquema" not in tablas
        or not campos_v2.issubset(columnas)
        or "recuperaciones_contrasena" not in tablas
    )
    respaldo = crear_respaldo_antes_migracion(ruta) if requiere_migracion else None

    with conectar(ruta) as conexion:
        conexion.executescript(ESQUEMA)
        _aplicar_migraciones(conexion)
        for item in CATALOGO:
            conexion.execute(
                """
                INSERT OR IGNORE INTO productos (
                    id, producto, familia, presentacion, unidad_conteo, clase_ia,
                    marca, modelo, tamano, codigo_producto, stock_registrado, origen_stock
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'simulado')
                """,
                (
                    item.id, item.producto, item.familia, item.presentacion,
                    item.unidad_conteo, item.clase_ia, item.marca, item.modelo,
                    item.tamano, item.codigo_producto, STOCK_SIMULADO_INICIAL[item.id],
                ),
            )
    return respaldo
