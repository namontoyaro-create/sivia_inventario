"""Aplicación web local de SIVIA."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from sivia_inventario.base_datos import RAIZ, inicializar_base_datos
from sivia_inventario.repositorio_inventario import resumen_dashboard

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
        {"resumen": resumen_dashboard(), "productos": 8},
    )
