from __future__ import annotations

from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

import triage_helpers as th


def task_predict(**context):
    guid = th.guid_from_context(context)
    resumen = th.fetch_resumen(guid)
    terms = th.fetch_entidades_normalizadas(guid)
    return th.post_json(
        "ml_prediction",
        "/run",
        {"guid": guid, "texto": resumen, "entidades_normalizadas": terms},
    )


with DAG(
    dag_id="dag_prediction_phase_2",
    description="Fase 2: ml-prediction sobre un GUID enriquecido",
    start_date=datetime(2026, 5, 1),
    schedule=None,
    catchup=False,
    tags=["triage", "fase2"],
    default_args=th.DEFAULT_ARGS,
) as dag:
    PythonOperator(task_id="predict", python_callable=task_predict)
