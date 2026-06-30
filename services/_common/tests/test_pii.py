from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from triage_common.pii import (
    AzureLanguagePii,
    LocalRegexPii,
    PiiError,
    select_pii_backend,
)


class TestLocalRegexPii:
    def test_redacts_phone(self):
        result = LocalRegexPii().redact("llama al 600123123 si empeora")
        assert "600123123" not in result.text
        assert "[TELEFONO]" in result.text

    def test_redacts_email(self):
        result = LocalRegexPii().redact("escribe a juan.perez@mail.com")
        assert "juan.perez@mail.com" not in result.text
        assert "[EMAIL]" in result.text

    def test_redacts_dni(self):
        result = LocalRegexPii().redact("mi DNI es 12345678Z")
        assert "12345678Z" not in result.text
        assert "[DNI]" in result.text

    def test_keeps_clinical_text(self):
        result = LocalRegexPii().redact("me duele el pecho")
        assert result.text == "me duele el pecho"
        assert result.entities == []


class TestAzureLanguagePii:
    def test_uses_redacted_text(self):
        doc = MagicMock()
        doc.redacted_text = "llama al ***"
        ent = MagicMock()
        ent.category = "PhoneNumber"
        ent.text = "600123123"
        doc.entities = [ent]
        client = MagicMock()
        client.recognize_pii_entities.return_value = [doc]

        result = AzureLanguagePii(client=client).redact("llama al 600123123")
        assert result.text == "llama al ***"
        assert result.entities[0]["category"] == "PhoneNumber"
        assert result.entities[0]["text"] == "600123123"

    def test_excludes_datetime_via_categories(self):
        doc = MagicMock()
        doc.redacted_text = "x"
        doc.entities = []
        client = MagicMock()
        client.recognize_pii_entities.return_value = [doc]
        AzureLanguagePii(client=client).redact("hola desde ayer")
        cats = client.recognize_pii_entities.call_args.kwargs["categories_filter"]
        assert "Person" in cats
        assert "DateTime" not in cats

    def test_respects_given_language(self):
        doc = MagicMock()
        doc.redacted_text = "x"
        doc.entities = []
        client = MagicMock()
        client.recognize_pii_entities.return_value = [doc]
        AzureLanguagePii(client=client).redact("hello", language="en")
        assert client.recognize_pii_entities.call_args.kwargs["language"] == "en"

    def test_auto_detects_language(self):
        from triage_common.pii import AzureLanguageConfig

        detected = MagicMock()
        detected.primary_language.iso6391_name = "en"
        doc = MagicMock()
        doc.redacted_text = "x"
        doc.entities = []
        client = MagicMock()
        client.detect_language.return_value = [detected]
        client.recognize_pii_entities.return_value = [doc]
        cfg = AzureLanguageConfig(endpoint="e", key="k", language="auto")
        AzureLanguagePii(config=cfg, client=client).redact("hello there")
        client.detect_language.assert_called_once()
        assert client.recognize_pii_entities.call_args.kwargs["language"] == "en"


class TestSelector:
    def test_local(self):
        assert isinstance(select_pii_backend("local"), LocalRegexPii)

    def test_azure(self):
        assert isinstance(select_pii_backend("azure"), AzureLanguagePii)

    def test_unknown(self):
        with pytest.raises(PiiError):
            select_pii_backend("marte")
