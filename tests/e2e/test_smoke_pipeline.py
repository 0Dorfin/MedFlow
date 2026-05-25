from __future__ import annotations

import httpx
import pytest


TRIAGE_LEVELS = {"C1", "C2", "C3", "C4", "C5"}
TEXTO_CLINICO = (
    "Tengo una presion muy fuerte en el pecho, como un elefante encima, "
    "me cuesta mucho respirar y tengo miedo de morirme"
)


@pytest.mark.e2e
def test_smoke_pipeline_texto(stack_urls, poll_resultado, enriched_states):
    resp = httpx.post(
        f"{stack_urls['ingesta']}/ingesta",
        data={"texto": TEXTO_CLINICO, "origen": "MVP"},
        timeout=30.0,
    )
    assert resp.status_code == 200, resp.text
    guid = resp.json()["guid"]
    assert guid

    record = poll_resultado(stack_urls["consulta"], guid)

    estado = record.get("estado") or record.get("Estado")
    assert estado in enriched_states

    assert record.get("triage_real") in TRIAGE_LEVELS
    assert record.get("justificacion_llm")

    entidades = record.get("entidades_normalizadas_es")
    assert entidades

    score = record.get("score_ansiedad")
    assert score is not None
    assert 0.0 <= float(score) <= 1.0
