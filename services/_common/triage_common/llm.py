from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

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
    provider: str
    base_url: str
    default_model: str
    timeout_seconds: float
    max_retries: int
    api_key: Optional[str] = None

    @classmethod
    def from_env(cls) -> "LLMConfig":
        provider = os.getenv("LLM_PROVIDER", "ollama").lower()
        if provider == "openrouter":
            return cls(
                provider="openrouter",
                base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
                default_model=os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.2-3b-instruct:free"),
                timeout_seconds=float(os.getenv("LLM_TIMEOUT", "120")),
                max_retries=int(os.getenv("LLM_MAX_RETRIES", "3")),
                api_key=os.getenv("OPENROUTER_API_KEY"),
            )
        return cls(
            provider="ollama",
            base_url=os.getenv("OLLAMA_HOST", "http://ollama:11434"),
            default_model=os.getenv("OLLAMA_DEFAULT_MODEL", "llama3"),
            timeout_seconds=float(os.getenv("OLLAMA_TIMEOUT", "120")),
            max_retries=int(os.getenv("OLLAMA_MAX_RETRIES", "3")),
        )


class LLMError(RuntimeError):
    pass


class LLMInvalidJSON(LLMError):
    pass


class LLMClient:
    def __init__(
        self,
        config: LLMConfig | None = None,
        client: Optional[httpx.Client] = None,
        prompts_dir: Path | None = None,
    ) -> None:
        self._config = config or LLMConfig.from_env()
        self._client = client or httpx.Client(timeout=self._config.timeout_seconds)
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
        think: bool = False,
    ) -> str:
        if self._config.provider == "openrouter":
            payload: dict[str, Any] = {
                "model": model or self._config.default_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": (options or {}).get("temperature", 0.1),
            }
            if json_mode:
                payload["response_format"] = {"type": "json_object"}
            if options and "max_tokens" in options:
                payload["max_tokens"] = options["max_tokens"]
            return self._call_openrouter(payload)
        payload = {
            "model": model or self._config.default_model,
            "prompt": prompt,
            "stream": False,
            "think": think,
        }
        if json_mode:
            payload["format"] = "json"
        if options:
            payload["options"] = options
        return self._call_generate(payload)

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
        if self._config.provider == "openrouter":
            response = self._client.get(
                f"{self._config.base_url}/models",
                headers={"Authorization": f"Bearer {self._config.api_key or ''}"},
            )
            response.raise_for_status()
            data = response.json()
            return [m.get("id", "") for m in data.get("data", [])]
        response = self._client.get(f"{self._config.base_url}/api/tags")
        response.raise_for_status()
        data = response.json()
        return [model["name"] for model in data.get("models", [])]

    def close(self) -> None:
        self._client.close()

    def _call_generate(self, payload: dict[str, Any]) -> str:
        attempts = max(1, self._config.max_retries)

        @retry(
            reraise=True,
            stop=stop_after_attempt(attempts),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception_type((httpx.HTTPError,)),
        )
        def _do_call() -> str:
            response = self._client.post(
                f"{self._config.base_url}/api/generate",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            if "response" not in data:
                raise LLMError(f"Respuesta Ollama sin campo 'response': {data}")
            return str(data["response"])

        return _do_call()

    def _call_openrouter(self, payload: dict[str, Any]) -> str:
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
                    "X-Title": "TriageIA",
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
