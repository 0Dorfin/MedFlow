from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from triage_common import db, llm
from triage_common.contracts import (
    EntrevistaEstado,
    EntrevistaTimestamps,
    ExtractRequest,
    ExtractResponse,
    TaskLogEntry,
    TaskStatus,
)


class TranslateSummarizeRequest(BaseModel):
    guid: str
    texto: str


class TranslateSummarizeResponse(BaseModel):
    guid: str
    resumen_es: str


app = FastAPI(title="TriageIA LLM Extraction", version="0.1.0")

_client: Optional[llm.LLMClient] = None


def get_client() -> llm.LLMClient:
    global _client
    if _client is None:
        _client = llm.LLMClient()
    return _client


_BAD_CHARS = set('{}[]"\\')


def _sanitize_entity(item: str) -> str:
    cleaned = "".join(c for c in str(item) if c not in _BAD_CHARS).strip()
    cleaned = cleaned.strip(" ,;:.-")
    return cleaned


def _normalize_entities(payload: dict) -> list[str]:
    raw = payload.get("entidades") or payload.get("entities") or []
    if not isinstance(raw, list):
        return []
    cleaned = [_sanitize_entity(item) for item in raw]
    return [c for c in cleaned if c and len(c) >= 2 and len(c) <= 120]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/run", response_model=ExtractResponse)
def run(req: ExtractRequest) -> ExtractResponse:
    started = datetime.utcnow()
    db.mark_timestamp(req.guid, EntrevistaTimestamps.EXTRACCION_ENTIDADES, "inicio", when=started)

    try:
        payload = get_client().render_and_generate_json(
            "extract_entities.j2",
            context={"texto": req.texto},
        )
    except llm.LLMError as exc:
        _log_error(req.guid, started, str(exc))
        raise HTTPException(status_code=502, detail=f"LLM error: {exc}")

    entidades = _normalize_entities(payload)

    db.upsert_texto_procesado(req.guid, {"entidades_extraidas_es": entidades})

    finished = datetime.utcnow()
    db.mark_timestamp(req.guid, EntrevistaTimestamps.EXTRACCION_ENTIDADES, "fin", when=finished)
    db.update_entrevista_estado(req.guid, EntrevistaEstado.ENTIDADES_EXTRAIDAS)

    db.log_task(
        TaskLogEntry(
            guid=req.guid,
            service_name="llm-extraction",
            timestamp_inicio=started,
            timestamp_fin=finished,
            status=TaskStatus.OK,
            payload_resultado={"entidades": entidades, "raw": payload},
        )
    )

    return ExtractResponse(guid=req.guid, entidades=entidades)


@app.post("/translate_summarize", response_model=TranslateSummarizeResponse)
def translate_summarize(req: TranslateSummarizeRequest) -> TranslateSummarizeResponse:
    started = datetime.utcnow()

    try:
        payload = get_client().render_and_generate_json(
            "translate_summarize.j2",
            context={"texto": req.texto},
        )
    except llm.LLMError as exc:
        _log_error(req.guid, started, str(exc))
        raise HTTPException(status_code=502, detail=f"LLM error: {exc}")

    resumen = str(payload.get("resumen_es") or "").strip()
    if not resumen:
        _log_error(req.guid, started, f"resumen vacio: {payload}")
        raise HTTPException(status_code=502, detail="LLM devolvio resumen vacio")

    db.upsert_texto_procesado(req.guid, {"resumen_es": resumen})

    finished = datetime.utcnow()
    db.log_task(
        TaskLogEntry(
            guid=req.guid,
            service_name="llm-extraction:translate_summarize",
            timestamp_inicio=started,
            timestamp_fin=finished,
            status=TaskStatus.OK,
            payload_resultado={"resumen_es": resumen, "raw": payload},
        )
    )

    return TranslateSummarizeResponse(guid=req.guid, resumen_es=resumen)


def _log_error(guid: str, started: datetime, msg: str) -> None:
    db.log_task(
        TaskLogEntry(
            guid=guid,
            service_name="llm-extraction",
            timestamp_inicio=started,
            timestamp_fin=datetime.utcnow(),
            status=TaskStatus.ERROR,
            error_msg=msg,
        )
    )
