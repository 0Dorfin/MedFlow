# Servicios

## Índice

1. [Infraestructura](#1-infraestructura)
2. [Librería común (`triage_common`)](#2-librería-común-triage_common)
3. [Modelo de datos](#3-modelo-de-datos)
4. [Pipeline Fase 1 — enriquecimiento](#4-pipeline-fase-1--enriquecimiento)
5. [ML y Fase 2 — predicción, evaluación, auditoría](#5-ml-y-fase-2--predicción-evaluación-auditoría)
6. [Consulta y front](#6-consulta-y-front)
7. [Orquestación: DAGs Airflow](#7-orquestación-dags-airflow)
8. [n8n: notificación y alerta](#8-n8n-notificación-y-alerta)
9. [Flujo end-to-end](#9-flujo-end-to-end)
10. [Estados de una entrevista](#10-estados-de-una-entrevista)

---

## 1. Infraestructura


| Servicio          | Puerto      | Rol                                                                                                                                            |
| ----------------- | ----------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| **Postgres 15**   | 5432        | Bases `triage_db` (dominio) y `airflow_db` (metadata Airflow).                                                                                 |
| **minIO**         | 9000 / 9001 | Almacén de objetos S3-compatible. Buckets: `audio-original`, `textos-originales`, `datasets`, `modelos`.                                       |
| **Airflow 3.0.5** | 8080        | Orquestador de DAGs. Procesos: `api-server` (UI + REST `/api/v2`), `scheduler`, `dag-processor`. Auth `SimpleAuthManager` (admin/admin) + JWT. |
| **n8n**           | 5678        | Automatización event-driven: alerta clínica por email + notificación de errores de Airflow.                                                    |


---

## 2. Librería común (`triage_common`)


| Módulo          | Contenido                                                                                                                                                                                                                                                                  |
| --------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `contracts.py`  | Modelos Pydantic de request/response entre servicios. Enums: `TriageLevel` (C1-C5 con `numeric`, `color`, `max_minutes`), `GrupoClinico` (RES/MSK/CAR/GAS/OTRO), `Origen`, `Validacion`, `EntrevistaEstado`. Helpers: `grupo_from_id_caso`, `under_triage`, `over_triage`. |
| `db.py`         | Cliente Postgres. Funciones: `insert_entrevista`, `upsert_texto_procesado`, `upsert_prediccion`, `update_entrevista_estado`, `mark_timestamp`, `log_task`.                                                                                                                 |
| `storage.py`    | Cliente minIO tipado por bucket. `put_bytes`, `get_bytes`, `list_objects`, `parse_uri`.                                                                                                                                                                                    |
| `llm.py`        | Cliente LLM (OpenRouter). Render de prompts Jinja2 (`render_and_generate_json`). Reintentos con `tenacity`.                                                                                                                                                                |
| `dictionary.py` | Carga el diccionario Manchester (`data/dictionaries/manchester_terms.csv`). `normalize(term)` con match exacto + substring; `canonical` (sin acentos, minúsculas).                                                                                                         |


---

## 3. Modelo de datos

### Tabla `Entrevista`

Registro maestro de cada caso. Arrastra el `GUID_Entrevista` por todo el pipeline.

- ID: `GUID_Entrevista` (PK), `ID_CASO`, `Origen` (Dataset/Simulacion/MVP/Web).
- URLs: `URL_Audio_Original`, `URL_Texto_Original`, `URL_Dataset_Generado`, `URL_Modelo_Entrenado`.
- Timestamps por etapa: `Inicio_*` / `Fin_*` (Solicitud, Transcripcion, Preprocesamiento, Extraccion_Entidades, Normalizacion, Etiquetado, Score, Entrenamiento).
- Orquestación: `Motor_Workflow`, `Workflow_Id`, `Estado`.

### Tabla `Texto_Procesado`

- `texto_original_en` (texto crudo si es inglés), `resumen_es` (resumen clínico español), `texto_preprocesado`.
- `entidades_extraidas_es` (síntomas en bruto), `entidades_normalizadas_es` (términos del diccionario).
- `triage_real` (C1-C5, etiqueta de referencia), `score_ansiedad` (0-1), `justificacion_llm`.

### Tabla `Prediccion`

- `prediccion_ia` (C1-C5), `score_ansiedad_ia`.
- `validacion` (Acierto/Under-triage/Over-triage/Pendiente), `motivo_fallo`, `accion_correctiva`, `fecha`.

### Tabla `Task_Log`

Trazabilidad: una fila por cada llamada HTTP a un servicio (`guid`, `service_name`, timestamps, `status` (OK/ERROR/RETRY/TIMEOUT), `payload_resultado`, `error_msg`).

### Vistas

- `v_resultado_completo` — join Entrevista + Texto_Procesado + Prediccion (vista completa de un caso).
- `v_auditoria_clinica` — solo desviaciones (Under/Over-triage) con `grupo_clinico` derivado del prefijo de `ID_CASO` (RES/MSK/CAR/GAS, resto OTRO) y `estatus` derivado (RECHAZADO si sesgo emocional, REVISAR si under clínico, ACEPTABLE si over, PENDIENTE en otro caso).

---

## 4. Pipeline Fase 1: enriquecimiento

Convierte texto/audio en datos clínicos estructurados. Cada servicio: FastAPI, `POST /run`, registra en `Task_Log`.

### api-gateway-ingesta`:8000`

**Puerta de entrada del sistema.**

- `POST /ingesta`: `texto` **o** `audio`, + `origen`, `id_caso`.
- Genera GUID. Sube audio a `minio://audio-original/{guid}.wav` o texto a `textos-originales/{guid}.txt`.
- Detecta idioma con `langdetect`: inglés → guarda en `texto_original_en`; español → `resumen_es`.
- Inserta `Entrevista` con `Estado=RECIBIDO`.
- Dispara el DAG Airflow (`dag_text_ingestion` o `dag_audio_ingestion`) vía REST `/api/v2` con token JWT.
- **Salida:** `{guid, estado, workflow_id}`.

### transcripcion `:9100`

**Audio → texto (faster-whisper).**

- `POST /transcribe {guid, audio_url}`. Descarga el audio de minIO y transcribe.
- Une los segmentos en texto plano. **No hace diarización** (no separa médico/paciente).
- Marca timestamps de transcripción en `Entrevista`.
- **Salida:** `{guid, texto, language, duration_seconds}`.

### preprocessing `:9101`

**Limpieza de texto.**

- `POST /run {guid, texto}` → normalización Unicode, limpieza → `texto_preprocesado`.

### llm-extraction `:9110`

**Extracción de síntomas y traducción/resumen.**

- `POST /run {guid, texto, language}` → LLM con prompt `extract_entities.j2` → lista de síntomas en bruto → `entidades_extraidas_es`.
- `POST /translate_summarize {guid, texto}` → si el texto es inglés, LLM con `translate_summarize.j2` traduce + resume a español clínico → `resumen_es`.

### llm-normalization `:9111`

**Mapeo al diccionario Manchester cerrado.**

- `POST /run {guid, entidades_extraidas}`.
- Primero match con `dictionary.py` (CSV cerrado, 112 entradas, EN+ES). Lo no mapeado se manda al LLM con `normalize_entities.j2`, que **fuerza** el mapeo a términos del diccionario.
- **Salida:** `entidades_normalizadas_es` (lista de términos clínicos) + `no_mapeadas`.

### llm-labeling `:9112`

**Etiquetado de triaje Manchester.**

- `POST /run {guid, resumen_es, entidades_normalizadas}` → LLM con `label_triage.j2` → `{triage: C1-C5, justificacion}`.
- Escribe `triage_real` y `justificacion_llm`.

### anxiety-score `:9113`

**Score de ansiedad subjetiva (0-1).**

- `POST /run {guid, texto}`.
- Combina **lexicón emocional bilingüe** (miedo, pánico, "me muero", scared, dying, can't breathe...) con un **score del LLM** (prompt calibrado 0.0-1.0).
- Se calcula sobre el `texto_original_en` (crudo, con emoción) si existe, no sobre el resumen clínico (neutro).
- **Salida:** `score_ansiedad`. Es independiente a la gravedad clínica → señal clave para detectar sesgo emocional en la auditoría.

---

## 5. ML y Fase 2: predicción, evaluación, auditoría

### dataset-builder `:9120`

**Construye los datasets para minIO.**

- `POST /run {min_rows, only_origin, mode}`.
- `mode=f1` (training): exporta `Texto_Procesado` (filas con `triage_real`) a `minio://datasets/triage_f1_*.parquet`. 9 columnas: guid, id_caso, origen, texto_original_en, resumen_es, entidades_extraidas_es, entidades_normalizadas_es, score_ansiedad, triage_real. Filtra `seed-*`/MVP sin id_caso (excepto C1).
- `mode=f2` (validación+inferencia): exporta `v_resultado_completo` a `triage_f2_*.parquet`.

### ml-training `:9121`

**Entrena el clasificador.**

- `POST /run {dataset_url}`.
- Features: **TF-IDF** (1-2 gramas) sobre `resumen_es` + **multi-hot** de `entidades_normalizadas_es`.
- Entrena 3 candidatos: `LogisticRegression`, `RandomForest` (ambos `class_weight='balanced'`) y `GradientBoosting`, con validación cruzada estratificada 5-fold.
- Elige el de mayor **F1-macro**. Guarda `*.joblib` + `metrics.json` (accuracy, recall por clase, matriz de confusión) en `minio://modelos/`.

### ml-prediction `:9122`

**Predice el nivel Manchester.**

- `POST /run {guid, texto, entidades_normalizadas}`.
- Carga el último modelo de `minio://modelos/`. Aplica TF-IDF + multi-hot → predice `prediccion_ia` + probabilidades por clase.
- Escribe `Prediccion`, pasa `Estado=PREDICHO`.
- `POST /reload` recarga el modelo más reciente.

### evaluation `:9123`

**Valida predicción contra etiqueta.**

- `POST /run {guid, prediccion_ia, triage_real}` → compara los niveles → `validacion`:
  - **Acierto** si coinciden.
  - **Under-triage** si la IA es menos urgente que la real (peligroso).
  - **Over-triage** si la IA es más urgente (falso positivo, sin riesgo clínico).
- Pasa `Estado=EVALUADO`.

### audit-ethics `:9124`

**Auditoría ética — detección de under-triage por sesgo emocional.**

- `POST /run {guid, prediccion_ia, triage_real, score_ansiedad_ia}`.
- Lógica:
  - Acierto → sin acción.
  - Under-triage **con `score_ansiedad_ia >= 0.8`** → **sesgo emocional**: el modelo infravaloró la gravedad de un paciente con alta carga emocional. `motivo_fallo` + `accion_correctiva` ("reentrenar con class_weight reforzado..."). **Dispara alerta n8n** → email.
  - Under-triage normal → "revisión humana".
  - Over-triage → "monitorizar falsos positivos".
- Pasa `Estado=AUDITADO`.

---

## 6. Consulta y front

### api-gateway-consulta `:8001`

- `GET /resultado/{guid}` → agrega `Entrevista + Texto_Procesado + Prediccion` (lectura completa de un caso).

### frontend (Next.js) `:3000`

- Bandeja de casos, detalle clínico, ingesta, métricas del modelo. Consume los api-gateways.

---

## 7. Orquestación: DAGs Airflow


| DAG                      | Disparo                      | Hace                                                                                                                                      |
| ------------------------ | ---------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `dag_text_ingestion`     | manual (`max_active_runs=8`) | Fase 1 texto: translate_summarize → preprocessing → extraction → normalization → labeling → anxiety_score → finalize (TEXTO_ENRIQUECIDO). |
| `dag_audio_ingestion`    | manual                       | Igual + `transcripcion` al inicio.                                                                                                        |
| `dag_llm_enrichment`     | `@hourly`                    | Batch: busca `RECIBIDO` y dispara `dag_text_ingestion` por cada uno.                                                                      |
| `dag_model_training`     | `@daily` / manual            | build_dataset (F1) → ml_training → reload_predictor.                                                                                      |
| `dag_prediction_phase_2` | manual                       | Predice 1 GUID enriquecido.                                                                                                               |
| `dag_evaluation`         | `@hourly`                    | Batch sobre `PREDICHO` con `triage_real` → marca validación.                                                                              |
| `dag_audit_ethics`       | `@hourly`                    | Batch sobre `EVALUADO` → audita + dispara alerta n8n en casos de sesgo.                                                                   |


Helpers comunes en `airflow/dags/triage_helpers.py`

---

## 8. n8n: notificación y alerta

Workflows en `n8n/workflows/`.


| Workflow                   | Endpoint                         | Uso real                                                                                                                       |
| -------------------------- | -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `error_notification`       | `POST /webhook/error`            | Recibe el `on_failure_callback` de Airflow → formatea alerta técnica. **Cableado** (`N8N_ERROR_WEBHOOK`).                      |
| `webhook_alerta_clinica`   | `POST /webhook/alerta-clinica`   | Disparado por `audit-ethics` ante sesgo emocional → email HTML al clínico vía Gmail SMTP. **Cableado** (`N8N_ALERTA_WEBHOOK`). |
| `webhook_triaje_procesado` | `POST /webhook/triaje-procesado` | Notificación de caso procesado → formatea resultado y envía email al clínico vía Gmail.                                        |


---

## 9. Flujo end-to-end

```
[paciente] texto/audio
  → api-gateway-ingesta            Estado: RECIBIDO
  → DAG Fase 1:
       (transcripcion si audio)
       translate_summarize
       preprocessing
       llm-extraction
       llm-normalization
       llm-labeling                triage_real + justificacion
       anxiety-score               score_ansiedad
                                    Estado: TEXTO_ENRIQUECIDO
  → dataset-builder (F1) → ml-training        modelo en minIO
  → ml-prediction                  prediccion_ia    Estado: PREDICHO
  → evaluation                     validacion       Estado: EVALUADO
  → audit-ethics                   motivo/accion    Estado: AUDITADO
       └→ si sesgo emocional → n8n → email
```

---

## 10. Estados de una entrevista

```
RECIBIDO
  → TRANSCRITO (solo audio)
  → TEXTO_PREPROCESADO
  → ENTIDADES_EXTRAIDAS
  → ENTIDADES_NORMALIZADAS
  → ETIQUETADO
  → SCORE_CALCULADO
  → TEXTO_ENRIQUECIDO      (fin Fase 1)
  → DATASET_GENERADO
  → MODELO_ENTRENADO
  → PREDICHO               (Fase 2)
  → EVALUADO
  → AUDITADO               
  [ERROR en cualquier punto → on_failure_callback → n8n]
```

