"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { motion } from "framer-motion";
import { ArrowLeft } from "@phosphor-icons/react";
import { getJson, postJson } from "@/lib/api";
import { ManchesterStrip } from "@/components/ManchesterStrip";
import {
  MANCHESTER,
  MANCHESTER_LEVELS,
  isManchesterCode,
  type ManchesterCode,
} from "@/lib/manchester";
import type { ResultadoCompleto } from "@/lib/types";

type AuditResponse = {
  guid: string;
  validacion: string;
  motivo_fallo?: string | null;
  sesgo_emocional_detectado?: boolean;
};

function asCode(value: string | null): ManchesterCode | null {
  return value && isManchesterCode(value) ? value : null;
}

export default function DetalleHistorialPage() {
  const params = useParams<{ guid: string }>();
  const guid = params?.guid;
  const [record, setRecord] = useState<ResultadoCompleto | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedReal, setSelectedReal] = useState<ManchesterCode | "">("");
  const [auditing, setAuditing] = useState(false);
  const [auditError, setAuditError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!guid) return;
    const data = await getJson<ResultadoCompleto>(`/api/consulta/resultado/${guid}`);
    setRecord(data);
  }, [guid]);

  useEffect(() => {
    load().catch((err) => {
      setError(err instanceof Error ? err.message : "Error al cargar el resultado");
    });
  }, [load]);

  const handleAudit = useCallback(async () => {
    if (!guid || !record?.prediccion_ia || !selectedReal) return;
    setAuditing(true);
    setAuditError(null);
    try {
      await postJson<AuditResponse>("/api/audit/run", {
        guid,
        prediccion_ia: record.prediccion_ia,
        triage_real: selectedReal,
        score_ansiedad_ia: record.score_ansiedad_ia ?? record.score_ansiedad ?? 0,
      });
      await load();
      setSelectedReal("");
    } catch (err) {
      setAuditError(err instanceof Error ? err.message : "Error al auditar");
    } finally {
      setAuditing(false);
    }
  }, [guid, record, selectedReal, load]);

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
              <div className="rounded-xl border border-zinc-200/80 bg-white p-3 shadow-card">
                <p className="text-xs text-zinc-500">Validación</p>
                <div className="mt-1">
                  <ValidacionBadge value={record.validacion} />
                </div>
              </div>
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
                <p className="mt-2 text-sm leading-relaxed text-zinc-700">
                  {meta.desc} · {meta.minutes === "0" ? "atención inmediata" : `atención en ≤ ${meta.minutes} min`}
                </p>
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

            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-xl border border-zinc-200/80 bg-white p-4 shadow-card">
                <p className="text-xs text-zinc-500">Ansiedad</p>
                <p className="font-mono text-3xl font-semibold tracking-tight text-zinc-900">
                  {record.score_ansiedad === null || record.score_ansiedad === undefined
                    ? "—"
                    : Number(record.score_ansiedad).toFixed(2)}
                </p>
                {record.score_ansiedad !== null && record.score_ansiedad !== undefined && (
                  <span
                    className={
                      record.score_ansiedad >= 0.8
                        ? "mt-3 inline-flex items-center gap-1.5 rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700 ring-1 ring-inset ring-amber-600/20"
                        : "mt-3 inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700 ring-1 ring-inset ring-emerald-600/20"
                    }
                  >
                    <span className={record.score_ansiedad >= 0.8 ? "h-1.5 w-1.5 rounded-full bg-amber-500" : "h-1.5 w-1.5 rounded-full bg-emerald-500"} />
                    {record.score_ansiedad >= 0.8
                      ? triage === "C1"
                        ? "Ansiedad alta"
                        : "Ansiedad alta: posible riesgo de infra-triaje"
                      : "Ansiedad en rango normal"}
                  </span>
                )}
              </div>
              <div className="rounded-xl border border-zinc-200/80 bg-white p-4 shadow-card">
                <p className="text-xs text-zinc-500">Triage real</p>
                {record.triage_real ? (
                  <>
                    <p className="font-mono text-3xl font-semibold tracking-tight text-zinc-900">
                      {record.triage_real}
                    </p>
                    {record.validacion === "Under-triage" && (record.score_ansiedad ?? 0) >= 0.8 && (
                      <span className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-red-50 px-2.5 py-1 text-xs font-medium text-red-700 ring-1 ring-inset ring-red-600/20">
                        <span className="h-1.5 w-1.5 rounded-full bg-red-500" />
                        Sesgo emocional confirmado
                      </span>
                    )}
                  </>
                ) : (
                  <div className="mt-2 space-y-2">
                    <p className="text-xs leading-relaxed text-zinc-500">
                      Registra el criterio médico para auditar la predicción.
                    </p>
                    <div className="flex gap-2">
                      <select
                        value={selectedReal}
                        onChange={(e) => setSelectedReal(e.target.value as ManchesterCode | "")}
                        className="flex-1 rounded-lg border border-zinc-200 bg-white px-2.5 py-1.5 text-sm text-zinc-900 outline-none focus:border-zinc-400"
                      >
                        <option value="">Nivel real…</option>
                        {MANCHESTER_LEVELS.map((code) => (
                          <option key={code} value={code}>
                            {code} · {MANCHESTER[code].label}
                          </option>
                        ))}
                      </select>
                      <button
                        type="button"
                        onClick={handleAudit}
                        disabled={!record.prediccion_ia || !selectedReal || auditing}
                        className="rounded-lg bg-zinc-900 px-3 py-1.5 text-sm font-medium text-zinc-50 transition hover:bg-zinc-800 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-40"
                      >
                        {auditing ? "Auditando…" : "Auditar"}
                      </button>
                    </div>
                    {!record.prediccion_ia && (
                      <p className="text-xs text-zinc-400">Sin predicción IA, no se puede auditar.</p>
                    )}
                    {auditError && <p className="text-xs text-red-600">{auditError}</p>}
                  </div>
                )}
              </div>
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

function ValidacionBadge({ value }: { value: string | null }) {
  const styles: Record<string, string> = {
    Acierto: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
    "Under-triage": "bg-red-50 text-red-700 ring-red-600/20",
    "Over-triage": "bg-amber-50 text-amber-700 ring-amber-600/20",
  };
  const style = value ? styles[value] : undefined;
  if (!style) {
    return <span className="text-sm font-medium text-zinc-400">Sin verdad médica</span>;
  }
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${style}`}>
      {value}
    </span>
  );
}
