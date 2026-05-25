# Arquitectura

Componentes del sistema, cómo se comunican y las decisiones de diseño que hay detrás.

---

## 1. Vista general

Se clasifica la urgencia de un paciente (nivel Manchester **C1-C5**) a partir de su texto o audio, calcula un **score de ansiedad** y audita el resultado en busca de **sesgo emocional** (under-triage de pacientes muy angustiados).

El sistema se organiza en cuatro capas:


| Capa              | Responsabilidad                                                      | Piezas                                                          |
| ----------------- | -------------------------------------------------------------------- | --------------------------------------------------------------- |
| **Orquestación**  | Decidir qué tarea se ejecuta después de cada paso. No procesa texto. | Airflow (pipeline batch), n8n (event-driven: alertas y errores) |
| **Procesamiento** | Lógica de negocio. Microservicios FastAPI sin estado, `POST /run`.   | 13 servicios (Fase 1 + Fase 2)                                  |
| **Persistencia**  | Estado del dominio y trazabilidad.                                   | Postgres (`triage_db`), minIO (artefactos)                      |
| **Presentación**  | Entrada de casos y consulta de resultados.                           | api-gateway-ingesta/consulta, frontend Next.js                  |


Cada caso arrastra un `**GUID_Entrevista`** por todo el pipeline y cada llamada HTTP queda registrada en `Task_Log`. Esto nos permite reconstruir el flujo completo de cualquier caso.

---

## 2. Diagrama de contenedores

```
                           ┌─────────────────────────────┐
        paciente  ───────► │  frontend (Next.js)  :3000  │
        texto/audio        └──────────────┬──────────────┘
                                          │ HTTP
                    ┌─────────────────────┴─────────────────────┐
                    ▼                                            ▼
        ┌───────────────────────┐                  ┌────────────────────────┐
        │ api-gateway-ingesta    │                 │ api-gateway-consulta    │
        │        :8000           │                 │        :8001            │
        └───────────┬───────────┘                  └────────────┬───────────┘
                    │ dispara DAG (REST /api/v2 + JWT)           │ lee v_resultado_completo
                    ▼                                            │
        ┌───────────────────────────────────────────┐           │
        │              AIRFLOW  :8080                │           │
        │  api-server · scheduler · dag-processor    │           │
        │  (LocalExecutor)                           │           │
        │                                            │           │
        │  Fase 1: dag_text/audio_ingestion          │           │
        │  Fase 2: dag_prediction / evaluation /     │           │
        │          audit_ethics / model_training     │           │
        └───────────┬───────────────────────────────┘           │
                    │ HTTP POST /run a cada servicio                         
        ┌───────────┴───────────────────────────────────────────────────┐
        │  MICROSERVICIOS FastAPI                                          │
        │                                                                  │
        │  Fase 1: transcripcion(9100) preprocessing(9101)                 │
        │          llm-extraction(9110) llm-normalization(9111)            │
        │          llm-labeling(9112) anxiety-score(9113)                  │
        │  Fase 2: dataset-builder(9120) ml-training(9121)                 │
        │          ml-prediction(9122) evaluation(9123) audit-ethics(9124) │
        └───┬───────────────┬───────────────────┬───────────────┬─────────┘
            │ SQL           │ objetos S3        │ LLM            │ alerta sesgo
            ▼               ▼                   ▼                ▼
     ┌────────────┐  ┌────────────┐   ┌─────────────────┐  ┌──────────────┐
     │ Postgres   │  │  minIO     │   │ OpenRouter      │  │ n8n  :5678   │
     │   :5432    │  │ :9000/9001 │   │                 │  │ alerta/error │
     │ triage_db  │  │ 4 buckets  │   └─────────────────┘  └──────┬───────┘
     │ airflow_db │  └────────────┘                               │ 
     └────────────┘                                            (Gmail)

        Airflow on_failure_callback ──────────────────────────────► n8n /webhook/error
```

Todos los contenedores comparten la red Docker `triage_net`. Definición completa en `docker-compose.yml`.

---

## 3. Motor del flujo: n8n y Airflow

Dos orquestadores con roles separados.

**Airflow — pipeline batch con dependencias.** Fase 1 es una cadena de 6-7 pasos encadenados (no se normaliza antes de extraer); Airflow la modela como DAG. Aporta reintentos por tarea, ejecuciones programadas (`@hourly` para enriquecimiento y evaluación, `@daily` para reentreno) y logs por tarea.

**n8n — eventos puntuales.**

- Alerta clínica: `audit-ethics` detecta sesgo emocional → webhook n8n → email HTML vía Gmail.
- Notificación de errores: el `on_failure_callback` de cualquier DAG llama a `/webhook/error` → alerta técnica formateada.

La comunicación entre servicios es HTTP: el volumen es de casos individuales, sin streaming masivo.

---

## 4. El LLM en el pipeline

El triaje parte del **lenguaje natural libre** del paciente ("me falta el aire y siento que me muero").  Las siguientes tareas se resuelven con un LLM.


| Tarea                        | Servicio          | Rol del LLM                                                                      |
| ---------------------------- | ----------------- | -------------------------------------------------------------------------------- |
| Extracción de síntomas       | llm-extraction    | Lenguaje coloquial y bilingüe (corpus en inglés, salida en español).             |
| Traducción + resumen clínico | llm-extraction    | Normaliza el corpus inglés (Fareez et al.) a español clínico antes de etiquetar. |
| Normalización al diccionario | llm-normalization | Mapea expresiones libres a términos Manchester.                                  |
| Etiquetado Manchester        | llm-labeling      | Razonamiento clínico few-shot para asignar C1-C5 con justificación.              |
| Score de ansiedad            | anxiety-score     | Combina lexicón emocional con una valoración 0-1 del LLM.                        |


**Control sobre las alucinaciones.** El LLM no inventa términos clínicos: la normalización fuerza el mapeo contra el **diccionario** (`data/dictionaries/manchester_terms.csv`, 112 entradas EN+ES).

**Proveedor LLM.** `triage_common/llm.py` usa OpenRouter en cloud. Reintentos con `tenacity`.

---

## 5. LLM etiqueta, ML predice

El reparto de roles entre las dos fases es la decisión central del diseño:

- **Fase 1 (LLM)** genera la **etiqueta de referencia** (`triage_real`)
- **Fase 2 (modelo ML)** genera la **predicción** (`prediccion_ia`)

El LLM **etiqueta el dataset**; el modelo **aprende de ese dataset** y es lo que corre en inferencia real. Así se puede comparar `prediccion_ia` vs `triage_real` (`evaluation`) y auditar sesgos (`audit-ethics`).

---

## 6. Trazabilidad y estado

- `**GUID_Entrevista`**: identificador único generado en la ingesta; viaja en cada payload HTTP y en cada fila de BD. Reconstruye el flujo completo de un caso.
- `**Task_Log`**: una fila por llamada a servicio (`guid`, `service_name`, `timestamp_inicio/fin`, `status`, `payload_resultado`, `error_msg`).
- `**Entrevista.Estado`**: máquina de estados del caso (`RECIBIDO → ... → TEXTO_ENRIQUECIDO → PREDICHO → EVALUADO → AUDITADO`).

---

## 8. Contenedores, stack y puertos

### Contenedores

**14 microservicios propios**.


| Grupo                                      | Contenedores                                                                                                                                                                                                             |
| ------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Microservicios propios                     | frontend, api-gateway-ingesta, api-gateway-consulta, transcripcion, preprocessing, llm-extraction, llm-normalization, llm-labeling, anxiety-score, dataset-builder, ml-training, ml-prediction, evaluation, audit-ethics |
| Infraestructura                            | postgres, minio, airflow-api-server, airflow-scheduler, airflow-dag-processor, n8n                                                                                                                                       |
| Auxiliares (one-shot, arrancan y terminan) | minio-bootstrap (crea buckets), airflow-init (migra BD + crea admin), n8n-bootstrap (importa workflows)                                                                                                                  |


### Stack tecnológico


| Componente                  | Tecnología                                                                         |
| --------------------------- | ---------------------------------------------------------------------------------- |
| Lenguaje servicios          | Python 3.11                                                                        |
| API microservicios          | FastAPI                                                                            |
| Frontend                    | Next.js 16 · React 19 · TypeScript · Tailwind 4                                    |
| Orquestación batch          | Apache Airflow 3.0.5                                                               |
| Automatización event-driven | n8n 1.74.1                                                                         |
| LLM                         | OpenRouter (`openai/gpt-oss-120b:free`) · prompts Jinja2 · reintentos `tenacity`   |
| Transcripción audio         | faster-whisper                                                                     |
| Detección de idioma         | langdetect                                                                         |
| Machine Learning            | scikit-learn (TF-IDF + LogisticRegression/RandomForest/GradientBoosting), `joblib` |
| Base de datos               | PostgreSQL 15 (`psycopg2`)                                                         |
| Almacenamiento objetos      | minIO (compatible S3, cliente `minio`)                                             |
| Contenedores                | Docker Compose                                                                     |


### Red y puertos (host)


| Puerto      | Servicio             | Uso                        |
| ----------- | -------------------- | -------------------------- |
| 3000        | frontend             | Dashboard Next.js          |
| 8000        | api-gateway-ingesta  | Entrada de casos           |
| 8001        | api-gateway-consulta | Lectura de resultados      |
| 8080        | airflow-api-server   | UI + REST `/api/v2`        |
| 5678        | n8n                  | Webhooks + UI              |
| 5432        | postgres             | `triage_db` + `airflow_db` |
| 9000 / 9001 | minio                | API S3 / consola web       |
| 9100        | transcripcion        | Audio → texto              |
| 9101        | preprocessing        | Limpieza de texto          |
| 9110        | llm-extraction       | Extracción de síntomas     |
| 9111        | llm-normalization    | Mapeo al diccionario       |
| 9112        | llm-labeling         | Etiquetado Manchester      |
| 9113        | anxiety-score        | Score de ansiedad          |
| 9120        | dataset-builder      | Datasets a minIO           |
| 9121        | ml-training          | Entrenamiento del modelo   |
| 9122        | ml-prediction        | Predicción Fase 2          |
| 9123        | evaluation           | Validación predicción      |
| 9124        | audit-ethics         | Auditoría ética + alerta   |


