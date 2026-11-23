"""Integración HTTP real de acceso local, sin usar la base de datos del proyecto."""

from http.cookiejar import CookieJar
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener


def _puerto_libre() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as servidor:
        servidor.bind(("127.0.0.1", 0))
        return servidor.getsockname()[1]


def _esperar_login(opener, url: str) -> str:
    ultimo_error = None
    for _ in range(50):
        try:
            with opener.open(f"{url}/login", timeout=0.5) as respuesta:
                return respuesta.read().decode("utf-8")
        except OSError as error:
            ultimo_error = error
            time.sleep(0.1)
    raise AssertionError("Uvicorn no inició el servidor local de prueba.") from ultimo_error


def _token_csrf(html: str) -> str:
    encontrado = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert encontrado, "La página no incluyó un token CSRF."
    return encontrado.group(1)


def _post(opener, url: str, ruta: str, datos: dict[str, str]) -> str:
    solicitud = Request(
        f"{url}{ruta}",
        data=urlencode(datos).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with opener.open(solicitud, timeout=5) as respuesta:
        return respuesta.read().decode("utf-8")


def test_login_http_real_con_cookie_y_csrf_estables(tmp_path):
    """Reproduce navegador+Uvicorn para detectar cookies Secure en HTTP o CSRF inestable."""
    puerto = _puerto_libre()
    url = f"http://127.0.0.1:{puerto}"
    entorno = os.environ.copy()
    entorno.update({
        "SIVIA_DB_PATH": str(tmp_path / "sivia-prueba.db"),
        "SIVIA_ENTORNO": "local",
        # Incluso si alguien dejó este valor de producción, HTTP local debe
        # funcionar: web.py solo activa Secure cuando el entorno es producción.
        "SIVIA_HTTPS_ONLY": "1",
        "SIVIA_SESION_SECRETA": "secreto-prueba-local-estable-de-mas-de-treinta-y-dos-caracteres",
        "SIVIA_BOOTSTRAP_TOKEN": "bootstrap-prueba-local",
    })
    entorno.pop("DATABASE_URL", None)
    entorno.pop("SIVIA_SIN_AUTENTICACION", None)
    proceso = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "sivia_inventario.web:app", "--host", "127.0.0.1", "--port", str(puerto)],
        cwd=Path(__file__).resolve().parents[1],
        env=entorno,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        cookies = CookieJar()
        navegador = build_opener(HTTPCookieProcessor(cookies))
        _esperar_login(navegador, url)
        with navegador.open(f"{url}/configurar-acceso", timeout=5) as respuesta:
            configuracion = respuesta.read().decode("utf-8")
        _post(navegador, url, "/configurar-acceso", {
            "usuario": "admin.prueba", "nombre": "Administradora de prueba",
            "contrasena": "ClaveSegura10", "confirmar_contrasena": "ClaveSegura10",
            "codigo_configuracion": "bootstrap-prueba-local", "csrf_token": _token_csrf(configuracion),
        })

        pagina_login = _esperar_login(navegador, url)
        # Simula el caso reportado: el formulario se obtiene en un navegador
        # pero la cookie anónima no acompaña el POST. El token firmado sigue
        # protegiendo CSRF y permite iniciar la sesión real.
        navegador_sin_cookie = build_opener(HTTPCookieProcessor(CookieJar()))
        inicio = _post(navegador_sin_cookie, url, "/login", {
            "usuario": "admin.prueba", "contrasena": "ClaveSegura10",
            "csrf_token": _token_csrf(pagina_login),
        })

        assert "Dashboard" in inicio
        assert any(cookie.name == "sivia_sesion" and not cookie.secure for cookie in cookies)
    finally:
        proceso.terminate()
        try:
            proceso.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proceso.kill()
            proceso.wait(timeout=5)
