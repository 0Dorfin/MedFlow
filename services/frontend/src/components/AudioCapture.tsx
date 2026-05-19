"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import {
  Microphone,
  Stop,
  UploadSimple,
  Waveform,
} from "@phosphor-icons/react";

type AudioCaptureProps = {
  disabled: boolean;
  onAudioReady: (blob: Blob, fileName: string) => void;
  onClear: () => void;
  compact?: boolean;
};

export function AudioCapture({ disabled, onAudioReady, onClear, compact }: AudioCaptureProps) {
  const [mode, setMode] = useState<"idle" | "recording" | "ready">("idle");
  const [elapsed, setElapsed] = useState(0);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [fileLabel, setFileLabel] = useState<string | null>(null);
  const mediaRecorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<BlobPart[]>([]);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const releasePreview = useCallback((url: string | null) => {
    if (url) URL.revokeObjectURL(url);
  }, []);

  useEffect(() => {
    return () => {
      if (timer.current) clearInterval(timer.current);
      releasePreview(previewUrl);
    };
  }, [previewUrl, releasePreview]);

  const setBlob = useCallback(
    (blob: Blob, name: string) => {
      releasePreview(previewUrl);
      const url = URL.createObjectURL(blob);
      setPreviewUrl(url);
      setFileLabel(name);
      setMode("ready");
      onAudioReady(blob, name);
    },
    [onAudioReady, previewUrl, releasePreview],
  );

  const clearAudio = useCallback(() => {
    if (timer.current) clearInterval(timer.current);
    releasePreview(previewUrl);
    setPreviewUrl(null);
    setFileLabel(null);
    setMode("idle");
    setElapsed(0);
    chunks.current = [];
    onClear();
  }, [onClear, previewUrl, releasePreview]);

  const startRecording = async () => {
    if (disabled) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunks.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.current.push(e.data);
      };
      recorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunks.current, { type: "audio/webm" });
        setBlob(blob, `grabacion-${Date.now()}.webm`);
      };
      mediaRecorder.current = recorder;
      recorder.start();
      setMode("recording");
      setElapsed(0);
      timer.current = setInterval(() => setElapsed((s) => s + 1), 1000);
    } catch {
      setMode("idle");
    }
  };

  const stopRecording = () => {
    if (timer.current) clearInterval(timer.current);
    mediaRecorder.current?.stop();
    mediaRecorder.current = null;
  };

  const onFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setBlob(file, file.name);
    event.target.value = "";
  };

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60)
      .toString()
      .padStart(2, "0");
    const s = (seconds % 60).toString().padStart(2, "0");
    return `${m}:${s}`;
  };

  const shell = compact
    ? "rounded-2xl border border-zinc-200/80 bg-white p-4 shadow-[0_12px_28px_-14px_rgba(0,0,0,0.06)]"
    : "rounded-[2rem] border border-zinc-200/80 bg-white p-8 shadow-[0_20px_40px_-15px_rgba(0,0,0,0.05)]";

  return (
    <motion.div layout className={shell}>
      <motion.div
        className={`flex items-center gap-2 ${compact ? "mb-3" : "mb-6"}`}
        animate={mode === "recording" ? { scale: [1, 1.02, 1] } : { scale: 1 }}
        transition={{ repeat: mode === "recording" ? Infinity : 0, duration: 1.2 }}
      >
        <span
          className={`flex items-center justify-center rounded-xl bg-emerald-50 text-emerald-700 ${
            compact ? "h-8 w-8" : "h-11 w-11 rounded-2xl"
          }`}
        >
          <Waveform size={compact ? 18 : 22} weight="duotone" />
        </span>
        <motion.div layoutId="audio-title">
          <p className="text-xs font-medium tracking-tight text-zinc-500">Entrada clinica</p>
          <h2 className={`font-semibold tracking-tight text-zinc-900 ${compact ? "text-sm" : "text-xl"}`}>
            Audio del paciente
          </h2>
        </motion.div>
      </motion.div>

      {previewUrl ? (
        <div className="space-y-4">
          <audio controls src={previewUrl} className="w-full" />
          <p className="text-sm text-zinc-500">{fileLabel}</p>
          <button
            type="button"
            onClick={clearAudio}
            disabled={disabled}
            className="text-sm font-medium text-zinc-500 transition active:scale-[0.98] hover:text-zinc-800 disabled:opacity-40"
          >
            Quitar audio
          </button>
        </div>
      ) : (
        <motion.div layout className="grid gap-2 sm:grid-cols-2">
          <button
            type="button"
            disabled={disabled || mode === "recording"}
            onClick={() => inputRef.current?.click()}
            className={`group flex flex-col items-start gap-2 rounded-xl border border-dashed border-zinc-300 bg-zinc-50/80 text-left transition hover:border-emerald-400 hover:bg-emerald-50/40 active:scale-[0.98] disabled:opacity-40 ${
              compact ? "p-3" : "gap-3 rounded-2xl p-5"
            }`}
          >
            <UploadSimple size={compact ? 20 : 24} className="text-zinc-500 group-hover:text-emerald-700" />
            <span className={`font-medium text-zinc-900 ${compact ? "text-sm" : ""}`}>Subir archivo</span>
            {!compact && <span className="text-sm text-zinc-500">WAV, MP3, WEBM, M4A</span>}
          </button>

          <button
            type="button"
            disabled={disabled}
            onClick={mode === "recording" ? stopRecording : startRecording}
            className={`flex flex-col items-start gap-2 rounded-xl border text-left transition active:scale-[0.98] disabled:opacity-40 ${
              compact ? "p-3" : "gap-3 rounded-2xl p-5"
            } ${
              mode === "recording"
                ? "border-rose-300 bg-rose-50"
                : "border-zinc-300 bg-zinc-50/80 hover:border-emerald-400 hover:bg-emerald-50/40"
            }`}
          >
            {mode === "recording" ? (
              <Stop size={24} className="text-rose-600" weight="fill" />
            ) : (
              <Microphone size={24} className="text-zinc-500" />
            )}
            <span className="font-medium text-zinc-900">
              {mode === "recording" ? "Detener grabacion" : "Grabar en vivo"}
            </span>
            <span className="font-mono text-sm text-zinc-500">
              {mode === "recording" ? formatTime(elapsed) : "Microfono del dispositivo"}
            </span>
          </button>
        </motion.div>
      )}

      <input
        ref={inputRef}
        type="file"
        accept="audio/*"
        className="hidden"
        onChange={onFileChange}
      />
    </motion.div>
  );
}
