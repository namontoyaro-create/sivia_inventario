from pathlib import Path
from io import BytesIO
import wave

import pytest
from fastapi.testclient import TestClient

from sivia_inventario.voz import ErrorAudio, decodificar_audio_para_whisper, validar_audio
from sivia_inventario import web
from sivia_inventario.web import app


def test_rechaza_extension_de_audio_no_permitida(tmp_path: Path):
    ruta = tmp_path / "audio.txt"
    ruta.write_bytes(b"no es audio")
    with pytest.raises(ErrorAudio, match="Formato no admitido"):
        validar_audio(ruta, ruta.stat().st_size)


def test_rechaza_audio_vacio(tmp_path: Path):
    ruta = tmp_path / "vacio.wav"
    ruta.write_bytes(b"")
    with pytest.raises(ErrorAudio, match="vacío"):
        validar_audio(ruta, 0)


def test_asistente_voz_muestra_captura_y_requiere_confirmacion_para_movimientos():
    with TestClient(app) as cliente:
        respuesta = cliente.get("/asistente-voz")
    assert respuesta.status_code == 200
    assert "Asistente de voz" in respuesta.text
    assert "Transcribir audio" in respuesta.text
    assert "requieren confirmación explícita" in respuesta.text


def test_decodifica_wav_valido_para_whisper(tmp_path: Path):
    ruta = tmp_path / "audio.wav"
    with wave.open(str(ruta), "wb") as archivo:
        archivo.setnchannels(1)
        archivo.setsampwidth(2)
        archivo.setframerate(16000)
        archivo.writeframes(b"\x00\x00" * 16000)
    audio = decodificar_audio_para_whisper(ruta)
    assert audio.dtype.name == "float32"
    assert len(audio) == 16000


def test_endpoint_recibe_el_campo_audio_y_responde_json(monkeypatch):
    contenido = BytesIO()
    with wave.open(contenido, "wb") as archivo:
        archivo.setnchannels(1)
        archivo.setsampwidth(2)
        archivo.setframerate(16000)
        archivo.writeframes(b"\x00\x00" * 16000)
    monkeypatch.setattr(web, "transcribir_audio", lambda ruta: "consulta de prueba")
    with TestClient(app) as cliente:
        respuesta = cliente.post("/asistente-voz/transcribir", files={"audio": ("voz.wav", contenido.getvalue(), "audio/wav")})
    assert respuesta.status_code == 200
    assert respuesta.json() == {"ok": True, "transcripcion": "consulta de prueba"}
