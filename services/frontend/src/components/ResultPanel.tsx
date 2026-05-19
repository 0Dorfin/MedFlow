"use client";

import { motion } from "framer-motion";
import { ManchesterStrip } from "./ManchesterStrip";
import {
  MANCHESTER,
  MANCHESTER_LEVELS,
  type ManchesterCode,
} from "@/lib/manchester";
import { JsonDisclosure } from "./JsonDisclosure";
import type { PipelineOutput, TriageResult } from "@/lib/types";

type ResultPanelProps = {
  result: TriageResult | null;
  output: PipelineOutput | null;
  loading: boolean;
};

function SkeletonBlock({ className }: { className: string }) {
  return (
    <motion.div
      className={`rounded-xl bg-zinc-100 ${className}`}
      animate={{ opacity: [0.55, 0.9, 0.55] }}
      transition={{ repeat: Infinity, duration: 1.4, ease: "easeInOut" }}
    />
  );
}

export function ResultPanel({ result, output, loading }: ResultPanelProps) {
  if (loading && !result) {
    return (
      <motion.div layout className="space-y-5">
        <SkeletonBlock className="h-24 w-full" />
        <motion.div layout className="grid grid-cols-5 gap-2">
          {MANCHESTER_LEVELS.map((c) => (
            <SkeletonBlock key={c} className="h-20" />
          ))}
        </motion.div>
        <SkeletonBlock className="h-40 w-full" />
      </motion.div>
    );
  }

  if (!result) {
    return (
      <motion.div
        layout
        className="flex min-h-[200px] flex-col justify-center rounded-[2rem] border border-dashed border-zinc-300 bg-zinc-50/60 px-8 py-10"
      >
        <p className="text-lg font-medium tracking-tight text-zinc-800">
          Esperando audio clinico
        </p>
        <p className="mt-2 max-w-md text-sm leading-relaxed text-zinc-500">
          Sube un archivo o graba la entrevista del paciente. El sistema transcribira el
          audio y devolvera el nivel Manchester con entidades normalizadas y probabilidades
          del modelo.
        </p>
      </motion.div>
    );
  }

  const triage: ManchesterCode | null =
    result.prediccionIa ?? result.triageLlm ?? null;
  const meta = triage ? MANCHESTER[triage] : null;

  return (
    <motion.div layout className="space-y-6">
      <div>
        <p className="text-sm font-medium text-zinc-500">Nivel Manchester</p>
        <ManchesterStrip active={triage} />
      </div>

      {meta && (
        <motion.div
          layout
          className="rounded-2xl border-l-[6px] px-5 py-4"
          style={{
            borderColor: meta.color,
            backgroundColor: `${meta.color}12`,
          }}
        >
          <p className="text-sm text-zinc-600">Prediccion del sistema</p>
          <p className="text-3xl font-semibold tracking-tight" style={{ color: meta.color }}>
            {meta.code} {meta.label}
          </p>
          <p className="mt-2 text-sm leading-relaxed text-zinc-700">{result.justificacion}</p>
        </motion.div>
      )}

      <motion.div layout className="grid gap-4 sm:grid-cols-2">
        <motion.div layout className="space-y-2">
          <p className="text-xs font-medium uppercase tracking-wider text-zinc-400">
            Transcripcion
          </p>
          <p className="text-sm leading-relaxed text-zinc-700">{result.textoTranscrito}</p>
        </motion.div>
        <motion.div layout className="grid grid-cols-2 gap-3">
          <motion.div layout className="rounded-xl border border-zinc-200/80 bg-white p-4">
            <p className="text-xs text-zinc-500">Ansiedad (LLM)</p>
            <p className="font-mono text-2xl font-semibold text-zinc-900">
              {result.scoreAnsiedad.toFixed(2)}
            </p>
          </motion.div>
          {result.scoreAnsiedadIa !== null && (
            <motion.div layout className="rounded-xl border border-zinc-200/80 bg-white p-4">
              <p className="text-xs text-zinc-500">Ansiedad (IA)</p>
              <p className="font-mono text-2xl font-semibold text-zinc-900">
                {result.scoreAnsiedadIa.toFixed(2)}
              </p>
            </motion.div>
          )}
        </motion.div>
      </motion.div>

      {result.entidadesNormalizadas.length > 0 && (
        <motion.div layout>
          <p className="mb-2 text-xs font-medium uppercase tracking-wider text-zinc-400">
            Entidades normalizadas
          </p>
          <motion.div layout className="flex flex-wrap gap-2">
            {result.entidadesNormalizadas.map((e) => {
              const color = MANCHESTER[e.prioridad_sugerida]?.color ?? "#71717a";
              return (
                <span
                  key={`${e.termino_clinico}-${e.sintoma_original}`}
                  className="rounded-full px-3 py-1 text-xs font-medium"
                  style={{ backgroundColor: `${color}22`, color }}
                >
                  {e.termino_clinico} · {e.prioridad_sugerida} · {e.grupo_clinico}
                </span>
              );
            })}
          </motion.div>
        </motion.div>
      )}

      {Object.keys(result.probabilidades).length > 0 && (
        <motion.div layout>
          <p className="mb-3 text-xs font-medium uppercase tracking-wider text-zinc-400">
            Probabilidades ML
          </p>
          <motion.div layout className="grid grid-cols-5 gap-2">
            {MANCHESTER_LEVELS.map((code) => {
              const prob = result.probabilidades[code] ?? 0;
              const color = MANCHESTER[code].color;
              return (
                <motion.div key={code} layout className="text-center">
                  <motion.div layout className="mb-1 flex h-16 items-end overflow-hidden rounded-lg bg-zinc-100">
                    <motion.div
                      className="w-full rounded-lg"
                      initial={{ height: 0 }}
                      animate={{ height: `${Math.max(prob * 100, 4)}%` }}
                      style={{ backgroundColor: color }}
                      transition={{ type: "spring", stiffness: 90, damping: 20 }}
                    />
                  </motion.div>
                  <p className="font-mono text-xs text-zinc-600">{code}</p>
                  <p className="font-mono text-sm font-semibold text-zinc-900">
                    {(prob * 100).toFixed(1)}%
                  </p>
                </motion.div>
              );
            })}
          </motion.div>
        </motion.div>
      )}

      {result.validacion && (
        <motion.p
          layout
          className={`rounded-xl px-4 py-3 text-sm ${
            result.validacion === "Acierto"
              ? "bg-emerald-50 text-emerald-800"
              : result.validacion === "Under-triage"
                ? "bg-rose-50 text-rose-800"
                : "bg-amber-50 text-amber-900"
          }`}
        >
          Validacion: {result.validacion}
          {result.groundTruth && ` (referencia ${result.groundTruth})`}
          {result.motivoFallo ? ` — ${result.motivoFallo}` : ""}
        </motion.p>
      )}

      <p className="font-mono text-xs text-zinc-400">GUID {result.guid}</p>

      <JsonDisclosure data={output} />
    </motion.div>
  );
}
