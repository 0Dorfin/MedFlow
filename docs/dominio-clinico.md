# Dominio clínico

Las reglas clínicas del sistema: niveles de triaje Manchester, diccionario de síntomas, score de ansiedad y auditoría ética.

---

## 1. Niveles Manchester (C1-C5)

El triaje asigna a cada caso uno de cinco niveles de urgencia. Menor número = más urgente.


| Nivel  | Color    | Tiempo máx. de atención | Significado                        |
| ------ | -------- | ----------------------- | ---------------------------------- |
| **C1** | Rojo     | 0 min (inmediato)       | Riesgo vital. Atención sin demora. |
| **C2** | Naranja  | 10 min                  | Muy urgente.                       |
| **C3** | Amarillo | 60 min                  | Urgente.                           |
| **C4** | Verde    | 120 min                 | Normal.                            |
| **C5** | Azul     | 240 min                 | No urgente.                        |


---

## 2. Grupos clínicos

Cada síntoma pertenece a un grupo funcional. Sirve para agrupar y dar contexto al caso (`GrupoClinico`):


| Grupo  | Dominio              | Términos en diccionario |
| ------ | -------------------- | ----------------------- |
| `RES`  | Respiratorio         | 41                      |
| `OTRO` | Inespecífico / otros | 28                      |
| `CAR`  | Cardiológico         | 17                      |
| `MSK`  | Musculoesquelético   | 14                      |
| `GAS`  | Gastrointestinal     | 12                      |


---

## 3. Diccionario cerrado de síntomas

`data/dictionaries/manchester_terms.csv` — 112 entradas. Cuatro columnas:

```
sintoma_coloquial, termino_clinico, prioridad_sugerida, grupo_clinico
"me ahogo",        disnea,          C1,                 RES
"falta de aire",   disnea,          C2,                 RES
```

- `sintoma_coloquial`: cómo lo dice el paciente.
- `**termino_clinico**`: término canónico (lo que se guarda en `entidades_normalizadas_es`).
- `**prioridad_sugerida**`: nivel Manchester orientativo del síntoma.
- `**grupo_clinico**`: RES/MSK/CAR/GAS/OTRO.

**Por qué cerrado.** El sistema **no inventa síntomas**. La normalización fuerza el mapeo de expresiones libres a términos de esta lista; lo que no encaja se marca como `no_mapeadas`. Esto mantiene el vocabulario clínico controlado y hace las features del modelo reproducibles.

---

## 4. Score de ansiedad (0-1)

Mide la **carga emocional subjetiva** del paciente, **independiente de la gravedad clínica**. Un paciente puede estar aterrado con una dolencia leve (score alto, triaje bajo) o tranquilo con algo grave (score bajo, triaje alto). Esa independencia es la clave de la auditoría.

Se calcula combinando dos señales (`anxiety-score/main.py`):

1. **Lexicón emocional bilingüe** (`ANXIETY_LEXICON`): términos ES+EN con peso (`"pánico"`→0.95, `"me ahogo"`→0.85, `"can't breathe"`→0.9, `"scared"`→0.7…). `lexicon_score` = peso máximo de los términos presentes.
2. **Valoración del LLM**: prompt calibrado que devuelve un decimal 0.00-1.00 (0.0 calma, 0.5 ansioso, 1.0 pánico extremo).

Combinación:

- Si el texto **no contiene** ninguna palabra de la lista: vale el score del LLM directamente.
- Si **contiene** alguna: se mezcla con el LLM, pero nunca baja del peso de esa palabra (y sube si el LLM detecta más angustia). Así una palabra de pánico garantiza score alto aunque el LLM falle.

Se calcula sobre el **texto crudo** (`texto_original_en` si existe), no sobre el resumen clínico neutro, para no perder la emoción original.

---

## 5. Auditoría ética

Tras predecir y validar, se comprueba si el modelo cometió un fallo por **sesgo emocional**.

### Tipos de desviación

Comparando `prediccion_ia` con `triage_real` (`under_triage`/`over_triage` en `contracts.py`):


| Desviación       | Definición                                                           | Riesgo                                |
| ---------------- | -------------------------------------------------------------------- | ------------------------------------- |
| **Acierto**      | predicción = real                                                    | —                                     |
| **Under-triage** | predicción menos urgente que la real (`pred.numeric > real.numeric`) | **Peligroso**: subestima la gravedad. |
| **Over-triage**  | predicción más urgente que la real                                   | Falso positivo, sin riesgo clínico.   |


### Detección de sesgo emocional

`audit-ethics` aplica `ANXIETY_BIAS_THRESHOLD = 0.8`:

- **Under-triage con `score_ansiedad_ia >= 0.8`** → **sesgo emocional detectado**. El modelo infravaloró a un paciente con alta carga emocional. Se registra `motivo_fallo` y `accion_correctiva` y se **dispara alerta n8n** → email al clínico.
- Under-triage sin esa carga → "revisión humana del caso".
- Over-triage → "monitorizar falsos positivos. Sin riesgo clínico".

### Vista de auditoría

`v_auditoria_clinica` expone solo las desviaciones (Under/Over) con un `estatus` derivado:


| Condición                                 | `estatus`   |
| ----------------------------------------- | ----------- |
| `motivo_fallo` contiene "sesgo emocional" | `RECHAZADO` |
| Under-triage (resto)                      | `REVISAR`   |
| Over-triage                               | `ACEPTABLE` |
