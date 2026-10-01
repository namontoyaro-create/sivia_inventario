"""Base SQLite local de SIVIA.

La base almacena inventario y verificaciones. La detección nunca modifica el
stock registrado por sí sola.
"""

from contextlib import contextmanager
from pathlib import Path
import sqlite3

from sivia_inventario.categorias import CATALOGO

RAIZ = Path(__file__).resolve().parents[2]
RUTA_BASE_DATOS = RAIZ / "datos" / "sivia.db"

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
);

CREATE TABLE IF NOT EXISTS sesiones_verificacion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    alcance TEXT NOT NULL,
    estado TEXT NOT NULL DEFAULT 'abierta' CHECK (estado IN ('abierta', 'finalizada', 'cancelada')),
    creada_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finalizada_en TEXT
);

CREATE TABLE IF NOT EXISTS capturas_verificacion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sesion_id INTEGER NOT NULL REFERENCES sesiones_verificacion(id),
    hash_imagen TEXT NOT NULL,
    ruta_evidencia TEXT NOT NULL,
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
    diferencia INTEGER NOT NULL,
    estado TEXT NOT NULL CHECK (estado IN ('stock_coincide', 'requiere_revision', 'no_concluyente')),
    confianza_promedio REAL CHECK (confianza_promedio >= 0 AND confianza_promedio <= 1),
    guardada_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
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


def inicializar_base_datos(ruta: Path = RUTA_BASE_DATOS) -> None:
    """Crea tablas y registra el catálogo inicial solo si aún no existe."""
    with conectar(ruta) as conexion:
        conexion.executescript(ESQUEMA)
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
