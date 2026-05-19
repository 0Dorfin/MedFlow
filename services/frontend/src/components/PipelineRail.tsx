"use client";

import { motion } from "framer-motion";
import { CheckCircle, Circle, WarningCircle } from "@phosphor-icons/react";
import type { PipelineStep } from "@/lib/types";

type PipelineRailProps = {
  steps: PipelineStep[];
};

export function PipelineRail({ steps }: PipelineRailProps) {
  if (!steps.length) {
    return (
      <motion.div
        layout
        className="flex h-[4.5rem] items-center justify-center rounded-2xl border border-dashed border-zinc-300 bg-white/70 px-4"
      >
        <p className="text-xs text-zinc-500">El progreso del pipeline aparecera aqui al analizar</p>
      </motion.div>
    );
  }

  return (
    <motion.div
      layout
      className="rounded-2xl border border-zinc-200/80 bg-white px-3 py-2 shadow-[0_8px_24px_-12px_rgba(0,0,0,0.08)]"
    >
      <div className="grid grid-cols-5 gap-1 sm:grid-cols-9 sm:gap-1.5">
        {steps.map((step, index) => (
          <motion.div
            key={step.id}
            layout
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.03 }}
            className={`flex min-h-[3.25rem] flex-col items-center justify-center rounded-xl px-1 py-1.5 text-center ${
              step.status === "running"
                ? "bg-emerald-50 ring-1 ring-emerald-200"
                : step.status === "error"
                  ? "bg-rose-50 ring-1 ring-rose-200"
                  : step.status === "ok"
                    ? "bg-zinc-50"
                    : "bg-transparent"
            }`}
            title={step.error ?? step.label}
          >
            <span className="mb-0.5 flex h-4 items-center justify-center">
              {step.status === "ok" && (
                <CheckCircle size={14} className="text-emerald-600" weight="fill" />
              )}
              {step.status === "running" && (
                <motion.span
                  className="inline-block h-3 w-3 rounded-full border-2 border-emerald-500 border-t-transparent"
                  animate={{ rotate: 360 }}
                  transition={{ repeat: Infinity, duration: 0.8, ease: "linear" }}
                />
              )}
              {step.status === "error" && (
                <WarningCircle size={14} className="text-rose-600" weight="fill" />
              )}
              {step.status === "pending" && <Circle size={14} className="text-zinc-300" />}
            </span>
            <span className="text-[10px] font-medium leading-tight text-zinc-700 sm:text-[11px]">
              {step.shortLabel}
            </span>
            {step.durationMs !== undefined && (
              <span className="font-mono text-[9px] text-zinc-400">
                {step.durationMs < 1000
                  ? `${step.durationMs.toFixed(0)}ms`
                  : `${(step.durationMs / 1000).toFixed(1)}s`}
              </span>
            )}
          </motion.div>
        ))}
      </div>
    </motion.div>
  );
}
