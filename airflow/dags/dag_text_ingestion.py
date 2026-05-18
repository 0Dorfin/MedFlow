from __future__ import annotations

from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

import triage_helpers as th


def task_preprocessing(**context):
    guid = th.guid_from_context(context)
    resumen = th.fetch_resumen(guid)
    return th.post_json("preprocessing", "/run", {"guid": guid, "texto": resumen})


def task_extraction(**context):
    guid = th.guid_from_context(context)
    resumen = th.fetch_resumen(guid)
    return th.post_json("llm_extraction", "/run", {"guid": guid, "texto": resumen, "language": "es"})


def task_normalization(**context):
    guid = th.guid_from_context(context)
    entidades = th.fetch_entidades_extraidas(guid)
    return th.post_json("llm_normalization", "/run", {"guid": guid, "entidades_extraidas": entidades})


def task_labeling(**context):
    guid = th.guid_from_context(context)
    resumen = th.fetch_resumen(guid)
    raw = th.fetch_entidades_normalizadas(guid)
    entidades = [
        {
            "termino_clinico": t,
            "prioridad_sugerida": "C4",
            "grupo_clinico": "OTRO",
            "sintoma_original": t,
        }
        for t in raw
    ]
    return th.post_json(
        "llm_labeling",
        "/run",
        {"guid": guid, "resumen_es": resumen, "entidades_normalizadas": entidades},
    )


def task_anxiety(**context):
    guid = th.guid_from_context(context)
    resumen = th.fetch_resumen(guid)
    return th.post_json("anxiety_score", "/run", {"guid": guid, "texto": resumen})


def task_finalize(**context):
    guid = th.guid_from_context(context)
    th.update_estado(guid, "TEXTO_ENRIQUECIDO")


with DAG(
    dag_id="dag_text_ingestion",
    description="Pipeline LLM completo sobre texto (Fase 1, sin transcripcion)",
    start_date=datetime(2026, 5, 1),
    schedule=None,
    catchup=False,
    max_active_runs=3,
    tags=["triage", "fase1", "texto"],
    default_args=th.DEFAULT_ARGS,
) as dag:
    t_pre = PythonOperator(task_id="preprocessing", python_callable=task_preprocessing)
    t_ext = PythonOperator(task_id="extraction", python_callable=task_extraction)
    t_norm = PythonOperator(task_id="normalization", python_callable=task_normalization)
    t_lab = PythonOperator(task_id="labeling", python_callable=task_labeling)
    t_anx = PythonOperator(task_id="anxiety_score", python_callable=task_anxiety)
    t_fin = PythonOperator(task_id="finalize_state", python_callable=task_finalize)

    t_pre >> t_ext >> t_norm >> t_lab >> t_anx >> t_fin
