import io
import numpy as np
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

import main


@pytest.fixture(autouse=True)
def mock_tts(monkeypatch):
    """Sustituye el modelo TTS por un mock para que los tests no carguen el modelo real."""
    fake_wav = np.zeros(22050, dtype=np.float32)
    mock = MagicMock()
    mock.tts.return_value = fake_wav
    monkeypatch.setitem(main._tts_instances, "celtia", mock)


@pytest.fixture
def client():
    with TestClient(app=main.app, raise_server_exceptions=True) as c:
        yield c


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_voices(client):
    response = client.get("/voces")
    assert response.status_code == 200
    assert "celtia" in response.json()["voces"]


def test_tts_returns_wav(client):
    response = client.get("/tts", params={"texto": "ola", "voz": "celtia"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    # comprueba que la respuesta es un archivo WAV válido (cabecera RIFF)
    assert response.content[:4] == b"RIFF"


def test_tts_empty_text_returns_400(client):
    response = client.get("/tts", params={"texto": "   ", "voz": "celtia"})
    assert response.status_code == 400


def test_tts_unknown_voice_returns_400(client):
    response = client.get("/tts", params={"texto": "ola", "voz": "inexistente"})
    assert response.status_code == 400


def test_tts_default_voice_is_celtia(client):
    response = client.get("/tts", params={"texto": "ola"})
    assert response.status_code == 200
