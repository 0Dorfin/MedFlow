"use client";

import { useCallback, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { AudioCapture } from "./AudioCapture";
import { ProcessButton } from "./ProcessButton";
import { PipelineRail } from "./PipelineRail";
import { ResultPanel } from "./ResultPanel";
import { runAudioPipeline } from "@/lib/pipeline";
import type { PipelineOutput, PipelineStep } from "@/lib/types";
import { isManchesterCode, MANCHESTER_LEVELS, type ManchesterCode } from "@/lib/manchester";

export function TriageWorkspace() {
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [audioName, setAudioName] = useState("audio.webm");
  const [idCaso, setIdCaso] = useState("");
  const [origen, setOrigen] = useState("MVP");
  const [groundTruth, setGroundTruth] = useState<ManchesterCode | "">("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [steps, setSteps] = useState<PipelineStep[]>([]);
  const [output, setOutput] = useState<PipelineOutput | null>(null);

  const handleAudio = useCallback((blob: Blob, name: string) => {
    setAudioBlob(blob);
    setAudioName(name);
    setError(null);
    setOutput(null);
    setSteps([]);
  }, []);

  const handleClear = useCallback(() => {
    setAudioBlob(null);
    setOutput(null);
    setSteps([]);
    setError(null);
  }, []);

  const process = async () => {
    if (!audioBlob) {
      setError("Selecciona o graba un audio antes de continuar.");
      return;
    }
    setLoading(true);
    setError(null);
    setOutput(null);
    setSteps([]);
    try {
      const data = await runAudioPipeline(
        audioBlob,
        audioName,
        {
          idCaso: idCaso.trim() || undefined,
          origen,
          groundTruth: groundTruth || undefined,
        },
        setSteps,
      );
      setOutput(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error en el pipeline");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-[100dvh] flex-col overflow-hidden">
      <header className="shrink-0 border-b border-zinc-200/80 bg-white/80 px-4 py-3 backdrop-blur-sm lg:px-6">
        <div className="mx-auto flex max-w-[1600px] items-center justify-between gap-4">
          <div>
            <p className="text-xs font-medium tracking-tight text-emerald-700">TriageIA</p>
            <h1 className="whitespace-nowrap text-lg font-semibold tracking-tight text-zinc-900 md:text-xl">
              Triaje Manchester por voz
            </h1>
          </div>
          <p className="hidden max-w-md text-right text-xs leading-relaxed text-zinc-500 lg:block">
            Audio, transcripcion, etiquetado y prediccion en una sola vista
          </p>
        </div>
      </header>

      <main className="mx-auto grid min-h-0 w-full max-w-[1600px] flex-1 grid-cols-1 gap-3 overflow-hidden p-3 lg:grid-cols-[minmax(280px,340px)_1fr] lg:gap-4 lg:p-4">
        <motion.section
          layout
          className="flex min-h-0 flex-col gap-3 overflow-y-auto lg:max-h-full"
        >
          <AudioCapture
            disabled={loading}
            onAudioReady={handleAudio}
            onClear={handleClear}
            compact
          />

          <motion.div
            layout
            className="grid gap-3 rounded-2xl border border-zinc-200/80 bg-white/80 p-4"
          >
            <div className="grid gap-1.5">
              <label htmlFor="id-caso" className="text-xs font-medium text-zinc-700">
                ID caso
              </label>
              <input
                id="id-caso"
                value={idCaso}
                onChange={(e) => setIdCaso(e.target.value)}
                disabled={loading}
                placeholder="RES0042"
                className="rounded-lg border border-zinc-200 bg-zinc-50 px-2.5 py-1.5 text-sm outline-none ring-emerald-500/30 focus:ring-2 disabled:opacity-50"
              />
            </div>
            <motion.div layout className="grid grid-cols-2 gap-2">
              <div className="grid gap-1.5">
                <label htmlFor="origen" className="text-xs font-medium text-zinc-700">
                  Origen
                </label>
                <select
                  id="origen"
                  value={origen}
                  onChange={(e) => setOrigen(e.target.value)}
                  disabled={loading}
                  className="rounded-lg border border-zinc-200 bg-zinc-50 px-2 py-1.5 text-sm outline-none ring-emerald-500/30 focus:ring-2 disabled:opacity-50"
                >
                  <option value="MVP">MVP</option>
                  <option value="Simulacion">Simulacion</option>
                  <option value="Dataset">Dataset</option>
                </select>
              </div>
              <div className="grid gap-1.5">
                <label htmlFor="ground-truth" className="text-xs font-medium text-zinc-700">
                  Ground truth
                </label>
                <select
                  id="ground-truth"
                  value={groundTruth}
                  onChange={(e) => {
                    const v = e.target.value;
                    setGroundTruth(v && isManchesterCode(v) ? v : "");
                  }}
                  disabled={loading}
                  className="rounded-lg border border-zinc-200 bg-zinc-50 px-2 py-1.5 text-sm outline-none ring-emerald-500/30 focus:ring-2 disabled:opacity-50"
                >
                  <option value="">—</option>
                  {MANCHESTER_LEVELS.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>
            </motion.div>
          </motion.div>

          <ProcessButton disabled={!audioBlob} loading={loading} onClick={process} />

          <AnimatePresence>
            {error && (
              <motion.p
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="rounded-xl bg-rose-50 px-3 py-2 text-xs text-rose-800"
              >
                {error}
              </motion.p>
            )}
          </AnimatePresence>
        </motion.section>

        <motion.section layout className="flex min-h-0 flex-col gap-2 overflow-hidden">
          <p className="shrink-0 text-xs font-medium uppercase tracking-wider text-zinc-400">
            Resultado clinico
          </p>
          <div className="min-h-0 flex-1 overflow-y-auto pr-1">
            <ResultPanel
              result={output?.result ?? null}
              output={output}
              loading={loading}
            />
          </div>
        </motion.section>
      </main>

      <footer className="shrink-0 border-t border-zinc-200/80 bg-zinc-100/90 px-3 py-2 backdrop-blur-sm lg:px-4">
        <div className="mx-auto max-w-[1600px]">
          <p className="mb-1.5 text-[10px] font-medium uppercase tracking-wider text-zinc-400">
            Pipeline
          </p>
          <PipelineRail steps={steps} />
        </div>
      </footer>
    </div>
  );
}
