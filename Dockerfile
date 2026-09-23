FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    git \
    && rm -rf /var/lib/apt/lists/*

# torch CPU primero (versión separada para evitar conflictos)
RUN pip install --no-cache-dir \
    torch==2.14.0 \
    torchaudio==2.11.0 \
    --index-url https://download.pytorch.org/whl/cpu

# resto de dependencias con versiones exactas probadas
RUN pip install --no-cache-dir \
    transformers==4.42.4 \
    coqui-tts==0.24.2 \
    fastapi==0.141.1 \
    uvicorn==0.53.0 \
    soundfile==0.14.0 \
    numpy==1.26.4 \
    huggingface-hub

# descarga el modelo de Celtia desde HuggingFace en tiempo de build
RUN python -c "\
from huggingface_hub import snapshot_download; \
snapshot_download(repo_id='proxectonos/Nos_TTS-celtia-vits-graphemes', local_dir='models/celtia')"

COPY main.py .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
