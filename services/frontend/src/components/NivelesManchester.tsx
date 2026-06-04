import { MANCHESTER, MANCHESTER_LEVELS, manchesterTextOn } from "@/lib/manchester";

export function NivelesManchester() {
  return (
    <div className="rounded-3xl border border-zinc-200/80 bg-white/90 p-5 dark:border-zinc-800/80 dark:bg-zinc-900/90 sm:p-6">
      <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-zinc-400 dark:text-zinc-500">
        Protocolo
      </p>
      <h2 className="mt-1 text-xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-100">
        Niveles Manchester
      </h2>
      <p className="mt-2 max-w-prose text-sm leading-relaxed text-zinc-500 dark:text-zinc-400">
        La clasificación ordena la urgencia en cinco niveles. Cada nivel define un tiempo máximo de
        atención recomendado, del rojo (atención inmediata) al azul (no urgente).
      </p>
      <ul className="mt-5 flex flex-col gap-2">
        {MANCHESTER_LEVELS.map((code) => {
          const meta = MANCHESTER[code];
          return (
            <li
              key={code}
              className="flex items-center gap-3 rounded-2xl border border-zinc-200/70 bg-zinc-50/50 p-3 dark:border-zinc-700/70 dark:bg-zinc-800/50"
            >
              <span
                className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-sm font-bold"
                style={{ backgroundColor: meta.color, color: manchesterTextOn(meta.color) }}
              >
                {code}
              </span>
              <div className="flex min-w-0 flex-1 items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                    {meta.label}
                  </p>
                  <p className="truncate text-xs text-zinc-500 dark:text-zinc-400">{meta.desc}</p>
                </div>
                <span className="shrink-0 font-mono text-xs text-zinc-400 dark:text-zinc-500">
                  {meta.minutes === "0" ? "0′ · inmediato" : `${meta.minutes}′`}
                </span>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
