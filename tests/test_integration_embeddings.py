"""
Integration tests with the real FastEmbed model (BAAI/bge-small-en-v1.5).

The model (~70 MB) is downloaded from Hugging Face on first run and cached.
No API keys and no paid services are involved.
"""

import numpy as np
import pytest

from config.settings import Settings, get_settings
from embedding.embedder import EmbeddingService
from helpers import POLICY_TEXT

pytestmark = pytest.mark.integration

# The shipped default (not whatever the test environment overrides).
DEFAULT_THRESHOLD = Settings.model_fields["similarity_threshold"].default

PASSAGES = {
    "refund": "REFUND POLICY\nCustomers may request a full refund within 30 days of purchase if they are "
              "unsatisfied.\n\nRefunds are returned to the original payment method within 5 business days.",
    "shipping": "SHIPPING\nOrders ship within 2 business days. Express shipping is available for an extra fee.",
    "security": "SECURITY\nAll customer data is encrypted at rest using AES-256 and in transit using TLS 1.3.",
    "vacation": "Employees accrue 20 days of paid vacation per year. Unused vacation can be carried over up to 5 days.",
    "revenue": "The quarterly report shows revenue grew 12% to $4.2M, driven by enterprise subscriptions.",
}

RELATED = {
    "How long do I have to get my money back?": "refund",
    "How many days do I have to ask for a refund?": "refund",
    "What is the refund policy?": "refund",
    "Where does my refund go?": "refund",
    "When will my order be delivered?": "shipping",
    "Can I get express delivery?": "shipping",
    "Is my data encrypted?": "security",
    "What encryption is used for data in transit?": "security",
    "How many vacation days do employees get?": "vacation",
    "How much did revenue grow last quarter?": "revenue",
}
UNRELATED = [
    "Who won the football world cup in 2018?",
    "What is the capital of France?",
    "Give me a recipe for chocolate cake.",
    "How do I change a car tire?",
    "What is the boiling point of water?",
    "Tell me a joke about cats.",
    "Who painted the Mona Lisa?",
    "How tall is Mount Everest?",
    "What's the weather tomorrow?",
    "Explain quantum entanglement.",
]


@pytest.fixture(scope="module")
def embedder():
    service = EmbeddingService(model_name="BAAI/bge-small-en-v1.5")
    service.embed_query("warm up")
    return service


def _cos(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def test_bge_query_instruction_is_applied(embedder):
    assert embedder.query_prefix.startswith("Represent this sentence")


def test_dimensions_match_configuration(embedder):
    vectors = embedder.embed_passages(list(PASSAGES.values()))
    assert vectors.shape == (len(PASSAGES), Settings(_env_file=None).embedding_dimension)
    assert vectors.dtype == np.float32
    assert embedder.embed_query("hello").shape == (384,)


def test_retrieval_picks_the_right_passage(embedder):
    keys = list(PASSAGES)
    vectors = embedder.embed_passages([PASSAGES[k] for k in keys])
    for question, expected in RELATED.items():
        q = embedder.embed_query(question)
        scores = [_cos(q, v) for v in vectors]
        assert keys[int(np.argmax(scores))] == expected, (question, scores)


def test_default_threshold_separates_related_from_unrelated(embedder):
    """Pins SIMILARITY_THRESHOLD: related questions must clear it, off-topic ones must not."""
    threshold = DEFAULT_THRESHOLD
    vectors = embedder.embed_passages(list(PASSAGES.values()))
    related_best = [max(_cos(embedder.embed_query(q), v) for v in vectors) for q in RELATED]
    unrelated_best = [max(_cos(embedder.embed_query(q), v) for v in vectors) for q in UNRELATED]
    print(f"\nrelated best scores:   {[round(s, 3) for s in related_best]}")
    print(f"unrelated best scores: {[round(s, 3) for s in unrelated_best]}")
    print(f"threshold:             {threshold}")
    assert min(related_best) >= threshold
    assert max(unrelated_best) < threshold


def test_end_to_end_with_real_embeddings(make_client, embedder, env):
    env.setenv("SIMILARITY_THRESHOLD", str(DEFAULT_THRESHOLD))
    get_settings.cache_clear()
    client, _ = make_client(embedder=embedder)
    r = client.post("/api/v1/upload", files={"file": ("policy.txt", POLICY_TEXT.encode(), "text/plain")})
    assert r.status_code == 200, r.text

    related = client.post("/api/v1/ask", json={"query": "How many days do I have to ask for a refund?"}).json()
    assert related["answer_status"] == "extractive"
    assert "30 days" in related["citations"][0]["snippet"]

    unrelated = client.post("/api/v1/ask", json={"query": "What is the capital of France?"}).json()
    assert unrelated["answer_status"] == "insufficient_context"
