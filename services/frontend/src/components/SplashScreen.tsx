"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Pulse } from "@phosphor-icons/react";

export function SplashScreen() {
  const [show, setShow] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => setShow(false), 1500);
    return () => clearTimeout(timer);
  }, []);

  return (
    <AnimatePresence>
      {show && (
        <motion.div
          initial={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.5, ease: "easeInOut" }}
          className="fixed inset-0 z-[100] flex flex-col items-center justify-center gap-6"
          style={{ backgroundColor: "var(--background)" }}
        >
          <motion.span
            animate={{ scale: [1, 1.08, 1] }}
            transition={{ repeat: Infinity, duration: 1.4, ease: "easeInOut" }}
            className="flex h-14 w-14 items-center justify-center rounded-2xl bg-zinc-900 text-white shadow-[0_18px_40px_-18px_rgba(24,24,27,0.6)]"
          >
            <Pulse size={28} weight="bold" />
          </motion.span>

          <div className="text-center">
            <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-zinc-400">
              TriageIA
            </p>
            <h1 className="mt-1.5 text-xl font-semibold tracking-tight text-zinc-900">
              Sistema de Triaje Manchester
            </h1>
          </div>

          <div className="flex items-center gap-2 text-sm text-zinc-500">
            <motion.span
              className="inline-block h-4 w-4 rounded-full border-2 border-zinc-300 border-t-zinc-900"
              animate={{ rotate: 360 }}
              transition={{ repeat: Infinity, duration: 0.8, ease: "linear" }}
            />
            Cargando…
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
