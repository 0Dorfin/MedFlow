"use client";

import { motion } from "framer-motion";
import { ManchesterStrip } from "./ManchesterStrip";
import {
  MANCHESTER,
  MANCHESTER_LEVELS,
  manchesterTextOn,
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
      className={`rounded-xl bg-zinc-100 dark:bg-zinc-800 ${className}`}
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
        className="rounded-[2rem] border border-zinc-200/80 bg-white p-6 shadow-card dark:border-zinc-800/80 dark:bg-zinc-900 sm:p-8"
      >
        <p className="text-xs font-medium uppercase tracking-wider text-zinc-400 dark:text-zinc-500">
          A la espera de entrada
        </p>
        <h2 className="mt-1 text-lg font-semibold tracking-tight text-zinc-900 dark:text-zinc-100">
          Sistema de Triaje Manchester
        </h2>
        <p className="mt-2 max-w-prose text-sm leading-relaxed text-zinc-500 dark:text-zinc-400">
          Sube un archivo o graba la entrevista del paciente. El sistema transcribirá el audio
          y devolverá el nivel de prioridad con entidades normalizadas y probabilidades del
          modelo. El protocolo clasifica la urgencia en cinco niveles, cada uno con un tiempo
          máximo de atención.
        </p>
        <ul className="mt-5 flex flex-col gap-2">
          {MANCHESTER_LEVELS.map((code) => {
            const meta = MANCHESTER[code];
            return (
              <li
                key={code}
                className="flex items-center gap-3 rounded-xl border border-zinc-200/70 bg-zinc-50/50 p-2.5 dark:border-zinc-700/70 dark:bg-zinc-800/50"
              >
                <span
                  className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-sm font-bold"
                  style={{ backgroundColor: meta.color, color: manchesterTextOn(meta.color) }}
                >
                  {code}
                </span>
                <div className="flex min-w-0 flex-1 items-baseline justify-between gap-2">
                  <p className="truncate text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                    {meta.label}{" "}
                    <span className="font-normal text-zinc-500 dark:text-zinc-400">· {meta.desc}</span>
                  </p>
                  <p className="shrink-0 font-mono text-xs text-zinc-500 dark:text-zinc-400">
                    {meta.minutes === "0" ? "inmediato" : `${meta.minutes} min`}
                  </p>
                </div>
              </li>
            );
          })}
        </ul>
      </motion.div>
    );
  }

  const triage: ManchesterCode | null = result.prediccionIa ?? result.triageLlm ?? null;
  const meta = triage ? MANCHESTER[triage] : null;

  return (
    <motion.div layout className="space-y-6">
      <div>
        <p className="text-sm font-medium text-zinc-500 dark:text-zinc-400">Nivel Manchester</p>
        <ManchesterStrip active={triage} />
      </div>

      {meta && (
        <motion.div
          layout
          className="rounded-2xl border-l-[6px] px-5 py-4 shadow-card"
          style={{
            borderColor: meta.color,
            backgroundColor: `${meta.color}12`,
          }}
        >
          <p className="text-sm text-zinc-600 dark:text-zinc-400">Predicción del sistema</p>
          <p className="text-3xl font-semibold tracking-tight" style={{ color: meta.color }}>
            {meta.code} {meta.label}
          </p>
          <p className="mt-2 text-sm leading-relaxed text-zinc-700 dark:text-zinc-300">
            {meta.desc} · {meta.minutes === "0" ? "atención inmediata" : `atención en ≤ ${meta.minutes} min`}
          </p>
        </motion.div>
      )}

      <motion.div layout className="grid gap-4 sm:grid-cols-2">
        <motion.div layout className="space-y-2">
          <p className="text-xs font-medium uppercase tracking-wider text-zinc-400 dark:text-zinc-500">
            Transcripción
          </p>
          <p className="text-sm leading-relaxed text-zinc-700 dark:text-zinc-300">
            {result.textoTranscrito}
          </p>
        </motion.div>
        <motion.div layout className="self-start rounded-xl border border-zinc-200/80 bg-white p-4 shadow-card dark:border-zinc-700/80 dark:bg-zinc-900">
          <p className="text-xs text-zinc-500 dark:text-zinc-400">Ansiedad</p>
          <p className="font-mono text-3xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-100">
            {result.scoreAnsiedad.toFixed(2)}
          </p>
          <span
            className={
              result.scoreAnsiedad >= 0.8
                ? "mt-3 inline-flex items-center gap-1.5 rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700 ring-1 ring-inset ring-amber-600/20 dark:bg-amber-950/40 dark:text-amber-300 dark:ring-amber-400/20"
                : "mt-3 inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700 ring-1 ring-inset ring-emerald-600/20 dark:bg-emerald-950/40 dark:text-emerald-300 dark:ring-emerald-400/20"
            }
          >
            <span className={result.scoreAnsiedad >= 0.8 ? "h-1.5 w-1.5 rounded-full bg-amber-500" : "h-1.5 w-1.5 rounded-full bg-emerald-500"} />
            {result.scoreAnsiedad >= 0.8
              ? triage === "C1"
                ? "Ansiedad alta"
                : "Ansiedad alta: posible riesgo de infra-triaje"
              : "Ansiedad en rango normal"}
          </span>
        </motion.div>
      </motion.div>

      {result.entidadesNormalizadas.length > 0 && (
        <motion.div layout>
          <p className="mb-2 text-xs font-medium uppercase tracking-wider text-zinc-400 dark:text-zinc-500">
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
          <p className="mb-3 text-xs font-medium uppercase tracking-wider text-zinc-400 dark:text-zinc-500">
            Probabilidades ML
          </p>
          <motion.div layout className="grid grid-cols-5 gap-2">
            {MANCHESTER_LEVELS.map((code) => {
              const prob = result.probabilidades[code] ?? 0;
              const color = MANCHESTER[code].color;
              return (
                <motion.div key={code} layout className="text-center">
                  <motion.div layout className="mb-1 flex h-16 items-end overflow-hidden rounded-lg bg-zinc-100 dark:bg-zinc-800">
                    <motion.div
                      className="w-full rounded-lg"
                      initial={{ height: 0 }}
                      animate={{ height: `${Math.max(prob * 100, 4)}%` }}
                      style={{ backgroundColor: color }}
                      transition={{ type: "spring", stiffness: 90, damping: 20 }}
                    />
                  </motion.div>
                  <p className="font-mono text-xs text-zinc-600 dark:text-zinc-400">{code}</p>
                  <p className="font-mono text-sm font-semibold text-zinc-900 dark:text-zinc-100">
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
              ? "border border-zinc-200 bg-zinc-100 text-zinc-700 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-300"
              : result.validacion === "Under-triage"
                ? "bg-zinc-900 font-medium text-zinc-50 dark:bg-zinc-100 dark:text-zinc-900"
                : "bg-zinc-200 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200"
          }`}
        >
          Validación: {result.validacion}
          {result.groundTruth && ` (referencia ${result.groundTruth})`}
          {result.motivoFallo ? ` — ${result.motivoFallo}` : ""}
        </motion.p>
      )}

      <p className="font-mono text-xs text-zinc-400 dark:text-zinc-600">GUID {result.guid}</p>

      <JsonDisclosure data={output} />
    </motion.div>
  );
}
