from __future__ import annotations

import csv
import os
import sys
from pathlib import Path


def main() -> int:
    endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    key = os.getenv("AZURE_SEARCH_KEY")
    index_name = os.getenv("AZURE_SEARCH_INDEX", "manchester-terms")
    csv_path = Path(
        os.getenv(
            "MANCHESTER_DICTIONARY_PATH",
            "data/dictionaries/manchester_terms.csv",
        )
    )

    if not (endpoint and key):
        print("faltan AZURE_SEARCH_ENDPOINT / AZURE_SEARCH_KEY")
        return 1
    if not csv_path.exists():
        print(f"no existe el diccionario: {csv_path}")
        return 1

    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents import SearchClient
    from azure.search.documents.indexes import SearchIndexClient
    from azure.search.documents.indexes.models import (
        SearchableField,
        SearchFieldDataType,
        SearchIndex,
        SimpleField,
    )

    credential = AzureKeyCredential(key)
    index_client = SearchIndexClient(endpoint=endpoint, credential=credential)

    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SearchableField(
            name="sintoma_coloquial",
            type=SearchFieldDataType.String,
            analyzer_name="es.lucene",
        ),
        SearchableField(
            name="termino_clinico",
            type=SearchFieldDataType.String,
            analyzer_name="es.lucene",
        ),
        SimpleField(
            name="prioridad_sugerida",
            type=SearchFieldDataType.String,
            filterable=True,
        ),
        SimpleField(
            name="grupo_clinico", type=SearchFieldDataType.String, filterable=True
        ),
    ]
    index_client.create_or_update_index(SearchIndex(name=index_name, fields=fields))

    docs: list[dict[str, str]] = []
    with csv_path.open(encoding="utf-8") as fh:
        for i, row in enumerate(csv.DictReader(fh)):
            docs.append(
                {
                    "id": str(i),
                    "sintoma_coloquial": row["sintoma_coloquial"],
                    "termino_clinico": row["termino_clinico"],
                    "prioridad_sugerida": row["prioridad_sugerida"].split("/")[0].strip(),
                    "grupo_clinico": row["grupo_clinico"],
                }
            )

    search_client = SearchClient(
        endpoint=endpoint, index_name=index_name, credential=credential
    )
    result = search_client.upload_documents(documents=docs)
    subidos = sum(1 for r in result if r.succeeded)
    print(f"index={index_name} subidos={subidos}/{len(docs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
