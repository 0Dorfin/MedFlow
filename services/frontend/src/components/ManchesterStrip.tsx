"use client";

import { motion } from "framer-motion";
import { MANCHESTER, MANCHESTER_LEVELS, type ManchesterCode } from "@/lib/manchester";

type ManchesterStripProps = {
  active: ManchesterCode | null;
};

export function ManchesterStrip({ active }: ManchesterStripProps) {
  return (
    <motion.div
      layout
      className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-5"
    >
      {MANCHESTER_LEVELS.map((code) => {
        const meta = MANCHESTER[code];
        const isActive = code === active;
        return (
          <motion.div
            key={code}
            layout
            animate={{
              opacity: active && !isActive ? 0.45 : 1,
              scale: isActive ? 1.04 : 1,
            }}
            transition={{ type: "spring", stiffness: 120, damping: 18 }}
            className="rounded-xl px-3 py-4 text-center"
            style={{
              border: `${isActive ? 4 : 1}px solid ${isActive ? meta.color : `${meta.color}55`}`,
              backgroundColor: `${meta.color}22`,
            }}
          >
            <p
              className="text-[22px] font-bold leading-none tracking-tight"
              style={{ color: meta.color }}
            >
              {code}
            </p>
            <p className="mt-1.5 text-xs text-zinc-600">{meta.label}</p>
            <p className="font-mono text-[11px] text-zinc-500">{meta.minutes} min</p>
            <p className="mt-0.5 text-[10px] text-zinc-500">{meta.desc}</p>
          </motion.div>
        );
      })}
    </motion.div>
  );
}
