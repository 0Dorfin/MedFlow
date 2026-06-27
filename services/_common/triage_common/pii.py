from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol


class PiiError(RuntimeError):
    pass


@dataclass
class PiiResult:
    text: str
    entities: list[dict[str, str]] = field(default_factory=list)


class PiiBackend(Protocol):
    def redact(self, text: str, language: Optional[str] = None) -> PiiResult:
        ...


_PATTERNS = [
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    ("DNI", re.compile(r"\b\d{8}[A-Za-z]\b")),
    ("TELEFONO", re.compile(r"\b\d{9}\b")),
]


class LocalRegexPii:
    def redact(self, text: str, language: Optional[str] = None) -> PiiResult:
        entities: list[dict[str, str]] = []
        redacted = text
        for label, pattern in _PATTERNS:
            for match in pattern.findall(redacted):
                entities.append({"category": label, "text": match})
            redacted = pattern.sub(f"[{label}]", redacted)
        return PiiResult(text=redacted, entities=entities)


DEFAULT_PII_CATEGORIES = ("Person", "PhoneNumber", "Email", "Address", "Organization")


@dataclass(frozen=True)
class AzureLanguageConfig:
    endpoint: Optional[str]
    key: Optional[str]
    language: str
    categories: tuple[str, ...] = DEFAULT_PII_CATEGORIES

    @classmethod
    def from_env(cls) -> "AzureLanguageConfig":
        raw = os.getenv("AZURE_PII_CATEGORIES")
        categories = (
            tuple(c.strip() for c in raw.split(",") if c.strip())
            if raw
            else DEFAULT_PII_CATEGORIES
        )
        return cls(
            endpoint=os.getenv("AZURE_LANGUAGE_ENDPOINT"),
            key=os.getenv("AZURE_LANGUAGE_KEY"),
            language=os.getenv("AZURE_LANGUAGE_PII_LANGUAGE", "auto"),
            categories=categories,
        )


class AzureLanguagePii:
    def __init__(
        self, config: Optional[AzureLanguageConfig] = None, client: Any = None
    ) -> None:
        self._config = config or AzureLanguageConfig.from_env()
        self._client = client

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not (self._config.endpoint and self._config.key):
            raise PiiError("AZURE_LANGUAGE_ENDPOINT/KEY no configurados")
        try:
            from azure.ai.textanalytics import TextAnalyticsClient
            from azure.core.credentials import AzureKeyCredential
        except ImportError as exc:
            raise PiiError(
                "azure-ai-textanalytics no instalado; pip install '.[azure]'"
            ) from exc
        self._client = TextAnalyticsClient(
            endpoint=self._config.endpoint,
            credential=AzureKeyCredential(self._config.key),
        )
        return self._client

    def redact(self, text: str, language: Optional[str] = None) -> PiiResult:
        client = self._get_client()
        lang = language or self._config.language
        if lang == "auto":
            detected = client.detect_language([text])
            lang = detected[0].primary_language.iso6391_name
        kwargs: dict[str, Any] = {"language": lang}
        if self._config.categories:
            kwargs["categories_filter"] = list(self._config.categories)
        response = client.recognize_pii_entities([text], **kwargs)
        doc = response[0]
        entities = [
            {"category": str(e.category), "text": e.text} for e in doc.entities
        ]
        return PiiResult(text=doc.redacted_text, entities=entities)


def select_pii_backend(
    name: str, config: Optional[AzureLanguageConfig] = None
) -> PiiBackend:
    if name == "local":
        return LocalRegexPii()
    if name == "azure":
        return AzureLanguagePii(config)
    raise PiiError(f"PII_BACKEND desconocido: {name}")
