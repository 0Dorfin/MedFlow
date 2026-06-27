from __future__ import annotations

import sys

from triage_common.llm import LLMConfig, LLMClient


def main() -> int:
    config = LLMConfig.from_env()
    if config.backend != "azure":
        print("LLM_BACKEND debe ser 'azure' para este smoke test")
        return 1
    if not config.azure_endpoint or not config.azure_deployment:
        print("Faltan AZURE_AI_ENDPOINT o AZURE_AI_DEPLOYMENT")
        return 1
    client = LLMClient(config=config)
    out = client.generate("Responde unicamente con la palabra: ok")
    print(f"endpoint={config.azure_endpoint}")
    print(f"deployment={config.azure_deployment}")
    print(f"respuesta={out!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
