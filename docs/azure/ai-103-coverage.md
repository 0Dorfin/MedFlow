# Cobertura del examen AI-103 en MedFlow

Matriz que mapea cada sub-habilidad del examen **AI-103: Developing AI Apps and Agents on
Azure** (outline vigente abril 2026) a un componente o artefacto concreto de MedFlow.

Es el documento backbone del portfolio: sirve de mapa de estudio, de orden de construcción y de
prueba al reviewer de qué partes del temario quedan demostradas.

**Decisiones de alcance:**
- Migración real a Azure mediante **adapter dual local/cloud** (`LLM_BACKEND=local|azure`, etc.):
  el camino local gratuito sigue ejecutable.
- **4 de 5 dominios** en alcance. **Computer vision (10-15%) queda fuera** por no haber señal
  visual clínica en el triage por voz/texto (ver sección final).

**Leyenda estado:** `Pendiente` · `En curso` · `Hecho`

---

## Plan and manage an Azure AI solution (25-30%)

### Choose the appropriate Foundry services for generative AI and agents
| Sub-habilidad (examen) | Componente / artefacto MedFlow | Servicio Azure | Estado |
|---|---|---|---|
| Elegir modelo por tarea (LLM / SLM / multimodal / Foundry Tools) | Matriz de modelos por servicio en `docs/azure/model-selection.md`: SLM para `llm-extraction`/`anxiety-score`, LLM fuerte para `llm-labeling` | Foundry model catalog | Pendiente |
| Elegir servicios Foundry para generación, grounding, vector search, agentes, multimodal | Justificación de arquitectura en `plan-azure.md` | Foundry project | Pendiente |
| Elegir método de retrieval e indexación | Diseño del índice Manchester (vector+hybrid) | Azure AI Search | Pendiente |
| Elegir memoria/herramientas/conocimiento para agentes | Diseño de `services/triage-agent/` (memoria por GUID, tools, knowledge store) | Foundry Agent Service | Pendiente |

### Set up AI solutions in Foundry
| Sub-habilidad | Componente MedFlow | Servicio Azure | Estado |
|---|---|---|---|
| Diseñar infra Azure para apps y agentes | `infra/azure/` (Bicep) | Foundry, RG, redes | Pendiente |
| Elegir opciones de despliegue | `azure.yaml` (azd), contenedores de `services/*` | Container Apps / azd | Pendiente |
| Configurar deployments de modelos y agentes | Bicep de deployments + agente | Foundry deployments | Pendiente |
| Integrar proyecto Foundry con CI/CD | GitHub Actions de despliegue | GitHub Actions + azd | Pendiente |

### Manage, monitor, and secure AI systems
| Sub-habilidad | Componente MedFlow | Servicio Azure | Estado |
|---|---|---|---|
| Cuotas, escalado, rate limits, coste | Cuotas TPM por deployment; doc de coste | Foundry quotas | Pendiente |
| Monitor de performance, drift, safety, grounding | Tracing + métricas; enriquecer `Task_Log.payload_resultado` | Application Insights + Foundry | Pendiente |
| Monitor de ingesta, salud del índice, relevancia | Alertas sobre el índice de búsqueda | AI Search + App Insights | Pendiente |
| Seguridad: managed identity, red privada, keyless, roles | `DefaultAzureCredential` en `AzureFoundryBackend` (keyless); pendiente quitar `POSTGRES_PASSWORD` estático + red privada | Managed Identity + Key Vault + RBAC | Parcial (keyless en código) |

### Implement responsible AI
| Sub-habilidad | Componente MedFlow | Servicio Azure | Estado |
|---|---|---|---|
| Filtros de seguridad, guardrails, detección de riesgo, moderación | `services/content-safety/` o middleware en `_common` | Azure AI Content Safety | Pendiente |
| Instrumentación RAI: evaluadores, evaluaciones de safety, explicación | `services/evaluation/` + `justificacion_llm` existente | Foundry evaluators | Pendiente |
| Auditoría: trace logging, provenance, workflows de aprobación | Provenance `{backend, model, prompt}` en `Task_Log` de labeling (`LLMClient.provenance`); oversight humano vía `triage_real` + `audit-ethics` existentes (no se duplica con gate redundante) | Task_Log + n8n | Hecho (provenance + oversight humano) |
| Gobierno del agente: oversight, restricciones, tool-access | C1/C2 requieren aprobación humana en `services/audit-ethics/` | Foundry Agent Service | Pendiente |

---

## Implement generative AI and agentic solutions (30-35%)

### Build generative applications by using Foundry
| Sub-habilidad | Componente MedFlow | Servicio Azure | Estado |
|---|---|---|---|
| Desplegar/consumir LLM, modelos pequeños, de código, multimodal | `AzureFoundryBackend` en `llm.py` (SDK `openai` v1; key o `DefaultAzureCredential`) | Azure OpenAI `gpt-4o-mini` | Hecho (live, key-based) |
| Implementar RAG | `llm-normalization` y `llm-labeling` grounded en el índice | AI Search + Foundry | Pendiente |
| Workflows, flujos con tools, razonamiento multipaso | El pipeline extracción→normalización→etiquetado | Foundry + Airflow | Pendiente |
| Evaluar (fabricación, relevancia, calidad, safety) | Eval offline de accuracy de grupo sobre corpus fareez (`scripts/eval_fareez.py`, `triage_common/evaluation.py`); baseline local 0.50 en muestra estratificada N=14; AI Search sin umbral baja a 0.29 (over-match), con `AZURE_SEARCH_MIN_SCORE=4.0` recupera 0.50 + recall semántico (capta variantes que el CSV pierde). CAR debil en ambos (extraccion/diccionario) | corpus labels + pipeline | Hecho (eval offline) |
| Integrar workflows con SDK/conectores Foundry | `azure-ai-projects` en cada servicio | Foundry SDK | Pendiente |
| Conectar la app a un proyecto Foundry | `LLM_BACKEND=azure` + `AZURE_AI_ENDPOINT`/`AZURE_AI_DEPLOYMENT`; smoke `scripts/smoke_azure_foundry.py` validado | Foundry project medflow-triage | Hecho (live) |

### Build agents by using Foundry
| Sub-habilidad | Componente MedFlow | Servicio Azure | Estado |
|---|---|---|---|
| Definir rol, goal, tracking de conversación, tool schemas | `services/triage-agent/` (rol triage Manchester) | Foundry Agent Service | Pendiente |
| Agentes con retrieval + function-calling + memoria | Tools: extraer/buscar/clasificar/score; memoria por GUID | Foundry Agent Service | Pendiente |
| Integrar tools: APIs, knowledge stores, search, custom functions | Tool `search_manchester` sobre AI Search + funciones | Foundry + AI Search | Pendiente |
| Multi-agente orquestado | Orquestador + especialistas (extracción, triage, safety) | Foundry Agent Service | Pendiente |
| Workflows (semi)autónomos con safeguards y aprobación | Gate humano para C1/C2 | Foundry + n8n | Pendiente |
| Monitorizar agentes, evaluar comportamiento, error analysis | Tracing del agente + revisión | App Insights + Foundry | Pendiente |

### Optimize and operationalize generative AI systems
| Sub-habilidad | Componente MedFlow | Servicio Azure | Estado |
|---|---|---|---|
| Tuning: prompt engineering, parámetros del modelo | `data/prompts/*.j2` versionados | Foundry | Pendiente |
| Reflexión, chain-of-thought, self-critique | Loop de auto-crítica en `llm-labeling` (regla precautoria) | Foundry | Pendiente |
| Observabilidad: tracing, tokens, safety, latencia | Enriquecer `db.log_task(...)` | App Insights + Foundry | Pendiente |
| Orquestar múltiples modelos / hybrid LLM + reglas | lexicón+LLM en `anxiety-score`; ML+LLM en labeling | Foundry + sklearn | Pendiente |

---

## Implement text analysis solutions (10-15%)

### Apply language model text analysis
| Sub-habilidad | Componente MedFlow | Servicio Azure | Estado |
|---|---|---|---|
| Extraer entidades/temas/resumen/JSON estructurado | `services/llm-extraction/` vía Foundry; validado con `scripts/smoke_azure_extraction.py` (prompt `extract_entities.j2` + corpus fareez) | Azure OpenAI `gpt-4o-mini` | Hecho (live) |
| Detectar sentiment, tono, safety, contenido sensible | `anxiety-score` (tono) + redacción PII en `preprocessing` (`PII_BACKEND`: regex local + `AzureLanguagePii` auto es/en, valida `scripts/smoke_azure_pii.py`, pilla nombres; `categories_filter` conserva DateTime/onset clínico) | Azure AI Language (PII) | Hecho (live, es+en) |
| Traducir (Azure Translator o flujo LLM) | `/translate_summarize` → Azure Translator | Azure Translator | Pendiente |
| Customizar salidas para dominio (resumen compliance, extracción) | Prompts clínicos de dominio | Foundry | Pendiente |

### Implement speech solutions
| Sub-habilidad | Componente MedFlow | Servicio Azure | Estado |
|---|---|---|---|
| STT y TTS para interacciones agénticas | `transcripcion`: `AzureSpeechBackend` (ConversationTranscriber + diarización, aísla voz paciente; conversión webm/mp3 -> wav 16k vía ffmpeg para el audio del frontend; validado con `scripts/smoke_azure_speech.py`); TTS pendiente | Azure AI Speech | STT Hecho (live, diarización aísla paciente); TTS pendiente |
| Speech como modalidad de agente + custom speech models | Custom Speech con vocabulario clínico de `manchester_terms.csv` | Azure AI Speech (Custom) | Pendiente |
| Razonamiento multimodal desde audio | Tono/urgencia desde el audio además del transcript | Foundry multimodal | Pendiente |
| Traducir voz a otros idiomas | EN→ES con Speech translation (sustituye el LLM) | Azure AI Speech | Pendiente |

---

## Implement information extraction solutions (10-15%)

### Build retrieval and grounding pipelines
| Sub-habilidad | Componente MedFlow | Servicio Azure | Estado |
|---|---|---|---|
| Ingerir/indexar documentos, imágenes, audio, vídeo | Diccionario Manchester ingestado (`scripts/ingest_manchester_search.py`, 112 docs, analizador es.lucene); protocolo PDF + corpus pendiente | AI Search | Parcial (diccionario hecho) |
| Semantic / hybrid / vector search para grounding | `AzureSearchBackend` en `llm-normalization` (consulta índice por síntoma; `NORMALIZATION_BACKEND=azure`); validado con `scripts/smoke_azure_search.py` (recall semántico > match literal CSV) | AI Search | Hecho (live, 112 términos) |
| Enriquecimiento con skills (texto, imágenes, layout) | Skillset de ingesta (key phrase, entidades) | AI Search skillset | Pendiente |
| RAG ingestion incl. OCR | OCR de `guia.pdf`/`guia2.pdf` en ingesta | Document Intelligence + AI Search | Pendiente |
| Conectar retrieval a workflows y tools de agente | Tool `search_manchester` del `triage-agent` | Foundry + AI Search | Pendiente |

### Extract content from documents
| Sub-habilidad | Componente MedFlow | Servicio Azure | Estado |
|---|---|---|---|
| Pipelines multimodales (OCR + layout + extracción de campos) | `services/document-ingestion/` sobre los PDF de guías | Document Intelligence | Pendiente |
| Representaciones limpias y grounded (Content Understanding) | Markdown grounded del protocolo Manchester | Content Understanding | Pendiente |
| Analizadores para salidas estructuradas/markdown | Salida estructurada para el knowledge store | Content Understanding | Pendiente |

---

## Fuera de alcance: Computer vision (10-15%)

Excluido por decisión: el triage actual no maneja señal visual. Si en el futuro se quisiera el
100% del temario, la extensión natural sería una vía de **foto de síntoma visible** (comprensión
multimodal + alt-text accesible + Content Safety sobre la imagen y detección de prompt-injection
embebido), dejando la generación de imagen/vídeo solo como datos sintéticos.

---

## Fuente

- [Study guide AI-103 (Microsoft Learn)](https://learn.microsoft.com/en-us/credentials/certifications/resources/study-guides/ai-103)
