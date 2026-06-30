from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Optional

from triage_common.contracts import GrupoClinico, NormalizedEntity


_PREFIX_MAP = {
    "CAR": GrupoClinico.CAR,
    "GAS": GrupoClinico.GAS,
    "MSK": GrupoClinico.MSK,
    "RES": GrupoClinico.RES,
}


def group_from_filename(filename: str) -> GrupoClinico:
    stem = Path(filename).name
    prefix = ""
    for ch in stem:
        if ch.isalpha():
            prefix += ch
        else:
            break
    return _PREFIX_MAP.get(prefix.upper(), GrupoClinico.OTRO)


def dominant_group(entities: list[NormalizedEntity]) -> Optional[GrupoClinico]:
    if not entities:
        return None
    counts = Counter(e.grupo_clinico for e in entities)
    top = max(counts.values())
    candidates = [g for g, c in counts.items() if c == top]
    if len(candidates) == 1:
        return candidates[0]
    best: Optional[GrupoClinico] = None
    best_severity: Optional[int] = None
    for grupo in candidates:
        severity = min(
            e.prioridad_sugerida.numeric
            for e in entities
            if e.grupo_clinico == grupo
        )
        if best_severity is None or severity < best_severity:
            best_severity = severity
            best = grupo
    return best


def accuracy(
    predictions: list[GrupoClinico], truths: list[GrupoClinico]
) -> float:
    if not truths:
        return 0.0
    hits = sum(1 for p, t in zip(predictions, truths) if p == t)
    return hits / len(truths)
