from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import httpx
import psycopg2


DEFAULT_TRANSCRIPTS_DIR = Path(__file__).resolve().parent.parent / "data" / "fareez_dataset" / "transcripts"
DEFAULT_GATEWAY = os.getenv("INGESTA_URL", "http://localhost:8000/ingesta")
DEFAULT_PG_DSN = "host=localhost port=5432 dbname={db} user={user} password={pw}".format(
    db=os.getenv("POSTGRES_DB", "triage_db"),
    user=os.getenv("POSTGRES_USER", "triage"),
    pw=os.getenv("POSTGRES_PASSWORD", "triage_pw"),
)


def load_already_ingested(dsn: str) -> set[str]:
    with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id_caso FROM Entrevista WHERE origen=%s AND id_caso IS NOT NULL",
            ("Dataset",),
        )
        return {row[0] for row in cur.fetchall()}


def discover_transcripts(directory: Path) -> list[Path]:
    if not directory.is_dir():
        raise SystemExit(f"directorio no encontrado: {directory}")
    files = sorted(directory.glob("*.txt"))
    if not files:
        raise SystemExit(f"sin .txt en {directory}")
    return files


def post_ingesta(client: httpx.Client, url: str, id_caso: str, texto: str) -> dict:
    response = client.post(
        url,
        data={"texto": texto, "id_caso": id_caso, "origen": "Dataset"},
        timeout=15.0,
    )
    response.raise_for_status()
    return response.json()


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed Postgres con corpus Fareez (text-only).")
    parser.add_argument("--dir", type=Path, default=DEFAULT_TRANSCRIPTS_DIR)
    parser.add_argument("--gateway", default=DEFAULT_GATEWAY)
    parser.add_argument("--dsn", default=DEFAULT_PG_DSN)
    parser.add_argument("--rate", type=float, default=0.3, help="segundos entre POST")
    parser.add_argument("--limit", type=int, default=0, help="max casos (0 = todos)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    files = discover_transcripts(args.dir)
    already = load_already_ingested(args.dsn)
    pending = [f for f in files if f.stem not in already]
    if args.limit > 0:
        pending = pending[: args.limit]

    print(f"total transcripts : {len(files)}")
    print(f"ya ingestados     : {len(already)}")
    print(f"a procesar        : {len(pending)}")

    if args.dry_run:
        for f in pending[:10]:
            print(f"  + {f.stem}")
        if len(pending) > 10:
            print(f"  ... y {len(pending) - 10} mas")
        return 0

    if not pending:
        print("nada que hacer.")
        return 0

    ok = 0
    fail = 0
    started = time.time()
    with httpx.Client() as client:
        for i, path in enumerate(pending, start=1):
            id_caso = path.stem
            try:
                texto = path.read_text(encoding="utf-8").strip()
            except UnicodeDecodeError:
                texto = path.read_text(encoding="utf-16").strip()
            if not texto:
                print(f"[{i}/{len(pending)}] SKIP empty {id_caso}")
                continue
            try:
                resp = post_ingesta(client, args.gateway, id_caso, texto)
                ok += 1
                guid = resp.get("guid", "?")
                workflow = resp.get("workflow_id") or "-"
                print(f"[{i}/{len(pending)}] OK {id_caso} guid={guid[:8]} wf={workflow}")
            except httpx.HTTPError as exc:
                fail += 1
                print(f"[{i}/{len(pending)}] FAIL {id_caso}: {exc}", file=sys.stderr)
            time.sleep(args.rate)

    elapsed = time.time() - started
    print(f"\ndone: ok={ok} fail={fail} elapsed={elapsed:.1f}s")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
