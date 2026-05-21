"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { motion } from "framer-motion";
import { ArrowLeft } from "@phosphor-icons/react";
import { getJson } from "@/lib/api";
import { ManchesterStrip } from "@/components/ManchesterStrip";
import { MANCHESTER, isManchesterCode, type ManchesterCode } from "@/lib/manchester";
import type { ResultadoCompleto } from "@/lib/types";

function asCode(value: string | null): ManchesterCode | null {
  return value && isManchesterCode(value) ? value : null;
}

export default function DetalleHistorialPage() {
  const params = useParams<{ guid: string }>();
  const guid = params?.guid;
  const [record, setRecord] = useState<ResultadoCompleto | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!guid) return;
    let active = true;
    getJson<ResultadoCompleto>(`/api/consulta/resultado/${guid}`)
      .then((data) => {
        if (active) setRecord(data);
      })
      .catch((err) => {
        if (active) setError(err instanceof Error ? err.message : "Error al cargar el resultado");
      });
    return () => {
      active = false;
    };
  }, [guid]);

  const triage = record ? asCode(record.prediccion_ia) ?? asCode(record.triage_real) : null;
  const meta = triage ? MANCHESTER[triage] : null;
  const entidades = record?.entidades_normalizadas_es ?? [];

  return (
    <div className="flex h-[100dvh] flex-col overflow-hidden">
      <header className="shrink-0 border-b border-zinc-200/80 bg-white/80 px-4 py-3 backdrop-blur-sm lg:px-6">
        <div className="mx-auto flex max-w-[1000px] items-center gap-3">
          <Link
            href="/historial"
            className="flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs font-medium text-zinc-700 shadow-card transition hover:border-zinc-300 hover:text-zinc-900 active:scale-[0.98]"
          >
            <ArrowLeft size={15} weight="bold" />
            Historial
          </Link>
          <div className="min-w-0">
            <p className="text-xs font-medium tracking-tight text-zinc-500">Entrevista</p>
            <h1 className="truncate font-mono text-sm font-semibold text-zinc-900 md:text-base">
              {guid}
            </h1>
          </div>
        </div>
      </header>

      <main className="scroll-area mx-auto w-full max-w-[1000px] flex-1 overflow-y-auto p-3 lg:p-6">
        {error && (
          <div className="rounded-2xl border border-zinc-300 bg-white p-6 text-sm text-zinc-700 shadow-card">
            <p className="font-medium text-zinc-900">No se pudo cargar el resultado</p>
            <p className="mt-1 text-zinc-500">{error}</p>
          </div>
        )}

        {!error && record === null && (
          <div className="flex flex-col gap-4">
            <motion.div
              className="h-28 rounded-2xl bg-zinc-100"
              animate={{ opacity: [0.55, 0.9, 0.55] }}
              transition={{ repeat: Infinity, duration: 1.4, ease: "easeInOut" }}
            />
            <motion.div
              className="h-40 rounded-2xl bg-zinc-100"
              animate={{ opacity: [0.55, 0.9, 0.55] }}
              transition={{ repeat: Infinity, duration: 1.4, ease: "easeInOut", delay: 0.1 }}
            />
          </div>
        )}

        {!error && record !== null && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <Field label="ID caso" value={record.id_caso} />
              <Field label="Origen" value={record.origen} />
              <Field label="Estado" value={record.estado} />
              <Field label="Validación" value={record.validacion} />
            </div>

            <div>
              <p className="text-sm font-medium text-zinc-500">Nivel Manchester</p>
              <ManchesterStrip active={triage} />
            </div>

            {meta && (
              <div
                className="rounded-2xl border-l-[6px] px-5 py-4 shadow-card"
                style={{ borderColor: meta.color, backgroundColor: `${meta.color}12` }}
              >
                <p className="text-sm text-zinc-600">Predicción del sistema</p>
                <p className="text-3xl font-semibold tracking-tight" style={{ color: meta.color }}>
                  {meta.code} {meta.label}
                </p>
                {record.justificacion_llm && (
                  <p className="mt-2 text-sm leading-relaxed text-zinc-700">{record.justificacion_llm}</p>
                )}
                {record.motivo_fallo && (
                  <p className="mt-2 text-sm leading-relaxed text-zinc-500">{record.motivo_fallo}</p>
                )}
              </div>
            )}

            {record.resumen_es && (
              <div className="space-y-2">
                <p className="text-xs font-medium uppercase tracking-wider text-zinc-400">Resumen</p>
                <p className="text-sm leading-relaxed text-zinc-700">{record.resumen_es}</p>
              </div>
            )}

            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              <Metric label="Ansiedad (LLM)" value={record.score_ansiedad} />
              <Metric label="Ansiedad (IA)" value={record.score_ansiedad_ia} />
              <Field label="Triage real" value={record.triage_real} />
            </div>

            {entidades.length > 0 && (
              <div>
                <p className="mb-2 text-xs font-medium uppercase tracking-wider text-zinc-400">
                  Entidades normalizadas
                </p>
                <div className="flex flex-wrap gap-2">
                  {entidades.map((e) => {
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
                </div>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="rounded-xl border border-zinc-200/80 bg-white p-3 shadow-card">
      <p className="text-xs text-zinc-500">{label}</p>
      <p className="mt-0.5 truncate text-sm font-medium text-zinc-900">{value ?? "—"}</p>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="rounded-xl border border-zinc-200/80 bg-white p-4 shadow-card">
      <p className="text-xs text-zinc-500">{label}</p>
      <p className="font-mono text-2xl font-semibold text-zinc-900">
        {value === null || value === undefined ? "—" : Number(value).toFixed(2)}
      </p>
    </div>
  );
}
