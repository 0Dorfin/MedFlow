from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import requests
import streamlit as st


INGESTA_URL = os.getenv("API_GATEWAY_INGESTA_URL", "http://api-gateway-ingesta:8000")
CONSULTA_URL = os.getenv("API_GATEWAY_CONSULTA_URL", "http://api-gateway-consulta:8001")
PREPROCESSING_URL = os.getenv("PREPROCESSING_URL", "http://preprocessing:9101")
EXTRACTION_URL = os.getenv("LLM_EXTRACTION_URL", "http://llm-extraction:9110")
NORMALIZATION_URL = os.getenv("LLM_NORMALIZATION_URL", "http://llm-normalization:9111")
LABELING_URL = os.getenv("LLM_LABELING_URL", "http://llm-labeling:9112")
ANXIETY_URL = os.getenv("ANXIETY_SCORE_URL", "http://anxiety-score:9113")
PREDICTION_URL = os.getenv("ML_PREDICTION_URL", "http://ml-prediction:9122")
EVALUATION_URL = os.getenv("EVALUATION_URL", "http://evaluation:9123")
AUDIT_URL = os.getenv("AUDIT_ETHICS_URL", "http://audit-ethics:9124")

LEVELS = {
    "C1": {"color": "#d62828", "label": "Rojo", "minutes": "0", "desc": "Emergencia"},
    "C2": {"color": "#f77f00", "label": "Naranja", "minutes": "10", "desc": "Muy urgente"},
    "C3": {"color": "#fcbf49", "label": "Amarillo", "minutes": "60", "desc": "Urgente"},
    "C4": {"color": "#43aa8b", "label": "Verde", "minutes": "120", "desc": "Menos urgente"},
    "C5": {"color": "#277da1", "label": "Azul", "minutes": "240", "desc": "No urgente"},
}


@dataclass
class StepResult:
    name: str
    ok: bool = False
    duration_ms: float = 0.0
    detail: Any = None
    error: Optional[str] = None


@dataclass
class PipelineResult:
    guid: Optional[str] = None
    steps: list[StepResult] = field(default_factory=list)
    final: dict[str, Any] = field(default_factory=dict)


def call_post(url: str, payload: dict, timeout: int = 180) -> dict:
    r = requests.post(url, json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json()


def call_post_form(url: str, data: dict, files: Optional[dict] = None, timeout: int = 60) -> dict:
    r = requests.post(url, data=data, files=files or {}, timeout=timeout)
    r.raise_for_status()
    return r.json()


def call_get(url: str, timeout: int = 30) -> dict:
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return r.json()


def run_step(name: str, fn) -> StepResult:
    started = time.time()
    try:
        detail = fn()
        return StepResult(name=name, ok=True, duration_ms=(time.time() - started) * 1000, detail=detail)
    except requests.HTTPError as exc:
        body = ""
        try:
            body = exc.response.text[:200]
        except Exception:
            body = str(exc)
        return StepResult(name=name, ok=False, duration_ms=(time.time() - started) * 1000, error=f"HTTP {exc.response.status_code}: {body}")
    except Exception as exc:
        return StepResult(name=name, ok=False, duration_ms=(time.time() - started) * 1000, error=str(exc))


def run_pipeline(
    texto: str,
    id_caso: Optional[str],
    origen: str,
    ground_truth: Optional[str],
) -> PipelineResult:
    result = PipelineResult()
    status_box = st.empty()

    def step(label: str, fn):
        with status_box.container():
            st.info(f"Ejecutando: {label}")
        r = run_step(label, fn)
        result.steps.append(r)
        return r

    def render_progress():
        with status_box.container():
            for s in result.steps:
                icon = "OK" if s.ok else "ERROR"
                col1, col2, col3 = st.columns([1, 5, 2])
                col1.write(icon)
                col2.write(s.name)
                col3.write(f"{s.duration_ms:.0f} ms")
                if not s.ok:
                    st.error(s.error)

    data = {"texto": texto, "origen": origen}
    if id_caso:
        data["id_caso"] = id_caso

    r_ing = step("ingesta", lambda: call_post_form(f"{INGESTA_URL}/ingesta", data=data))
    render_progress()
    if not r_ing.ok:
        return result
    guid = r_ing.detail["guid"]
    result.guid = guid

    base = {"guid": guid, "texto": texto}

    r_pre = step("preprocessing", lambda: call_post(f"{PREPROCESSING_URL}/run", base))
    render_progress()
    if not r_pre.ok:
        return result
    cleaned = r_pre.detail.get("texto_preprocesado", texto)

    r_ext = step("llm-extraction", lambda: call_post(f"{EXTRACTION_URL}/run", {"guid": guid, "texto": cleaned, "language": "es"}))
    render_progress()
    if not r_ext.ok:
        return result
    entidades = r_ext.detail.get("entidades", [])

    r_norm = step("llm-normalization", lambda: call_post(f"{NORMALIZATION_URL}/run", {"guid": guid, "entidades_extraidas": entidades}))
    render_progress()
    if not r_norm.ok:
        return result
    entidades_normalizadas = r_norm.detail.get("entidades_normalizadas", [])
    no_mapeadas = r_norm.detail.get("no_mapeadas", [])

    r_lab = step("llm-labeling", lambda: call_post(f"{LABELING_URL}/run", {"guid": guid, "resumen_es": cleaned, "entidades_normalizadas": entidades_normalizadas}))
    render_progress()
    if not r_lab.ok:
        return result
    triage_llm = r_lab.detail.get("triage")
    justificacion = r_lab.detail.get("justificacion", "")

    r_anx = step("anxiety-score", lambda: call_post(f"{ANXIETY_URL}/run", base))
    render_progress()
    if not r_anx.ok:
        return result
    score_ansiedad = r_anx.detail.get("score_ansiedad", 0.0)

    pred_terms = [e["termino_clinico"] for e in entidades_normalizadas]
    r_pred = step("ml-prediction", lambda: call_post(f"{PREDICTION_URL}/run", {"guid": guid, "texto": cleaned, "entidades_normalizadas": pred_terms}))
    render_progress()
    prediccion_ia = None
    score_ansiedad_ia = None
    probabilidades = {}
    if r_pred.ok:
        prediccion_ia = r_pred.detail.get("prediccion_ia")
        score_ansiedad_ia = r_pred.detail.get("score_ansiedad_ia")
        probabilidades = r_pred.detail.get("probabilidades", {})

    validacion = None
    motivo_fallo = None
    sesgo_emocional = False
    if ground_truth and prediccion_ia:
        r_audit = step(
            "audit-ethics",
            lambda: call_post(
                f"{AUDIT_URL}/run",
                {
                    "guid": guid,
                    "prediccion_ia": prediccion_ia,
                    "triage_real": ground_truth,
                    "score_ansiedad_ia": score_ansiedad_ia or 0.0,
                },
            ),
        )
        render_progress()
        if r_audit.ok:
            validacion = r_audit.detail.get("validacion")
            motivo_fallo = r_audit.detail.get("motivo_fallo")
            sesgo_emocional = r_audit.detail.get("sesgo_emocional_detectado", False)

    result.final = {
        "guid": guid,
        "triage_llm": triage_llm,
        "justificacion": justificacion,
        "entidades": entidades,
        "entidades_normalizadas": entidades_normalizadas,
        "no_mapeadas": no_mapeadas,
        "score_ansiedad": score_ansiedad,
        "prediccion_ia": prediccion_ia,
        "score_ansiedad_ia": score_ansiedad_ia,
        "probabilidades": probabilidades,
        "ground_truth": ground_truth,
        "validacion": validacion,
        "motivo_fallo": motivo_fallo,
        "sesgo_emocional": sesgo_emocional,
        "texto_preprocesado": cleaned,
    }
    return result


def render_manchester_strip(active: Optional[str]) -> None:
    cols = st.columns(5)
    for col, code in zip(cols, ["C1", "C2", "C3", "C4", "C5"]):
        info = LEVELS[code]
        is_active = code == active
        border = "4px" if is_active else "1px"
        opacity = "1.0" if is_active else "0.45"
        col.markdown(
            f"""
            <div style="border: {border} solid {info['color']}; border-radius: 8px;
                        padding: 10px; background: {info['color']}22; opacity: {opacity};
                        text-align: center;">
                <div style="font-size: 22px; font-weight: 700; color: {info['color']};">{code}</div>
                <div style="font-size: 12px; color: #444;">{info['label']}</div>
                <div style="font-size: 11px; color: #666;">{info['minutes']} min</div>
                <div style="font-size: 10px; color: #888;">{info['desc']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_results(final: dict) -> None:
    triage_ia = final.get("prediccion_ia") or final.get("triage_llm")
    if not triage_ia:
        st.error("Pipeline no produjo triage.")
        return

    st.subheader("Resultado del triaje")
    render_manchester_strip(triage_ia)

    col_a, col_b = st.columns([3, 1])
    info = LEVELS.get(triage_ia, {})
    col_a.markdown(
        f"""
        <div style="background: {info.get('color','#222')}1a; border-left: 6px solid {info.get('color','#222')};
                    padding: 14px 18px; border-radius: 6px; margin-top: 14px;">
            <div style="font-size: 14px; color: #555;">Nivel Manchester predicho</div>
            <div style="font-size: 30px; font-weight: 700; color: {info.get('color','#222')}; margin-bottom: 6px;">
                {triage_ia} {info.get('label','')}
            </div>
            <div style="color: #333; font-size: 15px;">{final.get('justificacion','')}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    col_b.metric("Score ansiedad", f"{final.get('score_ansiedad',0):.2f}")
    if final.get("score_ansiedad_ia") is not None:
        col_b.metric("Score ansiedad IA", f"{final['score_ansiedad_ia']:.2f}")

    if final.get("ground_truth"):
        gt = final["ground_truth"]
        val = final.get("validacion")
        if val == "Acierto":
            st.success(f"Validación: Acierto (predicción IA = real {gt})")
        elif val == "Under-triage":
            st.error(
                f"Validación: UNDER-TRIAGE — IA predijo {final['prediccion_ia']}, real {gt}."
            )
            if final.get("sesgo_emocional"):
                st.warning(f"Sesgo emocional detectado: {final.get('motivo_fallo','')}")
        elif val == "Over-triage":
            st.warning(f"Validación: Over-triage — IA predijo {final['prediccion_ia']}, real {gt}.")

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Entidades extraídas** (LLM crudo)")
        if final["entidades"]:
            st.write(", ".join(final["entidades"]))
        else:
            st.caption("—")
    with col2:
        st.markdown("**Entidades normalizadas** (diccionario cerrado)")
        if final["entidades_normalizadas"]:
            for e in final["entidades_normalizadas"]:
                clr = LEVELS.get(e["prioridad_sugerida"], {}).get("color", "#888")
                st.markdown(
                    f"<span style='background:{clr}22; color:{clr}; padding:2px 8px;"
                    f"border-radius:10px; font-size:12px; margin-right:4px;'>"
                    f"{e['termino_clinico']} · {e['prioridad_sugerida']} · {e['grupo_clinico']}</span>",
                    unsafe_allow_html=True,
                )
        else:
            st.caption("—")
        if final["no_mapeadas"]:
            st.caption(f"No mapeadas: {', '.join(final['no_mapeadas'])}")

    if final.get("probabilidades"):
        st.divider()
        st.markdown("**Probabilidades del modelo ML**")
        cols = st.columns(5)
        for col, code in zip(cols, ["C1", "C2", "C3", "C4", "C5"]):
            prob = final["probabilidades"].get(code, 0.0)
            col.metric(code, f"{prob*100:.1f}%")

    with st.expander("Detalles técnicos (JSON)"):
        st.code(json.dumps(final, indent=2, ensure_ascii=False), language="json")


def main() -> None:
    st.set_page_config(page_title="TriageIA", layout="wide")
    st.title("TriageIA - Sistema de Triaje Manchester")
    st.caption("Curso de especializacion IA-BD 25/26 - Proyecto 3")

    with st.sidebar:
        st.header("Entrada")
        texto = st.text_area(
            "Texto del paciente",
            value="Doctor, presion fuerte en el pecho y me he desmayado dos veces",
            height=140,
        )
        id_caso = st.text_input("ID_CASO (opcional)", value="")
        origen = st.selectbox("Origen", ["MVP", "Simulacion", "Dataset"], index=0)
        ground_truth = st.selectbox(
            "Ground truth (opcional, para evaluación)",
            ["", "C1", "C2", "C3", "C4", "C5"],
            index=0,
        )
        submit = st.button("Procesar", type="primary", use_container_width=True)

    with st.sidebar:
        st.divider()
        st.caption("Niveles Manchester")
        for code, info in LEVELS.items():
            st.markdown(
                f"<span style='color:{info['color']}; font-weight:600;'>{code} {info['label']}</span> "
                f"<span style='color:#888; font-size:11px;'>{info['minutes']} min · {info['desc']}</span>",
                unsafe_allow_html=True,
            )

    if not submit:
        st.info(
            "Introduce el texto del paciente en la barra lateral y pulsa **Procesar**. "
            "El pipeline ejecutará: ingesta → preprocessing → extracción LLM → normalización "
            "→ etiquetado triaje → score ansiedad → predicción ML (si hay modelo) → auditoría "
            "ética (si proporcionas ground truth)."
        )
        return

    if not texto or not texto.strip():
        st.error("Texto vacío.")
        return

    result = run_pipeline(
        texto=texto.strip(),
        id_caso=id_caso.strip() or None,
        origen=origen,
        ground_truth=ground_truth or None,
    )

    if not result.final:
        st.error("Pipeline interrumpido. Revisa los pasos arriba.")
        return

    st.divider()
    render_results(result.final)
    st.caption(f"GUID: `{result.guid}`")


main()
