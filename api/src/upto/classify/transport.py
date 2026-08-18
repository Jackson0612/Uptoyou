"""One retry policy for both model calls — owner-ruled 2026-08-18, D75 amended.

**Why it exists.** 松山's backfill died at row 400 of 3,324 on
`http.client.RemoteDisconnected: Remote end closed connection without response`, raised inside the
generation client's `urlopen`. The relay was healthy either side of it — checked from the host and
from inside the container, all three models visible — so the drop was transient, and one blip cost
2,900 names their place in the queue.

**Why it is one module rather than a copy in each client.** The ruling covers `model.ask` and
`embed.embed`, and the embedding side is the one the batching change made worse: since a commit
batch now asks for 25 names in a single request, a dropped embed call costs 25 rows rather than 1.
Two copies of a retry policy drift, and the *count* has to be one number — a run that retried twice
on the generator and once on the embedder spent three retries, and a reader chasing a flaky link
wants that total rather than two half-answers. The crib load and the evaluation rounds inherit the
policy by using the same client, which the owner named as the point rather than a side effect.

**Bounded, and connection-level only.** Three attempts, then the original failure is raised **as it
always was** — not wrapped — so no caller's `except` changes meaning and the traceback still names
the link that failed. The rejected branch is unbounded or open-ended retry, which papers over a
genuinely dead tunnel; the cost accepted is that a dead tunnel is discovered about thirty seconds
later than before, and that is the whole cost.

**A retry is for a call that never got an answer, never for an answer we did not like.** Two
exclusions carry that, and both are easy to get wrong:

- `urllib.error.HTTPError` is re-raised immediately **even though it subclasses `URLError`**. A 400
  or a 404 *is* the server answering; asking three times gets the same answer three times and turns
  a clear error into a slow one.
- A reply whose body will not parse is also an answer, so decoding happens **outside** the retried
  block. Re-asking there would be asking the model to change its mind about something it already
  said.

**The count is printed, and that is part of the ruling rather than a nicety.** A link that drops one
call in fifty now succeeds silently and reads as a slow night; `retries_spent()` is what a backfill
prints so it shows up as a number instead.
"""

from __future__ import annotations

import http.client
import json
import sys
import time
import urllib.error
import urllib.request

RETRIES = 3
BACKOFF_S = (0.5, 2.0)  # slept after the first failure, then after the second

# A dropped call and a dropped connection are the same class of event here, and both are `OSError`
# subclasses in practice — `RemoteDisconnected` is one. `http.client.HTTPException` is listed anyway
# because not every member of that family is an `OSError`, and the one that killed 松山 is the one
# this must not miss.
TRANSIENT = (urllib.error.URLError, http.client.HTTPException, TimeoutError, OSError)

_retried = 0


def retries_spent() -> int:
    """How many connection-level retries this process has spent, across both clients."""
    return _retried


def reset_retries() -> None:
    """Zero the counter. A caller measuring one pass calls this before it starts."""
    global _retried
    _retried = 0


def fetch(request: urllib.request.Request, timeout: int, what: str) -> dict:
    """One HTTP call, decoded, retried on a connection-level failure only.

    `what` names the caller in the retry line — `model` or `embed` — because a run that retried
    should say *which* link dropped, and the two go to the same host over the same tunnel.
    """
    global _retried
    for attempt in range(1, RETRIES + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read()
        except urllib.error.HTTPError:
            raise  # the server answered; that is not a dropped call
        except TRANSIENT as failure:
            if attempt == RETRIES:
                raise
            _retried += 1
            pause = BACKOFF_S[attempt - 1]
            print(
                f"  {what} call failed ({type(failure).__name__}: {failure}) — attempt "
                f"{attempt} of {RETRIES}, retrying in {pause}s",
                file=sys.stderr,
                flush=True,
            )
            time.sleep(pause)
        else:
            # Outside the retried block on purpose: a body that will not parse is an answer.
            return json.loads(body)
    raise AssertionError("unreachable: the loop either returns or raises")
