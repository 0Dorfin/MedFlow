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
