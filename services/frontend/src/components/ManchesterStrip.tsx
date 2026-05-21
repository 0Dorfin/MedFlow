"use client";

import { motion } from "framer-motion";
import {
  MANCHESTER,
  MANCHESTER_LEVELS,
  manchesterTextOn,
  type ManchesterCode,
} from "@/lib/manchester";

type ManchesterStripProps = {
  active: ManchesterCode | null;
};

export function ManchesterStrip({ active }: ManchesterStripProps) {
  return (
    <motion.div layout className="mt-3 grid grid-cols-5 gap-1.5">
      {MANCHESTER_LEVELS.map((code) => {
        const meta = MANCHESTER[code];
        const isActive = code === active;
        const fg = isActive ? manchesterTextOn(meta.color) : meta.color;
        return (
          <motion.div
            key={code}
            layout
            animate={{
              opacity: active && !isActive ? 0.5 : 1,
              y: isActive ? -4 : 0,
            }}
            transition={{ type: "spring", stiffness: 220, damping: 22 }}
            className="relative flex flex-col items-center gap-1 rounded-2xl px-1.5 pb-2.5 pt-3 text-center"
            style={{
              backgroundColor: isActive ? meta.color : `${meta.color}14`,
              border: `1px solid ${isActive ? meta.color : `${meta.color}40`}`,
              boxShadow: isActive ? `0 12px 26px -12px ${meta.color}` : "none",
            }}
          >
            <span
              className="text-lg font-bold leading-none tracking-tight sm:text-xl"
              style={{ color: fg }}
            >
              {code}
            </span>
            <span
              className="text-[10px] font-medium leading-tight sm:text-[11px]"
              style={{ color: isActive ? fg : "#52525b" }}
            >
              {meta.label}
            </span>
            <span
              className="font-mono text-[9px] leading-none sm:text-[10px]"
              style={{ color: isActive ? fg : "#71717a", opacity: isActive ? 0.85 : 1 }}
            >
              {meta.minutes === "0" ? "inmediato" : `${meta.minutes} min`}
            </span>
            {isActive && (
              <motion.span
                layoutId="manchester-marker"
                className="absolute -bottom-1.5 h-1.5 w-1.5 rounded-full"
                style={{ backgroundColor: meta.color }}
                transition={{ type: "spring", stiffness: 320, damping: 26 }}
              />
            )}
          </motion.div>
        );
      })}
    </motion.div>
  );
}
