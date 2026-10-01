"""Relación conservadora entre conteos y stock: no supone ceros ni resuelve ambigüedades."""

from sivia_inventario.categorias import CATALOGO
from sivia_inventario.inventario import comparar_con_referencia
from sivia_inventario.resumen import relacionar_con_catalogo
from sivia_inventario.stock import StockReferencia


def comparar_conteos(conteos: dict[str, int], referencia: StockReferencia, catalogo=CATALOGO) -> list[dict]:
    filas = []
    for fila in relacionar_con_catalogo(conteos, catalogo):
        registro = {"clase": fila.clase_ia, "detectado": fila.cantidad, "estado": fila.estado}
        if fila.estado == "coincidencia_unica":
            producto = fila.candidatos[0]
            registro.update(producto_id=producto.id, producto=producto.producto, presentacion=producto.presentacion)
            if producto.id not in referencia.stock_por_producto:
                registro["estado"] = "stock_desconocido"
            else:
                comparacion = comparar_con_referencia(producto, fila.cantidad, referencia)
                registro.update(registrado=comparacion.stock_registrado, diferencia=comparacion.diferencia, estado=comparacion.estado)
        else:
            registro["candidatos"] = [p.id for p in fila.candidatos]
        filas.append(registro)
    for producto in catalogo:
        if producto.clase_ia not in conteos:
            filas.append({"producto_id": producto.id, "clase": producto.clase_ia, "detectado": None, "estado": "sin_deteccion_no_concluyente"})
    return filas
