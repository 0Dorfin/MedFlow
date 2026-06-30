from __future__ import annotations
import json
import os
from pathlib import Path

def main() -> int:
    base_dir = Path(__file__).resolve().parents[1]
    baseline = json.loads((base_dir / "eval-baseline.json").read_text(encoding="utf-8"))
    result = json.loads((base_dir / "eval-result.json").read_text(encoding="utf-8"))

    base_acc = float(baseline["accuracy_grupo"])
    curr_acc = float(result["accuracy_grupo"])
    delta = curr_acc - base_acc
    max_drop = float(os.getenv("MAX_DROP", "0.05"))

    print(f"baseline={base_acc:.2f} actual={curr_acc:.2f} delta={delta:+.2f}")
    if delta < -max_drop:
        print(f"REGRESIÓN: cayo más de {max_drop}")
        return 1
    print("OK: sin regresión")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
