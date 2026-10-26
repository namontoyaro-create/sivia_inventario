from sivia_inventario.asistente_voz_logica import interpretar_instruccion


def test_interpreta_consulta_entrada_y_salida():
    assert interpretar_instruccion("Cuántos candados tenemos en inventario").tipo == "consulta"
    entrada = interpretar_instruccion("Registrar entrada de cinco candados")
    assert (entrada.tipo, entrada.operacion, entrada.cantidad) == ("movimiento", "entrada", 5)
    salida = interpretar_instruccion("Registrar salida de 2 cerraduras")
    assert (salida.operacion, salida.cantidad) == ("salida", 2)


def test_rechaza_cantidad_cero_y_operacion_ambigua():
    assert interpretar_instruccion("Registrar entrada de cero candados").tipo == "aclaracion"
    assert interpretar_instruccion("Registrar entrada y salida de dos candados").tipo == "aclaracion"
