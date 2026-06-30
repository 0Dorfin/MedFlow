from __future__ import annotations
import json
import os
from collections import Counter, defaultdict
from pathlib import Path
from triage_common.evaluation import accuracy, dominant_group, group_from_filename
from triage_common.llm import LLMClient, LLMConfig
from triage_common.search import select_normalization_backend

_BAD_CHARS = set('{}[]"\\')

def _sanitize(item: str) -> str:
    cleaned = "".join(c for c in str(item) if c not in _BAD_CHARS).strip()
    return cleaned.strip(" ,;:.-")

def _read_text(path: Path) -> str:
    data = path.read_bytes()
    for enc in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")

def _entities(payload: dict) -> list[str]:
    raw = payload.get("entidades") or payload.get("entities") or []
    if not isinstance(raw, list):
        return []
    cleaned = [_sanitize(x) for x in raw]
    return [c for c in cleaned if c and 2 <= len(c) <= 120]

def main() -> int:
    repo = Path(__file__).resolve().parents[3]
    prompts = repo / "data" / "prompts"
    transcripts = repo / "data" / "fareez_dataset" / "transcripts"
    per_group = int(os.getenv("EVAL_PER_GROUP", "3"))
    norm_name = os.getenv("NORMALIZATION_BACKEND", "local")

    by_group: dict = defaultdict(list)
    for f in sorted(transcripts.glob("*.txt")):
        by_group[group_from_filename(f.name)].append(f)
    sample = [f for files in by_group.values() for f in files[:per_group]]

    client = LLMClient(config=LLMConfig.from_env(), prompts_dir=prompts)
    norm = select_normalization_backend(norm_name)

    preds: list = []
    truths: list = []
    confusion: dict = Counter()
    for f in sample:
        texto = _read_text(f).strip()
        payload = client.render_and_generate_json(
            "extract_entities.j2", context={"texto": texto}
        )
        mapped, _ = norm.normalize_many(_entities(payload))
        pred = dominant_group(mapped)
        truth = group_from_filename(f.name)
        preds.append(pred)
        truths.append(truth)
        pred_label = pred.value if pred else "None"
        confusion[(truth.value, pred_label)] += 1
        print(f"{f.name}: truth={truth.value} pred={pred_label}")

    acc = accuracy(preds, truths)
    print(f"\nN={len(sample)} backend_llm={os.getenv('LLM_BACKEND','local')} norm={norm_name}")
    print(f"accuracy_grupo={acc:.2f}")
    print("confusion (truth->pred):")
    for (truth, pred), n in sorted(confusion.items()):
        print(f"  {truth} -> {pred}: {n}")

    result = {"accuracy_grupo": round(acc, 4), "n": len(sample)}
    (repo / "services" / "_common" / "eval-result.json").write_text(
        json.dumps(result), encoding="utf-8"
    )
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
