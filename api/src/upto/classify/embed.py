"""The embedding model, reached the same way the classifier's is — and absent as ordinarily.

D88, 2026-08-15. Retrieval needs a second model beside the classifier, and it lives in the
same Ollama service behind the same compose profile, so **absence is the ordinary case here
too**: `available()` answers without raising, and a caller records a skipped pass rather
than a broken one. That is `model.py`'s argument, and this module deliberately repeats its
shape instead of inventing a second one — one service, one host variable, one habit.

**Which embedder is now an argument, not a constant.** D88's amendment, owner-ruled
2026-08-17: the embedder is a measured variable, so `EMBED_MODELS` pins one string per short
CLI key exactly as `run_round.LOCAL_MODELS` pins the generators, and every function here
takes an explicit model with `EMBED_MODEL` as the default. The store keys on the model string
(0019), so the string that reached the service and the string written beside the row have to
be the same one — which is why it is passed rather than read from a global at two depths.

**The dimension is checked on every call and a mismatch raises.** This is the failure the
example table cannot see: a different embedding model returns vectors that are perfectly
well-formed and mean something else, and a crib built from mixed vectors would order
neighbours by nothing. `embed_model` is stored beside every row for the same reason; this
check is the half that fires before anything is written.

The check has two halves, and the weaker one is the one that always runs. **Every vector in
one reply must share a width** — that holds for any model, named here or not, so an unknown
embedder is measured rather than refused. **A model in `EXPECTED_DIMENSIONS` must also return
the width recorded there**; all three of D88's candidates measured 1024 on 2026-08-17, and
that number is what 0019's column pins. A model absent from the map is allowed through on the
first half alone — blocking it would make trying a fourth embedder a code change before it is
a measurement, which is backwards.

`EmbedUnavailable` is separated from every other error on purpose, and it is the same
distinction `ingest_run` draws between *no change* and *failed*: the service being down is
a wait, a 1024 that came back 768 is not.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from upto.classify.transport import fetch

# D88's embedder slate, owner-ruled 2026-08-17: one CLI key per model, the string pinned
# here and written into every row and every round file. Same shape and same reason as
# `run_round.LOCAL_MODELS` — a round is a measurement of one named model, and a key that
# resolved differently on two days would produce two scores belonging to neither.
EMBED_MODELS = {
    "bge": "bge-m3",
    "qwen3e": "qwen3-embedding:0.6b",
    "arctic": "snowflake-arctic-embed2",
}

# The default key, and it is `bge` because the three scored v5-rag rounds were embedded by
# bge-m3 — they are the matrix's first column, and a default that moved would orphan them.
DEFAULT_EMBED_KEY = "bge"

EMBED_MODEL = os.environ.get("UPTO_EMBED_MODEL", EMBED_MODELS[DEFAULT_EMBED_KEY])
HOST = os.environ.get("UPTO_MODEL_HOST", "ollama:11434")
TIMEOUT_S = int(os.environ.get("UPTO_EMBED_TIMEOUT", "180"))

# Measured widths, 2026-08-17, one `/api/embed` call each. Pinned here and in 0019's column:
# the loader refuses before writing, PostgreSQL refuses after, and neither is trusted to be
# the only one. A model absent from this map is not refused — see the module docstring.
EXPECTED_DIMENSIONS = {
    "bge-m3": 1024,
    "qwen3-embedding:0.6b": 1024,
    "snowflake-arctic-embed2": 1024,
}

# The width 0019's column holds. Every candidate measures this today, so it is still one
# number rather than a per-model column type.
DIMENSION = 1024


class EmbedUnavailable(Exception):
    """The embedding service cannot answer now and will be able to later — a wait, not a bug."""


def resolve(key: str) -> str:
    """A short CLI key to its pinned model string. Raises KeyError for an unknown key.

    Callers turn that into their own usage error, because what a bad key costs depends on
    where it was typed — a round refuses at argv, a load refuses before it embeds anything.
    """
    return EMBED_MODELS[key]


def available(model: str | None = None) -> bool:
    """Is the service up and holding this embedding model? Never raises — absence is ordinary."""
    model = model or EMBED_MODEL
    try:
        with urllib.request.urlopen(f"http://{HOST}/api/tags", timeout=5) as response:
            tags = json.load(response)
    except (urllib.error.URLError, OSError, ValueError):
        return False
    prefix = model.split(":")[0]
    return any(entry.get("name", "").startswith(prefix) for entry in tags.get("models", []))


def embed(texts: list[str], model: str | None = None) -> list[list[float]]:
    """One batch of strings in, one vector each out, in the order they were given.

    Order is load-bearing and unstated by the API's docs, so the count is asserted: a reply
    holding fewer vectors than it was asked about would silently pair a name with its
    neighbour's embedding, and every crib after it would be wrong in a way no test of the
    SQL could catch. **The count is not the same guarantee as the order**, and since the
    backfill began asking for a whole commit batch at once there is an order to get wrong —
    `tests/test_batched_retrieval_integration.py` holds the pairing shut from the caller's side.

    **A dropped call is retried three times (owner-ruled 2026-08-18, see `transport`).** It
    matters more here than it looks: a commit batch asks for 25 names in one request, so one
    blip on this call costs 25 rows rather than one. The retries are connection-level only, and
    what this function raises is unchanged — `EmbedUnavailable` for a service that did not
    answer, after three attempts instead of one.
    """
    if not texts:
        return []
    model = model or EMBED_MODEL
    body = json.dumps({"model": model, "input": texts}).encode()
    request = urllib.request.Request(
        f"http://{HOST}/api/embed", data=body, headers={"Content-Type": "application/json"}
    )
    try:
        reply = fetch(request, TIMEOUT_S, "embed")
    # The caught tuple is deliberately unchanged from before the retry landed. `transport` may also
    # raise a bare `http.client.HTTPException` — that is not caught here, and was not caught before
    # either, so it still surfaces as a traceback rather than as "the service did not answer".
    # Widening it would file an odd protocol error under `EmbedUnavailable`, which means *ordinary,
    # exit 3, wait and re-run* — the one thing an unexplained error is not.
    except (urllib.error.URLError, OSError, ValueError) as error:
        raise EmbedUnavailable(f"{model} at {HOST} did not answer: {error}") from None
    vectors = reply.get("embeddings")
    if not isinstance(vectors, list) or len(vectors) != len(texts):
        raise ValueError(
            f"asked {model} for {len(texts)} vectors and got "
            f"{len(vectors) if isinstance(vectors, list) else type(vectors).__name__} back"
        )
    widths = {len(vector) for vector in vectors}
    if len(widths) != 1:
        raise ValueError(
            f"{model} returned vectors of {sorted(widths)} dimensions in one reply — one model "
            "has one space, and rows of unequal width could not be compared at all"
        )
    width = widths.pop()
    expected = EXPECTED_DIMENSIONS.get(model)
    if expected is not None and width != expected:
        raise ValueError(
            f"{model} returned a {width}-dimension vector where {expected} was expected — this "
            "is a different embedding model under a known name, and mixing two of them in one "
            "embedder's rows would order neighbours by nothing"
        )
    return vectors


def as_literal(vector: list[float]) -> str:
    """A vector as pgvector's own text form, `'[1,2,3]'`, for a `::vector` cast in SQL.

    The whole of what the pgvector Python package would buy for this project is this one
    function, so the dependency is not taken. `repr` of a float round-trips exactly in
    CPython, which is what keeps the stored vector the vector the model returned.
    """
    return "[" + ",".join(repr(float(value)) for value in vector) + "]"
