"""The model, as reached from inside the stack — and what to do when it is not there.

The service is behind a compose profile (ruled 2026-08-14), so **absence is the ordinary
case, not the failure case**. `available()` answers that question without raising, and the
runner uses it to record a skipped pass rather than a broken one — the same distinction
`ingest_run` already draws between *no change* and *failed*, and for the same reason: an
absence inferred from an error looks exactly like a bug.

The endpoint is an environment variable because the model is the one dependency that is
sometimes simply not running; D33's rule about credentials does not apply — there is no
credential here, only a host.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from upto.classify.transport import fetch

MODEL = os.environ.get("UPTO_MODEL", "qwen2.5:3b-instruct-q4_K_M")
HOST = os.environ.get("UPTO_MODEL_HOST", "ollama:11434")
TIMEOUT_S = int(os.environ.get("UPTO_MODEL_TIMEOUT", "180"))

# The retry lives in `transport`, because the ruling covers this client and the embedding one and
# the printed count has to be a single number across both. See that module for the whole argument;
# the short version is three attempts, connection-level failures only, and the original exception
# raised rather than wrapped.


def available() -> bool:
    """Is the model service up and holding the model? Never raises — absence is ordinary.

    **Deliberately not retried.** It is a question rather than a request, and it already answers
    "no" instead of raising. Retrying it would turn the ordinary case — the profile is off — into
    a three-second pause before the same answer.
    """
    try:
        with urllib.request.urlopen(f"http://{HOST}/api/tags", timeout=5) as response:
            tags = json.load(response)
    except (urllib.error.URLError, OSError, ValueError):
        return False
    return any(entry.get("name", "").startswith(MODEL.split(":")[0]) for entry in tags.get("models", []))


def ask(prompt: str) -> str:
    """One completion, deterministic, short — the answer is at most a few characters."""
    body = json.dumps(
        {
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            # temperature 0 so a re-run of the same prompt version is as close to repeatable
            # as this kind of tool gets. D39 admits it is not fully reproducible.
            "options": {"temperature": 0, "num_predict": 8},
        }
    ).encode()
    request = urllib.request.Request(
        f"http://{HOST}/api/generate", data=body, headers={"Content-Type": "application/json"}
    )
    return fetch(request, TIMEOUT_S, "model")["response"]
