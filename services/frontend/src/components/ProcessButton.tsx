"use client";

import { useRef } from "react";
import { motion, useMotionValue, useSpring, useTransform } from "framer-motion";
import { ArrowRight, Pulse } from "@phosphor-icons/react";

type ProcessButtonProps = {
  disabled: boolean;
  loading: boolean;
  onClick: () => void;
};

export function ProcessButton({ disabled, loading, onClick }: ProcessButtonProps) {
  const ref = useRef<HTMLButtonElement>(null);
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const springX = useSpring(x, { stiffness: 150, damping: 18 });
  const springY = useSpring(y, { stiffness: 150, damping: 18 });
  const translateX = useTransform(springX, [-40, 40], [-6, 6]);
  const translateY = useTransform(springY, [-40, 40], [-4, 4]);

  const handleMove = (event: React.MouseEvent<HTMLButtonElement>) => {
    const el = ref.current;
    if (!el || disabled || loading) return;
    const rect = el.getBoundingClientRect();
    x.set(event.clientX - rect.left - rect.width / 2);
    y.set(event.clientY - rect.top - rect.height / 2);
  };

  const handleLeave = () => {
    x.set(0);
    y.set(0);
  };

  const idle = !disabled && !loading;

  return (
    <motion.button
      ref={ref}
      type="button"
      disabled={disabled || loading}
      onClick={onClick}
      onMouseMove={handleMove}
      onMouseLeave={handleLeave}
      style={{ x: translateX, y: translateY }}
      whileTap={{ scale: 0.98 }}
      className={`flex w-full items-center justify-center gap-2 rounded-2xl bg-zinc-900 px-6 py-4 text-base font-semibold text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.14),0_12px_26px_-12px_rgba(24,24,27,0.5)] transition hover:bg-black disabled:cursor-not-allowed disabled:opacity-45 dark:bg-zinc-100 dark:text-zinc-900 dark:shadow-[inset_0_1px_0_rgba(0,0,0,0.06),0_12px_26px_-12px_rgba(0,0,0,0.3)] dark:hover:bg-white ${idle ? "sheen" : ""}`}
    >
      {loading ? (
        <>
          <motion.span
            animate={{ rotate: 360 }}
            transition={{ repeat: Infinity, duration: 1, ease: "linear" }}
          >
            <Pulse size={20} weight="bold" />
          </motion.span>
          Procesando pipeline...
        </>
      ) : (
        <>
          Iniciar triaje
          <ArrowRight size={18} weight="bold" />
        </>
      )}
    </motion.button>
  );
}
