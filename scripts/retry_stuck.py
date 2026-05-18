from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime

import httpx
import psycopg2


PG_DSN = "host=localhost port=5432 dbname={db} user={user} password={pw}".format(
    db=os.getenv("POSTGRES_DB", "triage_db"),
    user=os.getenv("POSTGRES_USER", "triage"),
    pw=os.getenv("POSTGRES_PASSWORD", "triage_pw"),
)
AIRFLOW = os.getenv("AIRFLOW_BASE_URL", "http://localhost:8080")
AUTH = (os.getenv("AIRFLOW_ADMIN_USER", "admin"), os.getenv("AIRFLOW_ADMIN_PASSWORD", "admin"))
DAG = os.getenv("DAG_TEXT_INGESTION", "dag_text_ingestion")
TERMINAL = ("TEXTO_ENRIQUECIDO", "MODELO_ENTRENADO", "PREDICHO", "EVALUADO", "AUDITADO")


def select_stuck() -> list[tuple[str, str]]:
    with psycopg2.connect(PG_DSN) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT GUID_Entrevista, estado FROM Entrevista "
            "WHERE origen='Dataset' AND estado NOT IN %s ORDER BY Inicio_Solicitud",
            (TERMINAL,),
        )
        return cur.fetchall()


def reset_state(guids: list[str]) -> None:
    if not guids:
        return
    with psycopg2.connect(PG_DSN) as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE Entrevista SET Estado='RECIBIDO' WHERE GUID_Entrevista = ANY(%s)",
            (guids,),
        )


def airflow_token(client: httpx.Client) -> str:
    response = client.post(
        f"{AIRFLOW}/auth/token",
        json={"username": AUTH[0], "password": AUTH[1]},
        timeout=10.0,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def trigger_dag(client: httpx.Client, token: str, guid: str, suffix: str) -> str | None:
    run_id = f"retry-{suffix}-{guid}"
    response = client.post(
        f"{AIRFLOW}/api/v2/dags/{DAG}/dagRuns",
        json={
            "conf": {"guid": guid},
            "dag_run_id": run_id,
            "logical_date": None,
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=10.0,
    )
    if response.status_code in (200, 201):
        return run_id
    print(f"  trigger fail {guid}: {response.status_code} {response.text[:120]}", file=sys.stderr)
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rate", type=float, default=0.2)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    stuck = select_stuck()
    print(f"stuck rows: {len(stuck)}")
    if args.limit > 0:
        stuck = stuck[: args.limit]
    if args.dry_run:
        for g, e in stuck[:20]:
            print(f"  {g[:8]} {e}")
        return 0

    guids = [g for g, _ in stuck]
    reset_state(guids)
    print(f"reset to RECIBIDO: {len(guids)}")

    suffix = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    ok = 0
    fail = 0
    with httpx.Client() as client:
        token = airflow_token(client)
        for i, guid in enumerate(guids, 1):
            run = trigger_dag(client, token, guid, suffix)
            if run:
                ok += 1
                print(f"[{i}/{len(guids)}] OK {guid[:8]} {run}")
            else:
                fail += 1
            time.sleep(args.rate)
    print(f"\ndone: ok={ok} fail={fail}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
