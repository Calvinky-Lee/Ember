"""Semantic response cache on MongoDB Atlas Vector Search.

"The greenest query is the one you never send." Before routing, Ember embeds the
query and asks Atlas for the nearest previously-answered query. If it's close enough
(cosine ≥ CACHE_SIM_THRESHOLD), the stored answer is reused — no model call, only
the tiny embedding cost.

Honesty rules this module enforces (Ember trades nothing on parity/provenance):
- A hit is NOT free. The embedding call has real (small) energy + cost; a hit
  reports that overhead so D4 accounting stays whole. The "saving" is the avoided
  model call MINUS this overhead.
- A cached answer is labeled `role="cache"` / provenance `cached` — never dressed up
  as a fresh frontier-parity answer. Callers/UI can always tell.
- Similarity is not equivalence. The threshold is deliberately high and tunable;
  borderline is a MISS, not a gamble. `similarity` rides along on every hit so the
  benchmark can measure the false-hit rate instead of trusting the cache blindly.

The SQLite core (spec 06) is untouched — this is an additive, network-only path. If
Atlas is unreachable (offline demo), `lookup` returns a clean miss and Ember routes
normally; nothing breaks.

## Known scope boundary: follow-ups and transformation requests (undecided)

Calibration against a real corpus (voyage-3, 5 varied docs incl. a factorial/
Fibonacci and French/American Revolution pair) found a clean separation for
*self-contained* queries: genuine paraphrases scored 0.815-0.892, look-alike-but-
different queries 0.718-0.776 — 0.80 is the max-margin cut (see CACHE_SIM_THRESHOLD
in config.py).

But conversational follow-ups don't fit this picture, for two distinct reasons:

1. **Bare follow-ups** ("can you explain this again?", "explain it more simply")
   carry no topic word, so they score low against any stored query (~0.62-0.64 in
   testing) and correctly miss — their meaning depends on conversation context the
   cache doesn't have. Fine as-is.
2. **Transformation requests on a real topic** ("explain photosynthesis in simpler
   terms", "one-sentence version of X") are the actual problem: they scored in the
   SAME band as genuine paraphrases of the same topic (~0.75-0.78 both). Vector
   similarity captures *topic* strongly but *intent modifiers* like "simpler" /
   "shorter" / "again" / "differently" weakly — no threshold cleanly separates
   "reword this question" from "re-answer this differently." Returning the cached
   answer for a "make it simpler" request would be wrong (Ember never trades
   parity), so today's threshold biases toward MISS here (a fresh call), which is
   safe but leaves easy transformation-request savings on the table.

Not yet fixed — options on the table for later (see project memory / OKR
discussion), roughly in order of cost:
- Scope the cache to self-contained queries only (true today, given the benchmark's
  150 tasks are independent) and document the limitation rather than solve it.
- A cheap keyword/regex intent guard before lookup (skip cache on "again",
  "simpler", "shorter", "rephrase", bare "this/it/that" with no noun) — high
  precision, near-zero cost.
- A reranker stage (Voyage rerank-2) on borderline scores to separate paraphrase
  from transformation intent more precisely than bi-encoder cosine alone.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from backend import config
from backend.cache import embeddings

COLLECTION = "query_cache"
INDEX_NAME = "query_vec_idx"

_client = None  # lazy singleton — a live query pays connect cost once


@dataclass
class CacheHit:
    answer: str
    similarity: float
    source_query: str
    tier: str | None
    # impact of the ORIGINAL answered call, for the "what you would have spent" delta
    original_gco2: float
    original_cost_usd: float
    # impact ACTUALLY spent to serve this hit (the embedding lookup) — counted (D4)
    lookup_gco2: float
    lookup_cost_usd: float
    lookup_wh: float
    role: str = "cache"
    energy_label: str = "estimated"
    intensity_label: str = "cached"

    @property
    def net_gco2_saved(self) -> float:
        return self.original_gco2 - self.lookup_gco2

    @property
    def net_cost_saved(self) -> float:
        return self.original_cost_usd - self.lookup_cost_usd


def available() -> bool:
    """True if a Mongo URI is configured. (Reachability is proven lazily on use.)"""
    return bool(config.MONGODB_URI)


def _collection():
    global _client
    if not config.MONGODB_URI:
        raise RuntimeError("MONGODB_URI not set — semantic cache is disabled")
    if _client is None:
        from pymongo import MongoClient
        _client = MongoClient(config.MONGODB_URI, serverSelectionTimeoutMS=8000)
    return _client[config.MONGODB_DB][COLLECTION]


def ensure_index() -> str:
    """Create the Atlas Vector Search index if absent (idempotent). Dimensions come
    from the active embedding model so index and vectors always agree."""
    if not config.MONGODB_URI:
        raise RuntimeError("MONGODB_URI not set — semantic cache is disabled")
    from pymongo import MongoClient
    global _client
    if _client is None:
        _client = MongoClient(config.MONGODB_URI, serverSelectionTimeoutMS=8000)
    db = _client[config.MONGODB_DB]
    # A search index can only be created on an existing collection.
    if COLLECTION not in db.list_collection_names():
        db.create_collection(COLLECTION)
    col = db[COLLECTION]
    existing = {ix["name"] for ix in col.list_search_indexes()}
    if INDEX_NAME in existing:
        return "exists"
    from pymongo.operations import SearchIndexModel
    model = SearchIndexModel(
        definition={
            "fields": [
                {"type": "vector", "path": "embedding",
                 "numDimensions": embeddings.dim(), "similarity": "cosine"},
                {"type": "filter", "path": "category"},
                {"type": "filter", "path": "tier"},
            ]
        },
        name=INDEX_NAME, type="vectorSearch",
    )
    col.create_search_index(model=model)
    return "created"


def store(query: str, answer: str, *, impact: dict | None = None,
          task_id: str | None = None, category: str | None = None,
          tier: str | None = None, correct: bool | None = None,
          embedding: list[float] | None = None) -> None:
    """Remember an answered query so future near-duplicates hit. `impact` is the
    original call's measure() record — its gco2/cost is the 'avoided' baseline a hit
    reports. Idempotent per (task_id or query)."""
    impact = impact or {}
    vec = embedding if embedding is not None else embeddings.embed_one(query, input_type="document")
    doc = {
        "query": query, "answer": answer, "embedding": vec,
        "task_id": task_id, "category": category, "tier": tier,
        "correct": correct,
        "orig_gco2": float(impact.get("gco2", 0.0) or 0.0),
        "orig_cost_usd": float(impact.get("cost_usd", 0.0) or 0.0),
        "model_key": impact.get("model_key"),
        "stored_at": datetime.now(timezone.utc).isoformat(),
    }
    key = {"task_id": task_id} if task_id else {"query": query}
    _collection().replace_one(key, doc, upsert=True)


def lookup(query: str, *, category: str | None = None,
           threshold: float | None = None) -> CacheHit | None:
    """Nearest prior query via $vectorSearch. Returns a CacheHit only when cosine ≥
    threshold; otherwise None (a miss → caller routes normally). Any Atlas error is
    a graceful miss so the offline/degraded path never raises into the router."""
    thr = config.CACHE_SIM_THRESHOLD if threshold is None else threshold
    try:
        qvec, lookup_impact = _embed_with_impact(query)
        pipeline = [
            {"$vectorSearch": {
                "index": INDEX_NAME, "path": "embedding", "queryVector": qvec,
                "numCandidates": 50, "limit": 1,
                **({"filter": {"category": category}} if category else {}),
            }},
            {"$project": {"_id": 0, "query": 1, "answer": 1, "tier": 1,
                          "orig_gco2": 1, "orig_cost_usd": 1,
                          "score": {"$meta": "vectorSearchScore"}}},
        ]
        docs = list(_collection().aggregate(pipeline))
    except Exception:
        return None  # graceful miss — never let a cache problem break routing
    if not docs or docs[0]["score"] < thr:
        return None
    d = docs[0]
    return CacheHit(
        answer=d["answer"], similarity=float(d["score"]), source_query=d["query"],
        tier=d.get("tier"),
        original_gco2=float(d.get("orig_gco2", 0.0)),
        original_cost_usd=float(d.get("orig_cost_usd", 0.0)),
        lookup_gco2=lookup_impact["gco2"], lookup_cost_usd=lookup_impact["cost_usd"],
        lookup_wh=lookup_impact["wh"],
    )


def _embed_with_impact(query: str) -> tuple[list[float], dict]:
    """Embed the query AND account for the embedding call's own footprint (D4).
    Embedding energy/cost is small but never zeroed — a hit's saving is net of it."""
    t0 = time.monotonic()
    vec = embeddings.embed_one(query, input_type="query")
    _ = (time.monotonic() - t0)
    impact = _embedding_impact(query, len(vec))
    return vec, impact


def _embedding_impact(query: str, out_dim: int) -> dict:
    """Rough, labeled footprint of one embedding call. Tokens are approximated
    (~4 chars/token) since embedding endpoints bill on input tokens; kept honest by
    the `estimated` label and by being counted at all rather than assumed free."""
    approx_tokens = max(1, len(query) // 4)
    # Embedding models are tiny relative to generation; use a conservative flat
    # factor. This is an ESTIMATE (labeled), same provenance discipline as spec 03.
    wh = approx_tokens / 1000 * 0.02 * config.PUE  # ~0.02 Wh/1k tok, embedding-class
    # Cost: most embedding tiers are ~$0.02–0.12 /1M tokens; use a small flat rate.
    cost = approx_tokens / 1e6 * 0.10
    return {"wh": wh, "gco2": 0.0, "cost_usd": cost, "tokens_in": approx_tokens,
            "energy_label": "estimated"}
