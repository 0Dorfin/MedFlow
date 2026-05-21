"use client";

import { motion } from "framer-motion";
import { CheckCircle, Circle, WarningCircle } from "@phosphor-icons/react";
import type { PipelineStep } from "@/lib/types";

type PipelineRailProps = {
  steps: PipelineStep[];
};

function fmtDuration(ms: number): string {
  return ms < 1000 ? `${ms.toFixed(0)}ms` : `${(ms / 1000).toFixed(1)}s`;
}

export function PipelineRail({ steps }: PipelineRailProps) {
  if (!steps.length) {
    return (
      <motion.div
        layout
        className="flex h-[3.25rem] items-center justify-center rounded-2xl border border-dashed border-zinc-300 bg-white/70 px-4 dark:border-zinc-700 dark:bg-zinc-900/70"
      >
        <p className="text-xs text-zinc-500 dark:text-zinc-400">
          El progreso del pipeline aparecerá aquí al analizar
        </p>
      </motion.div>
    );
  }

  return (
    <motion.div
      layout
      className="rounded-2xl border border-zinc-200/80 bg-white px-4 py-3 shadow-card dark:border-zinc-800/80 dark:bg-zinc-950"
    >
      <div className="flex flex-wrap items-center justify-center gap-2">
        {steps.map((step, index) => (
          <motion.div
            key={step.id}
            layout
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.03 }}
            title={step.error ?? step.label}
            className={`flex items-center gap-2 rounded-xl border px-3.5 py-2.5 ${
              step.status === "ok"
                ? "border-emerald-600/20 bg-emerald-50 text-emerald-700 dark:border-emerald-500/20 dark:bg-emerald-950/50 dark:text-emerald-400"
                : step.status === "running"
                  ? "border-zinc-300 bg-zinc-100 text-zinc-800 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-200"
                  : step.status === "error"
                    ? "border-zinc-500 bg-zinc-900 text-zinc-50 dark:border-zinc-400 dark:bg-zinc-100 dark:text-zinc-900"
                    : "border-zinc-200 bg-white text-zinc-400 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-600"
            }`}
          >
            <span className="flex h-5 w-5 items-center justify-center">
              {step.status === "ok" && (
                <motion.span
                  initial={{ scale: 0.4, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  transition={{ type: "spring", stiffness: 360, damping: 18 }}
                >
                  <CheckCircle size={20} className="text-emerald-600 dark:text-emerald-400" weight="fill" />
                </motion.span>
              )}
              {step.status === "running" && (
                <motion.span
                  className="inline-block h-4 w-4 rounded-full border-2 border-zinc-500 border-t-transparent dark:border-zinc-400 dark:border-t-transparent"
                  animate={{ rotate: 360 }}
                  transition={{ repeat: Infinity, duration: 0.8, ease: "linear" }}
                />
              )}
              {step.status === "error" && (
                <WarningCircle size={20} className="text-zinc-50 dark:text-zinc-900" weight="fill" />
              )}
              {step.status === "pending" && (
                <Circle size={20} className="text-zinc-300 dark:text-zinc-600" />
              )}
            </span>
            <div className="flex flex-col leading-tight">
              <span className="text-sm font-medium">{step.shortLabel}</span>
              {step.durationMs !== undefined && step.status === "ok" && (
                <span className="font-mono text-[10px] text-emerald-700/70 dark:text-emerald-400/70">
                  {fmtDuration(step.durationMs)}
                </span>
              )}
            </div>
          </motion.div>
        ))}
      </div>
    </motion.div>
  );
}
