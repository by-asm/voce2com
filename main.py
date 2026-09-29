import io
from contextlib import asynccontextmanager

import soundfile as sf
from TTS.api import TTS
from fastapi import FastAPI, Header, Query
from fastapi.responses import StreamingResponse

from errors import resolve_locale, tts_error

MAX_TEXT_LENGTH = 200

VOICES = {
    "gl": {
        "celtia": {
            "model_path": "models/celtia/celtia.pth",
            "config_path": "models/celtia/config.json",
            "gender": "female",
            "sample_rate": 22050,
        },
    },
}

_tts_instances: dict[str, TTS] = {}


def get_tts(language: str, voice: str) -> TTS:
    key = f"{language}:{voice}"
    if key not in _tts_instances:
        cfg = VOICES[language][voice]
        _tts_instances[key] = TTS(
            model_path=cfg["model_path"],
            config_path=cfg["config_path"],
            progress_bar=False,
        )
    return _tts_instances[key]


@asynccontextmanager
async def lifespan(app: FastAPI):
    for language, voices in VOICES.items():
        for voice in voices:
            get_tts(language, voice)
    yield


app = FastAPI(title="voce2com TTS", version="1.0.0", lifespan=lifespan)


@app.get("/tts", response_class=StreamingResponse)
def synthesize(
    text: str = Query(..., description="Text to synthesize"),
    language: str = Query(default="gl", description="Language code (e.g. gl, eu, ca)"),
    voice: str = Query(default="celtia", description="Voice name"),
    accept_language: str | None = Header(default=None),
):
    locale = resolve_locale(accept_language)

    if not text.strip():
        raise tts_error("TEXT_EMPTY", locale, 400)

    if len(text) > MAX_TEXT_LENGTH:
        raise tts_error(
            "TEXT_TOO_LONG",
            locale,
            400,
            max_length=MAX_TEXT_LENGTH,
            received_length=len(text),
        )

    if language not in VOICES:
        raise tts_error(
            "LANGUAGE_NOT_FOUND",
            locale,
            404,
            available_languages=list(VOICES.keys()),
        )

    if voice not in VOICES[language]:
        raise tts_error(
            "VOICE_NOT_FOUND",
            locale,
            404,
            available_voices=list(VOICES[language].keys()),
        )

    tts = get_tts(language, voice)
    wav = tts.tts(text=text)

    buf = io.BytesIO()
    sample_rate = VOICES[language][voice]["sample_rate"]
    sf.write(buf, wav, samplerate=sample_rate, format="WAV")
    size = buf.tell()
    buf.seek(0)

    filename = f"{text[:30].replace(' ', '_')}_{language}_{voice}.wav"
    return StreamingResponse(
        buf,
        media_type="audio/wav",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(size),
        },
    )


@app.get("/voices")
def list_voices(
    language: str = Query(description="Language code (e.g. gl, eu, ca)"),
    accept_language: str | None = Header(default=None),
):
    locale = resolve_locale(accept_language)

    if language not in VOICES:
        raise tts_error(
            "LANGUAGE_NOT_FOUND",
            locale,
            404,
            available_languages=list(VOICES.keys()),
        )

    return {
        voice: {"gender": cfg["gender"], "sample_rate": cfg["sample_rate"]}
        for voice, cfg in VOICES[language].items()
    }


@app.get("/health")
def health():
    return {"status": "ok"}
