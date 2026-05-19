from __future__ import annotations

import argparse
import json
import os
import sys
import time

import httpx
import psycopg2


PG_DSN = "host=localhost port=5432 dbname={db} user={user} password={pw}".format(
    db=os.getenv("POSTGRES_DB", "triage_db"),
    user=os.getenv("POSTGRES_USER", "triage"),
    pw=os.getenv("POSTGRES_PASSWORD", "triage_pw"),
)
PREDICT_URL = os.getenv("PREDICT_URL", "http://localhost:9122/run")

ENRICHED_STATES = (
    "TEXTO_ENRIQUECIDO",
    "DATASET_GENERADO",
    "MODELO_ENTRENADO",
    "EVALUADO",
    "AUDITADO",
)


def select_targets() -> list[tuple[str, str, list[str]]]:
    sql = (
        "SELECT t.guid, COALESCE(t.resumen_es,''), COALESCE(t.entidades_normalizadas_es,'[]'::jsonb) "
        "FROM Texto_Procesado t "
        "JOIN Entrevista e ON e.GUID_Entrevista = t.guid "
        "WHERE t.triage_real IS NOT NULL "
        "  AND e.Estado IN %s"
    )
    with psycopg2.connect(PG_DSN) as conn, conn.cursor() as cur:
        cur.execute(sql, (ENRICHED_STATES,))
        out = []
        for guid, resumen, ents in cur.fetchall():
            if isinstance(ents, str):
                ents = json.loads(ents)
            ents = ents or []
            if resumen:
                out.append((guid, resumen, list(ents)))
        return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rate", type=float, default=0.05)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    targets = select_targets()
    if args.limit > 0:
        targets = targets[: args.limit]
    print(f"targets: {len(targets)}")

    ok = 0
    fail = 0
    with httpx.Client(timeout=30.0) as client:
        for i, (guid, texto, ents) in enumerate(targets, 1):
            try:
                r = client.post(
                    PREDICT_URL,
                    json={"guid": guid, "texto": texto, "entidades_normalizadas": ents},
                )
                r.raise_for_status()
                ok += 1
                if i % 25 == 0 or i == len(targets):
                    pred = r.json().get("prediccion_ia", "?")
                    print(f"[{i}/{len(targets)}] last guid={guid[:8]} pred={pred}")
            except httpx.HTTPError as exc:
                fail += 1
                print(f"[{i}/{len(targets)}] FAIL {guid[:8]}: {exc}", file=sys.stderr)
            time.sleep(args.rate)

    print(f"\ndone ok={ok} fail={fail}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
