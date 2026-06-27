from __future__ import annotations

import pytest

from triage_common.contracts import GrupoClinico, NormalizedEntity, TriageLevel
from triage_common.evaluation import accuracy, dominant_group, group_from_filename


class TestGroupFromFilename:
    def test_known_prefix(self):
        assert group_from_filename("CAR0001.txt") == GrupoClinico.CAR
        assert group_from_filename("RES0021.txt") == GrupoClinico.RES
        assert group_from_filename("MSK0009.txt") == GrupoClinico.MSK

    def test_unknown_prefix_maps_to_otro(self):
        assert group_from_filename("DER0001.txt") == GrupoClinico.OTRO
        assert group_from_filename("GEN0001.txt") == GrupoClinico.OTRO


class TestDominantGroup:
    def _ent(self, grupo, prio=TriageLevel.C4):
        return NormalizedEntity(
            termino_clinico="x",
            prioridad_sugerida=prio,
            grupo_clinico=grupo,
            sintoma_original="y",
        )

    def test_majority(self):
        ents = [
            self._ent(GrupoClinico.RES),
            self._ent(GrupoClinico.RES),
            self._ent(GrupoClinico.CAR),
        ]
        assert dominant_group(ents) == GrupoClinico.RES

    def test_tie_breaks_most_severe(self):
        ents = [
            self._ent(GrupoClinico.CAR, TriageLevel.C1),
            self._ent(GrupoClinico.RES, TriageLevel.C4),
        ]
        assert dominant_group(ents) == GrupoClinico.CAR

    def test_empty_returns_none(self):
        assert dominant_group([]) is None


class TestAccuracy:
    def test_accuracy(self):
        preds = [GrupoClinico.RES, GrupoClinico.CAR, GrupoClinico.RES]
        truths = [GrupoClinico.RES, GrupoClinico.RES, GrupoClinico.RES]
        assert accuracy(preds, truths) == pytest.approx(2 / 3)

    def test_empty(self):
        assert accuracy([], []) == 0.0
