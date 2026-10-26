"""Entrenamiento local de un prototipo, con trazabilidad de datos y métricas."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

from sivia_inventario.dataset import RAIZ, auditar, sha256, validar_caja


def verificar_exportacion(config: Path) -> dict:
    """Comprueba que las imágenes y etiquetas exportadas corresponden al manifiesto."""
    config = config.resolve()
    datos = json.loads(config.read_text(encoding="utf-8"))
    carpeta = config.parent
    if Path(datos.get("path", "")).resolve() != carpeta:
        raise ValueError("La ruta del dataset no coincide con la carpeta de exportación.")
    manifiesto, informe = auditar(carpeta / "anotaciones.json")
    if datos.get("names") != manifiesto["clases"] or "download" in datos:
        raise ValueError("Configuración de entrenamiento incompatible.")
    esperados = set()
    for e in manifiesto["imagenes"]:
        if e["estado"] == "excluida":
            continue
        original = Path(e["archivo"])
        nombre = f"{e['sha256'][:12]}_{original.stem}"
        imagen = carpeta / "images" / e["split"] / (nombre + original.suffix.lower())
        etiqueta = carpeta / "labels" / e["split"] / (nombre + ".txt")
        if sha256(imagen) != e["sha256"]:
            raise ValueError("Imagen exportada alterada.")
        lineas = [str(manifiesto["clases"].index(o["clase"])) + " " + " ".join(f"{v:.8f}" for v in validar_caja(o["xyxy"])) for o in e["objetos"]]
        if etiqueta.read_text(encoding="utf-8").splitlines() != lineas:
            raise ValueError("Etiquetas exportadas alteradas; vuelva a exportar el dataset.")
        esperados.update((imagen.resolve(), etiqueta.resolve()))
    encontrados = {p.resolve() for parte in ("images", "labels") for p in (carpeta / parte).rglob("*") if p.is_file() and p.suffix != ".cache"}
    if encontrados != esperados:
        raise ValueError("Archivos adicionales o faltantes en la exportación.")
    for split in ("train", "val"):
        if datos.get(split) != f"images/{split}":
            raise ValueError("Partición de entrenamiento modificada.")
    return informe


def main() -> None:
    parser = argparse.ArgumentParser(description="Entrenar un detector experimental de ferretería")
    parser.add_argument("--datos", type=Path, default=RAIZ / "datos/entrenamiento/pilotos/piloto_v1/data.yaml")
    parser.add_argument("--epocas", type=int, default=30)
    parser.add_argument("--tamano", type=int, default=320)
    parser.add_argument("--nombre", default="piloto", help="Prefijo aislado para resultados y pesos.")
    parser.add_argument("--experimental", action="store_true", help="Reconoce que el dataset piloto no valida fiabilidad en inventario")
    args = parser.parse_args()
    if not args.experimental:
        parser.error("Este dataset es experimental. Revise su informe y use --experimental para la prueba técnica.")
    if not 1 <= args.epocas <= 300 or not 32 <= args.tamano <= 1280 or args.tamano % 32:
        parser.error("Épocas: 1–300. Tamaño: múltiplo de 32 entre 32 y 1280.")
    try:
        informe = verificar_exportacion(args.datos)
        from ultralytics import YOLO, __version__ as version_yolo
        import torch

        torch.set_num_threads(4)
        instante = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        nombre = "".join(caracter for caracter in args.nombre if caracter.isalnum() or caracter in "_-")
        if not nombre:
            parser.error("El nombre debe contener letras, números, guiones o guiones bajos.")
        print("ENTRENAMIENTO EXPERIMENTAL: no valida conteo fiable en almacén.", flush=True)
        for aviso in informe["advertencias"]:
            print(aviso, flush=True)
        modelo = YOLO(str(RAIZ / "modelos/yolo26n.pt"))
        modelo.train(
            data=str(args.datos.resolve()), epochs=args.epocas, imgsz=args.tamano,
            batch=4, nbs=4, optimizer="AdamW", lr0=0.001,
            device="cpu", workers=0, amp=False, cache=False,
            seed=42, deterministic=True, freeze=10, patience=25,
            project=str(RAIZ / "resultados/entrenamiento"), name=f"{nombre}_{instante}",
            exist_ok=False, plots=True, verbose=False,
        )
        mejor = Path(modelo.trainer.best)
        if not mejor.is_file():
            raise RuntimeError("No se generó best.pt.")
        destino = RAIZ / "modelos" / f"ferreteria_{nombre}_{instante}.pt"
        shutil.copy2(mejor, destino)
        metricas = {str(k): float(v) for k, v in modelo.trainer.metrics.items()}
        registro = {
            "experimental": True, "validado_para_inventario": False,
            "modelo": destino.name, "sha256_modelo": sha256(destino),
            "ultralytics": version_yolo, "torch": torch.__version__,
            "epocas_solicitadas": args.epocas, "tamano": args.tamano,
            "batch": 4, "nbs": 4, "optimizer": "AdamW", "lr0": 0.001,
            "dataset": informe, "metricas_validacion_piloto": metricas,
            "entrenamiento": str(mejor.parent.parent.relative_to(RAIZ)),
        }
        destino.with_suffix(".json").write_text(json.dumps(registro, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("Modelo piloto:", destino, flush=True)
        print("Métricas exploratorias:", json.dumps(metricas), flush=True)
    except (OSError, ValueError, RuntimeError, KeyError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
