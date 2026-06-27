# MedFlow → Azure AI: migración para demostrar AI-103

## Contexto

MedFlow es un pipeline de triage clínico (Protocolo Manchester) hoy montado sobre stack
gratuito/local: OpenRouter (`LLMClient`), whisperx (`transcripcion`), lookup de diccionario
CSV (`dictionary.py`), minIO, Postgres en Docker, orquestación con Airflow + n8n. El objetivo
es **migrar realmente a Azure** y, al hacerlo, ejercitar de forma demostrable las habilidades
del examen **AI-103: Developing AI Apps and Agents on Azure** (vigente abril 2026, centrado en
Microsoft Foundry + agentes).

Decisiones tomadas:
- **Migración real a Azure** (provisionar y desplegar, con coste).
- **Patrón adapter, dual local/cloud** (no borrar el local). Cada backend se elige por env
  (`LLM_BACKEND=local|azure`, y equivalente por servicio). La migración a Azure es real pero
  detrás de una interfaz: el camino local gratuito sigue ejecutable para desarrollo y para que
  un reviewer del portfolio lo corra sin coste. Revisa la decisión previa de "reemplazar".
- **4 dominios** que encajan con triage por voz/texto. **Se omite computer vision (10-15%)**
  por no tener señal visual clínica en el flujo actual (decisión confirmada).
- **Proyecto de portfolio**: prioridad cobertura máxima demostrable del temario. Artefacto
  estrella: `docs/azure/ai-103-coverage.md` (matriz sub-bullet del examen → componente MedFlow).

Resultado buscado: el mismo pipeline funcional, ahora sobre Foundry/Azure AI, con un agente de
triage, RAG sobre el Protocolo Manchester, y responsible AI reforzando lo que ya existe
(`audit-ethics`, `Task_Log`, detección de sesgo).

## Mapa habilidad AI-103 → componente MedFlow

| Dominio AI-103 (peso) | Sub-habilidad | Dónde se demuestra en MedFlow |
|---|---|---|
| **Plan & manage (25-30%)** | Elegir modelo por tarea (LLM/SLM/multimodal) | Matriz de modelos: SLM barato para `llm-extraction`/`anxiety-score`, LLM fuerte para `llm-labeling` (decisión clínica) |
| | Set up en Foundry + CI/CD | `infra/azure/` Bicep + `azure.yaml` (azd) + GitHub Actions |
| | Quotas, escalado, coste, monitor drift/safety/grounding | Cuotas TPM por deployment; App Insights + Foundry tracing; salud del índice AI Search |
| | Seguridad: managed identity, keyless, red privada, roles | `DefaultAzureCredential` + Key Vault; eliminar `OPENROUTER_API_KEY`/`POSTGRES_PASSWORD` estáticos |
| | Responsible AI: filtros, guardrails, auditoría, oversight | Content Safety + evaluadores Foundry; provenance en `Task_Log`/`Prediccion`; gate de aprobación humana para C1/C2 vía `audit-ethics`+n8n |
| **Gen-AI & agents (30-35%)** | RAG en app | `llm-normalization` y `llm-labeling` grounded sobre índice AI Search del Protocolo Manchester |
| | Agentes: rol/goal/tool schemas, function-calling, memoria | Nuevo `services/triage-agent/` (Foundry Agent Service): tools = extraer / buscar diccionario / clasificar / score; memoria por `GUID_Entrevista` |
| | Multi-agente orquestado + aprobación/safeguards | Orquestador + agentes especialistas (extracción, triage, safety); C1/C2 requiere aprobación humana |
| | Evaluadores (fabricación, relevancia, calidad, safety) | `evaluation`: token `no_mapeado` ya es un detector de alucinación de términos; añadir groundedness/safety evaluators |
| | Prompt engineering, reflexión/self-critique, hybrid LLM+reglas | `data/prompts/*.j2` versionados; loop de auto-crítica en `llm-labeling` (regla precautoria Manchester); hybrid = lexicón+LLM (`anxiety-score`) y ML+LLM |
| | Observabilidad: tracing, tokens, safety, latencia | App Insights + Foundry; enriquecer `Task_Log.payload_resultado` |
| **Text analysis (10-15%)** | Entidades/JSON/resumen estructurado | `llm-extraction` vía Foundry |
| | Sentiment/tono/contenido sensible (PII) | `anxiety-score` (tono); nuevo paso PII (Azure AI Language PII / Content Safety) sobre la voz del paciente |
| | Traducción (Azure Translator) | `/translate_summarize` → Azure Translator en Foundry Tools |
| | Speech STT/TTS, custom speech, traducción de voz | `transcripcion`: whisperx → Azure AI Speech (batch + diarización), modelo Custom Speech con vocabulario clínico, traducción de voz EN→ES, TTS para devolver triage |
| **Info extraction (10-15%)** | Ingest+index, semantic/hybrid/vector search | Azure AI Search: Manchester protocol + `manchester_terms.csv` + corpus fareez |
| | Enriquecimiento (skills), RAG ingestion + OCR | Skillset de enriquecimiento; OCR de `guia.pdf`/`guia2.pdf` |
| | Extraer de documentos (OCR+layout+campos), Content Understanding | Azure AI Document Intelligence sobre los PDF de guías → markdown grounded |

## Arquitectura objetivo (Azure)

- **Microsoft Foundry project** = núcleo: deployments de modelos, conexiones a Speech / AI
  Search / Document Intelligence / Content Safety, Agent Service, evaluadores, tracing.
- **Datos**: minIO → Azure Blob Storage (containers = buckets actuales); Postgres local →
  Azure Database for PostgreSQL Flexible Server. Esquema y vistas se conservan.
- **Identidad**: una managed identity por servicio; acceso keyless a Foundry/Speech/Search/
  Blob/Postgres vía RBAC + `DefaultAzureCredential`. Secretos restantes en Key Vault.
- **Orquestación**: Airflow se mantiene para el camino batch (corpus fareez, reentrenamiento);
  el camino interactivo (frontend) pasa por `triage-agent` (Foundry Agent Service).

## Plan por fases

### Fase 0 — Provisioning e IaC (Plan & manage)
- Crear `infra/azure/` con **Bicep** + `azure.yaml` para `azd up`: Foundry hub+project,
  deployments de modelos, Azure AI Speech, AI Search, Document Intelligence, Content Safety,
  Key Vault, Blob, PostgreSQL Flexible, Application Insights, Log Analytics.
- Managed identities + asignaciones RBAC keyless. Sin claves estáticas en `.env`.
- GitHub Actions: workflow que despliega el proyecto Foundry y publica las imágenes de
  `services/*` (cubre "Integrate Foundry projects with CI/CD").

### Fase 1 — Cliente Foundry + identidad keyless
- Reescribir `services/_common/triage_common/llm.py`: `LLMClient` deja de usar OpenRouter
  httpx y usa `azure-ai-projects` / `azure-ai-inference` (o `openai` apuntando al endpoint
  Foundry) con `DefaultAzureCredential`. Mantener la API pública (`render`,
  `render_and_generate_json`) para no tocar a los consumidores.
- Matriz de selección de modelo por servicio en `docs/azure/model-selection.md`.
- `services/_common/triage_common/db.py` config para Azure PostgreSQL; añadir columnas de
  provenance (model id, deployment, prompt version, content-safety verdict) en
  `infra/postgres/01-init-triage.sql` y en `contracts.py` (`TaskLogEntry`, `Prediccion`).

### Fase 2 — Speech (Text analysis · Speech)
- Reescribir `services/transcripcion/main.py`: whisperx → **Azure AI Speech** batch
  transcription + conversation transcription (diarización para aislar la voz del paciente,
  que ya es un requisito del proyecto).
- Entrenar un **Custom Speech model** con vocabulario clínico (términos de
  `manchester_terms.csv`).
- Camino EN→ES: usar **Speech translation** de Azure en lugar del LLM para audio en inglés.
- Añadir **TTS** para leer el resultado de triage al paciente (modalidad agéntica) — feature
  en `frontend` + endpoint en `transcripcion` o `triage-agent`.

### Fase 3 — AI Search + Document Intelligence (Info extraction)
- Provisionar índice **Azure AI Search** (vector + hybrid + semantic) con: Protocolo
  Manchester, `data/dictionaries/manchester_terms.csv`, corpus `data/fareez_dataset/`.
- Nuevo `services/document-ingestion/` (o DAG Airflow): **Document Intelligence** hace OCR +
  layout + extracción de campos sobre `guia.pdf`/`guia2.pdf` → markdown grounded indexado.
- Reescribir `services/llm-normalization/main.py`: el lookup exacto/substring de
  `dictionary.py` se sustituye por búsqueda vectorial en AI Search (la normalización pasa a
  ser grounding por recuperación). `dictionary.py` queda como cliente de AI Search o se retira.

### Fase 4 — Agente de triage + RAG + reflexión (Gen-AI & agents)
- Nuevo `services/triage-agent/` sobre **Foundry Agent Service**: rol/goal/instrucciones del
  triage Manchester; tool schemas para `extract_entities`, `search_manchester` (AI Search),
  `classify_triage`, `score_anxiety`; knowledge store = índice AI Search; memoria de
  conversación por `GUID_Entrevista`.
- **Multi-agente**: orquestador + especialistas (extracción, triage, safety/audit).
- **RAG** en `llm-labeling` y `llm-normalization` grounded sobre AI Search.
- **Self-critique** en `services/llm-labeling/main.py`: el modelo critica su nivel C1-C5 contra
  el protocolo antes de fijarlo (refuerza la regla precautoria "ante duda, el más grave").
- Formalizar **hybrid LLM + reglas** ya presente: lexicón+LLM en `anxiety-score`, ML+LLM en
  labeling.

### Fase 5 — Responsible AI (Plan & manage · Responsible AI)
- Nuevo guardrail con **Azure AI Content Safety** (middleware en `_common` o
  `services/content-safety/`): prompt shields / detección de prompt-injection + contenido
  dañino sobre la voz del paciente y las salidas del LLM.
- Paso **PII** sobre el transcript (Azure AI Language PII) antes de persistir.
- **Evaluadores Foundry** (groundedness, relevancia, fabricación, safety) en
  `services/evaluation/main.py`, con eval offline sobre el corpus fareez.
- **Gate de aprobación humana**: `services/audit-ethics/main.py` + workflow n8n existente pasa
  a ser human-in-the-loop obligatorio para C1/C2 (oversight + tool-access control).
- **Provenance/auditoría**: model id, prompt version, veredicto de safety en `Task_Log` y
  `Prediccion`.

### Fase 6 — Observabilidad y operación (Plan & manage)
- **Application Insights** + Foundry tracing en todos los servicios; enriquecer el patrón
  existente `db.log_task(...)` con tokens, latencia y señales de safety en
  `payload_resultado` (reutilizar, no reinventar).
- Cuotas TPM, alertas de drift/grounding, salud del índice AI Search.

## Ficheros clave

Reescribir/extender:
- `services/_common/triage_common/llm.py`, `dictionary.py`, `storage.py`, `db.py`,
  `contracts.py`
- `services/transcripcion/main.py`, `services/llm-extraction/main.py`,
  `services/llm-normalization/main.py`, `services/llm-labeling/main.py`,
  `services/anxiety-score/main.py`, `services/evaluation/main.py`,
  `services/audit-ethics/main.py`
- `infra/postgres/01-init-triage.sql` (columnas de provenance)
- `data/prompts/*.j2` (versionado), `airflow/dags/*` (camino batch)

Nuevo:
- `infra/azure/` (Bicep + `azure.yaml` + GitHub Actions)
- `services/triage-agent/`, `services/content-safety/`, `services/document-ingestion/`
- `docs/azure/model-selection.md`, `docs/azure/ai-103-coverage.md`

Reutilizar (no reinventar): patrón `db.log_task` / `mark_timestamp` para telemetría; token
`no_mapeado` de `dictionary.py` como detector de fabricación; `audit-ethics` + webhooks n8n
como gate de aprobación; servicio `evaluation` como host de los evaluadores Foundry.

## Verificación

- **Por servicio**: tests existentes (`services/*/tests/`) verdes tras el swap de backend
  (mockear clientes Azure).
- **E2E**: `tests/e2e/test_smoke_pipeline.py` pasa contra el pipeline en Azure (texto y audio),
  comprobando `triage_real`, `justificacion_llm`, `entidades_normalizadas_es`, `score_ansiedad`.
- **Agente**: conversación de prueba al `triage-agent` devuelve C1-C5 con grounding citado del
  índice AI Search; C1/C2 dispara el gate de aprobación.
- **Responsible AI**: caso con prompt-injection embebido es bloqueado por Content Safety; caso
  con PII se redacta antes de persistir; evaluador de groundedness reporta score sobre el
  corpus fareez.
- **Observabilidad**: trazas y métricas de tokens/latencia visibles en Application Insights y
  en `Task_Log.payload_resultado`.
- **Cobertura temario**: `docs/azure/ai-103-coverage.md` mapea cada sub-bullet del examen a un
  PR/commit concreto.

## Riesgos y coste

- Coste Azure real: Foundry deployments (TPM), Speech batch, AI Search (tier con vector),
  Document Intelligence por página. Mitigar con SLM donde aplique y cuotas.
- Custom Speech y multi-agente son los items de mayor esfuerzo; si hay que recortar, son los
  primeros candidatos a versión mínima.
- Computer vision queda fuera por decisión; si más adelante se quiere el 100% del temario, la
  extensión natural es análisis multimodal de una foto de lesión visible + alt-text accesible.

## Fuentes

- [Study guide AI-103 (Microsoft Learn)](https://learn.microsoft.com/en-us/credentials/certifications/resources/study-guides/ai-103)
