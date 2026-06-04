"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Moon, Sun } from "@phosphor-icons/react";
import { Logo } from "@/components/Logo";

function ThemeToggle() {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    setDark(document.documentElement.classList.contains("dark"));
  }, []);

  const toggle = () => {
    const next = !dark;
    setDark(next);
    if (next) {
      document.documentElement.classList.add("dark");
      localStorage.setItem("theme", "dark");
    } else {
      document.documentElement.classList.remove("dark");
      localStorage.setItem("theme", "light");
    }
  };

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label="Cambiar tema"
      className="flex h-8 w-8 items-center justify-center rounded-lg border border-zinc-200 bg-white text-zinc-500 transition hover:border-zinc-300 hover:text-zinc-900 active:scale-[0.96] dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-400 dark:hover:border-zinc-600 dark:hover:text-zinc-100"
    >
      {dark ? <Sun size={16} weight="bold" /> : <Moon size={16} weight="bold" />}
    </button>
  );
}

function Brand() {
  return (
    <Link href="/" className="flex items-center gap-2.5">
      <Logo size={28} className="h-7 w-7" priority />
      <span className="flex items-baseline gap-2">
        <span className="text-sm font-semibold tracking-tight text-zinc-900 dark:text-zinc-100">
          MedFlow
        </span>
        <span className="hidden text-[10px] font-medium uppercase tracking-[0.18em] text-zinc-400 dark:text-zinc-500 sm:inline">
          Manchester C1–C5
        </span>
      </span>
    </Link>
  );
}

type NavKey = "ingesta" | "entrevistas";

function NavLink({ href, label, active }: { href: string; label: string; active: boolean }) {
  return (
    <Link
      href={href}
      className={`rounded-full px-3.5 py-1.5 text-xs font-medium transition active:scale-[0.98] ${
        active
          ? "bg-zinc-900 text-white shadow-[0_8px_20px_-12px_rgba(24,24,27,0.6)] dark:bg-zinc-100 dark:text-zinc-900"
          : "text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
      }`}
    >
      {label}
    </Link>
  );
}

export function TopNav({ active }: { active: NavKey }) {
  return (
    <header className="shrink-0 border-b border-zinc-200/70 bg-white/70 px-4 py-3 backdrop-blur-sm dark:border-zinc-800/70 dark:bg-zinc-950/70 lg:px-8">
      <div className="mx-auto flex max-w-[1500px] items-center justify-between gap-4">
        <Brand />
        <nav className="flex items-center gap-2">
          <NavLink href="/" label="Ingesta" active={active === "ingesta"} />
          <NavLink href="/historial" label="Entrevistas" active={active === "entrevistas"} />
          <ThemeToggle />
        </nav>
      </div>
    </header>
  );
}

export function Footer() {
  return (
    <footer className="shrink-0 border-t border-zinc-200/70 bg-white/60 px-4 py-3 backdrop-blur-sm dark:border-zinc-800/70 dark:bg-zinc-950/60 lg:px-8">
      <div className="mx-auto flex max-w-[1500px] items-center justify-between text-[10px] font-medium uppercase tracking-[0.18em] text-zinc-400 dark:text-zinc-600">
        <span>MedFlow · Protocolo Manchester</span>
      </div>
    </footer>
  );
}
