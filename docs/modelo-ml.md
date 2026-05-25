# Modelo de Machine Learning

Clasificador que predice el nivel Manchester (**C1-C5**) de un caso a partir de su texto clínico y sus síntomas normalizados.

---

## 1. Dataset

Lo construye **dataset-builder** y lo deja en `minio://datasets/` como Parquet.


| Modo | Origen                                            | Uso                     |
| ---- | ------------------------------------------------- | ----------------------- |
| `f1` | tabla `Texto_Procesado` (filas con `triage_real`) | Entrenamiento           |
| `f2` | vista `v_resultado_completo`                      | Validación + inferencia |


Columnas: `guid`, `id_caso`, `origen`, `texto_original_en`, `resumen_es`, `entidades_extraidas_es`, `entidades_normalizadas_es`, `score_ansiedad`, `triage_real`.

---

## 2. Variables de entrenamiento

Dos bloques concatenados con `hstack` (`pipeline.py:_make_vectorizers`):


| Bloque   | Técnica                                                     | Sobre                       |
| -------- | ----------------------------------------------------------- | --------------------------- |
| Texto    | `TfidfVectorizer(ngram_range=(1,2), min_df=1, max_df=0.95)` | `resumen_es`                |
| Síntomas | `MultiLabelBinarizer` (multi-hot)                           | `entidades_normalizadas_es` |


El TF-IDF capta el lenguaje del resumen clínico; el multi-hot codifica qué síntomas canónicos del diccionario Manchester están presentes. Juntos dan señal léxica + señal estructurada.

**Etiqueta** (`y`): `triage_real` (C1-C5).

---

## 3. Algoritmo

Se entrenan **3 candidatos** y se elige el mejor por F1-macro.


| Candidato             | Configuración                                                                                     |
| --------------------- | ------------------------------------------------------------------------------------------------- |
| `logistic_regression` | `class_weight="balanced"`, `solver="liblinear"`, `multi_class="ovr"`, `max_iter=1000`             |
| `random_forest`       | `class_weight="balanced"`, `n_estimators=200`, `random_state=42`                                  |
| `gradient_boosting`   | `n_estimators=120`, `random_state=42` (sin `class_weight`; el estimador de sklearn no lo soporta) |


`class_weight="balanced"` en los dos primeros compensa el **desbalance de clases** (hay muchos menos C1 que C3/C4).

**Selección.** Por cada candidato se evalúa con `cross_val_predict` sobre `StratifiedKFold(n_splits, shuffle, random_state=42)`, donde `n_splits = min(5, tamaño de la clase más pequeña)`. Se ordena por `f1_macro` descendente y se toma el primero. El ganador se **reentrena sobre el dataset completo** antes de guardarlo.

**Caso de pocos datos.** Si alguna clase tiene <2 ejemplos, `_safe_cv` devuelve 0: no hay validación cruzada posible, se entrena y predice sobre el mismo conjunto. Las métricas resultantes son optimistas y `cv_splits=0` lo señala. Es una salvaguarda para datasets muy pequeños, no el modo normal.

---

## 4. Métricas

`_compute_metrics` calcula, para cada candidato y para el elegido:

- `accuracy`
- `f1_macro` (criterio de selección — robusto al desbalance)
- `recall_per_class` (recall por nivel; el recall de C1/C2 es el que importa clínicamente)
- `classification_report` completo
- `confusion_matrix`
- `cv_splits` (0 si no hubo CV)

Se persisten en `minio://modelos/{run_id}-metrics.json` con `selected_model`, métricas de todos los `candidates` y bloque `best`.

---

## 5. Guardado y carga del modelo

**Guardado** (`ml-training`): `joblib.dump` de un único objeto pipeline que empaqueta todo lo necesario para predecir:

```python
{ "estimator_name", "estimator", "tfidf", "mlb", "classes" }
```

→ `minio://modelos/{run_id}.joblib` (+ `{run_id}-metrics.json`). `run_id` por defecto es un timestamp `YYYYMMDDTHHMMSS`, así que cada entrenamiento queda versionado sin pisar el anterior.

**Carga** (`ml-prediction`): `_latest_model_url` lista los `.joblib` del bucket, los ordena y carga **el más reciente** en caché. La predicción aplica el mismo `tfidf` + `mlb` guardados (sin re-fit) y devuelve clase + `predict_proba` por nivel. `POST /reload` fuerza recargar el último modelo (lo invoca `dag_model_training` tras reentrenar); `?dry_run=true` predice sin escribir en BD.

Empaquetar vectorizadores y estimador juntos garantiza que inferencia use exactamente la misma transformación que entrenamiento.

---

## 6. Flujo completo (DAG `dag_model_training`)

```
build_dataset (f1)  →  ml-training  →  ml-prediction /reload
   Parquet              .joblib +          carga modelo
   en minIO             metrics.json       más reciente
```

Programado `@daily` (o manual). A partir de ahí `dag_prediction_phase_2` usa el modelo cargado para predecir casos nuevos.

---

## 7. Limitaciones conocidas

- Con dataset pequeño la CV se degrada (`cv_splits` bajo o 0) y las métricas pierden fiabilidad. La señal de alerta es `cv_splits`.
- `gradient_boosting` no pondera clases; en datasets muy desbalanceados parte en desventaja frente a los otros dos.
- El modelo depende de la calidad de `triage_real` (etiqueta del LLM): si la Fase 1 etiqueta mal, el modelo aprende ese error. Por eso existen `evaluation` y `audit-ethics`.

