from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Optional, Protocol

from triage_common import dictionary
from triage_common.contracts import GrupoClinico, NormalizedEntity, TriageLevel


class NormalizationError(RuntimeError):
    pass


class NormalizationBackend(Protocol):
    def normalize_many(
        self, terms: list[str]
    ) -> tuple[list[NormalizedEntity], list[str]]:
        ...


class LocalDictionaryBackend:
    def normalize_many(
        self, terms: list[str]
    ) -> tuple[list[NormalizedEntity], list[str]]:
        return dictionary.normalize_many(terms)


@dataclass(frozen=True)
class AzureSearchConfig:
    endpoint: Optional[str]
    key: Optional[str]
    index_name: str
    min_score: float

    @classmethod
    def from_env(cls) -> "AzureSearchConfig":
        return cls(
            endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
            key=os.getenv("AZURE_SEARCH_KEY"),
            index_name=os.getenv("AZURE_SEARCH_INDEX", "manchester-terms"),
            min_score=float(os.getenv("AZURE_SEARCH_MIN_SCORE", "0.0")),
        )


class AzureSearchBackend:
    def __init__(
        self,
        config: Optional[AzureSearchConfig] = None,
        client: Any = None,
        min_score: Optional[float] = None,
    ) -> None:
        self._config = config or AzureSearchConfig.from_env()
        self._client = client
        self._min_score = self._config.min_score if min_score is None else min_score

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not (self._config.endpoint and self._config.key):
            raise NormalizationError("AZURE_SEARCH_ENDPOINT/KEY no configurados")
        try:
            from azure.core.credentials import AzureKeyCredential
            from azure.search.documents import SearchClient
        except ImportError as exc:
            raise NormalizationError(
                "azure-search-documents no instalado; pip install '.[azure]'"
            ) from exc
        self._client = SearchClient(
            endpoint=self._config.endpoint,
            index_name=self._config.index_name,
            credential=AzureKeyCredential(self._config.key),
        )
        return self._client

    def normalize_many(
        self, terms: list[str]
    ) -> tuple[list[NormalizedEntity], list[str]]:
        client = self._get_client()
        mapeados: list[NormalizedEntity] = []
        no_mapeados: list[str] = []
        for term in terms:
            hits = list(client.search(search_text=term, top=1))
            if not hits:
                no_mapeados.append(term)
                continue
            doc = hits[0]
            score = float(doc.get("@search.score", 0.0))
            if score < self._min_score:
                no_mapeados.append(term)
                continue
            mapeados.append(
                NormalizedEntity(
                    termino_clinico=doc["termino_clinico"],
                    prioridad_sugerida=TriageLevel(doc["prioridad_sugerida"]),
                    grupo_clinico=GrupoClinico(doc["grupo_clinico"]),
                    sintoma_original=term,
                )
            )
        return mapeados, no_mapeados


def select_normalization_backend(
    name: str, config: Optional[AzureSearchConfig] = None
) -> NormalizationBackend:
    if name == "local":
        return LocalDictionaryBackend()
    if name == "azure":
        return AzureSearchBackend(config)
    raise NormalizationError(f"NORMALIZATION_BACKEND desconocido: {name}")
