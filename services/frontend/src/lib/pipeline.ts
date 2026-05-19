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
  transcripcion: "Transcripcion Whisper",
  preprocessing: "Preprocesamiento",
  extraction: "Extraccion de entidades",
  normalization: "Normalizacion Manchester",
  labeling: "Etiquetado LLM",
  anxiety: "Score de ansiedad",
  prediction: "Prediccion ML",
  audit: "Auditoria etica",
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

const INITIAL_STEPS: PipelineStepId[] = [
  "ingesta",
  "transcripcion",
  "preprocessing",
  "extraction",
  "normalization",
  "labeling",
  "anxiety",
  "prediction",
];

function buildSteps(extraAudit: boolean): PipelineStep[] {
  const ids = extraAudit ? [...INITIAL_STEPS, "audit" as PipelineStepId] : INITIAL_STEPS;
  return ids.map((id) => ({
    id,
    label: STEP_LABELS[id],
    shortLabel: STEP_SHORT[id],
    status: "pending",
  }));
}

async function runStep<T>(
  steps: PipelineStep[],
  id: PipelineStepId,
  fn: () => Promise<T>,
  onUpdate: (steps: PipelineStep[]) => void,
): Promise<T> {
  const next = steps.map((s) =>
    s.id === id ? { ...s, status: "running" as const, error: undefined } : s,
  );
  onUpdate(next);
  const started = performance.now();
  try {
    const result = await fn();
    const done = next.map((s) =>
      s.id === id
        ? {
            ...s,
            status: "ok" as const,
            durationMs: performance.now() - started,
            response: result,
          }
        : s,
    );
    onUpdate(done);
    return result;
  } catch (err) {
    const message = err instanceof Error ? err.message : "Error desconocido";
    const failed = next.map((s) =>
      s.id === id
        ? {
            ...s,
            status: "error" as const,
            durationMs: performance.now() - started,
            error: message,
          }
        : s,
    );
    onUpdate(failed);
    throw err;
  }
}

function audioUri(guid: string): string {
  return `s3://audio-original/${guid}.wav`;
}

export async function runAudioPipeline(
  audio: Blob,
  fileName: string,
  options: PipelineOptions,
  onUpdate: (steps: PipelineStep[]) => void,
): Promise<PipelineOutput> {
  const steps = buildSteps(Boolean(options.groundTruth));
  const pasos: Partial<Record<PipelineStepId, unknown>> = {};
  onUpdate(steps);

  const ingesta = await runStep(steps, "ingesta", async () => {
    const form = new FormData();
    form.append("audio", audio, fileName);
    form.append("origen", options.origen);
    if (options.idCaso) form.append("id_caso", options.idCaso);
    return postForm<IngestaResponse>("/api/ingesta/ingesta", form, TIMEOUT_INGESTA_MS);
  }, onUpdate);
  pasos.ingesta = ingesta;

  const guid = ingesta.guid;

  const transcribed = await runStep(
    steps,
    "transcripcion",
    () =>
      postJson<TranscribeResponse>(
        "/api/transcripcion/transcribe",
        {
          guid,
          audio_url: audioUri(guid),
          language: "es",
        },
        TIMEOUT_TRANSCRIPCION_MS,
      ),
    onUpdate,
  );
  pasos.transcripcion = transcribed;

  const texto = transcribed.texto;
  if (!texto.trim()) {
    throw new Error("La transcripcion no produjo texto");
  }

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
    const current = steps.map((s) =>
      s.id === "prediction"
        ? { ...s, status: "error" as const, error: "Modelo ML no disponible" }
        : s,
    );
    onUpdate(current);
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

  const result: TriageResult = {
    guid,
    textoTranscrito: texto,
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

  return { result, pasos };
}
