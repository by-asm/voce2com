import numpy as np
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

import main


@pytest.fixture(autouse=True)
def mock_tts(monkeypatch):
    """Replace TTS model with a mock so tests run without loading the real model."""
    fake_wav = np.zeros(22050, dtype=np.float32)
    mock = MagicMock()
    mock.tts.return_value = fake_wav
    monkeypatch.setitem(main._tts_instances, "gl:celtia", mock)


@pytest.fixture
def client():
    with TestClient(app=main.app, raise_server_exceptions=True) as c:
        yield c


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_voices_returns_voices_for_language(client):
    response = client.get("/voices", params={"language": "gl"})
    assert response.status_code == 200
    data = response.json()
    assert "celtia" in data
    assert data["celtia"]["gender"] == "female"
    assert data["celtia"]["sample_rate"] == 22050


def test_tts_returns_wav(client):
    response = client.get("/tts", params={"text": "ola", "language": "gl", "voice": "celtia"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.content[:4] == b"RIFF"


def test_tts_includes_content_length(client):
    response = client.get("/tts", params={"text": "ola", "language": "gl", "voice": "celtia"})
    assert response.status_code == 200
    assert int(response.headers["content-length"]) > 0


def test_tts_default_language_and_voice(client):
    response = client.get("/tts", params={"text": "ola"})
    assert response.status_code == 200


def test_tts_empty_text_returns_text_empty(client):
    response = client.get("/tts", params={"text": "   "})
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "TEXT_EMPTY"


def test_tts_text_too_long_returns_text_too_long(client):
    response = client.get("/tts", params={"text": "a" * 201})
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "TEXT_TOO_LONG"


def test_tts_unknown_language_returns_language_not_found(client):
    response = client.get("/tts", params={"text": "hello", "language": "xx"})
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "LANGUAGE_NOT_FOUND"


def test_tts_unknown_voice_returns_voice_not_found(client):
    response = client.get("/tts", params={"text": "ola", "language": "gl", "voice": "unknown"})
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "VOICE_NOT_FOUND"


def test_list_voices_unknown_language_returns_language_not_found(client):
    response = client.get("/voices", params={"language": "xx"})
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "LANGUAGE_NOT_FOUND"


def test_error_message_in_galician(client):
    response = client.get(
        "/tts",
        params={"text": "   "},
        headers={"Accept-Language": "gl"},
    )
    assert response.json()["detail"]["message"] == "O parámetro 'text' non pode estar baleiro"


def test_error_message_in_spanish(client):
    response = client.get(
        "/tts",
        params={"text": "   "},
        headers={"Accept-Language": "es"},
    )
    assert response.json()["detail"]["message"] == "El parámetro 'text' no puede estar vacío"


def test_error_message_defaults_to_english(client):
    response = client.get("/tts", params={"text": "   "})
    assert response.json()["detail"]["message"] == "The 'text' parameter cannot be empty"
