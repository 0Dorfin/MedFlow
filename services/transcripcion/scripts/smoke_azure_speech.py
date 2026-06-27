from __future__ import annotations

import sys
from pathlib import Path

import transcription


def main() -> int:
    if len(sys.argv) < 2:
        print("uso: smoke_azure_speech.py <ruta_audio> [language]")
        return 1
    audio_path = Path(sys.argv[1])
    language = sys.argv[2] if len(sys.argv) > 2 else None

    backend = transcription.select_backend("azure")
    result = backend.transcribe(audio_path.read_bytes(), language)

    print(f"language={result.language} diarized={result.diarized} dur={result.duration_seconds:.1f}s")
    print(f"turns={len(result.turns)}")
    print(f"texto={result.texto[:500]!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
