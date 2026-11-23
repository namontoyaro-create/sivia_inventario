"""Ejecuta la migración PostgreSQL solo con DATABASE_URL configurada."""
from sivia_inventario.migraciones_postgres import aplicar_migraciones_postgres
if __name__ == "__main__":
    print(f"Migración PostgreSQL aplicada hasta versión {aplicar_migraciones_postgres()}.")
