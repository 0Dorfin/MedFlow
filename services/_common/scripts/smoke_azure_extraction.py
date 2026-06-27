from __future__ import annotations

import sys
from pathlib import Path

from triage_common.llm import LLMConfig, LLMClient


_BAD_CHARS = set('{}[]"\\')


def sanitize(item: str) -> str:
    cleaned = "".join(c for c in str(item) if c not in _BAD_CHARS).strip()
    return cleaned.strip(" ,;:.-")


def normalize_entities(payload: dict) -> list[str]:
    raw = payload.get("entidades") or payload.get("entities") or []
    if not isinstance(raw, list):
        return []
    cleaned = [sanitize(x) for x in raw]
    return [c for c in cleaned if c and 2 <= len(c) <= 120]


def main() -> int:
    repo_root = Path(__file__).resolve().parents[3]
    prompts_dir = repo_root / "data" / "prompts"
    default_sample = repo_root / "data" / "fareez_dataset" / "transcripts" / "CAR0001.txt"
    sample_path = Path(sys.argv[1]) if len(sys.argv) > 1 else default_sample

    texto = sample_path.read_text(encoding="utf-8").strip()

    config = LLMConfig.from_env()
    client = LLMClient(config=config, prompts_dir=prompts_dir)

    payload = client.render_and_generate_json(
        "extract_entities.j2", context={"texto": texto}
    )
    entidades = normalize_entities(payload)

    print(f"backend={config.backend} deployment={config.azure_deployment}")
    print(f"sample={sample_path.name} chars={len(texto)}")
    print(f"raw={payload}")
    print(f"entidades={entidades}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
