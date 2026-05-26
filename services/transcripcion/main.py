from __future__ import annotations

import os
import tempfile
from datetime import datetime
from typing import Any, Optional

import torch
import whisperx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

_original_torch_load = torch.load


def _torch_load_full_weights(*args: Any, **kwargs: Any):
    kwargs["weights_only"] = False
    return _original_torch_load(*args, **kwargs)


torch.load = _torch_load_full_weights

from triage_common import db, storage
from triage_common.contracts import (
    EntrevistaEstado,
    EntrevistaTimestamps,
    TaskLogEntry,
    TaskStatus,
    TranscribeRequest,
    TranscribeResponse,
)

try:
    from whisperx.diarize import DiarizationPipeline
except ImportError:
    from whisperx import DiarizationPipeline


app = FastAPI(title="TriageIA Transcripcion", version="0.2.0")

MODEL_NAME = os.getenv("WHISPER_MODEL", "base")
DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
BATCH_SIZE = int(os.getenv("WHISPER_BATCH_SIZE", "16"))
HF_TOKEN = os.getenv("HF_TOKEN") or None
NUM_SPEAKERS = int(os.getenv("DIARIZATION_NUM_SPEAKERS", "2")) or None

_model = None
_diarizer: Optional[DiarizationPipeline] = None
_storage: Optional[storage.StorageClient] = None
_align_models: dict[str, tuple[Any, Any]] = {}


def get_model():
    global _model
    if _model is None:
        _model = whisperx.load_model(MODEL_NAME, DEVICE, compute_type=COMPUTE_TYPE)
    return _model


def get_diarizer() -> Optional[DiarizationPipeline]:
    global _diarizer
    if not HF_TOKEN:
        return None
    if _diarizer is None:
        _diarizer = DiarizationPipeline(use_auth_token=HF_TOKEN, device=DEVICE)
    return _diarizer


def get_align_model(language: str) -> tuple[Any, Any]:
    if language not in _align_models:
        _align_models[language] = whisperx.load_align_model(
            language_code=language, device=DEVICE
        )
    return _align_models[language]


def get_storage() -> storage.StorageClient:
    global _storage
    if _storage is None:
        _storage = storage.StorageClient()
    return _storage


class HealthResponse(BaseModel):
    status: str
    model: str
    device: str
    compute_type: str
    diarization: bool


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        model=MODEL_NAME,
        device=DEVICE,
        compute_type=COMPUTE_TYPE,
        diarization=bool(HF_TOKEN),
    )


def _segment_majority_speaker(segment: dict[str, Any]) -> Optional[str]:
    counts: dict[str, int] = {}
    for word in segment.get("words", []):
        speaker = word.get("speaker")
        if speaker:
            counts[speaker] = counts.get(speaker, 0) + 1
    if not counts:
        return None
    return max(counts, key=counts.get)


def _group_segment_turns(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    turns: list[dict[str, Any]] = []
    for seg in segments:
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        speaker = _segment_majority_speaker(seg)
        start = seg.get("start")
        end = seg.get("end")
        if speaker is None and turns:
            turns[-1]["text"] += " " + text
            if end is not None:
                turns[-1]["end"] = end
            continue
        if turns and turns[-1]["speaker"] == speaker:
            turns[-1]["text"] += " " + text
            if end is not None:
                turns[-1]["end"] = end
        else:
            turns.append(
                {"speaker": speaker, "start": start, "end": end, "text": text}
            )
    return turns


def _select_patient(
    turns: list[dict[str, Any]]
) -> tuple[str, list[dict[str, Any]], bool]:
    located = [t for t in turns if t["speaker"] is not None and t["start"] is not None]
    distinct = {t["speaker"] for t in located}
    if len(distinct) < 2:
        texto = " ".join(t["text"] for t in turns).strip()
        return texto, turns, False

    doctor_speaker = min(located, key=lambda t: t["start"])["speaker"]
    for t in turns:
        t["is_patient"] = t["speaker"] != doctor_speaker

    patient_pieces = [t["text"] for t in turns if t["speaker"] != doctor_speaker]
    texto = " ".join(patient_pieces).strip()
    return texto, turns, True


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

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name

    try:
        audio = whisperx.load_audio(tmp_path)
        result = get_model().transcribe(
            audio,
            batch_size=BATCH_SIZE,
            language=req.language,
        )
        segments = result.get("segments", [])
        detected_language = result.get("language", req.language or "es")
        duration = float(len(audio)) / 16000.0

        diarized = False
        diarization_error: Optional[str] = None
        labeled: list[dict[str, Any]] = []
        texto = ""
        diarizer = get_diarizer()
        if diarizer is not None and segments:
            try:
                align_model, metadata = get_align_model(detected_language)
                aligned = whisperx.align(
                    segments,
                    align_model,
                    metadata,
                    audio,
                    DEVICE,
                    return_char_alignments=False,
                )
                if NUM_SPEAKERS:
                    diarize_segments = diarizer(audio, num_speakers=NUM_SPEAKERS)
                else:
                    diarize_segments = diarizer(audio)
                assigned = whisperx.assign_word_speakers(diarize_segments, aligned)
                turns = _group_segment_turns(assigned.get("segments", []))
                texto, labeled, diarized = _select_patient(turns)
            except Exception as exc:
                diarization_error = str(exc)
                diarized = False

        if not diarized:
            texto = " ".join(seg["text"].strip() for seg in segments).strip()
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    fields = {"resumen_es": texto}
    if detected_language == "en":
        fields["texto_original_en"] = texto

    db.upsert_texto_procesado(req.guid, fields)

    finished = datetime.utcnow()
    db.mark_timestamp(req.guid, EntrevistaTimestamps.TRANSCRIPCION, "fin", when=finished)
    db.update_entrevista_estado(req.guid, EntrevistaEstado.TRANSCRITO)

    payload: dict[str, Any] = {
        "language": detected_language,
        "duration_seconds": duration,
        "chars": len(texto),
        "diarized": diarized,
        "transcripcion_completa": labeled,
    }
    if diarization_error:
        payload["diarization_error"] = diarization_error

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
        texto=texto,
        language=detected_language,
        duration_seconds=duration,
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
