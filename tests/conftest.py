"""Configuración aislada para pruebas de interfaz sin requerir una sesión real."""

import os


os.environ.setdefault("SIVIA_SIN_AUTENTICACION", "1")
