# CLAUDE.md — TriageIA

Instrucciones permanentes para Claude Code al trabajar en este repositorio.

## Reglas de estilo (obligatorias)

- **No comentarios en el código.** Esto incluye `#` en Python/Bash/YAML/`.env`, `--` en SQL, `//` y `/* */` en JS/TS, y docstrings (`"""..."""`) en Python. El código debe explicarse por sí mismo: nombres descriptivos, funciones pequeñas, tipos cuando aplique. Si una decisión necesita explicación, va en este `CLAUDE.md` o en `docs/`, no en el fichero de código.
- **No emojis en el código.** Ni en identificadores, ni en strings, ni en logs, ni en mensajes que se rendericen al usuario final desde el código (Streamlit, FastAPI, errores, etc.). Markdown de documentación (`README.md`, `docs/*.md`, este `CLAUDE.md`) sí puede usarlos.

Estas dos reglas aplican a todo nuevo código y a cualquier refactor de código existente. Cuando edites un fichero que ya tenga comentarios o emojis previos, retíralos en la misma pasada.

## Convenciones del proyecto

- Idioma del código: identificadores en inglés cuando son técnicos genéricos (`guid`, `status`, `payload`), en español cuando son del dominio clínico (`entidades_normalizadas_es`, `triage_real`, `Entrevista`, `score_ansiedad`).
- Esquema de Postgres: ver `infra/postgres/01-init-triage.sql`. Tablas: `Entrevista`, `Texto_Procesado`, `Prediccion`, `Task_Log`. Vista: `v_resultado_completo`.
- Niveles Manchester: `C1, C2, C3, C4, C5` (mayúsculas, con prefijo C). No usar números sueltos.
- Grupos clínicos: `RES, MSK, CAR, GAS, OTRO`.
- Diccionario cerrado de síntomas: `data/dictionaries/manchester_terms.csv`. No se inventan términos clínicos.
- Trazabilidad: todo paso del pipeline arrastra `GUID_Entrevista` y registra `timestamp_inicio`/`timestamp_fin` + `status` en `Task_Log`.

## Stack y puertos

| Servicio | Puerto host | Notas |
|---|---|---|
| Postgres | 5432 | bases `triage_db` y `airflow_db` |
| minIO API / consola | 9000 / 9001 | buckets: `audio-original`, `textos-originales`, `datasets`, `modelos` |
| Ollama (host, opcional) | 11434 | fallback local; activo solo si `LLM_PROVIDER=ollama` |
| Airflow API server | 8080 | Airflow **3.0.5** + `LocalExecutor` + `SimpleAuthManager` (admin/admin). REST: `/api/v2/...`, auth `POST /auth/token` → Bearer JWT |
| Airflow scheduler + dag-processor | interno | Airflow 3 separa `dag-processor` como proceso independiente |
| n8n | 5678 | basic auth, webhooks `/predict`, `/resultado?guid=`, `/error` |
| Transcripción (faster-whisper) | 9100 | `services/transcripcion/` (CPU `base` model) |
| Streamlit MVP | 8501 | `services/streamlit-mvp/` |
| API Gateway ingesta | 8000 | `services/api-gateway-ingesta/` |
| API Gateway consulta | 8001 | `services/api-gateway-consulta/` |
| Microservicios LLM | 9110-9113 | extraction, normalization, labeling, anxiety-score |
| ML / Dataset / Eval / Audit | 9120-9124 | dataset-builder, ml-training, ml-prediction, evaluation, audit-ethics |

Levantar / parar: `docker compose up -d` / `docker compose down`. Variables en `.env` (plantilla `.env.example`).

## LLM provider

Pluggable vía env (`services/_common/triage_common/llm.py`).

- `LLM_PROVIDER=openrouter` (default actual) → usa `OPENROUTER_API_KEY` + `OPENROUTER_MODEL` (ej. `openai/gpt-oss-120b:free`) contra `https://openrouter.ai/api/v1/chat/completions` (OpenAI-compatible). Latencia ~3-30s/call, sin contención local.
- `LLM_PROVIDER=ollama` → usa `OLLAMA_HOST` + `OLLAMA_DEFAULT_MODEL` (ej. `llama3.2:3b`). Requiere Ollama corriendo en host (`http://host.docker.internal:11434`) o container. Lento sin GPU buena.

Decisión vivida: Ollama local con qwen3:4b tuvo problemas de _thinking mode leak_ y timeouts en CPU; switch a `llama3.2:3b` mejoró pero GPU pequeña (RTX 5050) limita; final swap a OpenRouter `gpt-oss-120b:free` resolvió ambos (clases C1-C5 representadas, justificaciones clínicas razonadas, ~30s/caso completo).

Privacy caveat: con OpenRouter el texto clínico viaja a cloud — académicamente OK, prod-clínico requiere revisión legal.

## Airflow 3.x detalles operativos

- Imagen `apache/airflow:3.0.5-python3.11`.
- 3 servicios mínimos: `airflow-api-server`, `airflow-scheduler`, `airflow-dag-processor` (+ `airflow-init` one-shot).
- `SimpleAuthManager` persiste passwords en `./airflow/secrets/simple_auth_manager_passwords.json.generated` (bind-mounted, idempotente vía `airflow-init`).
- Health endpoint: `GET /api/v2/monitor/health`.
- Trigger DAG: `POST /auth/token` (basic) → Bearer → `POST /api/v2/dags/{dag_id}/dagRuns` con body `{"conf":{...}, "dag_run_id":"...", "logical_date": null}`.
- DAGs limitados via `max_active_runs=3` en `dag_text_ingestion.py` para no saturar LLM cuando se trigger en lote.

## Plan vivo

Plan completo del proyecto en `/home/dorfin/.claude/plans/fizzy-fluttering-sunrise.md`. Estructura por iteraciones (0 a 7). Estado actual: Iter 0-4 completadas; Iter 5 en curso (corpus Fareez 272 transcripts seedeados, ~150 enriquecidos, F1 provisional generado, falta drenar resto + ground truth + ML training real). Iter 6-7 pendientes.

## Fuentes del proyecto

- `guia.pdf` — infraestructura técnica (n8n+Airflow, microservicios, GUID, trazabilidad).
- `guia2.pdf` — dominio clínico (Protocolo Manchester, corpus Fareez et al., MVP Streamlit, auditoría ética). `guia2.pdf` manda en cualquier conflicto de dominio.
