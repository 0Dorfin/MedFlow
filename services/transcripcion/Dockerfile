FROM nvidia/cuda:12.8.0-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-dev ffmpeg curl \
 && rm -rf /var/lib/apt/lists/* \
 && ln -sf /usr/bin/python3 /usr/bin/python

WORKDIR /app

COPY services/_common ./_common
COPY services/transcripcion/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
 && pip install --no-cache-dir "ctranslate2==4.5.0" "huggingface_hub==0.25.2" "transformers==4.44.2" \
 && pip install --no-cache-dir setuptools wheel \
 && pip install --no-cache-dir --no-build-isolation ./_common

COPY services/transcripcion/main.py ./

EXPOSE 9100

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
  CMD curl -fsS http://localhost:9100/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9100"]
