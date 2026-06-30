from __future__ import annotations

import os
import tempfile
import threading
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol


class TranscriptionError(RuntimeError):
    pass


@dataclass
class TranscriptionResult:
    texto: str
    language: str
    duration_seconds: float
    diarized: bool = False
    turns: list[dict[str, Any]] = field(default_factory=list)
    diarization_error: Optional[str] = None


def segment_majority_speaker(segment: dict[str, Any]) -> Optional[str]:
    counts: dict[str, int] = {}
    for word in segment.get("words", []):
        speaker = word.get("speaker")
        if speaker:
            counts[speaker] = counts.get(speaker, 0) + 1
    if not counts:
        return None
    return max(counts, key=counts.get)


def group_segment_turns(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    turns: list[dict[str, Any]] = []
    for seg in segments:
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        speaker = segment_majority_speaker(seg)
        start = seg.get("start")
        end = seg.get("end")
        if speaker is None and turns:
            turns[-1]["text"] += " " + text
            if end is not None:
                turns[-1]["end"] = end
            continue
        if turns and turns[-1]["speaker"] == speaker:
            turns[-1]["text"] += " " + text
            if end is not None:
                turns[-1]["end"] = end
        else:
            turns.append({"speaker": speaker, "start": start, "end": end, "text": text})
    return turns


def select_patient(
    turns: list[dict[str, Any]]
) -> tuple[str, list[dict[str, Any]], bool]:
    located = [t for t in turns if t["speaker"] is not None and t["start"] is not None]
    distinct = {t["speaker"] for t in located}
    if len(distinct) < 2:
        texto = " ".join(t["text"] for t in turns).strip()
        return texto, turns, False

    doctor_speaker = min(located, key=lambda t: t["start"])["speaker"]
    for t in turns:
        t["is_patient"] = t["speaker"] != doctor_speaker

    patient_pieces = [t["text"] for t in turns if t["speaker"] != doctor_speaker]
    texto = " ".join(patient_pieces).strip()
    return texto, turns, True


@dataclass(frozen=True)
class WhisperxConfig:
    model_name: str
    device: str
    compute_type: str
    batch_size: int
    hf_token: Optional[str]
    num_speakers: Optional[int]

    @classmethod
    def from_env(cls) -> "WhisperxConfig":
        return cls(
            model_name=os.getenv("WHISPER_MODEL", "base"),
            device=os.getenv("WHISPER_DEVICE", "cpu"),
            compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "int8"),
            batch_size=int(os.getenv("WHISPER_BATCH_SIZE", "16")),
            hf_token=os.getenv("HF_TOKEN") or None,
            num_speakers=int(os.getenv("DIARIZATION_NUM_SPEAKERS", "2")) or None,
        )


class TranscriptionBackend(Protocol):
    def transcribe(
        self, audio_bytes: bytes, language: Optional[str]
    ) -> TranscriptionResult:
        ...


class WhisperxBackend:
    def __init__(self, config: Optional[WhisperxConfig] = None) -> None:
        self._config = config or WhisperxConfig.from_env()
        self._whisperx: Any = None
        self._model: Any = None
        self._diarizer: Any = None
        self._align_models: dict[str, tuple[Any, Any]] = {}

    def _ensure_whisperx(self) -> Any:
        if self._whisperx is not None:
            return self._whisperx
        import torch

        original_load = torch.load

        def _load_full_weights(*args: Any, **kwargs: Any) -> Any:
            kwargs["weights_only"] = False
            return original_load(*args, **kwargs)

        torch.load = _load_full_weights
        import whisperx

        self._whisperx = whisperx
        return whisperx

    def _get_model(self) -> Any:
        if self._model is None:
            wx = self._ensure_whisperx()
            self._model = wx.load_model(
                self._config.model_name,
                self._config.device,
                compute_type=self._config.compute_type,
            )
        return self._model

    def _get_diarizer(self) -> Any:
        if not self._config.hf_token:
            return None
        if self._diarizer is None:
            self._ensure_whisperx()
            try:
                from whisperx.diarize import DiarizationPipeline
            except ImportError:
                from whisperx import DiarizationPipeline
            self._diarizer = DiarizationPipeline(
                use_auth_token=self._config.hf_token, device=self._config.device
            )
        return self._diarizer

    def _get_align_model(self, language: str) -> tuple[Any, Any]:
        if language not in self._align_models:
            wx = self._ensure_whisperx()
            self._align_models[language] = wx.load_align_model(
                language_code=language, device=self._config.device
            )
        return self._align_models[language]

    def transcribe(
        self, audio_bytes: bytes, language: Optional[str]
    ) -> TranscriptionResult:
        wx = self._ensure_whisperx()
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            audio = wx.load_audio(tmp_path)
            result = self._get_model().transcribe(
                audio, batch_size=self._config.batch_size, language=language
            )
            segments = result.get("segments", [])
            detected_language = result.get("language", language or "es")
            duration = float(len(audio)) / 16000.0

            diarized = False
            diarization_error: Optional[str] = None
            labeled: list[dict[str, Any]] = []
            texto = ""
            diarizer = self._get_diarizer()
            if diarizer is not None and segments:
                try:
                    align_model, metadata = self._get_align_model(detected_language)
                    aligned = wx.align(
                        segments,
                        align_model,
                        metadata,
                        audio,
                        self._config.device,
                        return_char_alignments=False,
                    )
                    if self._config.num_speakers:
                        diarize_segments = diarizer(
                            audio, num_speakers=self._config.num_speakers
                        )
                    else:
                        diarize_segments = diarizer(audio)
                    assigned = wx.assign_word_speakers(diarize_segments, aligned)
                    turns = group_segment_turns(assigned.get("segments", []))
                    texto, labeled, diarized = select_patient(turns)
                except Exception as exc:
                    diarization_error = str(exc)
                    diarized = False

            if not diarized:
                texto = " ".join(seg["text"].strip() for seg in segments).strip()
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        return TranscriptionResult(
            texto=texto,
            language=detected_language,
            duration_seconds=duration,
            diarized=diarized,
            turns=labeled,
            diarization_error=diarization_error,
        )


_LOCALE_MAP = {"es": "es-ES", "en": "en-US"}


def _normalize_locale(lang: str) -> str:
    if "-" in lang:
        return lang
    return _LOCALE_MAP.get(lang.lower(), lang)


@dataclass(frozen=True)
class AzureSpeechConfig:
    key: Optional[str]
    region: Optional[str]
    endpoint: Optional[str]
    language: str

    @classmethod
    def from_env(cls) -> "AzureSpeechConfig":
        return cls(
            key=os.getenv("AZURE_SPEECH_KEY"),
            region=os.getenv("AZURE_SPEECH_REGION"),
            endpoint=os.getenv("AZURE_SPEECH_ENDPOINT"),
            language=os.getenv("AZURE_SPEECH_LANGUAGE", "auto"),
        )


def _convert_to_wav(src_path: str) -> str:
    try:
        import imageio_ffmpeg
    except ImportError as exc:
        raise TranscriptionError("imageio-ffmpeg no instalado") from exc
    import subprocess

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    out_path = f"{src_path}.16k.wav"
    subprocess.run(
        [ffmpeg, "-y", "-i", src_path, "-ar", "16000", "-ac", "1", "-f", "wav", out_path],
        check=True,
        capture_output=True,
    )
    return out_path


class AzureSpeechBackend:
    def __init__(
        self,
        config: Optional[AzureSpeechConfig] = None,
        recognize_fn: Any = None,
    ) -> None:
        self._config = config or AzureSpeechConfig.from_env()
        self._recognize_fn = recognize_fn or self._default_recognize

    def transcribe(
        self, audio_bytes: bytes, language: Optional[str] = None
    ) -> TranscriptionResult:
        lang = _normalize_locale(language or self._config.language)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        try:
            utterances = self._recognize_fn(tmp_path, lang)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        turns: list[dict[str, Any]] = []
        for u in utterances:
            text = (u.get("text") or "").strip()
            if not text:
                continue
            offset = float(u.get("offset") or 0.0)
            duration = float(u.get("duration") or 0.0)
            turns.append(
                {
                    "speaker": u.get("speaker"),
                    "start": offset,
                    "end": offset + duration,
                    "text": text,
                }
            )

        texto, labeled, diarized = select_patient(turns)
        total = max((t["end"] for t in turns), default=0.0)
        detected = next((u.get("locale") for u in utterances if u.get("locale")), None)
        result_language = detected or (lang if lang != "auto" else "es-ES")
        return TranscriptionResult(
            texto=texto,
            language=result_language.split("-")[0],
            duration_seconds=float(total),
            diarized=diarized,
            turns=labeled,
        )

    def _default_recognize(
        self, audio_path: str, language: str
    ) -> list[dict[str, Any]]:
        if not (self._config.key and (self._config.region or self._config.endpoint)):
            raise TranscriptionError(
                "AZURE_SPEECH_KEY y AZURE_SPEECH_REGION/ENDPOINT no configurados"
            )
        try:
            import azure.cognitiveservices.speech as speechsdk
        except ImportError as exc:
            raise TranscriptionError(
                "azure-cognitiveservices-speech no instalado"
            ) from exc

        if self._config.endpoint:
            speech_config = speechsdk.SpeechConfig(
                subscription=self._config.key, endpoint=self._config.endpoint
            )
        else:
            speech_config = speechsdk.SpeechConfig(
                subscription=self._config.key, region=self._config.region
            )
        auto = language == "auto"
        if not auto:
            speech_config.speech_recognition_language = language

        wav_path = _convert_to_wav(audio_path)
        audio_config = speechsdk.audio.AudioConfig(filename=wav_path)
        if auto:
            auto_config = speechsdk.languageconfig.AutoDetectSourceLanguageConfig(
                languages=["es-ES", "en-US"]
            )
            transcriber = speechsdk.transcription.ConversationTranscriber(
                speech_config=speech_config,
                auto_detect_source_language_config=auto_config,
                audio_config=audio_config,
            )
        else:
            transcriber = speechsdk.transcription.ConversationTranscriber(
                speech_config=speech_config, audio_config=audio_config
            )

        utterances: list[dict[str, Any]] = []
        done = threading.Event()

        def on_transcribed(evt: Any) -> None:
            result = evt.result
            if (
                result.reason == speechsdk.ResultReason.RecognizedSpeech
                and result.text
            ):
                entry = {
                    "speaker": result.speaker_id,
                    "text": result.text,
                    "offset": result.offset / 10_000_000.0,
                    "duration": result.duration / 10_000_000.0,
                }
                if auto:
                    try:
                        entry["locale"] = speechsdk.AutoDetectSourceLanguageResult(
                            result
                        ).language
                    except Exception:
                        pass
                utterances.append(entry)

        def on_stop(evt: Any) -> None:
            done.set()

        transcriber.transcribed.connect(on_transcribed)
        transcriber.session_stopped.connect(on_stop)
        transcriber.canceled.connect(on_stop)
        transcriber.start_transcribing_async().get()
        done.wait()
        transcriber.stop_transcribing_async().get()
        try:
            os.unlink(wav_path)
        except OSError:
            pass
        return utterances


def select_backend(
    name: str, config: Optional[WhisperxConfig] = None
) -> TranscriptionBackend:
    if name == "local":
        return WhisperxBackend(config)
    if name == "azure":
        return AzureSpeechBackend()
    raise TranscriptionError(f"TRANSCRIPTION_BACKEND desconocido: {name}")
