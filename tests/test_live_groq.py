"""
Optional live test against the real Groq API (free plan).

Skipped unless you opt in:
    RUN_LIVE_LLM_TESTS=1 GROQ_API_KEY=... pytest -m live

It makes exactly two small requests. On the free plan, exceeding limits
returns HTTP 429 rather than a charge — but check your Groq plan first.
"""

import asyncio
import os

import pytest

from api.llm_service import LLMService
from config.settings import Settings

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.environ.get("RUN_LIVE_LLM_TESTS") != "1" or not os.environ.get("GROQ_API_KEY"),
        reason="live LLM test: set RUN_LIVE_LLM_TESTS=1 and GROQ_API_KEY to run",
    ),
]

CHUNKS = [{"file_name": "policy.txt", "text": "Customers may request a full refund within 30 days of purchase."}]


def _service():
    settings = Settings(
        _env_file=None,
        llm_provider="groq",
        groq_api_key=os.environ["GROQ_API_KEY"],
        groq_model=os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b"),
    )
    return LLMService(settings)


def test_groq_answers_with_citation():
    answer = asyncio.run(_service().generate_answer("How long is the refund window?", CHUNKS))
    assert answer.status == "answered", answer.error
    assert "30" in answer.text and 1 in answer.cited


def test_groq_reports_insufficient_context():
    answer = asyncio.run(_service().generate_answer("What is the CEO's favourite colour?", CHUNKS))
    assert answer.status == "insufficient_context", (answer.status, answer.text, answer.error)
