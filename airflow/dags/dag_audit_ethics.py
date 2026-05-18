from __future__ import annotations

from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

import triage_helpers as th


def task_audit_batch(**context):
    guids = th.list_guids_in_state("EVALUADO", limit=500)
    audited = 0
    sesgos = 0
    for guid in guids:
        triage_real = th.fetch_triage_real(guid)
        prediccion, score = th.fetch_prediccion(guid)
        if not triage_real or not prediccion:
            continue
        result = th.post_json(
            "audit_ethics",
            "/run",
            {
                "guid": guid,
                "prediccion_ia": prediccion,
                "triage_real": triage_real,
                "score_ansiedad_ia": score or 0.0,
            },
        )
        audited += 1
        if result.get("sesgo_emocional_detectado"):
            sesgos += 1
    return {"audited": audited, "sesgos_detectados": sesgos}


with DAG(
    dag_id="dag_audit_ethics",
    description="Batch auditoria etica sobre EVALUADO (detecta under-triage por sesgo)",
    start_date=datetime(2026, 5, 1),
    schedule="@hourly",
    catchup=False,
    tags=["triage", "ml", "audit"],
    default_args=th.DEFAULT_ARGS,
) as dag:
    PythonOperator(task_id="audit_batch", python_callable=task_audit_batch)
