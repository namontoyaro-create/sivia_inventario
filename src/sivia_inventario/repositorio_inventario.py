"""Consultas de inventario usadas por la aplicación web."""

from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
from pathlib import Path
import re
from uuid import uuid4

from sivia_inventario.base_datos import RAIZ, RUTA_BASE_DATOS, conectar


@dataclass(frozen=True)
class ProductoInventario:
    id: str
    producto: str
    familia: str
    presentacion: str
    clase_ia: str
    stock_registrado: int
    origen_stock: str
    marca: str | None = None
    modelo: str | None = None
    tamano: str | None = None
    codigo_producto: str | None = None
    descripcion: str = ""
    imagen_ruta: str | None = None
    sku: str | None = None
    codigo_barras: str | None = None
    proveedor: str | None = None
    precio_compra: float = 0.0
    precio_venta: float = 0.0
    stock_minimo: int = 0
    unidad_medida: str = "unidad"
    estado_producto: str = "activo"


ESTADOS_PRODUCTO = {"activo", "inactivo", "descontinuado"}

FOTOGRAFIAS_CATALOGO_VERIFICADAS = {
    "bolsa_clavos": "datos/imagenes/bolsa_clavos/bolsa_clavos_01.jpg",
    "caja_clavos": "datos/imagenes/caja_clavos/caja_clavos_01.jpg",
    "candado": "datos/imagenes/candado/candado_01.jpg",
    "cerradura_sobreponer": "datos/imagenes/cerradura_sobreponer/cerradura_sobreponer_01.jpg",
    "tuberia_pvc": "datos/imagenes/tuberia_pvc/tuberia_pvc_01.jpg",
    "bolsa_cemento": "datos/imagenes/bolsa_cemento/bolsa_cemento_01.jpg",
    "disco_corte": "datos/imagenes/disco_corte/disco_corte_01.jpg",
    "caja_discos_corte": "datos/imagenes/caja_discos_corte/caja_discos_corte_11.jpg",
}


def _texto_opcional(valor, campo: str, maximo: int) -> str | None:
    if valor is None:
        return None
    if not isinstance(valor, str):
        raise ValueError(f"{campo} no es válido.")
    valor = valor.strip()
    if len(valor) > maximo:
        raise ValueError(f"{campo} no puede superar {maximo} caracteres.")
    return valor or None


def _validar_producto(codigo, producto, categoria, categoria_ia, presentacion, stock,
                      *, sku=None, codigo_barras=None, proveedor=None,
                      precio_compra=0, precio_venta=0, stock_minimo=0,
                      unidad_medida="unidad", estado_producto="activo"):
    valores = (codigo, producto, categoria, categoria_ia, presentacion)
    if any(not isinstance(valor, str) or not valor.strip() for valor in valores):
        raise ValueError("Código, producto, categoría, categoría IA y presentación son obligatorios.")
    if not codigo.strip().replace("-", "").replace("_", "").isalnum():
        raise ValueError("El código solo admite letras, números, guiones y guiones bajos.")
    if type(stock) is not int or stock < 0:
        raise ValueError("El stock registrado debe ser un entero no negativo.")
    sku = _texto_opcional(sku, "El SKU", 40)
    if sku and not re.fullmatch(r"[A-Za-z0-9_-]{3,40}", sku):
        raise ValueError("El SKU debe tener entre 3 y 40 letras, números, guiones o guiones bajos.")
    codigo_barras = _texto_opcional(codigo_barras, "El código de barras", 14)
    if codigo_barras and not re.fullmatch(r"\d{8,14}", codigo_barras):
        raise ValueError("El código de barras debe contener entre 8 y 14 dígitos.")
    proveedor = _texto_opcional(proveedor, "El proveedor", 100)
    if isinstance(precio_compra, bool) or not isinstance(precio_compra, (int, float)) or precio_compra < 0:
        raise ValueError("El precio de compra debe ser un número no negativo.")
    if isinstance(precio_venta, bool) or not isinstance(precio_venta, (int, float)) or precio_venta < 0:
        raise ValueError("El precio de venta debe ser un número no negativo.")
    if type(stock_minimo) is not int or stock_minimo < 0:
        raise ValueError("El stock mínimo debe ser un entero no negativo.")
    if not isinstance(unidad_medida, str) or not unidad_medida.strip() or len(unidad_medida.strip()) > 30:
        raise ValueError("La unidad de medida es obligatoria y no puede superar 30 caracteres.")
    if estado_producto not in ESTADOS_PRODUCTO:
        raise ValueError("El estado del producto no es válido.")
    return {
        "sku": sku, "codigo_barras": codigo_barras, "proveedor": proveedor,
        "precio_compra": float(precio_compra), "precio_venta": float(precio_venta),
        "stock_minimo": stock_minimo, "unidad_medida": unidad_medida.strip(),
        "estado_producto": estado_producto,
    }


def obtener_producto(codigo: str, ruta: Path = RUTA_BASE_DATOS) -> ProductoInventario | None:
    with conectar(ruta) as conexion:
        fila = conexion.execute(
            "SELECT id, producto, familia, presentacion, clase_ia, stock_registrado, "
            "origen_stock, marca, modelo, tamano, codigo_producto, descripcion, imagen_ruta, sku, codigo_barras, proveedor, precio_compra, precio_venta, stock_minimo, unidad_medida, estado_producto FROM productos WHERE id=? AND activo=1",
            (codigo,),
        ).fetchone()
    return ProductoInventario(**dict(fila)) if fila else None


def crear_producto(codigo, producto, categoria, categoria_ia, presentacion, stock,
                   ruta: Path = RUTA_BASE_DATOS, descripcion: str = "",
                   imagen_ruta: str | None = None, *, sku: str | None = None,
                   codigo_barras: str | None = None, proveedor: str | None = None,
                   precio_compra: float = 0, precio_venta: float = 0,
                   stock_minimo: int = 0, unidad_medida: str = "unidad",
                   estado_producto: str = "activo") -> None:
    comerciales = _validar_producto(
        codigo, producto, categoria, categoria_ia, presentacion, stock, sku=sku,
        codigo_barras=codigo_barras, proveedor=proveedor, precio_compra=precio_compra,
        precio_venta=precio_venta, stock_minimo=stock_minimo,
        unidad_medida=unidad_medida, estado_producto=estado_producto,
    )
    with conectar(ruta) as conexion:
        try:
            conexion.execute(
                "INSERT INTO productos (id,producto,familia,presentacion,unidad_conteo,"
                "clase_ia,stock_registrado,origen_stock,descripcion,imagen_ruta,sku,"
                "codigo_barras,proveedor,precio_compra,precio_venta,stock_minimo,"
                "unidad_medida,estado_producto) "
                "VALUES (?,?,?,?,?,?,?,'real',?,?,?,?,?,?,?,?,?,?)",
                (codigo.strip(), producto.strip(), categoria.strip(), presentacion.strip(),
                 f"Cada {presentacion.strip().lower()} visible", categoria_ia.strip(), stock,
                 descripcion.strip(), imagen_ruta, comerciales["sku"],
                 comerciales["codigo_barras"], comerciales["proveedor"],
                 comerciales["precio_compra"], comerciales["precio_venta"],
                 comerciales["stock_minimo"], comerciales["unidad_medida"],
                 comerciales["estado_producto"]),
            )
        except Exception as error:
            if "UNIQUE constraint failed" in str(error):
                raise ValueError("Ya existe un producto con ese c?digo, SKU o c?digo de barras.") from error
            raise


def actualizar_producto(codigo, producto, categoria, categoria_ia, presentacion, stock,
                        ruta: Path = RUTA_BASE_DATOS, descripcion: str = "",
                        imagen_ruta: str | None = None, *, sku: str | None = None,
                        codigo_barras: str | None = None, proveedor: str | None = None,
                        precio_compra: float = 0, precio_venta: float = 0,
                        stock_minimo: int = 0, unidad_medida: str = "unidad",
                        estado_producto: str = "activo") -> None:
    comerciales = _validar_producto(
        codigo, producto, categoria, categoria_ia, presentacion, stock, sku=sku,
        codigo_barras=codigo_barras, proveedor=proveedor, precio_compra=precio_compra,
        precio_venta=precio_venta, stock_minimo=stock_minimo,
        unidad_medida=unidad_medida, estado_producto=estado_producto,
    )
    with conectar(ruta) as conexion:
        actual = conexion.execute(
            "SELECT stock_registrado FROM productos WHERE id=? AND activo=1", (codigo,)
        ).fetchone()
        if not actual:
            raise ValueError("El producto no existe o est? inactivo.")
        if actual["stock_registrado"] != stock:
            raise ValueError("El stock no se edita aqu?. Registra un movimiento para modificar existencias.")
        try:
            actualizado = conexion.execute(
                "UPDATE productos SET producto=?,familia=?,clase_ia=?,presentacion=?,"
                "unidad_conteo=?,descripcion=?,imagen_ruta=COALESCE(?, imagen_ruta),"
                "sku=?,codigo_barras=?,proveedor=?,precio_compra=?,precio_venta=?,"
                "stock_minimo=?,unidad_medida=?,estado_producto=?,actualizado_en=CURRENT_TIMESTAMP "
                "WHERE id=? AND activo=1",
                (producto.strip(), categoria.strip(), categoria_ia.strip(), presentacion.strip(),
                 f"Cada {presentacion.strip().lower()} visible", descripcion.strip(), imagen_ruta,
                 comerciales["sku"], comerciales["codigo_barras"], comerciales["proveedor"],
                 comerciales["precio_compra"], comerciales["precio_venta"],
                 comerciales["stock_minimo"], comerciales["unidad_medida"],
                 comerciales["estado_producto"], codigo),
            )
        except Exception as error:
            if "UNIQUE constraint failed" in str(error):
                raise ValueError("Ya existe un producto con ese SKU o c?digo de barras.") from error
            raise
        if not actualizado.rowcount:
            raise ValueError("El producto no existe o est? inactivo.")

def listar_productos(ruta: Path = RUTA_BASE_DATOS) -> list[ProductoInventario]:
    with conectar(ruta) as conexion:
        filas = conexion.execute(
            """
            SELECT id, producto, familia, presentacion, clase_ia,
                   stock_registrado, origen_stock, marca, modelo, tamano, codigo_producto, descripcion, imagen_ruta,
                   sku, codigo_barras, proveedor, precio_compra, precio_venta, stock_minimo, unidad_medida, estado_producto
            FROM productos WHERE activo = 1
            ORDER BY id
            """
        ).fetchall()
    return [ProductoInventario(**dict(fila)) for fila in filas]


def listar_productos_por_clase(clase_ia: str, ruta: Path = RUTA_BASE_DATOS) -> list[ProductoInventario]:
    """Devuelve todas las presentaciones registradas para una clase de YOLO."""
    return [producto for producto in listar_productos(ruta) if producto.clase_ia == clase_ia]


def listar_categorias(ruta: Path = RUTA_BASE_DATOS) -> list[str]:
    with conectar(ruta) as conexion:
        filas = conexion.execute(
            "SELECT DISTINCT familia FROM productos WHERE activo=1 ORDER BY familia"
        ).fetchall()
    return [fila["familia"] for fila in filas]


def listar_presentaciones(ruta: Path = RUTA_BASE_DATOS) -> list[str]:
    with conectar(ruta) as conexion:
        filas = conexion.execute(
            "SELECT DISTINCT presentacion FROM productos WHERE activo=1 ORDER BY presentacion"
        ).fetchall()
    return [fila["presentacion"] for fila in filas]


def vincular_fotografias_catalogo(ruta: Path = RUTA_BASE_DATOS) -> dict[str, list[str]]:
    """Vincula solo las fotos locales revisadas que corresponden a cada clase IA.

    No reemplaza una foto cargada por el usuario ni descarga archivos externos.
    """
    vinculados: list[str] = []
    sin_foto: list[str] = []
    conservados: list[str] = []
    with conectar(ruta) as conexion:
        productos = conexion.execute(
            "SELECT id, clase_ia, imagen_ruta FROM productos WHERE activo=1 ORDER BY id"
        ).fetchall()
        for producto in productos:
            if producto["imagen_ruta"]:
                conservados.append(producto["id"])
                continue
            imagen = FOTOGRAFIAS_CATALOGO_VERIFICADAS.get(producto["clase_ia"])
            if not imagen or not (RAIZ / imagen).is_file():
                sin_foto.append(producto["id"])
                continue
            conexion.execute("UPDATE productos SET imagen_ruta=? WHERE id=?", (imagen, producto["id"]))
            vinculados.append(producto["id"])
    return {"vinculados": vinculados, "sin_foto": sin_foto, "conservados": conservados}


def eliminar_producto(codigo: str, ruta: Path = RUTA_BASE_DATOS) -> None:
    """Oculta el producto del inventario sin borrar su historial en SQLite."""
    with conectar(ruta) as conexion:
        resultado = conexion.execute(
            "UPDATE productos SET activo=0, actualizado_en=CURRENT_TIMESTAMP "
            "WHERE id=? AND activo=1",
            (codigo,),
        )
        if not resultado.rowcount:
            raise ValueError("El producto no existe o ya fue eliminado.")


def guardar_verificacion(nombre: str, evidencia_ruta: str, conteos: dict[str, int],
                         confianzas: dict[str, float] | None = None,
                         ruta: Path = RUTA_BASE_DATOS, *, conteos_yolo: dict[str, int] | None = None,
                         detector: str = "manual", alcance: str = "captura parcial revisada por usuario",
                         alcance_confirmado: bool = False, evidencia_resultado: str | None = None,
                         procedencia: str = "prueba_fisica") -> str:
    """Guarda conteo YOLO y conteo humano confirmado sin alterar existencias."""
    productos = listar_productos(ruta)
    por_id = {producto.id: producto for producto in productos}
    por_clase: dict[str, ProductoInventario] = {}
    for producto in productos:
        por_clase.setdefault(producto.clase_ia, producto)
    if procedencia not in {"internet", "prueba_fisica", "distribuidora_atencio", "no_confirmada"}:
        raise ValueError("La procedencia de la evidencia no es válida.")
    if procedencia == "internet":
        alcance_confirmado = False
    def resolver(clave: str) -> ProductoInventario | None:
        return por_id.get(clave) or por_clase.get(clave)
    confirmados = {
        clave: cantidad for clave, cantidad in conteos.items()
        if resolver(clave) and isinstance(cantidad, int) and cantidad > 0
    }
    originales = {
        clave: cantidad for clave, cantidad in (conteos_yolo or {}).items()
        if resolver(clave) and isinstance(cantidad, int) and cantidad >= 0
    }
    clases_guardadas = set(confirmados) | {clase for clase, cantidad in originales.items() if cantidad > 0}
    if not clases_guardadas:
        raise ValueError("No hay productos detectados y confirmados para guardar.")
    if not isinstance(alcance, str) or not alcance.strip():
        raise ValueError("Describe el alcance revisado de la captura.")
    with conectar(ruta) as conexion:
        sesion = conexion.execute(
            "INSERT INTO sesiones_verificacion(nombre, alcance, estado, detector, alcance_confirmado, finalizada_en) "
            "VALUES (?, ?, 'finalizada', ?, ?, CURRENT_TIMESTAMP)",
            (nombre, alcance.strip(), detector, int(alcance_confirmado)),
        )
        sesion_id = sesion.lastrowid
        codigo = f"VER-{sesion_id:04d}"
        conexion.execute(
            "UPDATE sesiones_verificacion SET codigo_verificacion=? WHERE id=?",
            (codigo, sesion_id),
        )
        archivo = (Path(ruta).resolve().parent.parent / evidencia_ruta).resolve()
        digest = hashlib.sha256(archivo.read_bytes()).hexdigest()
        captura = conexion.execute(
            "INSERT INTO capturas_verificacion(sesion_id, hash_imagen, ruta_evidencia, ruta_resultado, procedencia) VALUES (?,?,?,?,?)",
            (sesion_id, digest, evidencia_ruta, evidencia_resultado, procedencia),
        )
        captura_id = captura.lastrowid
        for clave in sorted(clases_guardadas):
            detectado = confirmados.get(clave, 0)
            producto = resolver(clave)
            assert producto is not None
            diferencia = detectado - producto.stock_registrado if alcance_confirmado else 0
            estado = ("stock_coincide" if diferencia == 0 else "requiere_revision") if alcance_confirmado else "no_concluyente"
            conexion.execute(
                "INSERT INTO verificaciones(sesion_id,captura_id,producto_id,stock_registrado,"
                "cantidad_detectada,cantidad_yolo,diferencia,estado,confianza_promedio) VALUES (?,?,?,?,?,?,?,?,?)",
                (sesion_id, captura_id, producto.id, producto.stock_registrado, detectado,
                 originales.get(clave), diferencia, estado, (confianzas or {}).get(clave)),
            )
    return codigo


def listar_verificaciones(ruta: Path = RUTA_BASE_DATOS) -> list[dict]:
    with conectar(ruta) as conexion:
        filas = conexion.execute(
            "SELECT v.id, v.guardada_en, p.id AS codigo, p.producto, p.clase_ia, "
            "v.stock_registrado, v.cantidad_detectada, v.diferencia, v.estado, "
            "c.ruta_evidencia FROM verificaciones v JOIN productos p ON p.id=v.producto_id "
            "LEFT JOIN capturas_verificacion c ON c.id=v.captura_id "
            "WHERE v.cantidad_detectada > 0 ORDER BY v.id DESC"
        ).fetchall()
    return [dict(fila) for fila in filas]


def listar_sesiones_verificacion(ruta: Path = RUTA_BASE_DATOS) -> list[dict]:
    """Una fila por captura guardada, no una fila por cada producto."""
    with conectar(ruta) as conexion:
        filas = conexion.execute(
            "SELECT s.id, COALESCE(s.codigo_verificacion, printf('VER-%04d', s.id)) AS codigo, "
            "s.finalizada_en, s.detector, s.alcance, s.alcance_confirmado, c.ruta_evidencia, c.ruta_resultado, c.procedencia, COUNT(v.id) AS productos_detectados, "
            "COALESCE(SUM(v.cantidad_yolo), 0) AS objetos_yolo, COALESCE(SUM(v.cantidad_detectada), 0) AS objetos_confirmados, "
            "SUM(CASE WHEN v.estado='requiere_revision' THEN 1 ELSE 0 END) AS diferencias "
            "FROM sesiones_verificacion s LEFT JOIN capturas_verificacion c ON c.sesion_id=s.id "
            "LEFT JOIN verificaciones v ON v.sesion_id=s.id AND v.cantidad_detectada > 0 "
            "GROUP BY s.id ORDER BY s.id DESC"
        ).fetchall()
    return [dict(fila) for fila in filas]


def obtener_sesion_verificacion(codigo: str, ruta: Path = RUTA_BASE_DATOS) -> dict | None:
    with conectar(ruta) as conexion:
        sesion = conexion.execute(
            "SELECT s.id, COALESCE(s.codigo_verificacion, printf('VER-%04d', s.id)) AS codigo, "
            "s.finalizada_en, s.detector, s.alcance, s.alcance_confirmado, c.ruta_evidencia, c.ruta_resultado, c.procedencia FROM sesiones_verificacion s "
            "LEFT JOIN capturas_verificacion c ON c.sesion_id=s.id "
            "WHERE COALESCE(s.codigo_verificacion, printf('VER-%04d', s.id))=?",
            (codigo,),
        ).fetchone()
        if not sesion:
            return None
        productos = conexion.execute(
            "SELECT p.id AS codigo, p.producto, p.clase_ia, v.stock_registrado, "
            "v.cantidad_detectada, v.cantidad_yolo, v.diferencia, v.estado, v.confianza_promedio "
            "FROM verificaciones v JOIN productos p ON p.id=v.producto_id "
            "WHERE v.sesion_id=? ORDER BY p.id",
            (sesion["id"],),
        ).fetchall()
    return {**dict(sesion), "productos": [dict(fila) for fila in productos]}


def listar_alertas(ruta: Path = RUTA_BASE_DATOS) -> list[dict]:
    return [fila for fila in listar_verificaciones(ruta) if fila["estado"] == "requiere_revision"]


def resumen_dashboard(ruta: Path = RUTA_BASE_DATOS) -> dict[str, int]:
    with conectar(ruta) as conexion:
        productos = conexion.execute("SELECT COUNT(*) FROM productos WHERE activo = 1").fetchone()[0]
        stock = conexion.execute("SELECT COALESCE(SUM(stock_registrado), 0) FROM productos WHERE activo = 1").fetchone()[0]
        verificaciones = conexion.execute("SELECT COUNT(*) FROM verificaciones").fetchone()[0]
        diferencias = conexion.execute(
            "SELECT COUNT(*) FROM verificaciones WHERE estado = 'requiere_revision'"
        ).fetchone()[0]
    return {
        "productos_registrados": productos,
        "stock_registrado": stock,
        "verificaciones": verificaciones,
        "diferencias": diferencias,
    }


def stock_por_categoria(ruta: Path = RUTA_BASE_DATOS) -> list[dict[str, int | str]]:
    """Suma el stock real registrado por familia, sin inventar categorías."""
    with conectar(ruta) as conexion:
        filas = conexion.execute(
            "SELECT familia, SUM(stock_registrado) AS cantidad FROM productos "
            "WHERE activo=1 GROUP BY familia ORDER BY cantidad DESC"
        ).fetchall()
    return [{"familia": fila["familia"], "cantidad": fila["cantidad"]} for fila in filas]


def actividad_dashboard(ruta: Path = RUTA_BASE_DATOS) -> dict[str, list[dict]]:
    """Devuelve actividad real para el panel, sin sintetizar movimientos."""
    hoy = datetime.now().date()
    fechas = [(hoy - timedelta(days=desplazamiento)).isoformat() for desplazamiento in range(6, -1, -1)]
    with conectar(ruta) as conexion:
        por_fecha = conexion.execute(
            "SELECT substr(confirmado_en, 1, 10) AS fecha, operacion, COALESCE(SUM(cantidad), 0) AS cantidad "
            "FROM movimientos_inventario WHERE substr(confirmado_en, 1, 10) >= ? "
            "GROUP BY substr(confirmado_en, 1, 10), operacion",
            (fechas[0],),
        ).fetchall()
        recientes = conexion.execute(
            "SELECT m.codigo_movimiento, m.confirmado_en, p.id AS codigo_producto, p.producto, "
            "p.imagen_ruta, m.operacion, m.cantidad, m.stock_anterior, m.stock_resultante "
            "FROM movimientos_inventario m JOIN productos p ON p.id=m.producto_id "
            "ORDER BY m.id DESC LIMIT 5"
        ).fetchall()
        mayores = conexion.execute(
            "SELECT p.id AS codigo_producto, p.producto, p.imagen_ruta, "
            "COALESCE(SUM(CASE WHEN m.operacion='entrada' THEN m.cantidad ELSE 0 END), 0) AS entradas, "
            "COALESCE(SUM(CASE WHEN m.operacion='salida' THEN m.cantidad ELSE 0 END), 0) AS salidas, "
            "COALESCE(SUM(m.cantidad), 0) AS total "
            "FROM movimientos_inventario m JOIN productos p ON p.id=m.producto_id "
            "GROUP BY p.id ORDER BY total DESC, p.producto LIMIT 5"
        ).fetchall()
        alertas = conexion.execute(
            "SELECT id AS codigo_producto, producto, imagen_ruta, stock_registrado, stock_minimo "
            "FROM productos WHERE activo=1 AND stock_registrado <= stock_minimo "
            "ORDER BY stock_registrado ASC, producto LIMIT 5"
        ).fetchall()
    mapa = {fecha: {"fecha": fecha, "entradas": 0, "salidas": 0} for fecha in fechas}
    for fila in por_fecha:
        if fila["fecha"] in mapa:
            mapa[fila["fecha"]][f"{fila['operacion']}s"] = fila["cantidad"]
    return {
        "por_fecha": list(mapa.values()), "recientes": [dict(fila) for fila in recientes],
        "mayores": [dict(fila) for fila in mayores], "alertas_stock": [dict(fila) for fila in alertas],
    }


class MovimientoNoDisponible(ValueError):
    """Una solicitud no puede ser confirmada sin cambiar el stock."""


def buscar_productos_voz(termino: str, ruta: Path = RUTA_BASE_DATOS) -> list[ProductoInventario]:
    """Busca por código, nombre, clase IA o datos comerciales sin usar YOLO."""
    from sivia_inventario.asistente_voz_logica import coincide_producto
    return [producto for producto in listar_productos(ruta) if coincide_producto(termino, producto)]


def crear_solicitud_movimiento(transcripcion: str, operacion: str, cantidad: int,
                               producto_id: str, ruta: Path = RUTA_BASE_DATOS) -> dict:
    if operacion not in {"entrada", "salida"} or type(cantidad) is not int or cantidad <= 0:
        raise ValueError("La operación y la cantidad solicitadas no son válidas.")
    producto = obtener_producto(producto_id, ruta)
    if not producto:
        raise ValueError("El producto seleccionado no existe o está inactivo.")
    if operacion == "salida" and cantidad > producto.stock_registrado:
        raise MovimientoNoDisponible("No hay suficientes unidades para registrar esa salida.")
    token = uuid4().hex
    with conectar(ruta) as conexion:
        conexion.execute(
            "INSERT INTO solicitudes_voz(token, transcripcion, operacion, cantidad, producto_id) VALUES (?,?,?,?,?)",
            (token, transcripcion.strip(), operacion, cantidad, producto.id),
        )
    resultado = producto.stock_registrado + cantidad if operacion == "entrada" else producto.stock_registrado - cantidad
    return {"token": token, "producto": producto, "operacion": operacion, "cantidad": cantidad,
            "stock_anterior": producto.stock_registrado, "stock_resultante": resultado}


def obtener_solicitud_movimiento(token: str, ruta: Path = RUTA_BASE_DATOS) -> dict | None:
    with conectar(ruta) as conexion:
        fila = conexion.execute(
            "SELECT s.token, s.transcripcion, s.operacion, s.cantidad, s.estado, p.id, p.producto, p.presentacion, p.stock_registrado "
            "FROM solicitudes_voz s JOIN productos p ON p.id=s.producto_id WHERE s.token=?",
            (token,),
        ).fetchone()
    if not fila:
        return None
    datos = dict(fila)
    datos["stock_resultante"] = datos["stock_registrado"] + datos["cantidad"] if datos["operacion"] == "entrada" else datos["stock_registrado"] - datos["cantidad"]
    return datos


def confirmar_movimiento(token: str, ruta: Path = RUTA_BASE_DATOS) -> dict:
    """Confirma una solicitud una sola vez mediante una transacción SQLite."""
    with conectar(ruta) as conexion:
        conexion.execute("BEGIN IMMEDIATE")
        solicitud = conexion.execute(
            "SELECT token, transcripcion, operacion, cantidad, producto_id, estado FROM solicitudes_voz WHERE token=?",
            (token,),
        ).fetchone()
        if not solicitud:
            raise MovimientoNoDisponible("La solicitud de movimiento no existe.")
        existente = conexion.execute(
            "SELECT m.codigo_movimiento, p.id, p.producto, m.operacion, m.cantidad, m.stock_resultante, m.confirmado_en "
            "FROM movimientos_inventario m JOIN productos p ON p.id=m.producto_id WHERE m.solicitud_token=?",
            (token,),
        ).fetchone()
        if existente:
            return {**dict(existente), "duplicado": True}
        if solicitud["estado"] != "pendiente":
            raise MovimientoNoDisponible("La solicitud ya no está disponible para confirmación.")
        producto = conexion.execute(
            "SELECT id, producto, stock_registrado FROM productos WHERE id=? AND activo=1",
            (solicitud["producto_id"],),
        ).fetchone()
        if not producto:
            raise MovimientoNoDisponible("El producto ya no está disponible.")
        anterior = producto["stock_registrado"]
        cantidad = solicitud["cantidad"]
        if solicitud["operacion"] == "salida" and cantidad > anterior:
            raise MovimientoNoDisponible("No hay suficientes unidades para registrar esa salida.")
        resultante = anterior + cantidad if solicitud["operacion"] == "entrada" else anterior - cantidad
        actualizado = conexion.execute(
            "UPDATE productos SET stock_registrado=?, actualizado_en=CURRENT_TIMESTAMP WHERE id=? AND stock_registrado=? AND activo=1",
            (resultante, producto["id"], anterior),
        )
        if not actualizado.rowcount:
            raise MovimientoNoDisponible("El stock cambió mientras se confirmaba. Revisa la solicitud nuevamente.")
        movimiento = conexion.execute(
            "INSERT INTO movimientos_inventario(solicitud_token, producto_id, operacion, cantidad, stock_anterior, stock_resultante, transcripcion) VALUES (?,?,?,?,?,?,?)",
            (token, producto["id"], solicitud["operacion"], cantidad, anterior, resultante, solicitud["transcripcion"]),
        )
        codigo = f"MOV-{movimiento.lastrowid:04d}"
        conexion.execute("UPDATE movimientos_inventario SET codigo_movimiento=? WHERE id=?", (codigo, movimiento.lastrowid))
        conexion.execute("UPDATE solicitudes_voz SET estado='confirmada', confirmada_en=CURRENT_TIMESTAMP WHERE token=?", (token,))
    return {"codigo_movimiento": codigo, "id": producto["id"], "producto": producto["producto"],
            "operacion": solicitud["operacion"], "cantidad": cantidad, "stock_resultante": resultante,
            "duplicado": False}


def listar_movimientos(ruta: Path = RUTA_BASE_DATOS) -> list[dict]:
    with conectar(ruta) as conexion:
        filas = conexion.execute(
            "SELECT m.codigo_movimiento, m.confirmado_en, p.id AS codigo_producto, p.producto, m.operacion, m.cantidad, m.stock_anterior, m.stock_resultante "
            "FROM movimientos_inventario m JOIN productos p ON p.id=m.producto_id ORDER BY m.id DESC"
        ).fetchall()
    return [dict(fila) for fila in filas]
