from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any, Iterable, Optional

import psycopg2
import requests


SERVICE_URLS = {
    "preprocessing": os.getenv("PREPROCESSING_URL", "http://preprocessing:9101"),
    "transcripcion": os.getenv("TRANSCRIPCION_URL", "http://transcripcion:9100"),
    "llm_extraction": os.getenv("LLM_EXTRACTION_URL", "http://llm-extraction:9110"),
    "llm_normalization": os.getenv("LLM_NORMALIZATION_URL", "http://llm-normalization:9111"),
    "llm_labeling": os.getenv("LLM_LABELING_URL", "http://llm-labeling:9112"),
    "anxiety_score": os.getenv("ANXIETY_SCORE_URL", "http://anxiety-score:9113"),
    "dataset_builder": os.getenv("DATASET_BUILDER_URL", "http://dataset-builder:9120"),
    "ml_training": os.getenv("ML_TRAINING_URL", "http://ml-training:9121"),
    "ml_prediction": os.getenv("ML_PREDICTION_URL", "http://ml-prediction:9122"),
    "evaluation": os.getenv("EVALUATION_URL", "http://evaluation:9123"),
    "audit_ethics": os.getenv("AUDIT_ETHICS_URL", "http://audit-ethics:9124"),
}

N8N_ERROR_WEBHOOK = os.getenv("N8N_ERROR_WEBHOOK", "")

DEFAULT_DB = {
    "host": os.getenv("POSTGRES_HOST", "postgres"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
    "user": os.getenv("POSTGRES_USER", "triage"),
    "password": os.getenv("POSTGRES_PASSWORD", "triage_pw"),
    "dbname": os.getenv("POSTGRES_DB", "triage_db"),
}


def db_conn() -> psycopg2.extensions.connection:
    return psycopg2.connect(**DEFAULT_DB)


def post_json(service: str, path: str, payload: dict, timeout: int = 240) -> dict:
    url = f"{SERVICE_URLS[service].rstrip('/')}/{path.lstrip('/')}"
    r = requests.post(url, json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json()


def fetch_resumen(guid: str) -> str:
    with db_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT resumen_es FROM Texto_Procesado WHERE guid = %s", (guid,))
        row = cur.fetchone()
        if not row or not row[0]:
            raise ValueError(f"No resumen_es para guid {guid}")
        return row[0]


def fetch_audio_url(guid: str) -> str:
    with db_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT URL_Audio_Original FROM Entrevista WHERE GUID_Entrevista = %s", (guid,))
        row = cur.fetchone()
        if not row or not row[0]:
            raise ValueError(f"No URL_Audio_Original para guid {guid}")
        return row[0]


def fetch_entidades_extraidas(guid: str) -> list[str]:
    with db_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT entidades_extraidas_es FROM Texto_Procesado WHERE guid = %s", (guid,)
        )
        row = cur.fetchone()
        return row[0] if row and row[0] else []


def fetch_entidades_normalizadas(guid: str) -> list[str]:
    with db_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT entidades_normalizadas_es FROM Texto_Procesado WHERE guid = %s", (guid,)
        )
        row = cur.fetchone()
        return row[0] if row and row[0] else []


def fetch_triage_real(guid: str) -> Optional[str]:
    with db_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT triage_real FROM Texto_Procesado WHERE guid = %s", (guid,))
        row = cur.fetchone()
        return row[0] if row else None


def fetch_prediccion(guid: str) -> tuple[Optional[str], Optional[float]]:
    with db_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT prediccion_ia, score_ansiedad_ia FROM Prediccion WHERE guid = %s",
            (guid,),
        )
        row = cur.fetchone()
        if not row:
            return None, None
        return row[0], (float(row[1]) if row[1] is not None else None)


def list_guids_in_state(estado: str, limit: int = 200) -> list[str]:
    with db_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT GUID_Entrevista FROM Entrevista WHERE Estado = %s ORDER BY Inicio_Solicitud LIMIT %s",
            (estado, limit),
        )
        return [r[0] for r in cur.fetchall()]


def update_estado(guid: str, estado: str) -> None:
    with db_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE Entrevista SET Estado = %s WHERE GUID_Entrevista = %s",
            (estado, guid),
        )


def notify_n8n(context: dict, error: BaseException) -> None:
    if not N8N_ERROR_WEBHOOK:
        return
    task = context.get("task_instance")
    payload = {
        "dag_id": context.get("dag").dag_id if context.get("dag") else None,
        "task_id": task.task_id if task else None,
        "run_id": context.get("run_id"),
        "guid": (context.get("dag_run").conf or {}).get("guid") if context.get("dag_run") else None,
        "error": str(error),
        "ts": datetime.utcnow().isoformat(),
    }
    try:
        requests.post(N8N_ERROR_WEBHOOK, json=payload, timeout=5)
    except Exception:
        pass


def on_failure_callback(context: dict) -> None:
    exc = context.get("exception")
    if isinstance(exc, BaseException):
        notify_n8n(context, exc)
    else:
        notify_n8n(context, RuntimeError(str(exc)))


DEFAULT_ARGS = {
    "owner": "triage",
    "retries": 2,
    "retry_delay": timedelta(seconds=15),
    "on_failure_callback": on_failure_callback,
}


def guid_from_context(context: dict) -> str:
    conf = (context.get("dag_run").conf or {}) if context.get("dag_run") else {}
    guid = conf.get("guid")
    if not guid:
        raise ValueError("dag_run.conf debe incluir 'guid'")
    return guid
