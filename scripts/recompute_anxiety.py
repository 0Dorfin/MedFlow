from __future__ import annotations

import argparse
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
ANXIETY_URL = os.getenv("ANXIETY_URL", "http://localhost:9113/run")


def select_targets(only_origin: str | None) -> list[tuple[str, str]]:
    sql = (
        "SELECT t.guid, COALESCE(t.texto_original_en, t.resumen_es) "
        "FROM Texto_Procesado t "
        "JOIN Entrevista e ON e.GUID_Entrevista = t.guid "
        "WHERE t.triage_real IS NOT NULL"
    )
    params: list = []
    if only_origin:
        sql += " AND e.Origen = %s"
        params.append(only_origin)
    with psycopg2.connect(PG_DSN) as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return [(g, t) for g, t in cur.fetchall() if t]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rate", type=float, default=0.2)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--only-origin", default=None)
    args = parser.parse_args()

    targets = select_targets(args.only_origin)
    if args.limit > 0:
        targets = targets[: args.limit]
    print(f"targets: {len(targets)}")

    ok = 0
    fail = 0
    with httpx.Client(timeout=60.0) as client:
        for i, (guid, texto) in enumerate(targets, 1):
            try:
                r = client.post(ANXIETY_URL, json={"guid": guid, "texto": texto})
                r.raise_for_status()
                score = r.json().get("score_ansiedad")
                ok += 1
                if i % 10 == 0 or i == len(targets):
                    print(f"[{i}/{len(targets)}] last guid={guid[:8]} score={score}")
            except httpx.HTTPError as exc:
                fail += 1
                print(f"[{i}/{len(targets)}] FAIL {guid[:8]}: {exc}", file=sys.stderr)
            time.sleep(args.rate)

    print(f"\ndone ok={ok} fail={fail}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
