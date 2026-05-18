from __future__ import annotations

from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

import triage_helpers as th


def task_evaluate_batch(**context):
    guids = th.list_guids_in_state("PREDICHO", limit=500)
    results = []
    for guid in guids:
        triage_real = th.fetch_triage_real(guid)
        prediccion, _ = th.fetch_prediccion(guid)
        if not triage_real or not prediccion:
            continue
        results.append(
            th.post_json(
                "evaluation",
                "/run",
                {"guid": guid, "prediccion_ia": prediccion, "triage_real": triage_real},
            )
        )
    return {"evaluated": len(results)}


with DAG(
    dag_id="dag_evaluation",
    description="Batch evaluation sobre PREDICHO con triage_real conocido",
    start_date=datetime(2026, 5, 1),
    schedule="@hourly",
    catchup=False,
    tags=["triage", "ml", "batch"],
    default_args=th.DEFAULT_ARGS,
) as dag:
    PythonOperator(task_id="evaluate_batch", python_callable=task_evaluate_batch)
