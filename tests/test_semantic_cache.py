"""Semantic cache (Atlas Vector Search) — the 'greenest query is the one you never
send' path. These pin the HONESTY rules, not the happy path:
- similarity is not equivalence → a below-threshold nearest neighbor is a MISS, and
  a cache problem degrades to a miss, never an exception into the router;
- a hit is NOT free → the embedding lookup's footprint is counted (D4), and the
  reported saving is net of it;
- a hit is labeled `cached`, never passed off as a fresh frontier-parity answer.
No network: embeddings and the Atlas collection are both faked.
"""
import pytest

from backend import config
from backend.cache import embeddings, semantic


class FakeCol:
    """Stands in for the Atlas collection — only .aggregate is exercised by lookup."""
    def __init__(self, docs=None, raises=False):
        self._docs = docs or []
        self._raises = raises

    def aggregate(self, _pipeline):
        if self._raises:
            raise RuntimeError("atlas unreachable")
        return iter(self._docs)


@pytest.fixture(autouse=True)
def no_real_embeddings(monkeypatch):
    """Every lookup embeds the query — fake it so tests never hit Voyage/Gemini."""
    monkeypatch.setattr(embeddings, "embed_one", lambda text, **kw: [0.1, 0.2, 0.3])


def _hit_doc(score):
    return {"query": "What is the capital of France?", "answer": "Paris.",
            "tier": "hard", "orig_gco2": 0.30, "orig_cost_usd": 0.02, "score": score}


def test_hit_above_threshold_returns_cached_answer(monkeypatch):
    """A near-duplicate at score ≥ threshold reuses the stored answer, labeled cached."""
    monkeypatch.setattr(semantic, "_collection", lambda: FakeCol([_hit_doc(0.814)]))
    hit = semantic.lookup("France's capital city?", threshold=0.78)
    assert hit is not None
    assert hit.answer == "Paris."
    assert hit.role == "cache"
    assert hit.intensity_label == "cached"
    assert hit.similarity == pytest.approx(0.814)


def test_below_threshold_is_a_miss(monkeypatch):
    """A similar-but-different question (capital of Germany ~0.718) must NOT hit —
    this is the parity guardrail: similarity is not equivalence."""
    monkeypatch.setattr(semantic, "_collection", lambda: FakeCol([_hit_doc(0.7176)]))
    assert semantic.lookup("What is the capital of Germany?", threshold=0.78) is None


def test_empty_index_is_a_miss(monkeypatch):
    monkeypatch.setattr(semantic, "_collection", lambda: FakeCol([]))
    assert semantic.lookup("anything", threshold=0.78) is None


def test_atlas_error_degrades_to_miss_never_raises(monkeypatch):
    """If Atlas is unreachable (offline demo, bad creds), lookup returns a clean miss
    so the router just proceeds — a cache problem must never break routing."""
    monkeypatch.setattr(semantic, "_collection", lambda: FakeCol(raises=True))
    assert semantic.lookup("anything", threshold=0.78) is None


def test_hit_saving_is_net_of_the_lookup_footprint(monkeypatch):
    """D4: the embedding call is counted, so the reported saving is original impact
    MINUS the lookup's own (small, nonzero) cost/carbon — never the gross figure."""
    monkeypatch.setattr(semantic, "_collection", lambda: FakeCol([_hit_doc(0.90)]))
    hit = semantic.lookup("France's capital city?", threshold=0.78)
    assert hit.lookup_cost_usd > 0          # a hit is NOT free
    assert hit.net_cost_saved == pytest.approx(hit.original_cost_usd - hit.lookup_cost_usd)
    assert hit.net_gco2_saved == pytest.approx(hit.original_gco2 - hit.lookup_gco2)
    assert hit.net_cost_saved < hit.original_cost_usd


def test_embedding_impact_is_labeled_estimate(monkeypatch):
    """The lookup footprint carries the same 'estimated' provenance as spec 03 —
    tokens approximated, never presented as measured."""
    imp = semantic._embedding_impact("a short query", 1024)
    assert imp["energy_label"] == "estimated"
    assert imp["cost_usd"] > 0 and imp["wh"] > 0


def test_bad_embedding_model_is_loud():
    """Never guess silently: a malformed EMBEDDING_MODEL raises, not defaults."""
    import backend.config as cfg
    old = cfg.EMBEDDING_MODEL
    cfg.EMBEDDING_MODEL = "voyage3-no-colon"
    try:
        with pytest.raises(embeddings.EmbeddingError):
            embeddings._provider_model()
    finally:
        cfg.EMBEDDING_MODEL = old


def test_available_reflects_configured_uri(monkeypatch):
    monkeypatch.setattr(config, "MONGODB_URI", "")
    assert semantic.available() is False
    monkeypatch.setattr(config, "MONGODB_URI", "mongodb+srv://x")
    assert semantic.available() is True
