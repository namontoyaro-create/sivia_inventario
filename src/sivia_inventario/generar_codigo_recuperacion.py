"""Herramienta local autorizada para recuperar una cuenta de SIVIA."""

import argparse

from sivia_inventario.autenticacion import (
    generar_codigo_recuperacion_local,
    identificar_administrador_local,
    obtener_usuario,
)
from sivia_inventario.base_datos import inicializar_base_datos


def _confirmar(cuenta, accion: str) -> bool:
    confirmacion = input(
        f"Cuenta local verificada: {cuenta.usuario} ({cuenta.rol}). "
        f"Escriba {accion} {cuenta.usuario} para continuar: "
    ).strip()
    return confirmacion == f"{accion} {cuenta.usuario}"


def _cuenta_local(argumentos):
    if argumentos.administrador or argumentos.identificar_administrador:
        return identificar_administrador_local()
    cuenta = obtener_usuario(argumentos.usuario)
    if not cuenta or not cuenta.activo:
        raise ValueError("No existe una cuenta activa con ese usuario.")
    return cuenta


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Genera un código temporal de un solo uso para recuperar una cuenta SIVIA."
    )
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--usuario", help="Usuario exacto de una cuenta activa.")
    grupo.add_argument("--administrador", action="store_true", help="Identifica la única cuenta administradora activa y genera su código.")
    grupo.add_argument("--identificar-administrador", action="store_true", help="Muestra solo localmente la única cuenta administradora activa.")
    parser.add_argument("--minutos", type=int, default=15, help="Vigencia: 1 a 60 minutos (predeterminado: 15).")
    argumentos = parser.parse_args()

    inicializar_base_datos()
    try:
        cuenta = _cuenta_local(argumentos)
    except ValueError as error:
        print(f"No se pudo identificar la cuenta: {error}")
        return 1

    if argumentos.identificar_administrador:
        if not _confirmar(cuenta, "IDENTIFICAR"):
            print("Operación cancelada. No se mostró ni generó ningún código.")
            return 1
        print(f"Usuario administrador local: {cuenta.usuario}")
        return 0

    if not _confirmar(cuenta, "RESTABLECER"):
        print("Operación cancelada. No se generó ningún código.")
        return 1
    try:
        codigo, vence_en = generar_codigo_recuperacion_local(cuenta.usuario, minutos=argumentos.minutos)
    except ValueError as error:
        print(f"No se pudo generar el código: {error}")
        return 1
    print("\nCódigo temporal (muéstralo solo a la persona autorizada):")
    print(codigo)
    print(f"Vence: {vence_en.isoformat()}")
    print("El código se invalida al usarlo o al generar otro para esta cuenta.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
