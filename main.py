import io
from contextlib import asynccontextmanager

import soundfile as sf
from TTS.api import TTS
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

VOICES = {
    "celtia": {
        "model_path": "models/celtia/celtia.pth",
        "config_path": "models/celtia/config.json",
    }
}

_tts_instances: dict[str, TTS] = {}


def get_tts(voice: str) -> TTS:
    if voice not in _tts_instances:
        cfg = VOICES[voice]
        _tts_instances[voice] = TTS(
            model_path=cfg["model_path"],
            config_path=cfg["config_path"],
            progress_bar=False,
        )
    return _tts_instances[voice]


@asynccontextmanager
async def lifespan(app: FastAPI):
    for voice in VOICES:
        get_tts(voice)
    yield


app = FastAPI(title="voce2com TTS", version="1.0.0", lifespan=lifespan)


@app.get("/tts", response_class=StreamingResponse)
def synthesize(texto: str, voz: str = "celtia"):
    if not texto.strip():
        raise HTTPException(status_code=400, detail="O parámetro 'texto' non pode estar baleiro")
    if voz not in VOICES:
        raise HTTPException(
            status_code=400,
            detail=f"Voz non dispoñible. Opcións: {list(VOICES.keys())}",
        )

    tts = get_tts(voz)
    wav = tts.tts(text=texto)

    buf = io.BytesIO()
    sf.write(buf, wav, samplerate=22050, format="WAV")
    buf.seek(0)

    filename = f"{texto[:30].replace(' ', '_')}_{voz}.wav"
    return StreamingResponse(
        buf,
        media_type="audio/wav",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/voces")
def list_voices():
    return {"voces": list(VOICES.keys())}


@app.get("/health")
def health():
    return {"status": "ok"}
