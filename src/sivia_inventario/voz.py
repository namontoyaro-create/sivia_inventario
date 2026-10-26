"""Transcripción local temporal para el Asistente de voz de SIVIA."""

from functools import lru_cache
import logging
from pathlib import Path

import av
import numpy as np
from faster_whisper import WhisperModel

FORMATOS_AUDIO = {".wav", ".mp3", ".m4a", ".webm", ".ogg"}
MAXIMO_AUDIO_BYTES = 25 * 1024 * 1024
MAXIMO_DURACION_SEGUNDOS = 180
REGISTRO = logging.getLogger(__name__)


class ErrorAudio(ValueError):
    """Error claro para la interfaz."""


@lru_cache(maxsize=1)
def modelo_voz() -> WhisperModel:
    """Carga base local una vez, en CPU e int8."""
    return WhisperModel("base", device="cpu", compute_type="int8")


def duracion_audio(ruta: Path) -> float:
    try:
        with av.open(str(ruta)) as contenedor:
            if contenedor.duration is not None:
                return float(contenedor.duration / av.time_base)
            flujos = [flujo for flujo in contenedor.streams if flujo.type == "audio"]
            if not flujos:
                raise ErrorAudio("El archivo no contiene una pista de audio.")
            flujo = flujos[0]
            if flujo.duration is None or flujo.time_base is None:
                raise ErrorAudio("No se pudo determinar la duración del audio.")
            return float(flujo.duration * flujo.time_base)
    except ErrorAudio:
        raise
    except av.FFmpegError as error:
        raise ErrorAudio("No se pudo leer el audio. Usa WAV, MP3, M4A, WEBM u OGG.") from error


def validar_audio(ruta: Path, tamano: int) -> float:
    if tamano <= 0:
        raise ErrorAudio("El audio seleccionado está vacío.")
    if tamano > MAXIMO_AUDIO_BYTES:
        raise ErrorAudio("El audio no puede superar 25 MB.")
    if ruta.suffix.lower() not in FORMATOS_AUDIO:
        raise ErrorAudio("Formato no admitido. Usa WAV, MP3, M4A, WEBM u OGG.")
    duracion = duracion_audio(ruta)
    if duracion <= 0:
        raise ErrorAudio("El audio no tiene una duración válida.")
    if duracion > MAXIMO_DURACION_SEGUNDOS:
        raise ErrorAudio("El audio no puede durar más de 3 minutos.")
    return duracion


def decodificar_audio_para_whisper(ruta: Path) -> np.ndarray:
    """Convierte cualquier formato aceptado a PCM mono de 16 kHz.

    faster-whisper 1.2.1 usa una llamada de PyAV retirada en PyAV 19. Se
    decodifica aquí para conservar PyAV actual y entregar a Whisper un arreglo
    de audio ya normalizado.
    """
    try:
        partes: list[np.ndarray] = []
        with av.open(str(ruta)) as contenedor:
            remuestreador = av.AudioResampler(format="flt", layout="mono", rate=16000)
            for cuadro in contenedor.decode(audio=0):
                for convertido in remuestreador.resample(cuadro):
                    partes.append(convertido.to_ndarray().reshape(-1))
            for convertido in remuestreador.resample(None):
                partes.append(convertido.to_ndarray().reshape(-1))
        if not partes:
            raise ErrorAudio("El audio no contiene muestras que puedan transcribirse.")
        return np.concatenate(partes).astype(np.float32, copy=False)
    except ErrorAudio:
        raise
    except Exception as error:
        REGISTRO.exception("No se pudo decodificar el audio temporal de SIVIA")
        raise ErrorAudio("No se pudo decodificar el audio. Graba nuevamente o usa WAV, MP3, M4A, WEBM u OGG.") from error


def transcribir_audio(ruta: Path) -> str:
    """Transcribe; no interpreta ni ejecuta instrucciones."""
    try:
        audio_pcm = decodificar_audio_para_whisper(ruta)
        segmentos, _ = modelo_voz().transcribe(audio_pcm, language="es", beam_size=5, vad_filter=True)
        texto = " ".join(segmento.text.strip() for segmento in segmentos).strip()
    except ErrorAudio:
        raise
    except Exception as error:
        REGISTRO.exception("Falló la transcripción local de SIVIA")
        raise ErrorAudio("No se pudo transcribir el audio. Revisa el formato y vuelve a intentarlo.") from error
    if not texto:
        raise ErrorAudio("No se detectó voz comprensible. Intenta hablar más cerca del micrófono.")
    return texto
