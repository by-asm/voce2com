import hmac
import io
import logging
import os
import re
from contextlib import asynccontextmanager

import sentry_sdk
import soundfile as sf
from TTS.api import TTS
from fastapi import APIRouter, Depends, FastAPI, Header, Query, Request, Security
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import APIKeyHeader
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from errors import resolve_locale, tts_error

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    integrations=[StarletteIntegration(), FastApiIntegration()],
    traces_sample_rate=0.2,
    send_default_pii=False,
)

logger = logging.getLogger(__name__)

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


def _get_client_key(request: Request) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(key_func=_get_client_key)
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(
    api_key: str | None = Security(_api_key_header),
    accept_language: str | None = Header(default=None),
):
    expected = os.getenv("API_KEY", "")
    if not expected or not api_key or not hmac.compare_digest(api_key, expected):
        raise tts_error("UNAUTHORIZED", resolve_locale(accept_language), 401)


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


def _safe_filename(text: str, language: str, voice: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", text[:30]).strip()
    slug = re.sub(r"\s+", "_", slug)
    return f"{slug}_{language}_{voice}.wav"


def _download_models():
    from huggingface_hub import snapshot_download
    token = os.getenv("HF_TOKEN")
    for cfg in (v for lang in VOICES.values() for v in lang.values()):
        model_dir = os.path.dirname(cfg["model_path"])
        if not os.path.exists(cfg["model_path"]):
            repo_id = f"proxectonos/{os.path.basename(model_dir)}-vits-graphemes"
            logger.info("Downloading model %s", repo_id)
            snapshot_download(repo_id=repo_id, local_dir=model_dir, token=token)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not os.getenv("API_KEY"):
        logger.warning("API_KEY environment variable is not set — all requests will be rejected")

    _download_models()

    for language, voices in VOICES.items():
        for voice in voices:
            get_tts(language, voice)
    yield


def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    accept_language = request.headers.get("Accept-Language")
    locale = resolve_locale(accept_language)
    error = tts_error("RATE_LIMIT_EXCEEDED", locale, 429)
    return JSONResponse(status_code=429, content={"detail": error.detail})


app = FastAPI(title="voce2com TTS", version="1.0.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)

router = APIRouter(prefix="/v1", dependencies=[Depends(verify_api_key)])


@router.get("/tts")
@limiter.limit("20/minute")
def synthesize(
    request: Request,
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

    return StreamingResponse(
        buf,
        media_type="audio/wav",
        headers={
            "Content-Disposition": f'attachment; filename="{_safe_filename(text, language, voice)}"',
            "Content-Length": str(size),
        },
    )


@router.get("/languages")
@limiter.limit("60/minute")
def list_languages(request: Request):
    return {"languages": list(VOICES.keys())}


@router.get("/voices")
@limiter.limit("60/minute")
def list_voices(
    request: Request,
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


app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok"}
