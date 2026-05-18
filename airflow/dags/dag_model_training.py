from __future__ import annotations

from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

import triage_helpers as th


def task_build_dataset(**context):
    payload = (context.get("dag_run").conf or {}) if context.get("dag_run") else {}
    return th.post_json(
        "dataset_builder",
        "/run",
        {
            "min_rows": int(payload.get("min_rows", 5)),
            "only_origin": payload.get("only_origin"),
        },
    )


def task_train(**context):
    ti = context["ti"]
    dataset = ti.xcom_pull(task_ids="build_dataset")
    if not dataset or "url" not in dataset:
        raise ValueError("dataset-builder no devolvio url")
    return th.post_json(
        "ml_training",
        "/run",
        {"dataset_url": dataset["url"]},
        timeout=900,
    )


def task_reload_predictor(**context):
    return th.post_json("ml_prediction", "/reload", {})


with DAG(
    dag_id="dag_model_training",
    description="Construye dataset F1 y entrena modelo ML; refresca ml-prediction",
    start_date=datetime(2026, 5, 1),
    schedule="@daily",
    catchup=False,
    tags=["triage", "ml"],
    default_args=th.DEFAULT_ARGS,
) as dag:
    t_build = PythonOperator(task_id="build_dataset", python_callable=task_build_dataset)
    t_train = PythonOperator(task_id="ml_training", python_callable=task_train)
    t_reload = PythonOperator(task_id="reload_predictor", python_callable=task_reload_predictor)

    t_build >> t_train >> t_reload
