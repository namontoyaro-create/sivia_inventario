"""Aplicación web local de SIVIA."""

from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path
import shutil
import tempfile
from uuid import uuid4

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool
from starlette.middleware.sessions import SessionMiddleware

from sivia_inventario.base_datos import RAIZ, inicializar_base_datos
from sivia_inventario.categorias import CATALOGO
from sivia_inventario.preparacion_v2 import (
    GALERIA_PENDIENTES,
    PROPUESTAS_PENDIENTES,
    actualizar_rectangulos_propuesta,
    auditar_imagenes_nuevas,
    generar_galeria_pendiente,
    plan_mejora_dataset,
    propuestas_pendientes,
    rechazar_propuesta,
    registrar_procedencia_imagen,
    registrar_aprobaciones,
)
from sivia_inventario.repositorio_inventario import (MovimientoNoDisponible, actualizar_producto, buscar_productos_voz, confirmar_movimiento, crear_producto, crear_solicitud_movimiento, eliminar_producto, guardar_verificacion, listar_alertas, listar_categorias, listar_movimientos, listar_presentaciones, listar_productos, listar_productos_por_clase, listar_sesiones_verificacion, obtener_sesion_verificacion, obtener_producto, resumen_dashboard, stock_por_categoria, actividad_dashboard)
from sivia_inventario.asistente_voz_logica import interpretar_instruccion
from sivia_inventario.voz import ErrorAudio, FORMATOS_AUDIO, transcribir_audio, validar_audio
from sivia_inventario.autenticacion import (
    NOMBRES_ROL, ROLES, autenticar, cambiar_contrasena, crear_usuario,
    existen_usuarios, listar_usuarios, obtener_usuario, restablecer_contrasena_con_codigo,
)

REGISTRO = logging.getLogger(__name__)

PLANTILLAS = RAIZ / "src" / "sivia_inventario" / "plantillas"
ESTATICOS = RAIZ / "src" / "sivia_inventario" / "estaticos"
CARPETA_PRODUCTOS = RAIZ / "datos" / "productos"
CARPETA_EVIDENCIAS = RAIZ / "datos" / "evidencias"
EXTENSIONES_IMAGEN = {".jpg", ".jpeg", ".png", ".webp"}
MAXIMO_IMAGEN_BYTES = 5 * 1024 * 1024
CARPETA_PRODUCTOS.mkdir(parents=True, exist_ok=True)
CARPETA_EVIDENCIAS.mkdir(parents=True, exist_ok=True)


def contexto_voz(request: Request, **extra):
    return plantillas.TemplateResponse(request, "asistente_voz.html", {"pagina": "voz", **extra})


def nombre_para_cantidad(producto, cantidad: int) -> str:
    nombre = producto.producto.lower()
    return nombre if cantidad == 1 or nombre.endswith("s") else f"{nombre}s"


@asynccontextmanager
async def ciclo_vida(app: FastAPI):
    inicializar_base_datos()
    yield


app = FastAPI(title="SIVIA", lifespan=ciclo_vida)
app.mount("/static", StaticFiles(directory=ESTATICOS), name="static")
app.mount("/productos", StaticFiles(directory=CARPETA_PRODUCTOS), name="productos")
app.mount("/evidencias", StaticFiles(directory=CARPETA_EVIDENCIAS), name="evidencias")
app.mount("/revision-pendiente", StaticFiles(directory=GALERIA_PENDIENTES), name="revision-pendiente")
app.mount("/imagenes", StaticFiles(directory=RAIZ / "datos" / "imagenes"), name="imagenes")

def contexto_global(request: Request) -> dict:
    usuario = request.session.get("usuario")
    if not usuario and os.getenv("SIVIA_SIN_AUTENTICACION") == "1":
        usuario = {"usuario": "pruebas", "nombre": "Modo de pruebas", "rol": "administrador", "rol_nombre": "Administrador"}
    rol = usuario.get("rol") if usuario else None
    return {
        "usuario_actual": usuario,
        "puede_administrar": rol == "administrador",
        "puede_operar": rol in {"administrador", "operador"},
        "es_auditor": rol == "auditor",
    }


plantillas = Jinja2Templates(directory=PLANTILLAS, context_processors=[contexto_global])

RUTAS_PUBLICAS = {"/login", "/configurar-acceso", "/cerrar-sesion", "/recuperar-contrasena", "/recuperar-acceso"}
PREFIJOS_ESTATICOS = ("/static/", "/productos/", "/evidencias/", "/imagenes/", "/revision-pendiente/")


def respuesta_sin_permiso(request: Request, mensaje: str, estado: int = 403):
    if request.url.path.startswith("/asistente-voz/transcribir"):
        return JSONResponse({"ok": False, "error": mensaje}, status_code=estado)
    return plantillas.TemplateResponse(request, "acceso_denegado.html", {"pagina": "", "mensaje": mensaje}, status_code=estado)


@app.middleware("http")
async def proteger_aplicacion(request: Request, call_next):
    ruta = request.url.path
    if os.getenv("SIVIA_SIN_AUTENTICACION") == "1" or ruta in RUTAS_PUBLICAS or ruta.startswith(PREFIJOS_ESTATICOS):
        return await call_next(request)
    if not existen_usuarios():
        return RedirectResponse("/configurar-acceso", status_code=303)
    datos = request.session.get("usuario")
    usuario = obtener_usuario(str(datos.get("usuario", ""))) if isinstance(datos, dict) else None
    if not usuario or not usuario.activo:
        request.session.clear()
        if ruta.startswith("/asistente-voz/transcribir"):
            return JSONResponse({"ok": False, "error": "Tu sesión terminó. Inicia sesión nuevamente."}, status_code=401)
        return RedirectResponse("/login", status_code=303)
    request.session["usuario"] = usuario.contexto()
    rol = usuario.rol
    solo_administrador = ruta.startswith(("/usuarios", "/entrenamiento-ia", "/verificar/tecnico"))
    escritura_inventario = ruta.startswith("/inventario/") and request.method != "GET"
    confirmar_movimiento = ruta == "/asistente-voz/confirmar"
    if rol != "administrador" and (solo_administrador or escritura_inventario or confirmar_movimiento):
        return respuesta_sin_permiso(request, "Tu perfil no tiene permiso para realizar esta acción.")
    if rol == "auditor" and request.method != "GET":
        return respuesta_sin_permiso(request, "El perfil de auditoría solo permite consultar información.")
    return await call_next(request)


# Se agrega después del middleware de permisos para que la sesión esté creada
# antes de consultar request.session en cada solicitud.
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SIVIA_SESION_SECRETA", "sivia-local-cambia-esta-clave-antes-de-publicar"),
    same_site="lax",
    https_only=False,
)


def url_imagen(ruta: str | None) -> str | None:
    """Convierte rutas locales permitidas en URL servida por FastAPI."""
    if not ruta:
        return None
    archivo = Path(str(ruta).replace("\\", "/"))
    partes = archivo.parts
    if "productos" in partes:
        return f"/productos/{archivo.name}"
    if "imagenes" in partes:
        indice = partes.index("imagenes")
        relativo = Path(*partes[indice + 1:]).as_posix()
        return f"/imagenes/{relativo}"
    return None


def producto_contexto(producto):
    return {**producto.__dict__, "imagen_url": url_imagen(producto.imagen_ruta)}


async def guardar_imagen(archivo: UploadFile | None) -> str | None:
    if archivo is None or not archivo.filename:
        return None
    extension = Path(archivo.filename).suffix.lower()
    if extension not in EXTENSIONES_IMAGEN:
        raise ValueError("La fotografía debe ser JPG, JPEG, PNG o WEBP.")
    contenido = await archivo.read()
    if not contenido:
        raise ValueError("La fotografía seleccionada está vacía.")
    if len(contenido) > MAXIMO_IMAGEN_BYTES:
        raise ValueError("La fotografía no puede superar 5 MB.")
    nombre = f"{uuid4().hex}{extension}"
    (CARPETA_PRODUCTOS / nombre).write_bytes(contenido)
    return f"datos/productos/{nombre}"


async def guardar_evidencia(archivo: UploadFile | None) -> tuple[str, str]:
    if archivo is None or not archivo.filename:
        raise ValueError("Selecciona o captura una imagen para verificar.")
    extension = Path(archivo.filename).suffix.lower() or ".jpg"
    if extension not in EXTENSIONES_IMAGEN:
        raise ValueError("La evidencia debe ser JPG, JPEG, PNG o WEBP.")
    contenido = await archivo.read()
    if not contenido or len(contenido) > MAXIMO_IMAGEN_BYTES:
        raise ValueError("La evidencia está vacía o supera 5 MB.")
    nombre = f"{uuid4().hex}{extension}"
    (CARPETA_EVIDENCIAS / nombre).write_bytes(contenido)
    return f"datos/evidencias/{nombre}", f"/evidencias/{nombre}"


def detectores_contexto() -> list[dict]:
    from sivia_inventario.deteccion import detectores_disponibles
    return [
        {"id": identificador, **datos, "disponible": datos["ruta"].is_file()}
        for identificador, datos in detectores_disponibles().items()
    ]


def detector_activo_contexto() -> dict:
    from sivia_inventario.deteccion import detector_activo
    identificador, datos = detector_activo()
    return {"id": identificador, **datos}


def guardar_resultado_anotado(ruta_resultado: str | Path) -> tuple[str, str]:
    """Conserva una copia de las cajas YOLO junto a la evidencia original."""
    nombre = f"resultado_{uuid4().hex}.jpg"
    destino = CARPETA_EVIDENCIAS / nombre
    shutil.copy2(Path(ruta_resultado), destino)
    return f"datos/evidencias/{nombre}", f"/evidencias/{nombre}"


@app.get("/configurar-acceso", response_class=HTMLResponse)
def configurar_acceso(request: Request):
    if existen_usuarios():
        return RedirectResponse("/login", status_code=303)
    return plantillas.TemplateResponse(request, "configurar_acceso.html", {"pagina": "", "valores": {}})


@app.post("/configurar-acceso", response_class=HTMLResponse)
def guardar_configuracion_acceso(request: Request, usuario: str = Form(""), nombre: str = Form(""), contrasena: str = Form(""), confirmar_contrasena: str = Form("")):
    if existen_usuarios():
        return RedirectResponse("/login", status_code=303)
    if contrasena != confirmar_contrasena:
        return plantillas.TemplateResponse(request, "configurar_acceso.html", {"pagina": "", "error": "Las contraseñas no coinciden.", "valores": {"usuario": usuario, "nombre": nombre}}, status_code=400)
    try:
        primer_usuario = crear_usuario(usuario, nombre, "administrador", contrasena)
    except ValueError as error:
        return plantillas.TemplateResponse(request, "configurar_acceso.html", {"pagina": "", "error": str(error), "valores": {"usuario": usuario, "nombre": nombre}}, status_code=400)
    request.session["usuario"] = primer_usuario.contexto()
    return RedirectResponse("/", status_code=303)


@app.get("/login", response_class=HTMLResponse)
def login(request: Request):
    if not existen_usuarios():
        return RedirectResponse("/configurar-acceso", status_code=303)
    return plantillas.TemplateResponse(request, "login.html", {"pagina": ""})


@app.post("/login", response_class=HTMLResponse)
def iniciar_sesion(request: Request, usuario: str = Form(""), contrasena: str = Form("")):
    cuenta = autenticar(usuario, contrasena)
    if not cuenta:
        return plantillas.TemplateResponse(request, "login.html", {"pagina": "", "error": "Usuario o contraseña incorrectos.", "usuario_ingresado": usuario}, status_code=401)
    request.session.clear()
    request.session["usuario"] = cuenta.contexto()
    return RedirectResponse("/", status_code=303)


@app.get("/recuperar-acceso", response_class=HTMLResponse)
def recuperar_acceso(request: Request):
    if not existen_usuarios():
        return RedirectResponse("/configurar-acceso", status_code=303)
    return plantillas.TemplateResponse(request, "recuperar_acceso.html", {"pagina": ""})


@app.get("/recuperar-contrasena")
def redirigir_recuperacion_anterior():
    """Mantiene enlaces existentes, pero usa la pantalla de acceso unificada."""
    return RedirectResponse("/recuperar-acceso", status_code=303)


@app.post("/recuperar-acceso", response_class=HTMLResponse)
@app.post("/recuperar-contrasena", response_class=HTMLResponse)
def guardar_contrasena_recuperada(
    request: Request,
    codigo_recuperacion: str = Form(""),
    nueva_contrasena: str = Form(""),
    confirmar_contrasena: str = Form(""),
):
    if nueva_contrasena != confirmar_contrasena:
        return plantillas.TemplateResponse(
            request, "recuperar_acceso.html",
            {"pagina": "", "error": "Las contraseñas nuevas no coinciden."},
            status_code=400,
        )
    try:
        restablecer_contrasena_con_codigo(codigo_recuperacion, nueva_contrasena)
    except ValueError as error:
        REGISTRO.warning("Restablecimiento de contraseña rechazado para un usuario local: %s", error)
        return plantillas.TemplateResponse(
            request, "recuperar_acceso.html",
            {"pagina": "", "error": str(error)}, status_code=400,
        )
    request.session.clear()
    return plantillas.TemplateResponse(
        request, "recuperar_acceso.html",
        {"pagina": "", "mensaje": "Contraseña restablecida. Ya puedes iniciar sesión con tu nueva contraseña."},
    )


@app.post("/cerrar-sesion")
def cerrar_sesion(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/usuarios", response_class=HTMLResponse)
def usuarios(request: Request):
    return plantillas.TemplateResponse(request, "usuarios.html", {"pagina": "usuarios", "usuarios": [item.contexto() | {"activo": item.activo} for item in listar_usuarios()], "roles": ROLES, "nombres_rol": NOMBRES_ROL, "valores": {}})


@app.post("/usuarios", response_class=HTMLResponse)
def guardar_usuario(request: Request, usuario: str = Form(""), nombre: str = Form(""), rol: str = Form(""), contrasena: str = Form(""), confirmar_contrasena: str = Form("")):
    if contrasena != confirmar_contrasena:
        return plantillas.TemplateResponse(request, "usuarios.html", {"pagina": "usuarios", "usuarios": [item.contexto() | {"activo": item.activo} for item in listar_usuarios()], "roles": ROLES, "nombres_rol": NOMBRES_ROL, "error": "Las contraseñas no coinciden.", "valores": {"usuario": usuario, "nombre": nombre, "rol": rol}}, status_code=400)
    try:
        crear_usuario(usuario, nombre, rol, contrasena)
    except ValueError as error:
        return plantillas.TemplateResponse(request, "usuarios.html", {"pagina": "usuarios", "usuarios": [item.contexto() | {"activo": item.activo} for item in listar_usuarios()], "roles": ROLES, "nombres_rol": NOMBRES_ROL, "error": str(error), "valores": {"usuario": usuario, "nombre": nombre, "rol": rol}}, status_code=400)
    return RedirectResponse("/usuarios?mensaje=creado", status_code=303)


@app.get("/mi-cuenta", response_class=HTMLResponse)
def mi_cuenta(request: Request):
    return plantillas.TemplateResponse(request, "mi_cuenta.html", {"pagina": ""})


@app.post("/mi-cuenta", response_class=HTMLResponse)
def actualizar_mi_contrasena(request: Request, contrasena_actual: str = Form(""), nueva_contrasena: str = Form(""), confirmar_contrasena: str = Form("")):
    if nueva_contrasena != confirmar_contrasena:
        return plantillas.TemplateResponse(request, "mi_cuenta.html", {"pagina": "", "error": "Las contraseñas nuevas no coinciden."}, status_code=400)
    datos = request.session.get("usuario") or {}
    try:
        cambiar_contrasena(str(datos.get("usuario", "")), contrasena_actual, nueva_contrasena)
    except ValueError as error:
        return plantillas.TemplateResponse(request, "mi_cuenta.html", {"pagina": "", "error": str(error)}, status_code=400)
    return plantillas.TemplateResponse(request, "mi_cuenta.html", {"pagina": "", "mensaje": "La contraseña se actualizó correctamente."})


@app.get("/", response_class=HTMLResponse)
def inicio(request: Request):
    productos = listar_productos()
    resumen = resumen_dashboard()
    resumen["stock_bajo"] = sum(p.stock_registrado <= p.stock_minimo for p in productos)
    resumen["agotados"] = sum(p.stock_registrado == 0 for p in productos)
    categorias_stock = stock_por_categoria()
    actividad = actividad_dashboard()
    total_stock = resumen["stock_registrado"]
    colores = ("#2387f4", "#18b979", "#ffbd27", "#fb6969", "#9a71e8", "#41bbd0")
    acumulado = 0.0
    segmentos = []
    for indice, fila in enumerate(categorias_stock):
        porcentaje = (float(fila["cantidad"]) * 100 / total_stock) if total_stock else 0
        inicio = acumulado
        acumulado += porcentaje
        fila["porcentaje"] = porcentaje
        fila["color"] = colores[indice % len(colores)]
        segmentos.append(f"{fila['color']} {inicio:.2f}% {acumulado:.2f}%")
    donut = ", ".join(segmentos) if segmentos else "#e8eff8 0 100%"
    for grupo in (actividad["recientes"], actividad["mayores"], actividad["alertas_stock"]):
        for fila in grupo:
            fila["imagen_url"] = url_imagen(fila.get("imagen_ruta"))
    maximo_movimiento = max((max(f["entradas"], f["salidas"]) for f in actividad["por_fecha"]), default=0)
    return plantillas.TemplateResponse(request, "inicio.html", {
        "pagina": "inicio", "resumen": resumen, "categorias_stock": categorias_stock,
        "movimientos_fecha": actividad["por_fecha"], "movimientos_recientes": actividad["recientes"],
        "productos_mayor_movimiento": actividad["mayores"], "alertas_stock": actividad["alertas_stock"],
        "maximo_movimiento": maximo_movimiento, "donut": donut,
    })


@app.get("/inventario", response_class=HTMLResponse)
def inventario(request: Request, mensaje: str | None = None):
    productos = [producto_contexto(p) for p in listar_productos()]
    return plantillas.TemplateResponse(request, "inventario.html", {"pagina": "inventario", "productos": productos, "total_stock": sum(p["stock_registrado"] for p in productos), "categorias": len(listar_categorias()), "stock_bajo": sum(p["stock_registrado"] <= p["stock_minimo"] for p in productos), "categorias_lista": listar_categorias(), "presentaciones_lista": listar_presentaciones(), "mensaje": mensaje})


def formulario(request, titulo, accion, valores=None, error=None, bloqueado=False):
    valores = valores or {}
    valores.setdefault("imagen_url", url_imagen(valores.get("imagen_ruta")))
    return plantillas.TemplateResponse(request, "producto_formulario.html", {"pagina": "inventario", "titulo_formulario": titulo, "accion": accion, "valores": valores, "error": error, "bloqueado": bloqueado, "clases_ia": [p.clase_ia for p in CATALOGO]}, status_code=400 if error else 200)


@app.get("/inventario/nuevo")
def nuevo(request: Request):
    return formulario(request, "Nuevo producto", "/inventario/nuevo")


@app.post("/inventario/nuevo")
async def guardar_nuevo(request: Request, codigo: str = Form(), producto: str = Form(), categoria: str = Form(), categoria_ia: str = Form(), presentacion: str = Form(), stock_registrado: str = Form(), descripcion: str = Form(""), fotografia: UploadFile | None = File(None), sku: str = Form(""), codigo_barras: str = Form(""), proveedor: str = Form(""), precio_compra: str = Form("0"), precio_venta: str = Form("0"), stock_minimo: str = Form("0"), unidad_medida: str = Form("unidad"), estado_producto: str = Form("activo")):
    valores = {"codigo": codigo, "producto": producto, "categoria": categoria, "categoria_ia": categoria_ia,
               "presentacion": presentacion, "stock_registrado": stock_registrado, "descripcion": descripcion,
               "sku": sku, "codigo_barras": codigo_barras, "proveedor": proveedor,
               "precio_compra": precio_compra, "precio_venta": precio_venta, "stock_minimo": stock_minimo,
               "unidad_medida": unidad_medida, "estado_producto": estado_producto}
    try:
        imagen_ruta = await guardar_imagen(fotografia)
        crear_producto(codigo, producto, categoria, categoria_ia, presentacion, int(stock_registrado),
                       descripcion=descripcion, imagen_ruta=imagen_ruta, sku=sku, codigo_barras=codigo_barras,
                       proveedor=proveedor, precio_compra=float(precio_compra), precio_venta=float(precio_venta),
                       stock_minimo=int(stock_minimo), unidad_medida=unidad_medida, estado_producto=estado_producto)
    except (ValueError, TypeError) as error:
        return formulario(request, "Nuevo producto", "/inventario/nuevo", valores, str(error))
    return RedirectResponse("/inventario?mensaje=creado", 303)


@app.get("/inventario/{codigo}/editar")
def editar(request: Request, codigo: str):
    producto = obtener_producto(codigo)
    if not producto:
        return HTMLResponse("Producto no encontrado", 404)
    valores = producto_contexto(producto)
    valores.update(codigo=producto.id, categoria=producto.familia)
    return formulario(request, "Editar producto", f"/inventario/{producto.id}/editar", valores, bloqueado=True)


@app.post("/inventario/{codigo}/editar")
async def guardar_edicion(request: Request, codigo: str, producto: str = Form(), categoria: str = Form(), categoria_ia: str = Form(), presentacion: str = Form(), descripcion: str = Form(""), fotografia: UploadFile | None = File(None), sku: str = Form(""), codigo_barras: str = Form(""), proveedor: str = Form(""), precio_compra: str = Form("0"), precio_venta: str = Form("0"), stock_minimo: str = Form("0"), unidad_medida: str = Form("unidad"), estado_producto: str = Form("activo")):
    existente = obtener_producto(codigo)
    if not existente:
        return HTMLResponse("Producto no encontrado", 404)
    valores = {"codigo": codigo, "producto": producto, "categoria": categoria, "categoria_ia": categoria_ia,
               "presentacion": presentacion, "stock_registrado": existente.stock_registrado,
               "descripcion": descripcion, "imagen_ruta": existente.imagen_ruta,
               "imagen_url": url_imagen(existente.imagen_ruta), "sku": sku,
               "codigo_barras": codigo_barras, "proveedor": proveedor, "precio_compra": precio_compra,
               "precio_venta": precio_venta, "stock_minimo": stock_minimo,
               "unidad_medida": unidad_medida, "estado_producto": estado_producto}
    try:
        imagen_ruta = await guardar_imagen(fotografia)
        actualizar_producto(codigo, producto, categoria, categoria_ia, presentacion,
                            existente.stock_registrado, descripcion=descripcion, imagen_ruta=imagen_ruta,
                            sku=sku, codigo_barras=codigo_barras, proveedor=proveedor,
                            precio_compra=float(precio_compra), precio_venta=float(precio_venta),
                            stock_minimo=int(stock_minimo), unidad_medida=unidad_medida,
                            estado_producto=estado_producto)
    except (ValueError, TypeError) as error:
        return formulario(request, "Editar producto", f"/inventario/{codigo}/editar", valores, str(error), True)
    return RedirectResponse("/inventario?mensaje=actualizado", 303)


@app.get("/inventario/{codigo}/eliminar", response_class=HTMLResponse)
def confirmar_eliminacion(request: Request, codigo: str):
    producto = obtener_producto(codigo)
    if not producto:
        return HTMLResponse("Producto no encontrado", 404)
    return plantillas.TemplateResponse(request, "confirmar_eliminacion.html", {"pagina": "inventario", "producto": producto_contexto(producto)})


@app.post("/inventario/{codigo}/eliminar")
def borrar_producto(codigo: str):
    try:
        eliminar_producto(codigo)
    except ValueError:
        return HTMLResponse("Producto no encontrado", 404)
    return RedirectResponse("/inventario?mensaje=eliminado", 303)


@app.get("/verificar", response_class=HTMLResponse)
def verificar(request: Request):
    try:
        activo = detector_activo_contexto()
    except FileNotFoundError as error:
        return plantillas.TemplateResponse(request, "verificar.html", {"pagina": "verificar", "error": str(error)}, status_code=503)
    return plantillas.TemplateResponse(request, "verificar.html", {"pagina": "verificar", "modelo_activo": activo})


@app.get("/verificar/tecnico", response_class=HTMLResponse)
def verificar_tecnico(request: Request):
    return plantillas.TemplateResponse(request, "verificar_tecnico.html", {"pagina": "verificar", "detectores": detectores_contexto()})


@app.get("/asistente-voz", response_class=HTMLResponse)
def asistente_voz(request: Request):
    return contexto_voz(request)


@app.post("/asistente-voz/transcribir", response_class=JSONResponse)
async def transcribir_instruccion_voz(request: Request, audio: UploadFile | None = File(None)):
    if audio is None or not audio.filename:
        return JSONResponse({"ok": False, "error": "Selecciona o graba un archivo de audio."}, 400)
    extension = Path(audio.filename).suffix.lower()
    if extension not in FORMATOS_AUDIO:
        return JSONResponse({"ok": False, "error": "Formato no admitido. Usa WAV, MP3, M4A, WEBM u OGG."}, 400)
    contenido = await audio.read()
    ruta_temporal = None
    try:
        REGISTRO.info("Audio recibido para transcripción: bytes=%d extension=%s mime=%s", len(contenido), extension, audio.content_type or "no_indicado")
        with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as temporal:
            temporal.write(contenido)
            ruta_temporal = Path(temporal.name)
        validar_audio(ruta_temporal, len(contenido))
        texto = await run_in_threadpool(transcribir_audio, ruta_temporal)
        return JSONResponse({"ok": True, "transcripcion": texto})
    except ErrorAudio as error:
        REGISTRO.warning("Audio no transcrito: extension=%s motivo=%s", extension, error)
        return JSONResponse({"ok": False, "error": str(error)}, 400)
    except Exception:
        REGISTRO.exception("Error inesperado durante la transcripción de audio")
        return JSONResponse({"ok": False, "error": "No se pudo procesar el audio. Intenta nuevamente."}, 500)
    finally:
        if ruta_temporal:
            ruta_temporal.unlink(missing_ok=True)


@app.post("/asistente-voz/interpretar", response_class=HTMLResponse)
def interpretar_voz(request: Request, transcripcion: str = Form("")):
    interpretacion = interpretar_instruccion(transcripcion)
    if interpretacion.tipo == "aclaracion":
        return contexto_voz(request, transcripcion=transcripcion, respuesta=interpretacion.mensaje)
    coincidencias = buscar_productos_voz(interpretacion.termino_producto or "")
    if not coincidencias:
        return contexto_voz(request, transcripcion=transcripcion, respuesta="No se encontró ese producto.")
    if interpretacion.tipo == "consulta":
        if len(coincidencias) == 1:
            producto = coincidencias[0]
            respuesta = f"Actualmente tienes {producto.stock_registrado} {nombre_para_cantidad(producto, producto.stock_registrado)} registrados."
        else:
            respuesta = "Se encontraron varios productos coincidentes. Revisa las existencias por separado."
        return contexto_voz(request, transcripcion=transcripcion, respuesta=respuesta, consulta_productos=coincidencias)
    if len(coincidencias) > 1:
        return contexto_voz(request, transcripcion=transcripcion, respuesta="Selecciona el producto exacto antes de continuar.", seleccion_productos=coincidencias, operacion=interpretacion.operacion, cantidad=interpretacion.cantidad)
    return preparar_movimiento_voz(request, transcripcion, interpretacion.operacion or "", interpretacion.cantidad or 0, coincidencias[0].id)


@app.post("/asistente-voz/preparar", response_class=HTMLResponse)
def preparar_movimiento_seleccionado(request: Request, transcripcion: str = Form(""), operacion: str = Form(""), cantidad: int = Form(0), producto_id: str = Form("")):
    interpretacion = interpretar_instruccion(transcripcion)
    candidatos = buscar_productos_voz(interpretacion.termino_producto or "")
    if interpretacion.tipo != "movimiento" or operacion != interpretacion.operacion or cantidad != interpretacion.cantidad or producto_id not in {producto.id for producto in candidatos}:
        return contexto_voz(request, transcripcion=transcripcion, respuesta="La selección no coincide con la instrucción. Corrige el texto e inténtalo nuevamente.")
    return preparar_movimiento_voz(request, transcripcion, operacion, cantidad, producto_id)


def preparar_movimiento_voz(request: Request, transcripcion: str, operacion: str, cantidad: int, producto_id: str):
    try:
        solicitud = crear_solicitud_movimiento(transcripcion, operacion, cantidad, producto_id)
    except MovimientoNoDisponible as error:
        return contexto_voz(request, transcripcion=transcripcion, respuesta=str(error))
    except ValueError as error:
        return contexto_voz(request, transcripcion=transcripcion, respuesta=str(error))
    verbo = "entrada" if operacion == "entrada" else "salida"
    respuesta = f"Confirma la {verbo} de {cantidad} {nombre_para_cantidad(solicitud['producto'], cantidad)}."
    return contexto_voz(request, transcripcion=transcripcion, respuesta=respuesta, solicitud=solicitud)


@app.post("/asistente-voz/confirmar", response_class=HTMLResponse)
def confirmar_movimiento_voz(request: Request, token: str = Form("")):
    try:
        comprobante = confirmar_movimiento(token)
    except MovimientoNoDisponible as error:
        return contexto_voz(request, respuesta=str(error))
    if comprobante["duplicado"]:
        respuesta = f"El movimiento {comprobante['codigo_movimiento']} ya estaba registrado."
    else:
        nombre = comprobante["producto"].lower()
        if comprobante["cantidad"] != 1 and not nombre.endswith("s"):
            nombre += "s"
        respuesta = f"La {comprobante['operacion']} de {comprobante['cantidad']} {nombre} se registró correctamente."
    return contexto_voz(request, respuesta=respuesta, comprobante=comprobante)


@app.get("/movimientos", response_class=HTMLResponse)
def movimientos(request: Request):
    return plantillas.TemplateResponse(request, "movimientos.html", {"pagina": "movimientos", "movimientos": listar_movimientos()})


@app.get("/entrenamiento-ia", response_class=HTMLResponse)
def entrenamiento_ia(request: Request, mensaje: str | None = None):
    generar_galeria_pendiente()
    propuestas = propuestas_pendientes()
    for indice, propuesta in enumerate(propuestas):
        propuesta["imagen_url"] = "/imagenes/" + propuesta["archivo"].removeprefix("datos/imagenes/")
        propuesta["revision_url"] = f"/revision-pendiente/propuesta_{indice:03d}.jpg"
    auditoria = auditar_imagenes_nuevas()
    return plantillas.TemplateResponse(request, "entrenamiento_ia.html", {"pagina": "entrenamiento", "propuestas": propuestas, "nuevas": auditoria["nuevas_pendientes_revision"], "duplicados": auditoria["duplicados_exactos"], "plan_mejora": plan_mejora_dataset(), "mensaje": mensaje})


@app.post("/entrenamiento-ia/procedencia")
async def guardar_procedencia_entrenamiento(archivo: str = Form(), origen: str = Form(), grupo_escena: str = Form(), split_propuesto: str = Form()):
    try:
        registrar_procedencia_imagen(archivo, origen, grupo_escena, split_propuesto)
    except ValueError as error:
        return HTMLResponse(str(error), 400)
    return RedirectResponse("/entrenamiento-ia?mensaje=procedencia", 303)


@app.get("/entrenamiento-ia/corregir", response_class=HTMLResponse)
def corregir_anotacion(request: Request, archivo: str):
    propuesta = next((item for item in propuestas_pendientes() if item["archivo"] == archivo), None)
    if not propuesta:
        return HTMLResponse("Propuesta pendiente no encontrada", 404)
    propuesta["imagen_url"] = "/imagenes/" + archivo.removeprefix("datos/imagenes/")
    return plantillas.TemplateResponse(request, "corregir_anotacion.html", {"pagina": "entrenamiento", "propuesta": propuesta})


@app.post("/entrenamiento-ia/corregir")
async def guardar_correccion_anotacion(request: Request, archivo: str = Form(), total: int = Form()):
    formulario = await request.form()
    try:
        objetos = [{
            "clase": str(formulario.get(f"clase_{indice}", "")),
            "xyxy": [float(formulario[f"{campo}_{indice}"]) for campo in ("x1", "y1", "x2", "y2")],
        } for indice in range(total)]
        actualizar_rectangulos_propuesta(archivo, objetos)
    except (KeyError, TypeError, ValueError):
        return HTMLResponse("Las coordenadas deben estar entre 0 y 1 y formar rectángulos válidos.", 400)
    return RedirectResponse("/entrenamiento-ia?mensaje=corregida", 303)


@app.post("/entrenamiento-ia/decision")
async def decidir_anotacion(archivo: str = Form(), decision: str = Form(), motivo: str = Form("")):
    try:
        if decision == "aprobar":
            registrar_aprobaciones({archivo})
            mensaje = "aprobada"
        elif decision == "rechazar":
            rechazar_propuesta(archivo, motivo)
            mensaje = "rechazada"
        else:
            return HTMLResponse("Decisión no válida.", 400)
    except ValueError as error:
        return HTMLResponse(str(error), 400)
    return RedirectResponse(f"/entrenamiento-ia?mensaje={mensaje}", 303)


@app.post("/verificar/analizar", response_class=HTMLResponse)
async def analizar_verificacion(request: Request, evidencia: UploadFile | None = File(None), detector: str | None = Form(None), procedencia: str = Form("prueba_fisica"), comparar_v1_v2: str | None = Form(None), modo_tecnico: str | None = Form(None)):
    if procedencia not in {"internet", "prueba_fisica", "distribuidora_atencio"}:
        return HTMLResponse("La procedencia seleccionada no es válida.", 400)
    try:
        evidencia_ruta, evidencia_url = await guardar_evidencia(evidencia)
    except ValueError as error:
        return plantillas.TemplateResponse(request, "verificar.html", {"pagina": "verificar", "modelo_activo": detector_activo_contexto(), "error": str(error)}, status_code=400)
    detectores = {item["id"]: item for item in detectores_contexto()}
    if modo_tecnico != "si":
        try:
            detector = detector_activo_contexto()["id"]
        except FileNotFoundError as error:
            return HTMLResponse(str(error), 503)
        comparar_v1_v2 = None
    if detector not in detectores or not detectores[detector]["disponible"]:
        return HTMLResponse("El detector seleccionado no está disponible.", 400)
    try:
        from sivia_inventario.deteccion import procesar_imagen
        resultado = procesar_imagen(RAIZ / evidencia_ruta, modelo_path=detectores[detector]["ruta"], confianza=0.40)
        resultado_bajo = None
        if not resultado["detecciones"]:
            # Solo diagnóstico: estas predicciones no participan en conteo ni guardado.
            resultado_bajo = procesar_imagen(RAIZ / evidencia_ruta, modelo_path=detectores[detector]["ruta"], confianza=0.05)
        comparacion_modelos = []
        if comparar_v1_v2 == "si":
            for identificador in ("piloto_sivia", "piloto_sivia_v2"):
                datos_detector = detectores.get(identificador)
                if not datos_detector or not datos_detector["disponible"]:
                    continue
                resultado_comparado = resultado if identificador == detector else procesar_imagen(
                    RAIZ / evidencia_ruta, modelo_path=datos_detector["ruta"], confianza=0.40
                )
                bajas_comparadas = []
                if not resultado_comparado["detecciones"]:
                    diagnostico = resultado_bajo if identificador == detector else procesar_imagen(
                        RAIZ / evidencia_ruta, modelo_path=datos_detector["ruta"], confianza=0.05
                    )
                    bajas_comparadas = [{"clase": item["clase"], "confianza": item["confianza"]} for item in diagnostico["detecciones"]]
                comparacion_modelos.append({"id": identificador, "nombre": datos_detector["nombre"], "conteos": resultado_comparado["conteos"], "total": resultado_comparado["total"], "bajas": bajas_comparadas})
    except Exception as error:
        plantilla = "verificar_tecnico.html" if modo_tecnico == "si" else "verificar.html"
        contexto = {"pagina": "verificar", "error": f"No se pudo ejecutar el detector: {error}"}
        if modo_tecnico == "si":
            contexto["detectores"] = detectores_contexto()
        else:
            contexto["modelo_activo"] = detector_activo_contexto()
        return plantillas.TemplateResponse(request, plantilla, contexto, status_code=500)
    por_clase: dict[str, list[float]] = {}
    dudas: dict[str, int] = {}
    for deteccion in resultado["detecciones"]:
        por_clase.setdefault(deteccion["clase"], []).append(deteccion["confianza"])
        if deteccion.get("dudosa") or deteccion.get("conflicto"):
            dudas[deteccion["clase"]] = dudas.get(deteccion["clase"], 0) + 1
    confianzas = {clase: sum(valores) / len(valores) for clase, valores in por_clase.items()}
    visual = resultado_bajo or resultado
    resultado_ruta, resultado_url = guardar_resultado_anotado(visual["imagen_resultado"])
    catalogo = {p.clase_ia for p in listar_productos()}
    detectados = []
    for numero, deteccion in enumerate(resultado["detecciones"], start=1):
        clase = deteccion["clase"]
        if clase not in catalogo:
            continue
        compatibles = [producto_contexto(producto) for producto in listar_productos_por_clase(clase)]
        detectados.append({"id": numero, "clase_ia": clase, "confianza": deteccion["confianza"], "dudosa": bool(deteccion.get("dudosa") or deteccion.get("conflicto")), "compatibles": compatibles})
    desconocidas = {clase: cantidad for clase, cantidad in resultado["conteos"].items() if clase not in catalogo}
    bajas = [{"clase": item["clase"], "confianza": item["confianza"], "xyxy": item["xyxy"]} for item in (resultado_bajo or {"detecciones": []})["detecciones"]]
    resumen_yolo = []
    for clase, confianzas_clase in sorted(por_clase.items()):
        compatibles = [producto_contexto(producto) for producto in listar_productos_por_clase(clase)]
        resumen_yolo.append({
            "clase_ia": clase,
            "cantidad": len(confianzas_clase),
            "confianzas": confianzas_clase,
            "confianza_promedio": sum(confianzas_clase) / len(confianzas_clase),
            # Es una referencia del catálogo, no una selección automática del producto.
            "referencia_catalogo": compatibles[0] if compatibles else None,
            "dudosas": dudas.get(clase, 0),
        })
    estado_resultado = "detectado" if detectados else ("fuera_catalogo" if desconocidas else ("baja_confianza" if bajas else "sin_deteccion"))
    return plantillas.TemplateResponse(request, "revision_verificacion.html", {"pagina": "verificar", "detectados": detectados, "desconocidas": desconocidas, "detecciones_bajas": bajas, "estado_resultado": estado_resultado, "evidencia_ruta": evidencia_ruta, "evidencia_url": evidencia_url, "resultado_ruta": resultado_ruta, "resultado_url": resultado_url, "detector": detector, "detector_nombre": detectores[detector]["nombre"], "procedencia": procedencia, "comparacion_modelos": comparacion_modelos, "resumen_yolo": resumen_yolo, "total_yolo": sum(item["cantidad"] for item in resumen_yolo), "aviso": "Predicciones reales del detector seleccionado. Las detecciones de baja confianza no se cuentan."})


@app.post("/verificar/guardar")
async def guardar_revision(request: Request, evidencia_ruta: str = Form(), resultado_ruta: str = Form(""), detector: str = Form("manual"), procedencia: str = Form("prueba_fisica"), alcance: str = Form("captura parcial revisada por usuario"), alcance_confirmado: str | None = Form(None)):
    ruta = (RAIZ / evidencia_ruta).resolve()
    if CARPETA_EVIDENCIAS.resolve() not in ruta.parents or not ruta.is_file():
        return HTMLResponse("La evidencia de la verificación no es válida.", 400)
    formulario = await request.form()
    conteos: dict[str, int] = {}
    conteos_yolo: dict[str, int] = {}
    suma_confianzas: dict[str, float] = {}
    cantidad_confianzas: dict[str, int] = {}
    if procedencia not in {"internet", "prueba_fisica", "distribuidora_atencio"}:
        return HTMLResponse("La procedencia de la evidencia no es válida.", 400)
    try:
        for identificador in formulario.getlist("deteccion_id"):
            producto_id = str(formulario.get(f"producto_{identificador}", "")).strip()
            if not producto_id:
                continue
            clase_ia = str(formulario.get(f"clase_{identificador}", "")).strip()
            compatibles = {producto.id for producto in listar_productos_por_clase(clase_ia)}
            if producto_id not in compatibles:
                return HTMLResponse("El producto seleccionado no corresponde a la clase detectada por YOLO.", 400)
            confianza = float(str(formulario.get(f"confianza_{identificador}", "0")))
            if not 0 <= confianza <= 1:
                raise ValueError
            conteos[producto_id] = conteos.get(producto_id, 0) + 1
            conteos_yolo[producto_id] = conteos_yolo.get(producto_id, 0) + 1
            suma_confianzas[producto_id] = suma_confianzas.get(producto_id, 0.0) + confianza
            cantidad_confianzas[producto_id] = cantidad_confianzas.get(producto_id, 0) + 1
    except ValueError:
        return HTMLResponse("Cada conteo debe ser un entero igual o mayor que cero.", 400)
    try:
        confianzas = {clave: suma_confianzas[clave] / cantidad_confianzas[clave] for clave in conteos}
        guardar_verificacion("Verificacion experimental desde imagen", evidencia_ruta, conteos, confianzas,
                            conteos_yolo=conteos_yolo, detector=detector, alcance=alcance,
                            alcance_confirmado=alcance_confirmado == "si", evidencia_resultado=resultado_ruta or None,
                            procedencia=procedencia)
    except ValueError:
        return plantillas.TemplateResponse(request, "error_verificacion.html", {
            "pagina": "verificar",
            "error": "No hay productos detectados y confirmados para guardar.",
        }, status_code=400)
    return RedirectResponse("/historial?mensaje=guardado", 303)

    try:
        guardar_verificacion("Verificación desde imagen", evidencia_ruta, conteos)
    except ValueError:
        return HTMLResponse("No hay productos detectados y confirmados para guardar.", 400)
    return RedirectResponse("/historial?mensaje=guardado", 303)


@app.get("/historial", response_class=HTMLResponse)
def historial(request: Request):
    return plantillas.TemplateResponse(request, "historial.html", {"pagina": "historial", "verificaciones": listar_sesiones_verificacion()})


@app.get("/historial/{codigo}", response_class=HTMLResponse)
def detalle_historial(request: Request, codigo: str):
    sesion = obtener_sesion_verificacion(codigo)
    if not sesion:
        return HTMLResponse("Verificación no encontrada", 404)
    return plantillas.TemplateResponse(request, "detalle_verificacion.html", {"pagina": "historial", "sesion": sesion})


@app.get("/alertas", response_class=HTMLResponse)
def alertas(request: Request):
    return plantillas.TemplateResponse(request, "alertas.html", {"pagina": "alertas", "alertas": listar_alertas()})


@app.get("/prueba-libre", response_class=HTMLResponse)
def prueba_libre(request: Request):
    return plantillas.TemplateResponse(request, "prueba_libre.html", {"pagina": "verificar"})
