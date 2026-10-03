"""Aplicación web local de SIVIA."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from sivia_inventario.base_datos import RAIZ, inicializar_base_datos
from sivia_inventario.repositorio_inventario import listar_productos, resumen_dashboard

PLANTILLAS = RAIZ / "src" / "sivia_inventario" / "plantillas"
ESTATICOS = RAIZ / "src" / "sivia_inventario" / "estaticos"


@asynccontextmanager
async def ciclo_vida(app: FastAPI):
    inicializar_base_datos()
    yield


app = FastAPI(title="SIVIA", lifespan=ciclo_vida)
app.mount("/static", StaticFiles(directory=ESTATICOS), name="static")
plantillas = Jinja2Templates(directory=PLANTILLAS)


@app.get("/", response_class=HTMLResponse)
def inicio(request: Request):
    return plantillas.TemplateResponse(
        request,
        "inicio.html",
        {"pagina": "inicio", "resumen": resumen_dashboard()},
    )


@app.get("/inventario", response_class=HTMLResponse)
def inventario(request: Request):
    return plantillas.TemplateResponse(request, "inventario.html", {"pagina": "inventario", "productos": listar_productos()})


@app.get("/verificar", response_class=HTMLResponse)
def verificar(request: Request):
    return plantillas.TemplateResponse(request, "verificar.html", {"pagina": "verificar"})


@app.get("/historial", response_class=HTMLResponse)
def historial(request: Request):
    return plantillas.TemplateResponse(request, "historial.html", {"pagina": "historial"})


@app.get("/alertas", response_class=HTMLResponse)
def alertas(request: Request):
    return plantillas.TemplateResponse(request, "alertas.html", {"pagina": "alertas"})
