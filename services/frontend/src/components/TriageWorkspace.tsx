"use client";

import { useCallback, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { TextAa, Waveform } from "@phosphor-icons/react";
import { TopNav, Footer } from "./Chrome";
import { NivelesManchester } from "./NivelesManchester";
import { AudioCapture } from "./AudioCapture";
import { ProcessButton } from "./ProcessButton";
import { PipelineRail } from "./PipelineRail";
import { ResultPanel } from "./ResultPanel";
import { runAudioPipeline, runTextPipeline } from "@/lib/pipeline";
import type { PipelineOutput, PipelineStep } from "@/lib/types";
import { isManchesterCode, MANCHESTER_LEVELS, type ManchesterCode } from "@/lib/manchester";

type InputMode = "texto" | "audio";

const MIN_CHARS = 40;
const PLACEHOLDER =
  'Ej. «Doctor, llevo dos horas con un dolor en el pecho como una losa, me cuesta respirar y tengo miedo de que me dé algo.»';

export function TriageWorkspace() {
  const [mode, setMode] = useState<InputMode>("texto");
  const [texto, setTexto] = useState("");
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [audioName, setAudioName] = useState("audio.webm");
  const [idCaso, setIdCaso] = useState("");
  const [origen, setOrigen] = useState("MVP");
  const [groundTruth, setGroundTruth] = useState<ManchesterCode | "">("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [steps, setSteps] = useState<PipelineStep[]>([]);
  const [output, setOutput] = useState<PipelineOutput | null>(null);

  const reset = useCallback(() => {
    setOutput(null);
    setSteps([]);
    setError(null);
  }, []);

  const handleAudio = useCallback(
    (blob: Blob, name: string) => {
      setAudioBlob(blob);
      setAudioName(name);
      reset();
    },
    [reset],
  );

  const handleClear = useCallback(() => {
    setAudioBlob(null);
    reset();
  }, [reset]);

  const ready = mode === "texto" ? texto.trim().length > 0 : Boolean(audioBlob);

  const process = async () => {
    if (!ready) {
      setError(
        mode === "texto"
          ? "Escribe la transcripción del paciente antes de continuar."
          : "Selecciona o graba un audio antes de continuar.",
      );
      return;
    }
    setLoading(true);
    setError(null);
    setOutput(null);
    setSteps([]);
    const options = {
      idCaso: idCaso.trim() || undefined,
      origen,
      groundTruth: groundTruth || undefined,
    };
    try {
      const data =
        mode === "texto"
          ? await runTextPipeline(texto.trim(), options, setSteps)
          : await runAudioPipeline(audioBlob as Blob, audioName, options, setSteps);
      setOutput(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error en el pipeline");
    } finally {
      setLoading(false);
    }
  };

  const showResult = loading || output !== null;

  const inputBase =
    "rounded-xl border border-zinc-200 bg-zinc-50/60 px-3 py-2 text-sm outline-none ring-zinc-900/15 transition focus:border-zinc-300 focus:ring-2 disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-800/60 dark:text-zinc-100 dark:ring-zinc-100/10 dark:focus:border-zinc-600 dark:placeholder:text-zinc-600";

  return (
    <div className="flex h-[100dvh] flex-col overflow-hidden">
      <TopNav active="ingesta" />

      <main className="mx-auto grid min-h-0 w-full max-w-[1500px] flex-1 grid-cols-1 gap-6 overflow-hidden p-4 lg:grid-cols-[minmax(0,520px)_1fr] lg:gap-10 lg:p-8">
        <section className="scroll-area min-h-0 overflow-y-auto pb-2">
          <div className="rounded-3xl border border-zinc-200/80 bg-white/90 p-5 shadow-card-lg dark:border-zinc-800/80 dark:bg-zinc-900/90 sm:p-6">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-zinc-400 dark:text-zinc-500">
                  Nueva entrevista
                </p>
                <h2 className="mt-1 text-xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-100">
                  Iniciar triaje
                </h2>
              </div>
              <span className="rounded-full border border-zinc-200 px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.14em] text-zinc-400 dark:border-zinc-700 dark:text-zinc-500">
                LLM + ML
              </span>
            </div>

            <div className="mt-5 grid grid-cols-2 gap-1 rounded-xl bg-zinc-100 p-1 dark:bg-zinc-800">
              {(
                [
                  { key: "texto" as const, label: "Texto", icon: TextAa },
                  { key: "audio" as const, label: "Audio", icon: Waveform },
                ]
              ).map(({ key, label, icon: Icon }) => (
                <button
                  key={key}
                  type="button"
                  disabled={loading}
                  onClick={() => {
                    setMode(key);
                    reset();
                  }}
                  className={`flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition disabled:opacity-50 ${
                    mode === key
                      ? "bg-white text-zinc-900 shadow-card dark:bg-zinc-700 dark:text-zinc-100"
                      : "text-zinc-500 hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-200"
                  }`}
                >
                  <Icon size={16} weight={mode === key ? "fill" : "regular"} />
                  {label}
                </button>
              ))}
            </div>

            <div className="mt-4">
              {mode === "texto" ? (
                <div className="grid gap-1.5">
                  <label
                    htmlFor="texto"
                    className="text-[10px] font-medium uppercase tracking-[0.16em] text-zinc-400 dark:text-zinc-500"
                  >
                    Voz del paciente · transcripción libre
                  </label>
                  <textarea
                    id="texto"
                    value={texto}
                    onChange={(e) => {
                      setTexto(e.target.value);
                      if (output || error) reset();
                    }}
                    disabled={loading}
                    rows={5}
                    placeholder={PLACEHOLDER}
                    className="resize-none rounded-xl border border-zinc-200 bg-zinc-50/60 px-3.5 py-3 text-sm leading-relaxed text-zinc-800 outline-none ring-zinc-900/15 transition placeholder:text-zinc-400 focus:border-zinc-300 focus:ring-2 disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-800/60 dark:text-zinc-100 dark:placeholder:text-zinc-600 dark:ring-zinc-100/10 dark:focus:border-zinc-600"
                  />
                  <div className="flex items-center justify-between text-[11px] text-zinc-400 dark:text-zinc-500">
                    <span>Mínimo recomendado: {MIN_CHARS} caracteres</span>
                    <span className="font-mono">{texto.length} chars</span>
                  </div>
                </div>
              ) : (
                <AudioCapture
                  disabled={loading}
                  onAudioReady={handleAudio}
                  onClear={handleClear}
                  compact
                />
              )}
            </div>

            <div className="mt-4 grid grid-cols-2 gap-3">
              <div className="grid gap-1.5">
                <label
                  htmlFor="id-caso"
                  className="text-[10px] font-medium uppercase tracking-[0.16em] text-zinc-400 dark:text-zinc-500"
                >
                  ID caso (opcional)
                </label>
                <input
                  id="id-caso"
                  value={idCaso}
                  onChange={(e) => setIdCaso(e.target.value)}
                  disabled={loading}
                  placeholder="ej. RES0001"
                  className={inputBase}
                />
              </div>
              <div className="grid gap-1.5">
                <label
                  htmlFor="origen"
                  className="text-[10px] font-medium uppercase tracking-[0.16em] text-zinc-400 dark:text-zinc-500"
                >
                  Origen
                </label>
                <select id="origen" value={origen} onChange={(e) => setOrigen(e.target.value)} disabled={loading} className={inputBase}>
                  <option value="MVP">MVP</option>
                  <option value="Simulacion">Simulación</option>
                  <option value="Dataset">Dataset</option>
                </select>
              </div>
            </div>

            <div className="mt-3 grid gap-1.5">
              <label
                htmlFor="ground-truth"
                className="text-[10px] font-medium uppercase tracking-[0.16em] text-zinc-400 dark:text-zinc-500"
              >
                Referencia · ground truth (opcional)
              </label>
              <select
                id="ground-truth"
                value={groundTruth}
                onChange={(e) => {
                  const v = e.target.value;
                  setGroundTruth(v && isManchesterCode(v) ? v : "");
                }}
                disabled={loading}
                className={inputBase}
              >
                <option value="">Sin referencia</option>
                {MANCHESTER_LEVELS.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>

            <div className="mt-5">
              <ProcessButton disabled={!ready} loading={loading} onClick={process} />
            </div>

            <AnimatePresence>
              {error && (
                <motion.p
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  className="mt-3 rounded-xl bg-zinc-900 px-3 py-2 text-xs font-medium text-zinc-100 dark:bg-zinc-100 dark:text-zinc-900"
                >
                  {error}
                </motion.p>
              )}
            </AnimatePresence>
          </div>
        </section>

        <section className="scroll-area min-h-0 overflow-y-auto pb-2">
          {showResult ? (
            <ResultPanel result={output?.result ?? null} output={output} loading={loading} />
          ) : (
            <NivelesManchester />
          )}
        </section>
      </main>

      {steps.length > 0 && (
        <div className="shrink-0 border-t border-zinc-200/70 bg-white/70 px-4 py-3 backdrop-blur-sm dark:border-zinc-800/70 dark:bg-zinc-950/70 lg:px-8">
          <div className="mx-auto max-w-[1500px]">
            <p className="mb-1.5 text-[10px] font-medium uppercase tracking-[0.16em] text-zinc-400 dark:text-zinc-500">
              Pipeline
            </p>
            <PipelineRail steps={steps} />
          </div>
        </div>
      )}

      <Footer />
    </div>
  );
}
