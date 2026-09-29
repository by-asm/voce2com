import json
import numpy as np
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

import main

TEST_API_KEY = "test-key-123"


@pytest.fixture(autouse=True)
def mock_tts(monkeypatch):
    fake_wav = np.zeros(22050, dtype=np.float32)
    mock = MagicMock()
    mock.tts.return_value = fake_wav
    monkeypatch.setitem(main._tts_instances, "gl:celtia", mock)
    monkeypatch.setenv("API_KEY", TEST_API_KEY)


@pytest.fixture
def client():
    with TestClient(app=main.app, raise_server_exceptions=True) as c:
        yield c


@pytest.fixture
def auth(client):
    class AuthClient:
        def get(self, url, **kwargs):
            headers = kwargs.pop("headers", {})
            headers["X-API-Key"] = TEST_API_KEY
            return client.get(url, headers=headers, **kwargs)
    return AuthClient()


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_missing_api_key_returns_401(client):
    response = client.get("/v1/languages")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "UNAUTHORIZED"


def test_invalid_api_key_returns_401(client):
    response = client.get("/v1/languages", headers={"X-API-Key": "wrong"})
    assert response.status_code == 401


def test_list_languages(auth):
    response = auth.get("/v1/languages")
    assert response.status_code == 200
    assert "gl" in response.json()["languages"]


def test_list_voices_returns_voices_for_language(auth):
    response = auth.get("/v1/voices", params={"language": "gl"})
    assert response.status_code == 200
    data = response.json()
    assert "celtia" in data
    assert data["celtia"]["gender"] == "female"
    assert data["celtia"]["sample_rate"] == 22050


def test_list_voices_unknown_language_returns_language_not_found(auth):
    response = auth.get("/v1/voices", params={"language": "xx"})
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "LANGUAGE_NOT_FOUND"


def test_tts_returns_wav(auth):
    response = auth.get("/v1/tts", params={"text": "ola", "language": "gl", "voice": "celtia"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.content[:4] == b"RIFF"


def test_tts_includes_content_length(auth):
    response = auth.get("/v1/tts", params={"text": "ola", "language": "gl", "voice": "celtia"})
    assert response.status_code == 200
    assert int(response.headers["content-length"]) > 0


def test_tts_default_language_and_voice(auth):
    response = auth.get("/v1/tts", params={"text": "ola"})
    assert response.status_code == 200


def test_tts_empty_text_returns_text_empty(auth):
    response = auth.get("/v1/tts", params={"text": "   "})
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "TEXT_EMPTY"


def test_tts_text_too_long_returns_text_too_long(auth):
    response = auth.get("/v1/tts", params={"text": "a" * 201})
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "TEXT_TOO_LONG"


def test_tts_unknown_language_returns_language_not_found(auth):
    response = auth.get("/v1/tts", params={"text": "hello", "language": "xx"})
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "LANGUAGE_NOT_FOUND"


def test_tts_unknown_voice_returns_voice_not_found(auth):
    response = auth.get("/v1/tts", params={"text": "ola", "language": "gl", "voice": "unknown"})
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "VOICE_NOT_FOUND"


def test_error_message_in_galician(auth):
    response = auth.get(
        "/v1/tts",
        params={"text": "   "},
        headers={"Accept-Language": "gl"},
    )
    assert response.json()["detail"]["message"] == "O parámetro 'text' non pode estar baleiro"


def test_error_message_in_spanish(auth):
    response = auth.get(
        "/v1/tts",
        params={"text": "   "},
        headers={"Accept-Language": "es"},
    )
    assert response.json()["detail"]["message"] == "El parámetro 'text' no puede estar vacío"


def test_error_message_defaults_to_english(auth):
    response = auth.get("/v1/tts", params={"text": "   "})
    assert response.json()["detail"]["message"] == "The 'text' parameter cannot be empty"


def test_rate_limit_response_is_json(client, monkeypatch):
    from starlette.requests import Request as StarletteRequest
    from main import _rate_limit_handler

    monkeypatch.setenv("API_KEY", TEST_API_KEY)
    scope = {"type": "http", "method": "GET", "path": "/v1/tts", "headers": []}
    request = StarletteRequest(scope)
    exc = MagicMock()

    response = _rate_limit_handler(request, exc)

    assert response.status_code == 429
    body = json.loads(response.body)
    assert body["detail"]["code"] == "RATE_LIMIT_EXCEEDED"


def test_filename_sanitizes_special_characters(auth):
    response = auth.get("/v1/tts", params={"text": 'ola "mundo"', "language": "gl", "voice": "celtia"})
    assert response.status_code == 200
    disposition = response.headers["content-disposition"]
    assert '"' not in disposition.split("filename=")[1].strip('"')
