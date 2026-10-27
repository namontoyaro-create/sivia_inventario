"""Usuarios, roles y credenciales locales para la aplicación SIVIA."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import re
import secrets
from pathlib import Path

from sivia_inventario.base_datos import RUTA_BASE_DATOS, conectar

ROLES = ("administrador", "operador", "auditor")
NOMBRES_ROL = {
    "administrador": "Administrador",
    "operador": "Operador de inventario",
    "auditor": "Auditor",
}
_USUARIO_VALIDO = re.compile(r"^[a-zA-Z0-9._-]{3,40}$")
MINUTOS_CODIGO_RECUPERACION = 15


@dataclass(frozen=True)
class Usuario:
    id: int
    usuario: str
    nombre: str
    rol: str
    activo: bool

    def contexto(self) -> dict:
        return {"id": self.id, "usuario": self.usuario, "nombre": self.nombre,
                "rol": self.rol, "rol_nombre": NOMBRES_ROL[self.rol]}


def _validar(usuario: str, nombre: str, rol: str, contrasena: str) -> tuple[str, str]:
    usuario = usuario.strip().lower()
    nombre = nombre.strip()
    if not _USUARIO_VALIDO.fullmatch(usuario):
        raise ValueError("El usuario debe tener entre 3 y 40 caracteres: letras, números, punto, guion o guion bajo.")
    if len(nombre) < 2 or len(nombre) > 100:
        raise ValueError("El nombre debe tener entre 2 y 100 caracteres.")
    if rol not in ROLES:
        raise ValueError("El rol seleccionado no es válido.")
    if len(contrasena) < 10:
        raise ValueError("La contraseña debe tener al menos 10 caracteres.")
    return usuario, nombre


def _derivar(contrasena: str, sal: bytes) -> str:
    return hashlib.scrypt(contrasena.encode("utf-8"), salt=sal, n=2**14, r=8, p=1).hex()


def _huella_codigo(codigo: str) -> str:
    """No guarda c\u00f3digos de recuperaci\u00f3n en texto plano."""
    return hashlib.sha256(codigo.strip().encode("utf-8")).hexdigest()


def _fila_usuario(fila) -> Usuario | None:
    if not fila:
        return None
    return Usuario(id=fila["id"], usuario=fila["usuario"], nombre=fila["nombre"], rol=fila["rol"], activo=bool(fila["activo"]))


def existen_usuarios(ruta: Path = RUTA_BASE_DATOS) -> bool:
    with conectar(ruta) as conexion:
        return bool(conexion.execute("SELECT 1 FROM usuarios LIMIT 1").fetchone())


def crear_usuario(usuario: str, nombre: str, rol: str, contrasena: str,
                  ruta: Path = RUTA_BASE_DATOS) -> Usuario:
    usuario, nombre = _validar(usuario, nombre, rol, contrasena)
    sal = secrets.token_bytes(16)
    try:
        with conectar(ruta) as conexion:
            cursor = conexion.execute(
                "INSERT INTO usuarios(usuario,nombre,rol,password_hash,password_salt) VALUES (?,?,?,?,?)",
                (usuario, nombre, rol, _derivar(contrasena, sal), sal.hex()),
            )
            fila = conexion.execute("SELECT * FROM usuarios WHERE id=?", (cursor.lastrowid,)).fetchone()
    except Exception as error:
        if "UNIQUE constraint failed" in str(error):
            raise ValueError("Ese nombre de usuario ya existe.") from error
        raise
    resultado = _fila_usuario(fila)
    assert resultado
    return resultado


def listar_usuarios(ruta: Path = RUTA_BASE_DATOS) -> list[Usuario]:
    with conectar(ruta) as conexion:
        filas = conexion.execute("SELECT id,usuario,nombre,rol,activo FROM usuarios ORDER BY nombre COLLATE NOCASE").fetchall()
    return [_fila_usuario(fila) for fila in filas if fila]


def identificar_administrador_local(ruta: Path = RUTA_BASE_DATOS) -> Usuario:
    """Identifica la cuenta administradora solamente en la consola local.

    No se expone mediante una ruta web ni por correo. El procedimiento exige
    acceso al entorno de desarrollo y solo continúa si hay una sola cuenta
    administradora activa, evitando elegir accidentalmente otra cuenta.
    """
    administradores = [item for item in listar_usuarios(ruta)
                       if item.rol == "administrador" and item.activo]
    if len(administradores) != 1:
        raise ValueError(
            "No hay una única cuenta administradora activa; revisa el acceso local con una persona autorizada."
        )
    return administradores[0]


def obtener_usuario(usuario: str, ruta: Path = RUTA_BASE_DATOS) -> Usuario | None:
    with conectar(ruta) as conexion:
        fila = conexion.execute("SELECT id,usuario,nombre,rol,activo FROM usuarios WHERE usuario=?", (usuario.strip().lower(),)).fetchone()
    return _fila_usuario(fila)


def autenticar(usuario: str, contrasena: str, ruta: Path = RUTA_BASE_DATOS) -> Usuario | None:
    with conectar(ruta) as conexion:
        fila = conexion.execute("SELECT * FROM usuarios WHERE usuario=? AND activo=1", (usuario.strip().lower(),)).fetchone()
    if not fila:
        return None
    esperado = str(fila["password_hash"])
    recibido = _derivar(contrasena, bytes.fromhex(str(fila["password_salt"])))
    return _fila_usuario(fila) if hmac.compare_digest(esperado, recibido) else None


def cambiar_contrasena(usuario: str, contrasena_actual: str, nueva_contrasena: str,
                       ruta: Path = RUTA_BASE_DATOS) -> None:
    actual = autenticar(usuario, contrasena_actual, ruta)
    if not actual:
        raise ValueError("La contraseña actual no es correcta.")
    _validar(actual.usuario, actual.nombre, actual.rol, nueva_contrasena)
    sal = secrets.token_bytes(16)
    with conectar(ruta) as conexion:
        conexion.execute("UPDATE usuarios SET password_hash=?,password_salt=?,actualizado_en=CURRENT_TIMESTAMP WHERE id=?",
                         (_derivar(nueva_contrasena, sal), sal.hex(), actual.id))


def generar_codigo_recuperacion_local(usuario: str, ruta: Path = RUTA_BASE_DATOS,
                                      minutos: int = MINUTOS_CODIGO_RECUPERACION) -> tuple[str, datetime]:
    """Genera un c\u00f3digo para una cuenta activa desde la consola local.

    El valor devuelto se muestra una sola vez al operador local; SQLite recibe
    solamente su huella SHA-256. Se invalida cualquier c\u00f3digo anterior de
    la misma cuenta para evitar dos restablecimientos simult\u00e1neos.
    """
    if minutos < 1 or minutos > 60:
        raise ValueError("La vigencia del c\u00f3digo debe estar entre 1 y 60 minutos.")
    cuenta = obtener_usuario(usuario, ruta)
    if not cuenta or not cuenta.activo:
        raise ValueError("No existe una cuenta activa con ese usuario.")
    codigo = f"SIVIA-{secrets.token_urlsafe(18)}"
    vence_en = datetime.now(timezone.utc) + timedelta(minutes=minutos)
    ahora = datetime.now(timezone.utc).isoformat()
    with conectar(ruta) as conexion:
        conexion.execute(
            "UPDATE recuperaciones_contrasena SET usada_en=? WHERE usuario_id=? AND usada_en IS NULL",
            (ahora, cuenta.id),
        )
        conexion.execute(
            "INSERT INTO recuperaciones_contrasena(usuario_id,codigo_hash,vence_en) VALUES (?,?,?)",
            (cuenta.id, _huella_codigo(codigo), vence_en.isoformat()),
        )
    return codigo, vence_en


def restablecer_contrasena_con_codigo(codigo: str, nueva_contrasena: str, usuario: str = "",
                                      ruta: Path = RUTA_BASE_DATOS) -> None:
    """Restablece una clave si el c\u00f3digo local vigente no fue utilizado.

    La actualizaci\u00f3n de hash y el consumo del c\u00f3digo ocurren en una misma
    transacci\u00f3n para impedir reusos y cambios parciales.
    """
    usuario_normalizado = usuario.strip().lower()
    mensaje_error = "No se pudo validar el usuario o el c\u00f3digo de recuperaci\u00f3n."
    if (usuario_normalizado and not _USUARIO_VALIDO.fullmatch(usuario_normalizado)) or not codigo.strip():
        raise ValueError(mensaje_error)
    filtro_usuario = "AND u.usuario=?" if usuario_normalizado else ""
    with conectar(ruta) as conexion:
        fila = conexion.execute(
            f"""
            SELECT r.id AS recuperacion_id, r.vence_en, r.usada_en,
                   u.id, u.usuario, u.nombre, u.rol, u.activo
            FROM recuperaciones_contrasena r
            JOIN usuarios u ON u.id=r.usuario_id
            WHERE r.codigo_hash=? {filtro_usuario}
            ORDER BY r.id DESC LIMIT 1
            """,
            (_huella_codigo(codigo), usuario_normalizado) if usuario_normalizado else (_huella_codigo(codigo),),
        ).fetchone()
        if not fila or not bool(fila["activo"]) or fila["usada_en"]:
            raise ValueError(mensaje_error)
        try:
            vencido = datetime.fromisoformat(str(fila["vence_en"])) <= datetime.now(timezone.utc)
        except ValueError:
            vencido = True
        if vencido:
            raise ValueError(mensaje_error)
        _validar(str(fila["usuario"]), str(fila["nombre"]), str(fila["rol"]), nueva_contrasena)
        sal = secrets.token_bytes(16)
        consumido = conexion.execute(
            "UPDATE recuperaciones_contrasena SET usada_en=? WHERE id=? AND usada_en IS NULL",
            (datetime.now(timezone.utc).isoformat(), fila["recuperacion_id"]),
        )
        if consumido.rowcount != 1:
            raise ValueError(mensaje_error)
        conexion.execute(
            "UPDATE usuarios SET password_hash=?,password_salt=?,actualizado_en=CURRENT_TIMESTAMP WHERE id=?",
            (_derivar(nueva_contrasena, sal), sal.hex(), fila["id"]),
        )
