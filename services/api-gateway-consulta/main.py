from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query

from triage_common import db


app = FastAPI(title="MedFlow API Gateway Consulta", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/historial")
def historial(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    return db.fetch_historial(limit=limit, offset=offset)


@app.get("/resultado/{guid}")
def resultado(guid: str) -> dict:
    record = db.fetch_resultado_completo(guid)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Entrevista no encontrada: {guid}")
    return record
