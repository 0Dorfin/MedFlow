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

Dos bloques concatenados (`ColumnTransformer` / `hstack` en `pipeline.py:_make_vectorizers`):


| Bloque   | Técnica                                                     | Sobre                       |
| -------- | ----------------------------------------------------------- | --------------------------- |
| Texto    | `TfidfVectorizer(ngram_range=(1,2), min_df=1, max_df=0.95)` | `resumen_es`                |
| Síntomas | `MultiLabelBinarizer` con **vocabulario cerrado**           | `entidades_normalizadas_es` |


El TF-IDF capta el lenguaje del resumen clínico; el multi-hot codifica qué síntomas canónicos del diccionario Manchester están presentes.

**Vocabulario cerrado.** El multi-hot se ajusta con los `termino_clinico` de `data/dictionaries/manchester_terms.csv` (30 términos), **no** con lo que aparezca en cada fold.

**Etiqueta** (`y`): `triage_real` (C1-C5).

---

## 3. Algoritmo

Se entrenan **3 modelos** y se elige el mejor por F1-macro.


| Candidato             | Configuración                                                                                     |
| --------------------- | ------------------------------------------------------------------------------------------------- |
| `logistic_regression` | `class_weight="balanced"`, `max_iter=1000` (solver `lbfgs` por defecto, multinomial)              |
| `random_forest`       | `class_weight="balanced"`, `n_estimators=200`, `random_state=42`                                  |
| `gradient_boosting`   | `n_estimators=120`, `random_state=42` (sin `class_weight`; el estimador de sklearn no lo soporta) |


`class_weight="balanced"` en los dos primeros compensa el desbalance de clases (hay muchos menos C1 que C3/C4).

`**class_weight` frente a SMOTE.** Se evaluó SMOTE como alternativa al reponderado. Mejora marginal en F1-macro de LogReg (0.712 vs 0.698) pero a costa de recall en C2/C4 y mayor under-triage. **Decisión:** `class_weight`, por dataset pequeño y features dispersas.

**Validación anti-leakage.** Los casos aumentados (`CAR_AUG_001`, ...) comparten origen con su semilla. Para que un caso y su augmentado no caigan en folds distintos usamos `StratifiedGroupKFold`, agrupando por el prefijo previo a `_AUG_`. `n_splits = min(5, tamaño de la clase más pequeña)`.

**Selección.** Por cada modelo se evalúa con `cross_val_predict` (cada fila predicha por un modelo que no la vio). Se ordena por `f1_macro` descendente y se toma el primero. El ganador se **reentrena sobre el dataset completo** antes de guardarlo.

**Caso de pocos datos.** Si alguna clase tiene <2 ejemplos, `_safe_cv` devuelve 0: no hay CV posible, se entrena y predice sobre el mismo conjunto.

---

## 4. Métricas

`_compute_metrics` calcula, para cada modelo y para el elegido:

- `accuracy`
- `f1_macro` (robusto al desbalance)
- `recall_per_class` (el recall de C1/C2 es el que importa clínicamente)
- `under_triage_rate` (proporción de casos predichos en un nivel **menos urgente** que el real: el error clínicamente peligroso)
- `classification_report` completo
- `confusion_matrix`
- `cv_splits` (0 si no hubo CV)

Se persisten en `minio://modelos/{run_id}-metrics.json` con `selected_model`, métricas de todos los `candidates` y bloque `best`.

---

## 5. Guardado y carga del modelo

**Guardado** (`ml-training`): `joblib.dump` de un único objeto pipeline:

```python
{ "estimator_name", "estimator", "tfidf", "mlb", "classes" }
```

`minio://modelos/{run_id}.joblib` (+ `{run_id}-metrics.json`). `run_id` por defecto es un timestamp `YYYYMMDDTHHMMSS`, así cada entrenamiento queda versionado sin pisar el anterior.

**Carga** (`ml-prediction`): `_latest_model_url` lista los `.joblib`, los ordena y carga el más reciente en caché. La predicción aplica el mismo `tfidf` + `mlb` guardados (sin re-fit) y devuelve clase + `predict_proba` por nivel. `POST /reload` fuerza recargar; `?dry_run=true` predice sin escribir en BD.

---

## 6. Flujo completo (DAG `dag_model_training`)

```
build_dataset (f1)  →  ml-training  →  ml-prediction /reload
   Parquet              .joblib +          carga modelo
   en minIO             metrics.json       más reciente
```

Programado `@daily` (o manual). A partir de ahí `dag_prediction_phase_2` usa el modelo cargado para predecir casos nuevos.