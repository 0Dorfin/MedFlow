from __future__ import annotations

import sys

from triage_common.search import select_normalization_backend


def main() -> int:
    terms = sys.argv[1:] or [
        "me ahogo",
        "presion fuerte",
        "no me llega el aire",
        "vomitos",
        "xyzzy nonsense",
    ]
    backend = select_normalization_backend("azure")
    mapped, unmapped = backend.normalize_many(terms)
    for m in mapped:
        print(
            f"  {m.sintoma_original!r} -> {m.termino_clinico} / "
            f"{m.prioridad_sugerida.value} / {m.grupo_clinico.value}"
        )
    print(f"unmapped={unmapped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
