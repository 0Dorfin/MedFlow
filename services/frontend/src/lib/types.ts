import type { ManchesterCode } from "./manchester";

export type NormalizedEntity = {
  termino_clinico: string;
  prioridad_sugerida: ManchesterCode;
  grupo_clinico: string;
  sintoma_original: string;
};

export type PipelineStepId =
  | "ingesta"
  | "transcripcion"
  | "preprocessing"
  | "extraction"
  | "normalization"
  | "labeling"
  | "anxiety"
  | "prediction"
  | "audit";

export type StepStatus = "pending" | "running" | "ok" | "error";

export type PipelineStep = {
  id: PipelineStepId;
  label: string;
  shortLabel: string;
  status: StepStatus;
  durationMs?: number;
  error?: string;
  response?: unknown;
};

export type PipelineOutput = {
  result: TriageResult;
  pasos: Partial<Record<PipelineStepId, unknown>>;
};

export type TriageResult = {
  guid: string;
  textoTranscrito: string;
  textoPreprocesado: string;
  triageLlm: ManchesterCode | null;
  justificacion: string;
  entidades: string[];
  entidadesNormalizadas: NormalizedEntity[];
  noMapeadas: string[];
  scoreAnsiedad: number;
  prediccionIa: ManchesterCode | null;
  scoreAnsiedadIa: number | null;
  probabilidades: Partial<Record<ManchesterCode, number>>;
  groundTruth: ManchesterCode | null;
  validacion: string | null;
  motivoFallo: string | null;
  sesgoEmocional: boolean;
};

export type PipelineOptions = {
  idCaso?: string;
  origen: string;
  groundTruth?: ManchesterCode;
};

export type HistorialItem = {
  guid_entrevista: string;
  id_caso: string | null;
  origen: string | null;
  estado: string | null;
  inicio_solicitud: string | null;
  triage_real: ManchesterCode | null;
  score_ansiedad: number | null;
  prediccion_ia: ManchesterCode | null;
  score_ansiedad_ia: number | null;
  validacion: string | null;
};

export type ResultadoCompleto = {
  guid_entrevista: string;
  id_caso: string | null;
  origen: string | null;
  estado: string | null;
  resumen_es: string | null;
  entidades_normalizadas_es: NormalizedEntity[] | null;
  triage_real: ManchesterCode | null;
  score_ansiedad: number | null;
  justificacion_llm: string | null;
  prediccion_ia: ManchesterCode | null;
  score_ansiedad_ia: number | null;
  validacion: string | null;
  motivo_fallo: string | null;
};
