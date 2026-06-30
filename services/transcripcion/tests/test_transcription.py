from __future__ import annotations

import pytest

from transcription import (
    AzureSpeechBackend,
    TranscriptionError,
    WhisperxBackend,
    group_segment_turns,
    select_backend,
    select_patient,
)


class TestGroupSegmentTurns:
    def test_merges_consecutive_same_speaker(self):
        segments = [
            {"text": "hola", "start": 0.0, "end": 1.0, "words": [{"speaker": "S1"}]},
            {"text": "que tal", "start": 1.0, "end": 2.0, "words": [{"speaker": "S1"}]},
            {"text": "bien", "start": 2.0, "end": 3.0, "words": [{"speaker": "S2"}]},
        ]
        turns = group_segment_turns(segments)
        assert len(turns) == 2
        assert turns[0]["speaker"] == "S1"
        assert turns[0]["text"] == "hola que tal"
        assert turns[1]["speaker"] == "S2"

    def test_skips_empty_text(self):
        segments = [{"text": "  ", "start": 0.0, "end": 1.0, "words": []}]
        assert group_segment_turns(segments) == []


class TestSelectPatient:
    def test_doctor_is_earliest_speaker(self):
        turns = [
            {"speaker": "S1", "start": 0.0, "end": 1.0, "text": "que le pasa"},
            {"speaker": "S2", "start": 1.0, "end": 2.0, "text": "me duele el pecho"},
        ]
        texto, labeled, diarized = select_patient(turns)
        assert diarized is True
        assert texto == "me duele el pecho"

    def test_single_speaker_returns_all(self):
        turns = [
            {"speaker": "S1", "start": 0.0, "end": 1.0, "text": "hola"},
            {"speaker": "S1", "start": 1.0, "end": 2.0, "text": "adios"},
        ]
        texto, labeled, diarized = select_patient(turns)
        assert diarized is False
        assert texto == "hola adios"


class TestSelectBackend:
    def test_local_returns_whisperx(self):
        assert isinstance(select_backend("local"), WhisperxBackend)

    def test_azure_returns_speech_backend(self):
        assert isinstance(select_backend("azure"), AzureSpeechBackend)

    def test_unknown_raises(self):
        with pytest.raises(TranscriptionError):
            select_backend("marte")


class TestAzureSpeechBackend:
    def _backend(self, utterances):
        return AzureSpeechBackend(recognize_fn=lambda path, lang: utterances)

    def test_isolates_patient_voice(self):
        utterances = [
            {"speaker": "Guest-1", "text": "que le pasa", "offset": 0.0, "duration": 1.0},
            {"speaker": "Guest-2", "text": "me duele el pecho", "offset": 1.0, "duration": 2.0},
        ]
        result = self._backend(utterances).transcribe(b"fake", "es-ES")
        assert result.diarized is True
        assert result.texto == "me duele el pecho"
        assert result.language == "es"

    def test_single_speaker_keeps_all(self):
        utterances = [
            {"speaker": "Guest-1", "text": "hola", "offset": 0.0, "duration": 1.0},
            {"speaker": "Guest-1", "text": "adios", "offset": 1.0, "duration": 1.0},
        ]
        result = self._backend(utterances).transcribe(b"fake", "es-ES")
        assert result.diarized is False
        assert result.texto == "hola adios"

    def test_language_normalized_to_two_letters(self):
        utterances = [{"speaker": "Guest-1", "text": "hi", "offset": 0.0, "duration": 1.0}]
        result = self._backend(utterances).transcribe(b"fake", "en-US")
        assert result.language == "en"

    def test_normalizes_two_letter_locale(self):
        captured = {}

        def fake(path, lang):
            captured["lang"] = lang
            return []

        AzureSpeechBackend(recognize_fn=fake).transcribe(b"x", "es")
        assert captured["lang"] == "es-ES"

    def test_keeps_full_locale(self):
        captured = {}

        def fake(path, lang):
            captured["lang"] = lang
            return []

        AzureSpeechBackend(recognize_fn=fake).transcribe(b"x", "en-US")
        assert captured["lang"] == "en-US"

    def test_auto_locale_passthrough(self):
        captured = {}

        def fake(path, lang):
            captured["lang"] = lang
            return []

        AzureSpeechBackend(recognize_fn=fake).transcribe(b"x", "auto")
        assert captured["lang"] == "auto"

    def test_result_language_from_detected_locale(self):
        utterances = [
            {"speaker": "G1", "text": "hi", "offset": 0.0, "duration": 1.0, "locale": "en-US"}
        ]
        result = AzureSpeechBackend(
            recognize_fn=lambda p, l: utterances
        ).transcribe(b"x", "auto")
        assert result.language == "en"
