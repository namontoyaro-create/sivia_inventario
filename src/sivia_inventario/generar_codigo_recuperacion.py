"""Genera, s\u00f3lo en la consola local, un c\u00f3digo temporal de recuperaci\u00f3n."""

import argparse

from sivia_inventario.autenticacion import generar_codigo_recuperacion_local, obtener_usuario
from sivia_inventario.base_datos import inicializar_base_datos


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Genera un c\u00f3digo temporal de un solo uso para recuperar una cuenta SIVIA."
    )
    parser.add_argument("--usuario", required=True, help="Usuario exacto de la cuenta activa.")
    parser.add_argument("--minutos", type=int, default=15, help="Vigencia: 1 a 60 minutos (predeterminado: 15).")
    argumentos = parser.parse_args()

    inicializar_base_datos()
    cuenta = obtener_usuario(argumentos.usuario)
    if not cuenta or not cuenta.activo:
        print("No existe una cuenta activa con ese usuario.")
        return 1

    confirmacion = input(
        f"Cuenta local verificada: {cuenta.usuario} ({cuenta.rol}). "
        f"Escriba RESTABLECER {cuenta.usuario} para generar el c\u00f3digo: "
    ).strip()
    if confirmacion != f"RESTABLECER {cuenta.usuario}":
        print("Operaci\u00f3n cancelada. No se gener\u00f3 ning\u00fan c\u00f3digo.")
        return 1

    try:
        codigo, vence_en = generar_codigo_recuperacion_local(
            cuenta.usuario, minutos=argumentos.minutos
        )
    except ValueError as error:
        print(f"No se pudo generar el c\u00f3digo: {error}")
        return 1
    print("\nC\u00f3digo temporal (mu\u00e9stralo s\u00f3lo a la persona autorizada):")
    print(codigo)
    print(f"Vence: {vence_en.isoformat()}")
    print("El c\u00f3digo se invalida al usarlo o al generar otro para esta cuenta.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
