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
NORM_URL = os.getenv("NORM_URL", "http://localhost:9111/run")


def select_targets() -> list[tuple[str, list[str]]]:
    sql = (
        "SELECT t.guid, t.entidades_extraidas_es "
        "FROM Texto_Procesado t "
        "WHERE t.triage_real IS NOT NULL"
    )
    with psycopg2.connect(PG_DSN) as conn, conn.cursor() as cur:
        cur.execute(sql)
        out = []
        for guid, ents in cur.fetchall():
            if isinstance(ents, str):
                ents = json.loads(ents)
            ents = ents or []
            if ents:
                out.append((guid, list(ents)))
        return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rate", type=float, default=0.1)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    targets = select_targets()
    if args.limit > 0:
        targets = targets[: args.limit]
    print(f"targets: {len(targets)}")

    ok = 0
    fail = 0
    matched_total = 0
    with httpx.Client(timeout=120.0) as client:
        for i, (guid, ents) in enumerate(targets, 1):
            try:
                r = client.post(NORM_URL, json={"guid": guid, "entidades_extraidas": ents})
                r.raise_for_status()
                resp = r.json()
                n_norm = len(resp.get("entidades_normalizadas", []))
                matched_total += n_norm
                ok += 1
                if i % 25 == 0 or i == len(targets):
                    print(f"[{i}/{len(targets)}] last guid={guid[:8]} ents={len(ents)} norm={n_norm}")
            except httpx.HTTPError as exc:
                fail += 1
                print(f"[{i}/{len(targets)}] FAIL {guid[:8]}: {exc}", file=sys.stderr)
            time.sleep(args.rate)

    avg = matched_total / max(1, ok)
    print(f"\ndone ok={ok} fail={fail} avg_normalized/case={avg:.2f}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
