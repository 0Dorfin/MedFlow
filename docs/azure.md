# Azure (local / cloud)

Cada paso de IA del pipeline tiene dos implementaciones intercambiables: una **local** (gratis, sin dependencias cloud) y una sobre **Azure AI**. Se elige con una variable de entorno, sin tocar código.

Solo la capa de IA es intercambiable. El ML clásico, la lógica de negocio y la infraestructura quedan fijos y no dependen de ningún proveedor cloud.

---

## 1. Backends conmutables


| Paso                                   | `local`         | `azure`                                              | Variable                |
| -------------------------------------- | --------------- | ---------------------------------------------------- | ----------------------- |
| LLM (extracción, etiquetado, ansiedad) | OpenRouter      | Azure OpenAI `gpt-4o-mini` (SDK `openai`)            | `LLM_BACKEND`           |
| Transcripción                          | whisperx        | Azure AI Speech (diarización gestionada, sin `HF_TOKEN` ni GPU) | `TRANSCRIPTION_BACKEND` |
| Normalización                          | diccionario CSV | Azure AI Search (búsqueda semántica)                 | `NORMALIZATION_BACKEND` |
| Redacción PII                          | regex           | Azure AI Language (auto es/en)                       | `PII_BACKEND`           |


Cada variable acepta `local` (por defecto) o `azure`.

## 2. Qué corre en Azure


| Capacidad                                            | Backend Azure              |
| ---------------------------------------------------- | -------------------------- |
| LLM: extracción, etiquetado, ansiedad                | Azure OpenAI `gpt-4o-mini` |
| Speech: transcripción + diarización (aísla paciente) | Azure AI Speech            |
| Normalización semántica                              | Azure AI Search            |
| Redacción PII (es/en)                                | Azure AI Language          |


**Local por diseño** (no se migra): ML sklearn, evaluación/auditoría, lexicón de ansiedad e infraestructura (Postgres, minIO, Airflow, n8n, frontend).

---

## 3. Decisiones y resultados

**Normalización literal vs semántica.** El diccionario CSV hace match exacto/substring y pierde variantes ("no me llega el aire" no casa con "me ahogo"). Azure AI Search lo resuelve por búsqueda semántica, pero sin umbral sobre-empareja. Medido sobre el corpus fareez (accuracy de grupo):


| Backend normalización                      | accuracy de grupo             |
| ------------------------------------------ | ----------------------------- |
| CSV literal                                | 0.50                          |
| AI Search sin umbral                       | 0.29                          |
| AI Search con `AZURE_SEARCH_MIN_SCORE=4.0` | 0.50 + variantes lingüísticas |


Con umbral iguala la precisión del CSV y capta variantes que el literal pierde.

**PII:** Azure AI Language redacta nombres y teléfonos (es/en, idioma auto-detectado) que el regex no cubre, conservando el *onset* clínico ("desde anoche") mediante `categories_filter` (no redacta DateTime).

**Speech:** `ConversationTranscriber` diariza médico/paciente y aísla la voz del paciente.

**Seguridad:** Acceso keyless con `DefaultAzureCredential` en el código; las claves van como variables de entorno (y GitHub Secrets en CI).

---

## 4. Recursos y configuración


| Recurso                      | Uso                                       |
| ---------------------------- | ----------------------------------------- |
| Azure OpenAI (`gpt-4o-mini`) | LLM: extracción, etiquetado, ansiedad     |
| Azure AI Speech              | transcripción + diarización               |
| Azure AI Search              | índice `manchester-terms` (normalización) |
| Azure AI Language            | detección/redacción de PII                |


Variables en `.env` (plantilla en `.env.example`): `*_BACKEND`, `AZURE_AI_`*, `AZURE_SPEECH_`*, `AZURE_SEARCH_*`, `AZURE_LANGUAGE_*`.

Ingesta del índice (una vez): `python services/_common/scripts/ingest_manchester_search.py` (sube el diccionario Manchester, 112 documentos).