import { postForm, postJson } from "./api";
import {
  TIMEOUT_INGESTA_MS,
  TIMEOUT_LLM_MS,
  TIMEOUT_ML_MS,
  TIMEOUT_TRANSCRIPCION_MS,
} from "./timeouts";
import type {
  NormalizedEntity,
  PipelineOptions,
  PipelineOutput,
  PipelineStep,
  PipelineStepId,
  TriageResult,
} from "./types";
import { isManchesterCode, type ManchesterCode } from "./manchester";

type IngestaResponse = { guid: string; estado: string; workflow_id?: string | null };
type TranscribeResponse = { guid: string; texto: string; language: string; duration_seconds: number };
type PreprocessResponse = { guid: string; texto_preprocesado: string };
type ExtractResponse = { guid: string; entidades: string[] };
type NormalizeResponse = {
  guid: string;
  entidades_normalizadas: NormalizedEntity[];
  no_mapeadas: string[];
};
type LabelResponse = { guid: string; triage: ManchesterCode; justificacion: string };
type ScoreResponse = { guid: string; score_ansiedad: number };
type PredictResponse = {
  guid: string;
  prediccion_ia: ManchesterCode;
  score_ansiedad_ia: number;
  probabilidades: Partial<Record<ManchesterCode, number>>;
};
type AuditResponse = {
  guid: string;
  validacion: string;
  motivo_fallo?: string | null;
  sesgo_emocional_detectado?: boolean;
};

const STEP_LABELS: Record<PipelineStepId, string> = {
  ingesta: "Ingesta del audio",
  transcripcion: "Transcripción Whisper",
  preprocessing: "Preprocesamiento",
  extraction: "Extracción de entidades",
  normalization: "Normalización Manchester",
  labeling: "Etiquetado LLM",
  anxiety: "Score de ansiedad",
  prediction: "Predicción ML",
  audit: "Auditoría ética",
};

const STEP_SHORT: Record<PipelineStepId, string> = {
  ingesta: "Ingesta",
  transcripcion: "STT",
  preprocessing: "Prep",
  extraction: "NER",
  normalization: "Norm",
  labeling: "Triage",
  anxiety: "Ansiedad",
  prediction: "ML",
  audit: "Audit",
};

const AUDIO_STEPS: PipelineStepId[] = [
  "ingesta",
  "transcripcion",
  "preprocessing",
  "extraction",
  "normalization",
  "labeling",
  "anxiety",
  "prediction",
];

const TEXT_STEPS: PipelineStepId[] = [
  "ingesta",
  "preprocessing",
  "extraction",
  "normalization",
  "labeling",
  "anxiety",
  "prediction",
];

function buildSteps(baseIds: PipelineStepId[], extraAudit: boolean): PipelineStep[] {
  const ids = extraAudit ? [...baseIds, "audit" as PipelineStepId] : baseIds;
  return ids.map((id) => ({
    id,
    label: STEP_LABELS[id],
    shortLabel: STEP_SHORT[id],
    status: "pending",
  }));
}

const MAX_ATTEMPTS = 3;
const RETRY_BASE_MS = 600;

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function runStep<T>(
  steps: PipelineStep[],
  id: PipelineStepId,
  fn: () => Promise<T>,
  onUpdate: (steps: PipelineStep[]) => void,
): Promise<T> {
  const target = steps.find((s) => s.id === id);
  if (!target) throw new Error(`Paso desconocido: ${id}`);

  target.status = "running";
  target.error = undefined;
  onUpdate([...steps]);

  const started = performance.now();
  let lastError: unknown;

  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt += 1) {
    try {
      const result = await fn();
      target.status = "ok";
      target.durationMs = performance.now() - started;
      target.response = result;
      onUpdate([...steps]);
      return result;
    } catch (err) {
      lastError = err;
      if (attempt < MAX_ATTEMPTS) {
        target.status = "running";
        target.error = `Reintentando (${attempt}/${MAX_ATTEMPTS})`;
        onUpdate([...steps]);
        await delay(RETRY_BASE_MS * attempt);
      }
    }
  }

  const message = lastError instanceof Error ? lastError.message : "Error desconocido";
  target.status = "error";
  target.durationMs = performance.now() - started;
  target.error = `${message} (tras ${MAX_ATTEMPTS} intentos)`;
  onUpdate([...steps]);
  throw lastError;
}

function audioUri(guid: string): string {
  return `s3://audio-original/${guid}.wav`;
}

async function notifyTriajeUrgente(body: {
  guid: string;
  id_caso: string | null;
  clasificacion: ManchesterCode;
  score_ansiedad_ia: number | null;
  resumen: string;
}): Promise<void> {
  try {
    await fetch("/api/n8n/triaje-procesado", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    return;
  }
}

async function runAnalysis(
  steps: PipelineStep[],
  guid: string,
  texto: string,
  textoTranscrito: string,
  options: PipelineOptions,
  pasos: Partial<Record<PipelineStepId, unknown>>,
  onUpdate: (steps: PipelineStep[]) => void,
): Promise<TriageResult> {
  const preprocessed = await runStep(
    steps,
    "preprocessing",
    () => postJson<PreprocessResponse>("/api/preprocessing/run", { guid, texto }),
    onUpdate,
  );
  pasos.preprocessing = preprocessed;
  const cleaned = preprocessed.texto_preprocesado || texto;

  const extracted = await runStep(
    steps,
    "extraction",
    () =>
      postJson<ExtractResponse>(
        "/api/extraction/run",
        { guid, texto: cleaned, language: "es" },
        TIMEOUT_LLM_MS,
      ),
    onUpdate,
  );
  pasos.extraction = extracted;

  const normalized = await runStep(
    steps,
    "normalization",
    () =>
      postJson<NormalizeResponse>(
        "/api/normalization/run",
        { guid, entidades_extraidas: extracted.entidades },
        TIMEOUT_LLM_MS,
      ),
    onUpdate,
  );
  pasos.normalization = normalized;

  const labeled = await runStep(
    steps,
    "labeling",
    () =>
      postJson<LabelResponse>(
        "/api/labeling/run",
        {
          guid,
          resumen_es: cleaned,
          entidades_normalizadas: normalized.entidades_normalizadas,
        },
        TIMEOUT_LLM_MS,
      ),
    onUpdate,
  );
  pasos.labeling = labeled;

  const anxiety = await runStep(
    steps,
    "anxiety",
    () => postJson<ScoreResponse>("/api/anxiety/run", { guid, texto: cleaned }, TIMEOUT_LLM_MS),
    onUpdate,
  );
  pasos.anxiety = anxiety;

  let prediccionIa: ManchesterCode | null = null;
  let scoreAnsiedadIa: number | null = null;
  let probabilidades: Partial<Record<ManchesterCode, number>> = {};

  try {
    const predTerms = normalized.entidades_normalizadas.map((e) => e.termino_clinico);
    const predicted = await runStep(
      steps,
      "prediction",
      () =>
        postJson<PredictResponse>(
          "/api/prediction/run",
          { guid, texto: cleaned, entidades_normalizadas: predTerms },
          TIMEOUT_ML_MS,
        ),
      onUpdate,
    );
    prediccionIa = predicted.prediccion_ia;
    scoreAnsiedadIa = predicted.score_ansiedad_ia;
    probabilidades = predicted.probabilidades ?? {};
    pasos.prediction = predicted;
  } catch {
    const pred = steps.find((s) => s.id === "prediction");
    if (pred) {
      pred.status = "error";
      pred.error = "Modelo ML no disponible";
    }
    onUpdate([...steps]);
  }

  if (prediccionIa === "C1" || prediccionIa === "C2") {
    void notifyTriajeUrgente({
      guid,
      id_caso: options.idCaso ?? null,
      clasificacion: prediccionIa,
      score_ansiedad_ia: scoreAnsiedadIa,
      resumen: cleaned,
    });
  }

  let validacion: string | null = null;
  let motivoFallo: string | null = null;
  let sesgoEmocional = false;

  if (options.groundTruth && prediccionIa) {
    const audited = await runStep(
      steps,
      "audit",
      () =>
        postJson<AuditResponse>("/api/audit/run", {
          guid,
          prediccion_ia: prediccionIa,
          triage_real: options.groundTruth,
          score_ansiedad_ia: scoreAnsiedadIa ?? 0,
        }),
      onUpdate,
    );
    validacion = audited.validacion;
    motivoFallo = audited.motivo_fallo ?? null;
    sesgoEmocional = Boolean(audited.sesgo_emocional_detectado);
    pasos.audit = audited;
  }

  const triageLlm = isManchesterCode(labeled.triage) ? labeled.triage : null;

  return {
    guid,
    textoTranscrito,
    textoPreprocesado: cleaned,
    triageLlm,
    justificacion: labeled.justificacion,
    entidades: extracted.entidades,
    entidadesNormalizadas: normalized.entidades_normalizadas,
    noMapeadas: normalized.no_mapeadas,
    scoreAnsiedad: anxiety.score_ansiedad,
    prediccionIa,
    scoreAnsiedadIa,
    probabilidades,
    groundTruth: options.groundTruth ?? null,
    validacion,
    motivoFallo,
    sesgoEmocional,
  };
}

export async function runAudioPipeline(
  audio: Blob,
  fileName: string,
  options: PipelineOptions,
  onUpdate: (steps: PipelineStep[]) => void,
): Promise<PipelineOutput> {
  const steps = buildSteps(AUDIO_STEPS, Boolean(options.groundTruth));
  const pasos: Partial<Record<PipelineStepId, unknown>> = {};
  onUpdate(steps);

  const ingesta = await runStep(
    steps,
    "ingesta",
    async () => {
      const form = new FormData();
      form.append("audio", audio, fileName);
      form.append("origen", options.origen);
      if (options.idCaso) form.append("id_caso", options.idCaso);
      return postForm<IngestaResponse>("/api/ingesta/ingesta", form, TIMEOUT_INGESTA_MS);
    },
    onUpdate,
  );
  pasos.ingesta = ingesta;
  const guid = ingesta.guid;

  const transcribed = await runStep(
    steps,
    "transcripcion",
    () =>
      postJson<TranscribeResponse>(
        "/api/transcripcion/transcribe",
        { guid, audio_url: audioUri(guid), language: "es" },
        TIMEOUT_TRANSCRIPCION_MS,
      ),
    onUpdate,
  );
  pasos.transcripcion = transcribed;

  const texto = transcribed.texto;
  if (!texto.trim()) {
    throw new Error("La transcripción no produjo texto");
  }

  const result = await runAnalysis(steps, guid, texto, texto, options, pasos, onUpdate);
  return { result, pasos };
}

export async function runTextPipeline(
  texto: string,
  options: PipelineOptions,
  onUpdate: (steps: PipelineStep[]) => void,
): Promise<PipelineOutput> {
  const steps = buildSteps(TEXT_STEPS, Boolean(options.groundTruth));
  const pasos: Partial<Record<PipelineStepId, unknown>> = {};
  onUpdate(steps);

  const ingesta = await runStep(
    steps,
    "ingesta",
    async () => {
      const form = new FormData();
      form.append("texto", texto);
      form.append("origen", options.origen);
      if (options.idCaso) form.append("id_caso", options.idCaso);
      return postForm<IngestaResponse>("/api/ingesta/ingesta", form, TIMEOUT_INGESTA_MS);
    },
    onUpdate,
  );
  pasos.ingesta = ingesta;
  const guid = ingesta.guid;

  const result = await runAnalysis(steps, guid, texto, texto, options, pasos, onUpdate);
  return { result, pasos };
}
