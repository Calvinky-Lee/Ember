"""Text → vector, provider-abstracted (config.EMBEDDING_MODEL = 'provider:model').

Voyage is the default — MongoDB owns Voyage, so it's the native embedding layer for
Atlas Vector Search. Gemini is offered as a zero-new-key fallback (reuses the judge
key). The rest of the cache neither knows nor cares which one produced the vector,
only that the same model is used for both indexing and querying (mismatched models =
meaningless cosine distances)."""
import os

from backend import config


class EmbeddingError(RuntimeError):
    pass


def _provider_model() -> tuple[str, str]:
    provider, _, model = config.EMBEDDING_MODEL.partition(":")
    if not model:
        raise EmbeddingError(
            f"EMBEDDING_MODEL must be 'provider:model', got {config.EMBEDDING_MODEL!r}"
        )
    return provider, model


def embed(texts: list[str], *, input_type: str | None = None) -> list[list[float]]:
    """Embed a batch. `input_type` ('query'|'document') lets asymmetric models place
    a question and the passages it should match into the same neighborhood — Voyage
    supports it; ignored where unsupported."""
    provider, model = _provider_model()
    if not texts:
        return []
    if provider == "voyage":
        return _embed_voyage(texts, model, input_type)
    if provider == "gemini":
        return _embed_gemini(texts, model, input_type)
    raise EmbeddingError(f"Unknown embedding provider {provider!r} (expected voyage|gemini)")


def embed_one(text: str, *, input_type: str | None = None) -> list[float]:
    return embed([text], input_type=input_type)[0]


def dim() -> int:
    """Vector dimensionality for the current model — the Atlas index must declare it."""
    provider, model = _provider_model()
    known = {
        "voyage:voyage-3": 1024, "voyage:voyage-3-lite": 512,
        "voyage:voyage-3-large": 1024,
        "gemini:text-embedding-004": 768, "gemini:gemini-embedding-001": 3072,
    }
    if config.EMBEDDING_MODEL in known:
        return known[config.EMBEDDING_MODEL]
    # Unknown model: probe once rather than guess (never silently wrong).
    return len(embed_one("probe"))


def _embed_voyage(texts: list[str], model: str, input_type: str | None) -> list[list[float]]:
    import voyageai
    key = config.VOYAGE_API_KEY or os.getenv("VOYAGE_API_KEY", "")
    if not key:
        raise EmbeddingError("VOYAGE_API_KEY not set — get one free at voyageai.com")
    client = voyageai.Client(api_key=key)
    return client.embed(texts, model=model, input_type=input_type).embeddings


def _embed_gemini(texts: list[str], model: str, input_type: str | None) -> list[list[float]]:
    import httpx
    key = os.getenv("GEMINI_API_KEY", "")
    if not key:
        raise EmbeddingError("GEMINI_API_KEY not set — needed for gemini embeddings")
    task = {"query": "RETRIEVAL_QUERY", "document": "RETRIEVAL_DOCUMENT"}.get(input_type or "")
    out = []
    for t in texts:  # Gemini's embed endpoint is one text per call
        body = {"model": f"models/{model}", "content": {"parts": [{"text": t}]}}
        if task:
            body["taskType"] = task
        resp = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:embedContent",
            headers={"x-goog-api-key": key}, json=body, timeout=30.0,
        )
        if resp.status_code != 200:
            raise EmbeddingError(f"gemini embed HTTP {resp.status_code}: {resp.text[:200]}")
        out.append(resp.json()["embedding"]["values"])
    return out
