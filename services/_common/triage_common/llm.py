from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Protocol

import httpx
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


DEFAULT_PROMPTS_DIR = Path(os.getenv("PROMPTS_DIR", "/app/data/prompts"))


@dataclass(frozen=True)
class LLMConfig:
    base_url: str
    default_model: str
    timeout_seconds: float
    max_retries: int
    api_key: Optional[str] = None
    backend: str = "local"
    azure_endpoint: Optional[str] = None
    azure_deployment: Optional[str] = None
    azure_api_key: Optional[str] = None

    @classmethod
    def from_env(cls) -> "LLMConfig":
        return cls(
            base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            default_model=os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.2-3b-instruct:free"),
            timeout_seconds=float(os.getenv("LLM_TIMEOUT", "120")),
            max_retries=int(os.getenv("LLM_MAX_RETRIES", "3")),
            api_key=os.getenv("OPENROUTER_API_KEY"),
            backend=os.getenv("LLM_BACKEND", "local"),
            azure_endpoint=os.getenv("AZURE_AI_ENDPOINT"),
            azure_deployment=os.getenv("AZURE_AI_DEPLOYMENT"),
            azure_api_key=os.getenv("AZURE_AI_KEY"),
        )


class LLMError(RuntimeError):
    pass


class LLMInvalidJSON(LLMError):
    pass


class LLMBackend(Protocol):
    def chat(self, payload: dict[str, Any]) -> str:
        ...

    def list_models(self) -> list[str]:
        ...


class OpenRouterBackend:
    def __init__(self, config: LLMConfig, client: Optional[httpx.Client] = None) -> None:
        self._config = config
        self._client = client or httpx.Client(timeout=config.timeout_seconds)

    def chat(self, payload: dict[str, Any]) -> str:
        if not self._config.api_key:
            raise LLMError("OPENROUTER_API_KEY no configurada")
        attempts = max(1, self._config.max_retries)

        @retry(
            reraise=True,
            stop=stop_after_attempt(attempts),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception_type((httpx.HTTPError,)),
        )
        def _do_call() -> str:
            response = self._client.post(
                f"{self._config.base_url}/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self._config.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://triage.local",
                    "X-Title": "MedFlow",
                },
            )
            response.raise_for_status()
            data = response.json()
            choices = data.get("choices") or []
            if not choices:
                raise LLMError(f"OpenRouter sin choices: {data}")
            content = choices[0].get("message", {}).get("content")
            if content is None:
                raise LLMError(f"OpenRouter sin content: {choices[0]}")
            return str(content)

        return _do_call()

    def list_models(self) -> list[str]:
        response = self._client.get(
            f"{self._config.base_url}/models",
            headers={"Authorization": f"Bearer {self._config.api_key or ''}"},
        )
        response.raise_for_status()
        data = response.json()
        return [m.get("id", "") for m in data.get("data", [])]

    def close(self) -> None:
        self._client.close()


class AzureFoundryBackend:
    def __init__(self, config: LLMConfig, client: Any | None = None) -> None:
        self._config = config
        self._client = client if client is not None else self._build_client()

    def _build_client(self) -> Any:
        if not self._config.azure_endpoint:
            raise LLMError("AZURE_AI_ENDPOINT no configurado")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise LLMError("openai no instalado; pip install '.[azure]'") from exc
        bearer = self._config.azure_api_key or self._aad_token()
        return OpenAI(
            base_url=self._config.azure_endpoint,
            api_key=bearer,
            timeout=self._config.timeout_seconds,
        )

    def _aad_token(self) -> str:
        try:
            from azure.identity import DefaultAzureCredential
        except ImportError as exc:
            raise LLMError("azure-identity no instalado; pip install '.[azure]'") from exc
        credential = DefaultAzureCredential()
        return credential.get_token("https://cognitiveservices.azure.com/.default").token

    def chat(self, payload: dict[str, Any]) -> str:
        kwargs: dict[str, Any] = {
            "model": self._config.azure_deployment or payload.get("model"),
            "messages": payload["messages"],
        }
        if "temperature" in payload:
            kwargs["temperature"] = payload["temperature"]
        if "max_tokens" in payload:
            kwargs["max_tokens"] = payload["max_tokens"]
        if "response_format" in payload:
            kwargs["response_format"] = payload["response_format"]
        response = self._client.chat.completions.create(**kwargs)
        choices = getattr(response, "choices", None) or []
        if not choices:
            raise LLMError(f"Azure Foundry sin choices: {response}")
        content = choices[0].message.content
        if content is None:
            raise LLMError("Azure Foundry sin content")
        return str(content)

    def list_models(self) -> list[str]:
        raise LLMError("list_models no soportado en backend 'azure'")


def _select_backend(config: LLMConfig, client: Optional[Any]) -> LLMBackend:
    if config.backend == "local":
        return OpenRouterBackend(config, client)
    if config.backend == "azure":
        return AzureFoundryBackend(config, client)
    raise LLMError(f"LLM_BACKEND desconocido: {config.backend}")


class LLMClient:
    def __init__(
        self,
        config: LLMConfig | None = None,
        client: Optional[Any] = None,
        prompts_dir: Path | None = None,
        backend: LLMBackend | None = None,
    ) -> None:
        self._config = config or LLMConfig.from_env()
        self._backend = backend or _select_backend(self._config, client)
        self._env = Environment(
            loader=FileSystemLoader(str(prompts_dir or DEFAULT_PROMPTS_DIR)),
            autoescape=select_autoescape(default=False),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(self, template_name: str, **context: Any) -> str:
        template = self._env.get_template(template_name)
        return template.render(**context)

    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        json_mode: bool = False,
        options: Optional[dict[str, Any]] = None,
    ) -> str:
        payload: dict[str, Any] = {
            "model": model or self._config.default_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": (options or {}).get("temperature", 0.1),
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        if options and "max_tokens" in options:
            payload["max_tokens"] = options["max_tokens"]
        return self._backend.chat(payload)

    def generate_json(
        self,
        prompt: str,
        model: Optional[str] = None,
        options: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        raw = self.generate(prompt=prompt, model=model, json_mode=True, options=options)
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LLMInvalidJSON(f"Respuesta LLM no es JSON valido: {raw[:200]}") from exc

    def render_and_generate(
        self,
        template_name: str,
        context: dict[str, Any],
        model: Optional[str] = None,
        json_mode: bool = False,
        options: Optional[dict[str, Any]] = None,
    ) -> str:
        prompt = self.render(template_name, **context)
        return self.generate(prompt=prompt, model=model, json_mode=json_mode, options=options)

    def render_and_generate_json(
        self,
        template_name: str,
        context: dict[str, Any],
        model: Optional[str] = None,
        options: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        prompt = self.render(template_name, **context)
        return self.generate_json(prompt=prompt, model=model, options=options)

    def list_models(self) -> list[str]:
        return self._backend.list_models()

    def provenance(self, prompt_name: Optional[str] = None) -> dict[str, Any]:
        if self._config.backend == "azure":
            model = self._config.azure_deployment or self._config.default_model
        else:
            model = self._config.default_model
        return {
            "backend": self._config.backend,
            "model": model,
            "prompt": prompt_name,
        }

    def close(self) -> None:
        closer = getattr(self._backend, "close", None)
        if callable(closer):
            closer()
