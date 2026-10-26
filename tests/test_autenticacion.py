from sivia_inventario.autenticacion import autenticar, cambiar_contrasena, crear_usuario
from sivia_inventario.base_datos import inicializar_base_datos


def test_usuarios_usan_contrasenas_derivadas_y_roles(tmp_path):
    ruta = tmp_path / "sivia.db"
    inicializar_base_datos(ruta)
    creado = crear_usuario("operador.ana", "Ana Operadora", "operador", "ClaveSegura10", ruta)

    assert creado.rol == "operador"
    assert autenticar("operador.ana", "ClaveSegura10", ruta).nombre == "Ana Operadora"
    assert autenticar("operador.ana", "incorrecta", ruta) is None


def test_cambiar_contrasena_exige_clave_actual(tmp_path):
    ruta = tmp_path / "sivia.db"
    inicializar_base_datos(ruta)
    crear_usuario("auditora", "Ana Auditora", "auditor", "ClaveSegura10", ruta)

    cambiar_contrasena("auditora", "ClaveSegura10", "NuevaClave11", ruta)

    assert autenticar("auditora", "ClaveSegura10", ruta) is None
    assert autenticar("auditora", "NuevaClave11", ruta).rol == "auditor"
