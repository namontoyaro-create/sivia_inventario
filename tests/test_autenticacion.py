from sivia_inventario.autenticacion import (
    autenticar, cambiar_contrasena, crear_usuario,
    generar_codigo_recuperacion_local, restablecer_contrasena_con_codigo,
)
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


def test_recuperacion_local_consumible_una_sola_vez(tmp_path):
    ruta = tmp_path / "sivia.db"
    inicializar_base_datos(ruta)
    crear_usuario("admin.local", "Admin Local", "administrador", "ClaveSegura10", ruta)

    codigo, _vence_en = generar_codigo_recuperacion_local("admin.local", ruta, minutos=15)
    restablecer_contrasena_con_codigo("admin.local", codigo, "NuevaClave12", ruta)

    assert autenticar("admin.local", "ClaveSegura10", ruta) is None
    assert autenticar("admin.local", "NuevaClave12", ruta) is not None
    try:
        restablecer_contrasena_con_codigo("admin.local", codigo, "OtraClave13", ruta)
    except ValueError as error:
        assert "No se pudo validar" in str(error)
    else:
        raise AssertionError("Un código de recuperación no puede reutilizarse.")


def test_recuperacion_no_permite_cuenta_inactiva_ni_codigo_vencido(tmp_path):
    ruta = tmp_path / "sivia.db"
    inicializar_base_datos(ruta)
    crear_usuario("admin.local", "Admin Local", "administrador", "ClaveSegura10", ruta)

    codigo, _vence_en = generar_codigo_recuperacion_local("admin.local", ruta, minutos=1)
    from sivia_inventario.base_datos import conectar
    with conectar(ruta) as conexion:
        conexion.execute("UPDATE recuperaciones_contrasena SET vence_en='2000-01-01T00:00:00+00:00'")
    try:
        restablecer_contrasena_con_codigo("admin.local", codigo, "NuevaClave12", ruta)
    except ValueError as error:
        assert "No se pudo validar" in str(error)
    else:
        raise AssertionError("Un código vencido no debe restablecer una contraseña.")
