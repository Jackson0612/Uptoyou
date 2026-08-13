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

MODEL = os.environ.get("UPTO_MODEL", "qwen2.5:3b-instruct-q4_K_M")
HOST = os.environ.get("UPTO_MODEL_HOST", "ollama:11434")
TIMEOUT_S = int(os.environ.get("UPTO_MODEL_TIMEOUT", "180"))


def available() -> bool:
    """Is the model service up and holding the model? Never raises — absence is ordinary."""
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
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
        return json.load(response)["response"]
