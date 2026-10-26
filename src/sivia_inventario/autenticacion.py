"""Usuarios, roles y credenciales locales para la aplicación SIVIA."""

from dataclasses import dataclass
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
