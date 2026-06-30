from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from triage_common import db, storage
from triage_common.contracts import (
    EntrevistaEstado,
    EntrevistaTimestamps,
    TaskLogEntry,
    TaskStatus,
    TranscribeRequest,
    TranscribeResponse,
)

import transcription


app = FastAPI(title="MedFlow Transcripcion", version="0.3.0")

BACKEND_NAME = os.getenv("TRANSCRIPTION_BACKEND", "local")

_backend: Optional[transcription.TranscriptionBackend] = None
_storage: Optional[storage.StorageClient] = None


def get_backend() -> transcription.TranscriptionBackend:
    global _backend
    if _backend is None:
        _backend = transcription.select_backend(BACKEND_NAME)
    return _backend


def get_storage() -> storage.StorageClient:
    global _storage
    if _storage is None:
        _storage = storage.StorageClient()
    return _storage


class HealthResponse(BaseModel):
    status: str
    backend: str


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", backend=BACKEND_NAME)


@app.post("/transcribe", response_model=TranscribeResponse)
def transcribe(req: TranscribeRequest) -> TranscribeResponse:
    started = datetime.utcnow()
    db.mark_timestamp(req.guid, EntrevistaTimestamps.TRANSCRIPCION, "inicio", when=started)

    try:
        bucket, key = storage.parse_uri(req.audio_url)
        data = get_storage().get_bytes(bucket, key)
    except Exception as exc:
        _log_error(req.guid, started, f"audio fetch failed: {exc}")
        raise HTTPException(status_code=400, detail=f"audio inaccesible: {exc}")

    try:
        result = get_backend().transcribe(data, req.language)
    except transcription.TranscriptionError as exc:
        _log_error(req.guid, started, f"transcription error: {exc}")
        raise HTTPException(status_code=502, detail=f"transcripcion fallo: {exc}")

    fields = {"resumen_es": result.texto}
    if result.language == "en":
        fields["texto_original_en"] = result.texto

    db.upsert_texto_procesado(req.guid, fields)

    finished = datetime.utcnow()
    db.mark_timestamp(req.guid, EntrevistaTimestamps.TRANSCRIPCION, "fin", when=finished)
    db.update_entrevista_estado(req.guid, EntrevistaEstado.TRANSCRITO)

    payload: dict = {
        "language": result.language,
        "duration_seconds": result.duration_seconds,
        "chars": len(result.texto),
        "diarized": result.diarized,
        "transcripcion_completa": result.turns,
        "backend": BACKEND_NAME,
    }
    if result.diarization_error:
        payload["diarization_error"] = result.diarization_error

    db.log_task(
        TaskLogEntry(
            guid=req.guid,
            service_name="transcripcion",
            timestamp_inicio=started,
            timestamp_fin=finished,
            status=TaskStatus.OK,
            payload_resultado=payload,
        )
    )

    return TranscribeResponse(
        guid=req.guid,
        texto=result.texto,
        language=result.language,
        duration_seconds=result.duration_seconds,
    )


def _log_error(guid: str, started: datetime, msg: str) -> None:
    db.log_task(
        TaskLogEntry(
            guid=guid,
            service_name="transcripcion",
            timestamp_inicio=started,
            timestamp_fin=datetime.utcnow(),
            status=TaskStatus.ERROR,
            error_msg=msg,
        )
    )
