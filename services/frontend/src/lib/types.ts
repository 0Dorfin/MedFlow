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
