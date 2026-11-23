import sqlite3
from datetime import datetime, timedelta

RUTA = "datos/sivia_alertas_demo.db"  # NUNCA la base real
con = sqlite3.connect(RUTA)
cur = con.cursor()

fila = cur.execute("SELECT id, sesion_id FROM capturas_verificacion LIMIT 1").fetchone()
if not fila:
    raise SystemExit("No hay capturas en la copia para reutilizar.")
captura_id, sesion_id = fila
ahora = datetime.now()

# 1) Tres verificaciones de P003: YOLO dijo 2, la persona confirmó 1
for i in range(3):
    cur.execute(
        """INSERT INTO verificaciones
           (sesion_id, captura_id, producto_id, stock_registrado, cantidad_detectada,
            diferencia, estado, confianza_promedio, guardada_en, cantidad_yolo)
           VALUES (?, ?, 'P003', 20, 1, -19, 'requiere_revision', 0.6, ?, 2)""",
        (sesion_id, captura_id, (ahora - timedelta(days=3 - i)).isoformat(timespec="seconds")),
    )

# 2) Cinco salidas de 1 unidad y una de 10 (solo registros, sin alterar el stock)
stock = 20
for n, cantidad in enumerate([1, 1, 1, 1, 1, 10], start=1):
    token = f"demo-token-{n}"
    fecha = (ahora - timedelta(days=10 - n)).isoformat(timespec="seconds")
    cur.execute(
        """INSERT INTO solicitudes_voz
           (token, transcripcion, operacion, cantidad, producto_id, estado, creada_en, confirmada_en)
           VALUES (?, 'demo', 'salida', ?, 'P003', 'confirmada', ?, ?)""",
        (token, cantidad, fecha, fecha),
    )
    cur.execute(
        """INSERT INTO movimientos_inventario
           (codigo_movimiento, solicitud_token, producto_id, operacion, cantidad,
            stock_anterior, stock_resultante, transcripcion, confirmado_en)
           VALUES (?, ?, 'P003', 'salida', ?, ?, ?, 'demo', ?)""",
        (f"DEMO-{n:04d}", token, cantidad, stock, max(stock - cantidad, 0), fecha),
    )
    stock = max(stock - cantidad, 0)

con.commit()
con.close()
print("Datos de demostración insertados en", RUTA)
