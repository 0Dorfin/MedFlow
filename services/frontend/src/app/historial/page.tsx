"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { ArrowRight, CaretLeft, CaretRight, MagnifyingGlass } from "@phosphor-icons/react";
import { TopNav, Footer } from "@/components/Chrome";
import { getJson } from "@/lib/api";
import { MANCHESTER, isManchesterCode } from "@/lib/manchester";
import type { HistorialItem } from "@/lib/types";

const PAGE_SIZE = 12;

type Periodo = "todas" | "hoy" | "7d" | "30d";

const PERIODOS: { key: Periodo; label: string }[] = [
  { key: "todas", label: "Todas las fechas" },
  { key: "hoy", label: "Hoy" },
  { key: "7d", label: "Últimos 7 días" },
  { key: "30d", label: "Últimos 30 días" },
];

function parseDate(iso: string | null): Date | null {
  if (!iso) return null;
  const hasTz = /[zZ]|[+-]\d{2}:?\d{2}$/.test(iso);
  const d = new Date(hasTz ? iso : `${iso}Z`);
  return Number.isNaN(d.getTime()) ? null : d;
}

function withinPeriodo(iso: string | null, periodo: Periodo): boolean {
  if (periodo === "todas") return true;
  const d = parseDate(iso);
  if (!d) return false;
  const now = new Date();
  if (periodo === "hoy") {
    const start = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    return d.getTime() >= start.getTime();
  }
  const days = periodo === "7d" ? 7 : 30;
  return now.getTime() - d.getTime() <= days * 86_400_000;
}

function formatFecha(iso: string | null): string {
  const d = parseDate(iso);
  if (!d) return "—";
  const fecha = d.toLocaleDateString("es-ES", {
    timeZone: "Europe/Madrid",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
  const hora = d.toLocaleTimeString("es-ES", {
    timeZone: "Europe/Madrid",
    hour: "2-digit",
    minute: "2-digit",
  });
  return `${fecha} · ${hora}`;
}

function shortGuid(guid: string): string {
  return guid.length > 16 ? `${guid.slice(0, 8)}…${guid.slice(-6)}` : guid;
}

function LevelDot({ code }: { code: string | null }) {
  if (!code || !isManchesterCode(code)) {
    return <span className="font-mono text-xs text-zinc-300 dark:text-zinc-600">—</span>;
  }
  const meta = MANCHESTER[code];
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="h-2 w-2 rounded-full" style={{ backgroundColor: meta.color }} />
      <span className="font-mono text-xs font-medium text-zinc-700 dark:text-zinc-300">{code}</span>
    </span>
  );
}

export default function HistorialPage() {
  const router = useRouter();
  const [items, setItems] = useState<HistorialItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [periodo, setPeriodo] = useState<Periodo>("todas");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);

  useEffect(() => {
    let active = true;
    getJson<HistorialItem[]>("/api/consulta/historial?limit=200")
      .then((data) => {
        if (active) setItems(data);
      })
      .catch((err) => {
        if (active) setError(err instanceof Error ? err.message : "Error al cargar el historial");
      });
    return () => {
      active = false;
    };
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (items ?? []).filter((it) => {
      if (!withinPeriodo(it.inicio_solicitud, periodo)) return false;
      if (!q) return true;
      const haystack = [it.id_caso, it.origen, it.guid_entrevista]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(q);
    });
  }, [items, periodo, query]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const pageItems = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);

  const inputBase =
    "rounded-xl border border-zinc-200 bg-white px-3 py-2 text-sm outline-none ring-zinc-900/15 transition focus:border-zinc-300 focus:ring-2 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:ring-zinc-100/10 dark:focus:border-zinc-600";

  return (
    <div className="flex h-[100dvh] flex-col overflow-hidden">
      <TopNav active="entrevistas" />

      <main className="scroll-area mx-auto w-full max-w-[1500px] flex-1 overflow-y-auto p-4 lg:p-8">
        <div className="flex items-end justify-between gap-4">
          <div>
            <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-zinc-400 dark:text-zinc-500">
              Historial
            </p>
            <h1 className="mt-1 text-3xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-100">
              Entrevistas
            </h1>
            <p className="mt-1.5 text-sm text-zinc-500 dark:text-zinc-400">
              {items === null
                ? "Cargando registros…"
                : `${filtered.length} ${filtered.length === 1 ? "registro" : "registros"} · página ${safePage} de ${totalPages}`}
            </p>
          </div>
          <Link
            href="/"
            className="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-zinc-900 px-4 py-2 text-sm font-medium text-white shadow-[0_10px_24px_-14px_rgba(24,24,27,0.7)] transition hover:bg-black active:scale-[0.98] dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white"
          >
            Nueva entrevista
            <ArrowRight size={15} weight="bold" />
          </Link>
        </div>

        <div className="mt-6 flex flex-wrap items-end gap-3">
          <div className="grid min-w-0 flex-1 gap-1 sm:max-w-sm">
            <label
              htmlFor="f-buscar"
              className="text-[10px] font-medium uppercase tracking-[0.16em] text-zinc-400 dark:text-zinc-500"
            >
              Buscar caso
            </label>
            <div className="relative">
              <MagnifyingGlass
                size={16}
                className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400 dark:text-zinc-500"
              />
              <input
                id="f-buscar"
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setPage(1);
                }}
                placeholder="ID caso, origen o GUID…"
                className={`w-full pl-9 pr-3 ${inputBase} placeholder:text-zinc-400 dark:placeholder:text-zinc-600`}
              />
            </div>
          </div>
          <div className="grid gap-1">
            <label
              htmlFor="f-periodo"
              className="text-[10px] font-medium uppercase tracking-[0.16em] text-zinc-400 dark:text-zinc-500"
            >
              Fecha
            </label>
            <select
              id="f-periodo"
              value={periodo}
              onChange={(e) => {
                setPeriodo(e.target.value as Periodo);
                setPage(1);
              }}
              className={`min-w-[12rem] ${inputBase}`}
            >
              {PERIODOS.map((p) => (
                <option key={p.key} value={p.key}>
                  {p.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {error && (
          <div className="mt-6 rounded-2xl border border-zinc-300 bg-white p-6 text-sm text-zinc-700 shadow-card dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300">
            <p className="font-medium text-zinc-900 dark:text-zinc-100">No se pudo cargar el historial</p>
            <p className="mt-1 text-zinc-500 dark:text-zinc-400">{error}</p>
          </div>
        )}

        {!error && items === null && (
          <div className="mt-6 flex flex-col gap-2">
            {Array.from({ length: 8 }).map((_, i) => (
              <motion.div
                key={i}
                className="h-12 rounded-xl bg-zinc-100 dark:bg-zinc-800"
                animate={{ opacity: [0.55, 0.9, 0.55] }}
                transition={{ repeat: Infinity, duration: 1.4, ease: "easeInOut", delay: i * 0.06 }}
              />
            ))}
          </div>
        )}

        {!error && items !== null && filtered.length === 0 && (
          <div className="mt-6 flex min-h-[200px] flex-col items-center justify-center rounded-2xl border border-dashed border-zinc-300 bg-zinc-50/60 px-8 py-12 text-center dark:border-zinc-700 dark:bg-zinc-900/60">
            <p className="text-lg font-medium tracking-tight text-zinc-800 dark:text-zinc-200">Sin resultados</p>
            <p className="mt-1 max-w-sm text-sm text-zinc-500 dark:text-zinc-400">
              No hay entrevistas en el periodo seleccionado.
            </p>
          </div>
        )}

        {!error && items !== null && filtered.length > 0 && (
          <>
            <div className="mt-6 overflow-x-auto overflow-hidden rounded-2xl border border-zinc-200/80 bg-white shadow-card dark:border-zinc-800/80 dark:bg-zinc-900">
              <table className="w-full min-w-[560px] text-left text-sm">
                <thead className="border-b border-zinc-200 text-[10px] uppercase tracking-[0.14em] text-zinc-400 dark:border-zinc-800 dark:text-zinc-500">
                  <tr>
                    <th className="px-5 py-3 font-medium">Caso</th>
                    <th className="px-5 py-3 font-medium">Predicción</th>
                    <th className="px-5 py-3 font-medium">Inicio</th>
                    <th className="px-5 py-3 text-right font-medium">GUID</th>
                  </tr>
                </thead>
                <tbody>
                  {pageItems.map((it) => (
                    <tr
                      key={it.guid_entrevista}
                      onClick={() => router.push(`/historial/${it.guid_entrevista}`)}
                      className="cursor-pointer border-b border-zinc-100 transition last:border-0 hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-800/60"
                    >
                      <td className="px-5 py-3">
                        <p className="font-medium text-zinc-900 dark:text-zinc-100">
                          {it.id_caso ?? "Caso anónimo"}
                        </p>
                        <p className="text-xs text-zinc-400 dark:text-zinc-500">{it.origen ?? "—"}</p>
                      </td>
                      <td className="px-5 py-3">
                        <LevelDot code={it.prediccion_ia} />
                      </td>
                      <td className="whitespace-nowrap px-5 py-3 font-mono text-xs text-zinc-500 dark:text-zinc-400">
                        {formatFecha(it.inicio_solicitud)}
                      </td>
                      <td className="whitespace-nowrap px-5 py-3 text-right font-mono text-xs text-zinc-400 dark:text-zinc-500">
                        {shortGuid(it.guid_entrevista)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {totalPages > 1 && (
              <div className="mt-4 flex items-center justify-end gap-2">
                <button
                  type="button"
                  disabled={safePage <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  className="flex items-center gap-1 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs font-medium text-zinc-600 transition hover:border-zinc-300 hover:text-zinc-900 disabled:opacity-40 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:border-zinc-600 dark:hover:text-zinc-100"
                >
                  <CaretLeft size={13} weight="bold" />
                  Anterior
                </button>
                <span className="px-1 text-xs text-zinc-400 dark:text-zinc-500">
                  {safePage} / {totalPages}
                </span>
                <button
                  type="button"
                  disabled={safePage >= totalPages}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  className="flex items-center gap-1 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs font-medium text-zinc-600 transition hover:border-zinc-300 hover:text-zinc-900 disabled:opacity-40 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:border-zinc-600 dark:hover:text-zinc-100"
                >
                  Siguiente
                  <CaretRight size={13} weight="bold" />
                </button>
              </div>
            )}
          </>
        )}
      </main>

      <Footer />
    </div>
  );
}
