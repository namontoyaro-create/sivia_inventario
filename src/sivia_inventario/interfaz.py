"""Interfaz de escritorio local para revisar imágenes y resultados experimentales."""

import json
import os
from pathlib import Path
from queue import Queue, Empty
from threading import Thread
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from PIL import Image, ImageOps, ImageTk

from sivia_inventario.dataset import RAIZ
from sivia_inventario.deteccion import MODELO_GENERAL, procesar_imagen


class Aplicacion(ttk.Frame):
    def __init__(self, root):
        super().__init__(root, padding=20)
        self.pack(fill="both", expand=True)
        self.root = root
        self.eventos = Queue()
        self.foto = None
        self.imagen = tk.StringVar()
        modelos = sorted((RAIZ / "modelos").glob("ferreteria_piloto_*.pt"))
        self.modelo = tk.StringVar(value=str(modelos[-1] if modelos else MODELO_GENERAL))
        self.stock = tk.StringVar()
        self.confianza = tk.StringVar(value="0.50")
        self.alcance = tk.BooleanVar(value=False)
        self.informe = None
        ttk.Label(self, text="SIVIA · Inventario visual", font=("Segoe UI", 22, "bold")).pack(anchor="w")
        ttk.Label(self, text="Prototipo experimental · Revisa las detecciones antes de usar los conteos.", wraplength=950).pack(anchor="w", pady=(5, 14))
        self.campo("Imagen", self.imagen, self.elegir_imagen)
        self.campo("Modelo", self.modelo, self.elegir_modelo)
        self.campo("Stock JSON (opcional)", self.stock, self.elegir_stock)
        controles = ttk.Frame(self)
        controles.pack(fill="x", pady=10)
        ttk.Label(controles, text="Confianza mínima:").pack(side="left")
        ttk.Spinbox(controles, from_=0.01, to=1, increment=0.05, textvariable=self.confianza, width=6).pack(side="left", padx=8)
        ttk.Button(controles, text="Quitar stock", command=lambda: self.stock.set("")).pack(side="left", padx=8)
        ttk.Checkbutton(self, text="Si comparo stock, confirmo la misma unidad y alcance que la imagen.", variable=self.alcance).pack(anchor="w")
        acciones = ttk.Frame(self)
        acciones.pack(fill="x", pady=12)
        self.boton = ttk.Button(acciones, text="Analizar imagen", command=self.analizar)
        self.boton.pack(side="left")
        self.boton_informe = ttk.Button(acciones, text="Abrir informe JSON", command=self.abrir_informe, state="disabled")
        self.boton_informe.pack(side="left", padx=10)
        self.estado = tk.StringVar(value="Selecciona una imagen. El procesamiento se realiza en este equipo.")
        ttk.Label(self, textvariable=self.estado, wraplength=950).pack(anchor="w")
        panel = ttk.Panedwindow(self, orient="horizontal")
        panel.pack(fill="both", expand=True, pady=10)
        self.vista = ttk.Label(panel, anchor="center")
        self.texto = tk.Text(panel, width=48, wrap="word", font=("Consolas", 10), state="disabled")
        panel.add(self.vista, weight=3)
        panel.add(self.texto, weight=2)
        self.root.after(150, self.recibir)

    def campo(self, titulo, variable, comando):
        fila = ttk.Frame(self)
        fila.pack(fill="x", pady=4)
        ttk.Label(fila, text=titulo, width=23).pack(side="left")
        ttk.Entry(fila, textvariable=variable).pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(fila, text="Elegir…", command=comando).pack(side="right")

    def elegir_imagen(self):
        ruta = filedialog.askopenfilename(initialdir=RAIZ / "datos/imagenes", filetypes=[("Imágenes", "*.jpg *.jpeg *.png *.bmp *.webp")])
        if ruta:
            self.imagen.set(ruta)
            self.informe = None
            self.boton_informe.configure(state="disabled")
            self.mostrar_imagen(ruta)

    def elegir_modelo(self):
        ruta = filedialog.askopenfilename(initialdir=RAIZ / "modelos", filetypes=[("Pesos YOLO", "*.pt")])
        if ruta:
            self.modelo.set(ruta)

    def elegir_stock(self):
        ruta = filedialog.askopenfilename(initialdir=RAIZ / "datos/inventario", filetypes=[("Stock", "*.json")])
        if ruta:
            self.stock.set(ruta)

    def mostrar_imagen(self, ruta):
        with Image.open(ruta) as original:
            im = ImageOps.contain(original.convert("RGB"), (560, 420))
        self.foto = ImageTk.PhotoImage(im)
        self.vista.configure(image=self.foto)

    def analizar(self):
        try:
            confianza = float(self.confianza.get())
            if not self.imagen.get() or not self.modelo.get():
                raise ValueError("Selecciona una imagen y un modelo.")
            if self.stock.get() and not self.alcance.get():
                raise ValueError("Confirma la misma unidad y alcance o quita el stock para analizar sin comparación.")
        except ValueError as error:
            messagebox.showerror("Revisar datos", str(error))
            return
        args = (self.imagen.get(), self.modelo.get(), confianza, self.stock.get() or None, self.alcance.get())
        self.boton.configure(state="disabled")
        self.boton_informe.configure(state="disabled")
        self.estado.set("Analizando en CPU…")
        Thread(target=self.trabajar, args=args, daemon=True).start()

    def trabajar(self, imagen, modelo, confianza, stock, alcance):
        try:
            self.eventos.put((True, procesar_imagen(imagen, modelo, confianza, stock_path=stock, mismo_alcance=alcance)))
        except Exception as error:
            self.eventos.put((False, str(error)))

    def recibir(self):
        try:
            correcto, resultado = self.eventos.get_nowait()
            self.boton.configure(state="normal")
            if correcto:
                self.informe = resultado["informe"]
                self.mostrar_imagen(resultado["imagen_resultado"])
                lineas = ["RESULTADO EXPERIMENTAL", "", f"Total detectado: {resultado['total']}"]
                lineas += [f"{clase}: {n}" for clase, n in resultado["conteos"].items()]
                if not resultado["conteos"]:
                    lineas.append("Sin detecciones. No equivale a stock cero.")
                if "comparaciones" in resultado:
                    lineas += ["", f"Stock de referencia: {resultado['tipo_stock']}", "Comparación orientativa:"]
                    lineas += [f"{r['clase']}: {r['estado']}" + (f" (diferencia {r['diferencia']:+d})" if "diferencia" in r else "") for r in resultado["comparaciones"]]
                lineas += ["", resultado["advertencia"], "", f"Informe: {self.informe}"]
                self.texto.configure(state="normal")
                self.texto.delete("1.0", "end")
                self.texto.insert("end", "\n".join(lineas))
                self.texto.configure(state="disabled")
                self.boton_informe.configure(state="normal")
                self.estado.set("Análisis terminado. Las existencias no se modificaron.")
            else:
                self.estado.set("No se pudo completar el análisis.")
                messagebox.showerror("Error de análisis", resultado)
        except Empty:
            pass
        self.root.after(150, self.recibir)

    def abrir_informe(self):
        if self.informe:
            os.startfile(self.informe)


def main():
    try:
        root = tk.Tk()
    except tk.TclError as error:
        raise SystemExit(
            "No se puede abrir la interfaz: Python no tiene Tcl/Tk disponible. "
            "Use el comando de detección por terminal o instale/repare Python con Tcl/Tk."
        ) from error
    root.title("SIVIA · Inventario visual")
    root.geometry("1100x850")
    root.minsize(850, 650)
    Aplicacion(root)
    root.mainloop()


if __name__ == "__main__":
    main()
