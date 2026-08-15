"""The embedding model, reached the same way the classifier's is — and absent as ordinarily.

D88, 2026-08-15. Retrieval needs a second model beside the classifier, and it lives in the
same Ollama service behind the same compose profile, so **absence is the ordinary case here
too**: `available()` answers without raising, and a caller records a skipped pass rather
than a broken one. That is `model.py`'s argument, and this module deliberately repeats its
shape instead of inventing a second one — one service, one host variable, one habit.

**The dimension is checked on every call and a mismatch raises.** This is the failure the
example table cannot see: a different embedding model returns vectors that are perfectly
well-formed and mean something else, and a crib built from mixed vectors would order
neighbours by nothing. `embed_model` is stored beside every row for the same reason; this
check is the half that fires before anything is written.

`EmbedUnavailable` is separated from every other error on purpose, and it is the same
distinction `ingest_run` draws between *no change* and *failed*: the service being down is
a wait, a 1024 that came back 768 is not.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

EMBED_MODEL = os.environ.get("UPTO_EMBED_MODEL", "bge-m3")
HOST = os.environ.get("UPTO_MODEL_HOST", "ollama:11434")
TIMEOUT_S = int(os.environ.get("UPTO_EMBED_TIMEOUT", "180"))

# bge-m3's output width. Pinned here and in 0018's column: the loader refuses before writing,
# PostgreSQL refuses after, and neither is trusted to be the only one.
DIMENSION = 1024


class EmbedUnavailable(Exception):
    """The embedding service cannot answer now and will be able to later — a wait, not a bug."""


def available() -> bool:
    """Is the service up and holding the embedding model? Never raises — absence is ordinary."""
    try:
        with urllib.request.urlopen(f"http://{HOST}/api/tags", timeout=5) as response:
            tags = json.load(response)
    except (urllib.error.URLError, OSError, ValueError):
        return False
    prefix = EMBED_MODEL.split(":")[0]
    return any(entry.get("name", "").startswith(prefix) for entry in tags.get("models", []))


def embed(texts: list[str]) -> list[list[float]]:
    """One batch of strings in, one vector each out, in the order they were given.

    Order is load-bearing and unstated by the API's docs, so the count is asserted: a reply
    holding fewer vectors than it was asked about would silently pair a name with its
    neighbour's embedding, and every crib after it would be wrong in a way no test of the
    SQL could catch.
    """
    if not texts:
        return []
    body = json.dumps({"model": EMBED_MODEL, "input": texts}).encode()
    request = urllib.request.Request(
        f"http://{HOST}/api/embed", data=body, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            reply = json.load(response)
    except (urllib.error.URLError, OSError, ValueError) as error:
        raise EmbedUnavailable(f"{EMBED_MODEL} at {HOST} did not answer: {error}") from None
    vectors = reply.get("embeddings")
    if not isinstance(vectors, list) or len(vectors) != len(texts):
        raise ValueError(
            f"asked {EMBED_MODEL} for {len(texts)} vectors and got "
            f"{len(vectors) if isinstance(vectors, list) else type(vectors).__name__} back"
        )
    for vector in vectors:
        if len(vector) != DIMENSION:
            raise ValueError(
                f"{EMBED_MODEL} returned a {len(vector)}-dimension vector where "
                f"{DIMENSION} was expected — this is a different embedding model, and mixing "
                "two of them in the example table would order neighbours by nothing"
            )
    return vectors


def as_literal(vector: list[float]) -> str:
    """A vector as pgvector's own text form, `'[1,2,3]'`, for a `::vector` cast in SQL.

    The whole of what the pgvector Python package would buy for this project is this one
    function, so the dependency is not taken. `repr` of a float round-trips exactly in
    CPython, which is what keeps the stored vector the vector the model returned.
    """
    return "[" + ",".join(repr(float(value)) for value in vector) + "]"
