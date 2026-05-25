# Gestión de errores

Cómo el sistema detecta, reintenta, registra y notifica los fallos del pipeline.

---

## 1. Defensa en capas

Un fallo se contiene en la capa más cercana posible. Si la supera, escala a la siguiente.


| Capa                    | Dónde                                   | Qué hace ante un fallo                                                                                              |
| ----------------------- | --------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| **Cliente LLM**         | `triage_common/llm.py`                  | Reintenta la llamada al proveedor con backoff exponencial (`tenacity`). Si agota, lanza `LLMError`.                 |
| **Servicio FastAPI**    | `services/*/main.py`                    | `try/except` alrededor de la lógica. Registra `Task_Log` con `status=ERROR` + `error_msg` y responde HTTP de error. |
| **Orquestador Airflow** | `airflow/dags/`                         | La tarea ve el HTTP de error → falla → reintenta (`retries=2`). Si agota, dispara `on_failure_callback`.            |
| **Notificación n8n**    | `n8n/workflows/error_notification.json` | Recibe el callback → formatea alerta → email al responsable.                                                        |


Resultado: un fallo transitorio (timeout del LLM, reinicio de un contenedor) casi siempre se resuelve solo por reintento; un fallo persistente queda **registrado en Postgres** y **notificado por email**, sin perder la trazabilidad del caso.

---

## 2. Estrategias de reintento

### Airflow (por tarea)

Definidas en `DEFAULT_ARGS` (`airflow/dags/triage_helpers.py`):

```
retries = 2
retry_delay = 15 s
on_failure_callback = notify_n8n
```

Cada tarea del DAG (una llamada `POST /run` a un servicio) se reintenta 2 veces con 15 s de espera antes de darse por fallida.

### Cliente LLM (por llamada)

Definidas con `tenacity` en `llm.py` (`_call_openrouter` / `_call_generate`):

```
stop  = stop_after_attempt(LLM_MAX_RETRIES)   # por defecto 3
wait  = wait_exponential(min=1 s, max=10 s)
retry = solo sobre httpx.HTTPError
reraise = True
timeout = LLM_TIMEOUT                          # por defecto 120 s
```

Solo reintenta errores de HTTP (timeout, 5xx, conexión). Un JSON malformado (`LLMInvalidJSON`) o falta de `OPENROUTER_API_KEY` **no** se reintentan: son fallos deterministas, reintentarlos no ayuda.

---

## 3. Registro de errores en Postgres

Toda llamada a un servicio escribe una fila en `**Task_Log`** (`db.log_task`), tanto en éxito como en error:


| Campo                                | En error                    |
| ------------------------------------ | --------------------------- |
| `status`                             | `ERROR`                     |
| `error_msg`                          | mensaje de la excepción     |
| `timestamp_inicio` / `timestamp_fin` | marca cuándo empezó y falló |
| `payload_resultado`                  | `NULL` (no hubo resultado)  |


Patrón en cada servicio (ejemplo `llm-labeling/main.py`):

```python
try:
    payload = get_client().render_and_generate_json(...)
except llm.LLMError as exc:
    _log_error(req.guid, started, str(exc))      # Task_Log status=ERROR
    raise HTTPException(status_code=502, detail=f"LLM error: {exc}")
```

Además, el `**Estado**` de la `Entrevista` solo avanza si la etapa termina bien (`update_entrevista_estado` se llama tras el `upsert`, no antes). Un caso que falla en etiquetado se queda en `ENTIDADES_NORMALIZADAS`: el estado indica exactamente hasta dónde llegó. Combinado con `Task_Log`, se reconstruye qué pasó y dónde.

---

## 4. Notificación de errores (n8n)

Cuando una tarea de Airflow agota sus reintentos, `on_failure_callback` → `notify_n8n` hace `POST` al webhook `error_notification` con:

```json
{ "dag_id": "...", "task_id": "...", "run_id": "...",
  "guid": "...", "error": "...", "ts": "...", "destinatario": "<clinico>" }
```

El workflow `error_notification` (webhook `/error`) formatea la alerta, envía email vía Gmail, loguea en consola y responde.

---

## 5. Escenarios concretos

### Falla un servicio

Airflow recibe un HTTP de error (o timeout de `post_json`, 240 s) → la tarea falla → 2 reintentos con 15 s. Si el servicio sigue caído, la tarea queda `failed`, salta `on_failure_callback` → email. El `Estado` de la `Entrevista` no avanza; el caso es recuperable relanzando el DAG.

### El LLM no responde

`tenacity` reintenta hasta 3 veces con backoff (1→10 s). Si agota, `LLMError` sube al servicio → `Task_Log` `ERROR` + `HTTPException 502` → Airflow ve el 502 y reintenta la tarea entera (otra ronda de hasta 3 intentos LLM). Si persiste → notificación n8n. Para JSON corrupto (`LLMInvalidJSON`), no hay reintento: falla directo y se registra.

### Una tarea del workflow no llega a ejecutarse

El `Estado` de la `Entrevista` no progresa: el caso permanece en el estado anterior. Los **DAGs batch** (`@hourly`) recogen lo pendiente por estado — `dag_llm_enrichment` busca `RECIBIDO`, `dag_evaluation` busca `PREDICHO`, `dag_audit_ethics` busca `EVALUADO` (`list_guids_in_state`). Esto da recuperación automática sin intervención.

### Postgres o minIO caídos

Los servicios fallan al conectar → la tarea de Airflow falla → reintentos. Como el avance de `Estado` es transaccional, no quedan estados a medias: al recuperarse la infraestructura, el reintento (o el siguiente barrido batch) retoma el caso.