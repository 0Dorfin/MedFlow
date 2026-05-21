"use client";

import { useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { CaretDown, Copy, Check } from "@phosphor-icons/react";
import type { PipelineOutput } from "@/lib/types";

type JsonDisclosureProps = {
  data: PipelineOutput | null;
};

export function JsonDisclosure({ data }: JsonDisclosureProps) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  const jsonText = useMemo(() => {
    if (!data) return "";
    return JSON.stringify({ resultado: data.result, pasos: data.pasos }, null, 2);
  }, [data]);

  const copy = async (event: React.MouseEvent) => {
    event.stopPropagation();
    if (!jsonText) return;
    await navigator.clipboard.writeText(jsonText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!data) return null;

  return (
    <motion.div layout className="overflow-hidden rounded-xl border border-zinc-200/70 bg-zinc-50/50 dark:border-zinc-700/70 dark:bg-zinc-900/50">
      <div className="flex items-center justify-between gap-3 px-3 py-2">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="flex flex-1 items-center gap-2 text-left transition hover:opacity-80 active:scale-[0.99]"
        >
          <motion.span animate={{ rotate: open ? 180 : 0 }} transition={{ duration: 0.2 }}>
            <CaretDown size={14} className="text-zinc-400 dark:text-zinc-500" />
          </motion.span>
          <span className="text-xs font-medium text-zinc-500 dark:text-zinc-400">
            Detalles técnicos (JSON)
          </span>
        </button>
        <button
          type="button"
          onClick={copy}
          className="flex shrink-0 items-center gap-1 rounded-lg px-2 py-1 text-xs text-zinc-500 transition hover:bg-zinc-100 hover:text-zinc-800 active:scale-[0.98] dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-200"
        >
          {copied ? <Check size={14} /> : <Copy size={14} />}
          {copied ? "Copiado" : "Copiar"}
        </button>
      </div>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ type: "spring", stiffness: 120, damping: 22 }}
            className="overflow-hidden border-t border-zinc-200/80 dark:border-zinc-700/80"
          >
            <pre className="scroll-area max-h-56 overflow-auto bg-zinc-950 p-3 font-mono text-[10px] leading-relaxed text-zinc-300">
              {jsonText}
            </pre>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
