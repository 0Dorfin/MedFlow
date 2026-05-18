from __future__ import annotations

from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.api.common.trigger_dag import trigger_dag

import triage_helpers as th


def task_batch_trigger(**context):
    guids = th.list_guids_in_state("RECIBIDO", limit=500)
    triggered = []
    for guid in guids:
        run_id = f"enrich-{guid}-{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}"
        trigger_dag(
            dag_id="dag_text_ingestion",
            run_id=run_id,
            conf={"guid": guid},
            replace_microseconds=False,
        )
        triggered.append(guid)
    return {"triggered": triggered, "count": len(triggered)}


with DAG(
    dag_id="dag_llm_enrichment",
    description="Batch: dispara dag_text_ingestion sobre todas las Entrevista en RECIBIDO",
    start_date=datetime(2026, 5, 1),
    schedule="@hourly",
    catchup=False,
    tags=["triage", "fase1", "batch"],
    default_args=th.DEFAULT_ARGS,
) as dag:
    PythonOperator(task_id="batch_trigger", python_callable=task_batch_trigger)
