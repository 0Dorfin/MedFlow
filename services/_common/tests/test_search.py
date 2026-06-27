from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from triage_common.contracts import GrupoClinico, TriageLevel
from triage_common.search import (
    AzureSearchBackend,
    LocalDictionaryBackend,
    NormalizationError,
    select_normalization_backend,
)


class TestLocalDictionaryBackend:
    def test_maps_known_term(self):
        mapped, unmapped = LocalDictionaryBackend().normalize_many(["me ahogo"])
        assert unmapped == []
        assert mapped[0].termino_clinico == "disnea"

    def test_unmapped_for_unknown(self):
        mapped, unmapped = LocalDictionaryBackend().normalize_many(["xyzzy nonsense"])
        assert mapped == []
        assert unmapped == ["xyzzy nonsense"]


def _doc(term, prio, grupo, score):
    return {
        "termino_clinico": term,
        "prioridad_sugerida": prio,
        "grupo_clinico": grupo,
        "@search.score": score,
    }


class TestAzureSearchBackend:
    def _backend(self, results_by_term, min_score=0.0):
        client = MagicMock()
        client.search.side_effect = lambda search_text, top=1, **kw: iter(
            results_by_term.get(search_text, [])
        )
        return AzureSearchBackend(client=client, min_score=min_score)

    def test_maps_top_hit(self):
        backend = self._backend({"me ahogo": [_doc("disnea", "C1", "RES", 5.0)]})
        mapped, unmapped = backend.normalize_many(["me ahogo"])
        assert unmapped == []
        assert mapped[0].termino_clinico == "disnea"
        assert mapped[0].prioridad_sugerida == TriageLevel.C1
        assert mapped[0].grupo_clinico == GrupoClinico.RES
        assert mapped[0].sintoma_original == "me ahogo"

    def test_no_results_unmapped(self):
        backend = self._backend({})
        mapped, unmapped = backend.normalize_many(["raro"])
        assert mapped == []
        assert unmapped == ["raro"]

    def test_below_min_score_unmapped(self):
        backend = self._backend(
            {"flojo": [_doc("astenia", "C4", "OTRO", 0.2)]}, min_score=1.0
        )
        mapped, unmapped = backend.normalize_many(["flojo"])
        assert unmapped == ["flojo"]


class TestSelector:
    def test_local(self):
        assert isinstance(select_normalization_backend("local"), LocalDictionaryBackend)

    def test_azure(self):
        assert isinstance(select_normalization_backend("azure"), AzureSearchBackend)

    def test_unknown(self):
        with pytest.raises(NormalizationError):
            select_normalization_backend("marte")
