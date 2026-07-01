# CI: tests y regression gate

Cambiar un prompt o el modelo puede degradar el triaje en silencio. La CI (GitHub Actions) corre la evaluación de forma automática y bloquea cambios que rompan la calidad antes de que lleguen a `master`.

---

## 1. Workflows


| Workflow                   | Fichero                       | Trigger                                                             | Qué hace                                                       |
| -------------------------- | ----------------------------- | ------------------------------------------------------------------- | -------------------------------------------------------------- |
| `tests`                    | `.github/workflows/tests.yml` | cada push                                                           | corre `pytest` en `services/_common`                           |
| `eval` (`regression-eval`) | `.github/workflows/eval.yml`  | toda PR (+ push del workflow / manual) | evalúa solo si cambian `data/prompts/**`: compara con el baseline y falla si hay regresión; en PR sin prompts reporta verde sin evaluar |


---

## 2. El regression gate

En un PR que toca un prompt, el job `regression-eval`:

1. Corre `services/_common/scripts/eval_fareez.py` sobre el corpus fareez y escribe `eval-result.json` con el `accuracy_grupo`.
2. Corre `services/_common/scripts/compare_eval.py`, que lo compara con el baseline (`services/_common/eval-baseline.json`, el accuracy aceptado).
3. Si la caída supera `MAX_DROP` (0.05 por defecto) → **exit 1** → el job falla → el check del PR sale en rojo.

Si el PR **no** toca prompts, el job reporta verde sin ejecutar el eval. El check es requerido en toda PR (debe reportar siempre), pero el eval Azure solo se ejecuta cuando hay prompts que evaluar.

**Por qué usar un umbral.** El LLM no es determinista y la muestra es pequeña, así que el accuracy oscila por ruido. Sin umbral, el gate fallaría por ruido y daría falsas alarmas.

---

## 3. Bloqueo de merge

Un **branch ruleset** sobre `master` exige que el check `regression-eval` pase (*Require status checks to pass*). Un PR hacia `master` con el eval en rojo **no se puede mergear**.

Si un cambio de prompt **mejora** el eval, actualiza `eval-baseline.json` en el mismo PR. Así el nuevo mínimo queda en git y los PRs futuros se comparan contra esa cifra, no contra la antigua.

---

## 4. Secrets

El eval llama a Azure desde el runner, así que las claves van como **GitHub Secrets** nunca en el código:

- `AZURE_AI_KEY`, `AZURE_AI_ENDPOINT`, `AZURE_AI_DEPLOYMENT`

El workflow los inyecta como variables de entorno; GitHub los censura en los logs.