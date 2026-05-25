from __future__ import annotations

import os
import time

import httpx
import pytest


INGESTA_URL = os.getenv("TRIAGE_INGESTA_URL", "http://localhost:8000")
CONSULTA_URL = os.getenv("TRIAGE_CONSULTA_URL", "http://localhost:8001")
POLL_TIMEOUT = float(os.getenv("TRIAGE_E2E_TIMEOUT", "180"))
POLL_INTERVAL = float(os.getenv("TRIAGE_E2E_INTERVAL", "3"))

ENRICHED_STATES = {
    "TEXTO_ENRIQUECIDO",
    "DATASET_GENERADO",
    "MODELO_ENTRENADO",
    "PREDICHO",
    "EVALUADO",
    "AUDITADO",
}


def pytest_configure(config):
    config.addinivalue_line("markers", "e2e: prueba end-to-end contra el stack docker")


def _service_up(url: str) -> bool:
    try:
        return httpx.get(f"{url}/health", timeout=3.0).status_code == 200
    except httpx.HTTPError:
        return False


@pytest.fixture(scope="session")
def stack_urls():
    caidos = [u for u in (INGESTA_URL, CONSULTA_URL) if not _service_up(u)]
    if caidos:
        pytest.skip(f"stack inaccesible {caidos}; ejecuta 'docker compose up -d' antes")
    return {"ingesta": INGESTA_URL, "consulta": CONSULTA_URL}


@pytest.fixture
def enriched_states():
    return ENRICHED_STATES


@pytest.fixture
def poll_resultado():
    def _poll(consulta_url, guid, hasta=ENRICHED_STATES, timeout=POLL_TIMEOUT, interval=POLL_INTERVAL):
        deadline = time.monotonic() + timeout
        ultimo = None
        while time.monotonic() < deadline:
            resp = httpx.get(f"{consulta_url}/resultado/{guid}", timeout=10.0)
            if resp.status_code == 200:
                ultimo = resp.json()
                estado = ultimo.get("estado") or ultimo.get("Estado")
                if estado in hasta:
                    return ultimo
                if estado == "ERROR":
                    raise AssertionError(f"pipeline en ERROR para {guid}: {ultimo}")
            time.sleep(interval)
        raise AssertionError(f"timeout {timeout}s esperando {hasta}; ultimo estado={ultimo}")

    return _poll
