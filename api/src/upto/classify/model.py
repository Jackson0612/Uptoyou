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

import http.client
import json
import os
import sys
import time
import urllib.error
import urllib.request

MODEL = os.environ.get("UPTO_MODEL", "qwen2.5:3b-instruct-q4_K_M")
HOST = os.environ.get("UPTO_MODEL_HOST", "ollama:11434")
TIMEOUT_S = int(os.environ.get("UPTO_MODEL_TIMEOUT", "180"))

# --- the retry, owner-ruled 2026-08-18 (D75 amended) --------------------------------------
#
# **Why it exists.** 松山's pass died at row 400 of 3,324 on
# `http.client.RemoteDisconnected: Remote end closed connection without response`, raised inside
# this module's `urlopen`. The relay was healthy before and after — checked from the host and from
# inside the container, all three models visible — so the drop was transient. Nothing was lost,
# because D75 commits per batch and resumes at the first undecided row, but 2,900 names had to be
# asked again for one blip, and 大安 is 5,462 names of the same exposure.
#
# **Bounded, and connection-level only.** Three attempts, then the failure is raised as it always
# was. The rejected branch is unbounded or open-ended retry, which papers over a genuinely dead
# tunnel: the cost accepted here is that a dead tunnel is discovered about 30 seconds later than
# before, and that is the whole cost.
#
# **A retry is for a call that never got an answer, never for an answer we did not like.** So
# `urllib.error.HTTPError` is re-raised immediately even though it is a `URLError` subclass — a 400
# or a 404 *is* the server answering, and asking three times gets the same answer three times. A
# reply whose body will not parse is an answer too, and `json` raising `ValueError` is outside the
# retried block for the same reason.
#
# **The count is printed, and that is part of the ruling rather than a nicety.** A link that drops
# one call in fifty now succeeds silently and looks like a slow night; `retries_spent()` is what
# the backfill prints so it shows up as a number instead.
RETRIES = 3
BACKOFF_S = (0.5, 2.0)  # slept after the first failure, then after the second

# A dropped call and a dropped connection are the same class of event here, and both are OSError
# subclasses in practice — `RemoteDisconnected` is one. `http.client.HTTPException` is listed
# anyway because not every member of that family is an OSError, and the one that killed 松山 is
# the one this must not miss.
_TRANSIENT = (urllib.error.URLError, http.client.HTTPException, TimeoutError, OSError)

_retried = 0


def retries_spent() -> int:
    """How many connection-level retries this process has spent. For the run's own summary."""
    return _retried


def reset_retries() -> None:
    """Zero the counter. A caller measuring one pass calls this before it starts."""
    global _retried
    _retried = 0


def _fetch(request: urllib.request.Request, timeout: int) -> dict:
    """One HTTP call, retried on a connection-level failure only. See the block above."""
    global _retried
    for attempt in range(1, RETRIES + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read()
        except urllib.error.HTTPError:
            raise  # the server answered; that is not a dropped call
        except _TRANSIENT as failure:
            if attempt == RETRIES:
                raise
            _retried += 1
            pause = BACKOFF_S[attempt - 1]
            print(
                f"  model call failed ({type(failure).__name__}: {failure}) — attempt "
                f"{attempt} of {RETRIES}, retrying in {pause}s",
                file=sys.stderr,
                flush=True,
            )
            time.sleep(pause)
        else:
            # Outside the retried block on purpose: a body that will not parse is an answer.
            return json.loads(body)
    raise AssertionError("unreachable: the loop either returns or raises")


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
    return _fetch(request, TIMEOUT_S)["response"]
