export type ManchesterCode = "C1" | "C2" | "C3" | "C4" | "C5";

export type ManchesterMeta = {
  code: ManchesterCode;
  color: string;
  label: string;
  minutes: string;
  desc: string;
};

export const MANCHESTER_LEVELS: ManchesterCode[] = ["C1", "C2", "C3", "C4", "C5"];

export const MANCHESTER: Record<ManchesterCode, ManchesterMeta> = {
  C1: { code: "C1", color: "#d62828", label: "Rojo", minutes: "0", desc: "Emergencia" },
  C2: { code: "C2", color: "#f77f00", label: "Naranja", minutes: "10", desc: "Muy urgente" },
  C3: { code: "C3", color: "#fcbf49", label: "Amarillo", minutes: "60", desc: "Urgente" },
  C4: { code: "C4", color: "#43aa8b", label: "Verde", minutes: "120", desc: "Menos urgente" },
  C5: { code: "C5", color: "#277da1", label: "Azul", minutes: "240", desc: "No urgente" },
};

export function isManchesterCode(value: string): value is ManchesterCode {
  return MANCHESTER_LEVELS.includes(value as ManchesterCode);
}

export function manchesterTextOn(color: string): string {
  const hex = color.replace("#", "");
  const r = parseInt(hex.slice(0, 2), 16);
  const g = parseInt(hex.slice(2, 4), 16);
  const b = parseInt(hex.slice(4, 6), 16);
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luminance > 0.62 ? "#1c1917" : "#ffffff";
}
