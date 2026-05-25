# TriageIA - Triaje Manchester con LLM + Machine Learning

Sistema que clasifica la urgencia clínica de un paciente (nivel Manchester **C1-C5**) a partir de su texto o audio. Enriquece con un LLM (extracción de síntomas, normalización, etiquetado, score de ansiedad), entrena un modelo de Machine Learning con esas etiquetas y, en producción, predice el nivel de nuevos casos. Incluye un bucle de **auditoría ética** que detecta subestimaciones de gravedad en pacientes con alta carga emocional.

El pipeline se orquesta con **Apache Airflow** (procesamiento batch) y **n8n** (alertas y notificaciones), sobre microservicios **FastAPI**, **Postgres** y **minIO**.

---

## Tabla de contenidos

1. [Pipeline](#pipeline)
2. [Requisitos](#requisitos)
3. [Cómo ejecutar](#cómo-ejecutar)
4. [Flujo de prueba](#flujo-de-prueba)
5. [Comandos útiles](#comandos-útiles)
6. [Stack tecnológico](#stack-tecnológico)
7. [Servicios](#servicios)
8. [Orquestación: Airflow y n8n](#orquestación-airflow-y-n8n)
9. [Variables de entorno](#variables-de-entorno)
10. [Documentación](#documentación)
11. [Estructura del repositorio](#estructura-del-repositorio)

---

## Pipeline

```
texto / audio
  └─► api-gateway-ingesta                          Estado: RECIBIDO
        └─► Fase 1 (DAG Airflow):
              (transcripción si es audio)
              traducción/resumen → preprocesado →
              extracción → normalización →
              etiquetado (triage_real) → score de ansiedad
                                                   Estado: TEXTO_ENRIQUECIDO
        └─► dataset-builder → ml-training          modelo en minIO
        └─► ml-prediction    (prediccion_ia)       Estado: PREDICHO
        └─► evaluation       (validación)          Estado: EVALUADO
        └─► audit-ethics     (auditoría ética)     Estado: AUDITADO
              └─► si hay sesgo emocional → n8n → email
```

Detalle del flujo y estados en `[docs/servicios.md](docs/servicios.md)`; arquitectura en `[docs/arquitectura.md](docs/arquitectura.md)`.

---

## Requisitos

- Docker y Docker Compose.
- Una `OPENROUTER_API_KEY` (proveedor LLM).

---

## Cómo ejecutar

```bash
cp .env.example .env        # rellena OPENROUTER_API_KEY y las credenciales
docker compose up -d        # levanta toda la plataforma
docker compose ps           # comprueba el estado
```

Accesos una vez arrancado:


| Servicio        | URL                                            |
| --------------- | ---------------------------------------------- |
| Frontend        | [http://localhost:3000](http://localhost:3000) |
| Airflow         | [http://localhost:8080](http://localhost:8080) |
| n8n             | [http://localhost:5678](http://localhost:5678) |
| minIO (consola) | [http://localhost:9001](http://localhost:9001) |
| API ingesta     | [http://localhost:8000](http://localhost:8000) |
| API consulta    | [http://localhost:8001](http://localhost:8001) |


Las credenciales de Airflow, n8n y minIO se definen en `.env` (ver `.env.example`).

El mapa completo de puertos está en `[docs/arquitectura.md](docs/arquitectura.md)`.

---

## Flujo de prueba

```bash
# 1. Ingesta de un caso de texto (origen: Dataset | Simulacion | MVP | Web)
curl -X POST http://localhost:8000/ingesta \
  -F "texto=Me falta el aire y siento que me muero" \
  -F "id_caso=RES0001" \
  -F "origen=Simulacion"
# → { "guid": "<GUID>", "estado": "RECIBIDO", "workflow_id": "<run_id>" }

# 2. Seguir el progreso del caso en Airflow (http://localhost:8080)
#    o consultar el resultado completo cuando termine el pipeline:
curl http://localhost:8001/resultado/<GUID>

# 3. Lista de los últimos casos procesados
curl "http://localhost:8001/historial?limit=20"
```

También puedes lanzar un caso desde el frontend ([http://localhost:3000](http://localhost:3000)).

---

## Comandos útiles

```bash
docker compose logs -f llm-labeling        # logs de un servicio concreto
docker compose up -d --build ml-training   # reconstruir un servicio tras cambios
docker compose down -v                     # parar y borrar volúmenes

pytest services/llm-labeling/tests/        # tests de un microservicio
pytest services/_common/tests/             # tests de la librería común
```

---

## Stack tecnológico


| Componente                  | Tecnología                                                                         |
| --------------------------- | ---------------------------------------------------------------------------------- |
| Lenguaje servicios          | Python 3.11                                                                        |
| API microservicios          | FastAPI                                                                            |
| Frontend                    | Next.js 16 · React 19 · TypeScript · Tailwind 4                                    |
| Orquestación batch          | Apache Airflow 3.0.5 (LocalExecutor)                                               |
| Automatización event-driven | n8n 1.74.1                                                                         |
| LLM                         | OpenRouter (`openai/gpt-oss-120b:free`) · prompts Jinja2 · reintentos `tenacity`   |
| Transcripción audio         | faster-whisper                                                                     |
| Detección de idioma         | langdetect                                                                         |
| Machine Learning            | scikit-learn (TF-IDF + LogisticRegression/RandomForest/GradientBoosting), `joblib` |
| Base de datos               | PostgreSQL 15 (`psycopg2`)                                                         |
| Almacenamiento objetos      | minIO (compatible S3, cliente `minio`)                                             |
| Contenedores                | Docker Compose                                                                     |


---

## Servicios

14 microservicios. Detalle completo (entradas/salidas, escrituras en BD) en [docs/servicios.md](docs/servicios.md).


| Servicio             | Puerto | Qué hace                                                                      |
| -------------------- | ------ | ----------------------------------------------------------------------------- |
| api-gateway-ingesta  | 8000   | Puerta de entrada: recibe texto/audio, genera GUID, dispara el DAG de Fase 1. |
| api-gateway-consulta | 8001   | Lectura del resultado completo de un caso.                                    |
| transcripcion        | 9100   | Audio → texto (faster-whisper).                                               |
| preprocessing        | 9101   | Limpieza y normalización del texto.                                           |
| llm-extraction       | 9110   | Extrae síntomas y traduce/resume a español clínico.                           |
| llm-normalization    | 9111   | Mapea los síntomas al diccionario Manchester cerrado.                         |
| llm-labeling         | 9112   | Asigna el nivel Manchester (`triage_real`) + justificación.                   |
| anxiety-score        | 9113   | Calcula el score de ansiedad (0-1).                                           |
| dataset-builder      | 9120   | Exporta los datasets de entrenamiento/validación a minIO.                     |
| ml-training          | 9121   | Entrena el clasificador y guarda modelo + métricas.                           |
| ml-prediction        | 9122   | Predice el nivel Manchester (`prediccion_ia`).                                |
| evaluation           | 9123   | Compara predicción contra etiqueta de referencia.                             |
| audit-ethics         | 9124   | Auditoría ética: detecta sesgo emocional y dispara alerta.                    |
| frontend             | 3000   | Dashboard Next.js: bandeja de casos, detalle, ingesta, métricas.              |


---

## Orquestación: Airflow y n8n

**Airflow** mueve cada caso por las fases (llamadas HTTP `POST /run` a los servicios). DAGs en `airflow/dags/`:


| DAG                      | Disparo   | Qué hace                                                                                  |
| ------------------------ | --------- | ----------------------------------------------------------------------------------------- |
| `dag_text_ingestion`     | manual    | Fase 1 (texto): resumen → preprocesado → extracción → normalización → etiquetado → score. |
| `dag_audio_ingestion`    | manual    | Igual + transcripción al inicio.                                                          |
| `dag_llm_enrichment`     | `@hourly` | Recoge casos `RECIBIDO` y lanza Fase 1 por cada uno.                                      |
| `dag_model_training`     | `@daily`  | build_dataset → entrena → recarga el predictor.                                           |
| `dag_prediction_phase_2` | manual    | Predice un caso enriquecido.                                                              |
| `dag_evaluation`         | `@hourly` | Valida los casos `PREDICHO`.                                                              |
| `dag_audit_ethics`       | `@hourly` | Audita los `EVALUADO` y alerta si hay sesgo.                                              |


**n8n** reacciona a eventos puntuales. Workflows en `n8n/workflows/`:


| Workflow                   | Disparo                           | Qué hace                           |
| -------------------------- | --------------------------------- | ---------------------------------- |
| `error_notification`       | fallo de un DAG                   | Email de alerta técnica.           |
| `webhook_alerta_clinica`   | sesgo emocional en `audit-ethics` | Email HTML al clínico vía Gmail.   |
| `webhook_triaje_procesado` | caso procesado                    | Email con el resultado del triaje. |


---

## Variables de entorno

Plantilla completa en `.env.example`. Las principales:


| Grupo         | Variables                                                                                             |
| ------------- | ----------------------------------------------------------------------------------------------------- |
| LLM           | `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `LLM_TIMEOUT`, `LLM_MAX_RETRIES`                            |
| Postgres      | `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`                                                   |
| minIO         | `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `MINIO_BUCKETS`                                             |
| Airflow       | `AIRFLOW_ADMIN_USER`, `AIRFLOW_ADMIN_PASSWORD`, `AIRFLOW_JWT_SECRET`                                  |
| n8n           | `N8N_BASIC_AUTH_USER`, `N8N_BASIC_AUTH_PASSWORD`, `N8N_ENCRYPTION_KEY`, `GMAIL_FROM`, `CLINICO_EMAIL` |
| Transcripción | `WHISPER_MODEL`, `WHISPER_DEVICE`, `WHISPER_COMPUTE_TYPE`                                             |


---

## Documentación


| Documento                                            | Contenido                                                                                          |
| ---------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| `[docs/arquitectura.md](docs/arquitectura.md)`       | Diagrama de contenedores, decisiones de diseño, stack y puertos.                                   |
| `[docs/servicios.md](docs/servicios.md)`             | Referencia detallada de cada microservicio, modelo de datos, DAGs y flujo end-to-end.              |
| `[docs/dominio-clinico.md](docs/dominio-clinico.md)` | Niveles Manchester, grupos clínicos, diccionario de síntomas, score de ansiedad y auditoría ética. |
| `[docs/modelo-ml.md](docs/modelo-ml.md)`             | Dataset, features, algoritmos, métricas y guardado/carga del modelo.                               |
| `[docs/gestion-errores.md](docs/gestion-errores.md)` | Reintentos, registro en Postgres, notificación n8n y recuperación.                                 |
| `[docs/flujo-n8n.md](docs/flujo-n8n.md)`             | Workflows de n8n.                                                                                  |


---

## Estructura del repositorio

```
triaje_urgencias/
├── docker-compose.yml              # Orquestación de todos los contenedores
├── .env.example                    # Plantilla de variables de entorno
├── README.md
│
├── docs/                           # Documentación
│   ├── arquitectura.md
│   ├── servicios.md
│   ├── dominio-clinico.md
│   ├── modelo-ml.md
│   ├── gestion-errores.md
│   └── flujo-n8n.md
│
├── data/
│   ├── dictionaries/
│   │   └── manchester_terms.csv    # Diccionario cerrado de síntomas (112 términos)
│   ├── prompts/                    # Plantillas Jinja2 de los prompts LLM
│   │   ├── extract_entities.j2
│   │   ├── normalize_entities.j2
│   │   ├── label_triage.j2
│   │   └── translate_summarize.j2
│   ├── fareez_dataset/             # Corpus de transcripciones clínicas (Fareez et al.)
│   │   └── transcripts/
│   └── samples/
│
├── infra/                          # Scripts de inicialización de la infraestructura
│   ├── postgres/
│   │   ├── 00-create-airflow-db.sh
│   │   └── 01-init-triage.sql      # Esquema: Entrevista, Texto_Procesado, Prediccion, Task_Log + vistas
│   ├── minio/
│   │   └── bootstrap-buckets.sh    # Crea los buckets de minIO
│   └── n8n/
│       └── import-workflows.sh     # Importa los workflows de n8n
│
├── airflow/
│   ├── dags/                       # DAGs del pipeline
│   │   ├── dag_text_ingestion.py   # Fase 1 (texto)
│   │   ├── dag_audio_ingestion.py  # Fase 1 (audio: + transcripción)
│   │   ├── dag_llm_enrichment.py   # Batch: enriquece casos RECIBIDO
│   │   ├── dag_model_training.py   # Construye dataset + entrena + recarga modelo
│   │   ├── dag_prediction_phase_2.py
│   │   ├── dag_evaluation.py       # Batch: valida predicciones
│   │   ├── dag_audit_ethics.py     # Batch: auditoría ética + alerta
│   │   └── triage_helpers.py       # Helpers comunes (post_json, reintentos, callback n8n)
│   ├── config/
│   └── logs/
│
├── n8n/
│   └── workflows/
│       ├── error_notification.json       # Alerta técnica ante fallo de Airflow
│       ├── webhook_alerta_clinica.json   # Alerta clínica por sesgo emocional
│       └── webhook_triaje_procesado.json # Alerta clínica para casos urgentes C1 o C2
│
├── services/
│   ├── _common/                    # Librería compartida
│   │   ├── triage_common/
│   │   │   ├── contracts.py        # Modelos Pydantic, enums (TriageLevel, GrupoClinico...)
│   │   │   ├── db.py               # Cliente Postgres + helpers
│   │   │   ├── storage.py          # Cliente minIO tipado por bucket
│   │   │   ├── llm.py              # Cliente LLM (OpenRouter) + Jinja2
│   │   │   └── dictionary.py       # Carga y normalización del diccionario Manchester
│   │   ├── tests/
│   │   └── pyproject.toml
│   │
│   ├── api-gateway-ingesta/        # :8000 Entrada de casos, dispara DAG
│   ├── api-gateway-consulta/       # :8001 Lectura de resultados
│   ├── transcripcion/              # :9100 Audio → texto (faster-whisper)
│   ├── preprocessing/              # :9101 Limpieza de texto
│   ├── llm-extraction/             # :9110 Extracción de síntomas + traducción/resumen
│   ├── llm-normalization/          # :9111 Mapeo al diccionario cerrado
│   ├── llm-labeling/               # :9112 Etiquetado Manchester (triage_real)
│   ├── anxiety-score/              # :9113 Score de ansiedad (lexicón + LLM)
│   ├── dataset-builder/            # :9120 Construye datasets Parquet en minIO
│   ├── ml-training/                # :9121 Entrena el clasificador
│   ├── ml-prediction/              # :9122 Predice el nivel (prediccion_ia)
│   ├── evaluation/                 # :9123 Valida predicción vs etiqueta
│   ├── audit-ethics/               # :9124 Auditoría ética + alerta n8n
│   └── frontend/                   # :3000 Dashboard Next.js
│       ├── Dockerfile
│       ├── package.json
│       └── src/
│           ├── app/                # Páginas (bandeja, historial)
│           ├── components/
│           └── lib/
│
├── scripts/                        # Operación y mantenimiento de datos
│   ├── seed_postgres.py            # Carga de datos de prueba
│   ├── predict_batch.py
│   ├── recompute_anxiety.py
│   ├── recompute_normalization.py
│   ├── retry_stuck.py              # Reintenta casos atascados
│
└── notebooks/
    └── ml_exploration.ipynb        # Exploración del modelo
```

