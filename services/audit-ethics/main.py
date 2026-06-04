from __future__ import annotations

import os
from datetime import datetime

import httpx
from fastapi import FastAPI

from triage_common import db
from triage_common.contracts import (
    AuditEthicsRequest,
    AuditEthicsResponse,
    EntrevistaEstado,
    TaskLogEntry,
    TaskStatus,
    Validacion,
    over_triage,
    under_triage,
)


app = FastAPI(title="MedFlow Audit Ethics", version="0.1.0")

ANXIETY_BIAS_THRESHOLD = 0.8
N8N_ALERTA_WEBHOOK = os.getenv("N8N_ALERTA_WEBHOOK", "")
CLINICO_EMAIL = os.getenv("CLINICO_EMAIL", "")


def _fetch_id_caso(guid: str) -> str | None:
    with db.get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT ID_CASO FROM Entrevista WHERE GUID_Entrevista = %s", (guid,))
        row = cur.fetchone()
        return row[0] if row else None


def _notify_clinico(req: AuditEthicsRequest, result: AuditEthicsResponse) -> None:
    if not N8N_ALERTA_WEBHOOK or not result.sesgo_emocional_detectado:
        return
    payload = {
        "guid": req.guid,
        "id_caso": _fetch_id_caso(req.guid),
        "triage_real": req.triage_real.value,
        "prediccion_ia": req.prediccion_ia.value,
        "score_ansiedad_ia": round(req.score_ansiedad_ia, 2),
        "motivo_fallo": result.motivo_fallo,
        "accion_correctiva": result.accion_correctiva,
        "destinatario": CLINICO_EMAIL,
    }
    try:
        httpx.post(N8N_ALERTA_WEBHOOK, json=payload, timeout=5.0)
    except httpx.HTTPError:
        pass


def evaluate(req: AuditEthicsRequest) -> AuditEthicsResponse:
    validacion = Validacion.PENDIENTE
    motivo: str | None = None
    accion: str | None = None
    sesgo = False

    if req.prediccion_ia == req.triage_real:
        validacion = Validacion.ACIERTO
    elif under_triage(req.prediccion_ia, req.triage_real):
        validacion = Validacion.UNDER_TRIAGE
        if req.score_ansiedad_ia >= ANXIETY_BIAS_THRESHOLD:
            sesgo = True
            motivo = (
                f"Under-triage por sesgo emocional: predicción {req.prediccion_ia.value} "
                f"vs real {req.triage_real.value} con score ansiedad {req.score_ansiedad_ia:.2f}."
            )
            accion = "Reentrenar con class_weight reforzado en C1/C2 y revisar prompts del LLM."
        else:
            motivo = (
                f"Under-triage clínico: predicción {req.prediccion_ia.value} vs real {req.triage_real.value}."
            )
            accion = "Revisión humana del caso y refuerzo de features clínicas."
    elif over_triage(req.prediccion_ia, req.triage_real):
        validacion = Validacion.OVER_TRIAGE
        motivo = (
            f"Over-triage: predicción {req.prediccion_ia.value} más urgente que real {req.triage_real.value}."
        )
        accion = "Monitorizar tasa de falsos positivos. Sin riesgo clínico."

    return AuditEthicsResponse(
        guid=req.guid,
        validacion=validacion,
        motivo_fallo=motivo,
        accion_correctiva=accion,
        sesgo_emocional_detectado=sesgo,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/run", response_model=AuditEthicsResponse)
def run(req: AuditEthicsRequest) -> AuditEthicsResponse:
    started = datetime.utcnow()
    result = evaluate(req)

    db.upsert_texto_procesado(req.guid, {"triage_real": req.triage_real.value})

    db.upsert_prediccion(
        req.guid,
        validacion=result.validacion,
        motivo_fallo=result.motivo_fallo,
        accion_correctiva=result.accion_correctiva,
    )
    db.update_entrevista_estado(req.guid, EntrevistaEstado.AUDITADO)

    db.log_task(
        TaskLogEntry(
            guid=req.guid,
            service_name="audit-ethics",
            timestamp_inicio=started,
            timestamp_fin=datetime.utcnow(),
            status=TaskStatus.OK,
            payload_resultado={
                "validacion": result.validacion.value,
                "sesgo_emocional_detectado": result.sesgo_emocional_detectado,
                "motivo_fallo": result.motivo_fallo,
            },
        )
    )

    _notify_clinico(req, result)

    return result
