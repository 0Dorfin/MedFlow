from __future__ import annotations

import sys

from triage_common.pii import select_pii_backend


def main() -> int:
    text = " ".join(sys.argv[1:]) or (
        "Soy Juan Perez, mi telefono 600123123, me duele el pecho desde ayer"
    )
    result = select_pii_backend("azure").redact(text)
    print(f"IN : {text}")
    print(f"OUT: {result.text}")
    print(f"PII: {result.entities}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
