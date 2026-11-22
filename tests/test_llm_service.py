import asyncio
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from api.llm_service import (
    INSUFFICIENT_CONTEXT_TOKEN,
    SYSTEM_PROMPT,
    LLMService,
    build_context_prompt,
    extract_citations,
    parse_llm_output,
)
from config.settings import Settings

CHUNKS = [
    {"file_name": "policy.pdf", "text": "Refunds within 30 days.", "page": 2, "score": 0.8, "doc_id": "d1"},
    {"file_name": "faq.txt", "text": "Shipping takes 2 days.", "score": 0.6, "doc_id": "d2"},
]


def run(coro):
    return asyncio.run(coro)


class FakeGroq:
    """Mimics groq.AsyncGroq().chat.completions.create."""

    def __init__(self, content=None, error=None, finish_reason="stop"):
        self.calls = []
        self._content, self._error, self._finish = content, error, finish_reason
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **params):
        self.calls.append(params)
        if self._error:
            raise self._error
        message = SimpleNamespace(content=self._content)
        return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason=self._finish)])


class FakeGemini:
    def __init__(self, text):
        self.calls = []

        async def generate_content(**kwargs):
            self.calls.append(kwargs)
            return SimpleNamespace(text=text)

        self.aio = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))


def groq_settings(**overrides):
    values = {"llm_provider": "groq", "groq_api_key": "test-key", "groq_model": "openai/gpt-oss-120b"}
    values.update(overrides)
    return Settings(_env_file=None, **values)


# ── Configuration ───────────────────────────────────────────

def test_paid_provider_is_rejected():
    with pytest.raises(ValidationError) as exc:
        Settings(_env_file=None, llm_provider="openai")
    assert "$0" in str(exc.value)


def test_unknown_provider_is_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, llm_provider="something")


def test_defaults_are_free(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    s = Settings(_env_file=None)
    assert s.llm_provider == "groq"
    assert s.storage_backend == "local"
    assert s.cors_origin_list == []


def test_missing_key_reported_without_network():
    service = LLMService(Settings(_env_file=None, llm_provider="groq", groq_api_key=None))
    assert service.check_configuration() == (False, "GROQ_API_KEY is not set")
    answer = run(service.generate_answer("q?", CHUNKS))
    assert answer.status == "llm_error" and "GROQ_API_KEY" in answer.error


# ── Prompt & parsing ────────────────────────────────────────

def test_prompt_numbers_excerpts_and_includes_pages():
    prompt = build_context_prompt("How long for refunds?", CHUNKS)
    assert '<excerpt id="1" source="policy.pdf, page 2">' in prompt
    assert '<excerpt id="2" source="faq.txt">' in prompt
    assert INSUFFICIENT_CONTEXT_TOKEN in prompt
    assert INSUFFICIENT_CONTEXT_TOKEN in SYSTEM_PROMPT


def test_extract_citations():
    assert extract_citations("A [1]. B [2, 3]. C [3][1]. D [9]. E [0]", 3) == [1, 2, 3]


@pytest.mark.parametrize(
    "raw",
    ["INSUFFICIENT_CONTEXT", " insufficient_context. ", "`INSUFFICIENT_CONTEXT`", "INSUFFICIENT_CONTEXT\nsorry", "", None],
)
def test_insufficient_context_detection(raw):
    status, text, cited = parse_llm_output(raw, 3)
    assert status == "insufficient_context" and text == "" and cited == []


def test_answer_parsing_strips_trailing_token():
    status, text, cited = parse_llm_output("Refunds take 30 days [1]. INSUFFICIENT_CONTEXT", 2)
    assert status == "answered" and cited == [1] and "INSUFFICIENT" not in text


# ── Providers ───────────────────────────────────────────────

def test_groq_provider_request_and_citations():
    fake = FakeGroq("Refunds are accepted within 30 days [1]. Shipping takes 2 days [2].")
    service = LLMService(groq_settings(), groq_client=fake)
    answer = run(service.generate_answer("refunds?", CHUNKS))

    assert answer.status == "answered" and answer.cited == [1, 2]
    assert answer.provider == "groq" and answer.model == "openai/gpt-oss-120b"
    params = fake.calls[0]
    assert params["model"] == "openai/gpt-oss-120b"
    assert params["messages"][0] == {"role": "system", "content": SYSTEM_PROMPT}
    assert "Refunds within 30 days." in params["messages"][1]["content"]
    assert params["reasoning_effort"] == "low"
    assert params["max_completion_tokens"] == 1024


def test_reasoning_effort_only_for_reasoning_models():
    fake = FakeGroq("ok [1]")
    run(LLMService(groq_settings(groq_model="llama-3.1-8b-instant"), groq_client=fake).generate_answer("q?", CHUNKS))
    assert "reasoning_effort" not in fake.calls[0]


def test_groq_insufficient_context():
    service = LLMService(groq_settings(), groq_client=FakeGroq(INSUFFICIENT_CONTEXT_TOKEN))
    assert run(service.generate_answer("q?", CHUNKS)).status == "insufficient_context"


def test_groq_failure_is_reported_not_hidden():
    service = LLMService(groq_settings(), groq_client=FakeGroq(error=RuntimeError("429 Too Many Requests")))
    answer = run(service.generate_answer("q?", CHUNKS))
    assert answer.status == "llm_error"
    assert "429" in answer.error


def test_groq_truncated_output_is_an_error():
    service = LLMService(groq_settings(), groq_client=FakeGroq(content="", finish_reason="length"))
    answer = run(service.generate_answer("q?", CHUNKS))
    assert answer.status == "llm_error" and "LLM_MAX_OUTPUT_TOKENS" in answer.error


def test_gemini_provider():
    fake = FakeGemini("Shipping takes 2 days [2].")
    settings = Settings(_env_file=None, llm_provider="gemini", gemini_api_key="k")
    answer = run(LLMService(settings, gemini_client=fake).generate_answer("shipping?", CHUNKS))
    assert answer.status == "answered" and answer.cited == [2]
    call = fake.calls[0]
    assert call["model"] == settings.gemini_model
    assert call["config"].system_instruction == SYSTEM_PROMPT


def test_extractive_provider_needs_no_llm():
    service = LLMService(Settings(_env_file=None, llm_provider="extractive"))
    assert service.check_configuration() == (True, None)
    answer = run(service.generate_answer("q?", CHUNKS))
    assert answer.status == "extractive" and answer.cited == [1, 2]
    assert "[1] Refunds within 30 days." in answer.text


def test_no_context_means_insufficient():
    service = LLMService(groq_settings(), groq_client=FakeGroq("should not be called"))
    assert run(service.generate_answer("q?", [])).status == "insufficient_context"
