from __future__ import annotations

import json
from unittest.mock import MagicMock

import httpx
import pytest

from triage_common.llm import (
    AzureFoundryBackend,
    LLMClient,
    LLMConfig,
    LLMError,
    LLMInvalidJSON,
)


@pytest.fixture
def config(tmp_path):
    return LLMConfig(
        base_url="https://openrouter.ai/api/v1",
        default_model="meta-llama/llama-3.2-3b-instruct:free",
        timeout_seconds=10.0,
        max_retries=2,
        api_key="test-key",
    )


@pytest.fixture
def fake_client():
    client = MagicMock(spec=httpx.Client)
    return client


@pytest.fixture
def llm(config, fake_client, prompts_path):
    return LLMClient(config=config, client=fake_client, prompts_dir=prompts_path)


def _fake_response(json_payload, status_code=200):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_payload
    if status_code >= 400:
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "boom", request=MagicMock(), response=MagicMock(status_code=status_code)
        )
    else:
        response.raise_for_status.return_value = None
    return response


def _chat_response(content):
    return _fake_response({"choices": [{"message": {"content": content}}]})


class TestGenerate:
    def test_returns_message_content(self, llm, fake_client):
        fake_client.post.return_value = _chat_response("hola")
        out = llm.generate("test prompt")
        assert out == "hola"
        kwargs = fake_client.post.call_args.kwargs
        assert kwargs["json"]["model"] == "meta-llama/llama-3.2-3b-instruct:free"
        assert kwargs["json"]["messages"] == [{"role": "user", "content": "test prompt"}]
        assert "response_format" not in kwargs["json"]
        assert kwargs["headers"]["Authorization"] == "Bearer test-key"

    def test_sets_json_response_format(self, llm, fake_client):
        fake_client.post.return_value = _chat_response("{}")
        llm.generate("p", json_mode=True)
        kwargs = fake_client.post.call_args.kwargs
        assert kwargs["json"]["response_format"] == {"type": "json_object"}

    def test_uses_override_model(self, llm, fake_client):
        fake_client.post.return_value = _chat_response("ok")
        llm.generate("p", model="openai/gpt-oss-120b:free")
        assert fake_client.post.call_args.kwargs["json"]["model"] == "openai/gpt-oss-120b:free"

    def test_raises_on_missing_choices(self, llm, fake_client):
        fake_client.post.return_value = _fake_response({"choices": []})
        with pytest.raises(LLMError):
            llm.generate("p")

    def test_raises_without_api_key(self, fake_client, prompts_path):
        config = LLMConfig(
            base_url="https://openrouter.ai/api/v1",
            default_model="m",
            timeout_seconds=10.0,
            max_retries=2,
            api_key=None,
        )
        client = LLMClient(config=config, client=fake_client, prompts_dir=prompts_path)
        with pytest.raises(LLMError):
            client.generate("p")


class TestRetries:
    def test_retries_on_http_error_then_succeeds(self, llm, fake_client):
        fake_client.post.side_effect = [
            httpx.ConnectError("temporarily unavailable"),
            _chat_response("ok-after-retry"),
        ]
        out = llm.generate("p")
        assert out == "ok-after-retry"
        assert fake_client.post.call_count == 2

    def test_gives_up_after_max_retries(self, llm, fake_client):
        fake_client.post.side_effect = httpx.ConnectError("nope")
        with pytest.raises(httpx.ConnectError):
            llm.generate("p")
        assert fake_client.post.call_count == 2


class TestGenerateJson:
    def test_parses_json_response(self, llm, fake_client):
        fake_client.post.return_value = _chat_response(
            json.dumps({"entidades": ["disnea", "sincope"]})
        )
        data = llm.generate_json("p")
        assert data == {"entidades": ["disnea", "sincope"]}

    def test_raises_on_invalid_json(self, llm, fake_client):
        fake_client.post.return_value = _chat_response("not json")
        with pytest.raises(LLMInvalidJSON):
            llm.generate_json("p")


class TestRender:
    def test_renders_extract_template(self, llm):
        prompt = llm.render("extract_entities.j2", texto="Me ahogo y tengo pitos")
        assert "Me ahogo y tengo pitos" in prompt
        assert '{"entidades"' in prompt or "entidades" in prompt

    def test_renders_normalize_with_loop(self, llm):
        prompt = llm.render(
            "normalize_entities.j2",
            terminos_permitidos=["disnea", "sibilancias", "edema"],
            sintomas_json='["me ahogo"]',
        )
        assert "- disnea" in prompt
        assert "- sibilancias" in prompt
        assert '"me ahogo"' in prompt

    def test_renders_label(self, llm):
        prompt = llm.render(
            "label_triage.j2",
            resumen_es="Dolor toracico opresivo",
            entidades_json='["dolor_toracico_opresivo"]',
        )
        assert "Dolor toracico opresivo" in prompt
        assert "dolor_toracico_opresivo" in prompt

    def test_strict_undefined_raises(self, llm):
        from jinja2 import UndefinedError

        with pytest.raises(UndefinedError):
            llm.render("extract_entities.j2")


class TestRenderAndGenerate:
    def test_combines_render_and_call(self, llm, fake_client):
        fake_client.post.return_value = _chat_response(
            json.dumps({"entidades": ["disnea"]})
        )
        result = llm.render_and_generate_json(
            "extract_entities.j2",
            context={"texto": "me ahogo"},
        )
        assert result == {"entidades": ["disnea"]}
        messages = fake_client.post.call_args.kwargs["json"]["messages"]
        assert "me ahogo" in messages[0]["content"]


class TestListModels:
    def test_parses_models_response(self, llm, fake_client):
        fake_client.get.return_value = _fake_response(
            {"data": [{"id": "model-a"}, {"id": "model-b"}]}
        )
        assert llm.list_models() == ["model-a", "model-b"]


class TestBackendSelection:
    def test_from_env_defaults_to_local(self, monkeypatch):
        monkeypatch.delenv("LLM_BACKEND", raising=False)
        assert LLMConfig.from_env().backend == "local"

    def test_from_env_reads_backend(self, monkeypatch):
        monkeypatch.setenv("LLM_BACKEND", "azure")
        assert LLMConfig.from_env().backend == "azure"

    def test_default_backend_calls_openrouter(self, config, fake_client, prompts_path):
        fake_client.post.return_value = _chat_response("ok")
        client = LLMClient(config=config, client=fake_client, prompts_dir=prompts_path)
        assert client.generate("p") == "ok"
        assert fake_client.post.called

    def test_unknown_backend_raises(self, fake_client, prompts_path):
        cfg = LLMConfig(
            base_url="https://x",
            default_model="m",
            timeout_seconds=10.0,
            max_retries=1,
            api_key="k",
            backend="marte",
        )
        with pytest.raises(LLMError):
            LLMClient(config=cfg, client=fake_client, prompts_dir=prompts_path)

    def test_azure_backend_requires_endpoint(self, prompts_path):
        cfg = LLMConfig(
            base_url="https://x",
            default_model="m",
            timeout_seconds=10.0,
            max_retries=1,
            api_key="k",
            backend="azure",
        )
        with pytest.raises(LLMError):
            LLMClient(config=cfg, prompts_dir=prompts_path)

    def test_injected_backend_delegates(self, config, prompts_path):
        backend = MagicMock()
        backend.chat.return_value = "from-backend"
        client = LLMClient(config=config, prompts_dir=prompts_path, backend=backend)
        assert client.generate("hola") == "from-backend"
        backend.chat.assert_called_once()


def _azure_response(content):
    response = MagicMock()
    message = MagicMock()
    message.content = content
    choice = MagicMock()
    choice.message = message
    response.choices = [choice]
    return response


def _azure_config(**overrides):
    base = dict(
        base_url="x",
        default_model="m",
        timeout_seconds=10.0,
        max_retries=1,
        api_key=None,
        backend="azure",
        azure_endpoint="https://foo.example",
        azure_deployment="gpt-4o-mini-dep",
    )
    base.update(overrides)
    return LLMConfig(**base)


class TestAzureFoundryBackend:
    def test_returns_message_content(self, prompts_path):
        fake = MagicMock()
        fake.chat.completions.create.return_value = _azure_response("hola-azure")
        client = LLMClient(config=_azure_config(), client=fake, prompts_dir=prompts_path)
        assert client.generate("p") == "hola-azure"
        kwargs = fake.chat.completions.create.call_args.kwargs
        assert kwargs["model"] == "gpt-4o-mini-dep"
        assert kwargs["messages"] == [{"role": "user", "content": "p"}]

    def test_passes_json_response_format(self, prompts_path):
        fake = MagicMock()
        fake.chat.completions.create.return_value = _azure_response("{}")
        client = LLMClient(config=_azure_config(), client=fake, prompts_dir=prompts_path)
        client.generate("p", json_mode=True)
        assert fake.chat.completions.create.call_args.kwargs["response_format"] == {"type": "json_object"}

    def test_raises_on_empty_choices(self, prompts_path):
        fake = MagicMock()
        empty = MagicMock()
        empty.choices = []
        fake.chat.completions.create.return_value = empty
        client = LLMClient(config=_azure_config(), client=fake, prompts_dir=prompts_path)
        with pytest.raises(LLMError):
            client.generate("p")

    def test_backend_constructed_directly(self, prompts_path):
        fake = MagicMock()
        fake.chat.completions.create.return_value = _azure_response("ok")
        backend = AzureFoundryBackend(_azure_config(), client=fake)
        out = backend.chat(
            {"model": "ignored", "messages": [{"role": "user", "content": "x"}]}
        )
        assert out == "ok"


class TestProvenance:
    def test_local_provenance(self, config, fake_client, prompts_path):
        client = LLMClient(config=config, client=fake_client, prompts_dir=prompts_path)
        assert client.provenance("label_triage.j2") == {
            "backend": "local",
            "model": "meta-llama/llama-3.2-3b-instruct:free",
            "prompt": "label_triage.j2",
        }

    def test_azure_provenance(self, prompts_path):
        client = LLMClient(
            config=_azure_config(), client=MagicMock(), prompts_dir=prompts_path
        )
        prov = client.provenance()
        assert prov["backend"] == "azure"
        assert prov["model"] == "gpt-4o-mini-dep"
        assert prov["prompt"] is None
