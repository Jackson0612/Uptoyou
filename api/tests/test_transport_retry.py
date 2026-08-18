#!/usr/bin/env python3
"""The shared bounded retry — owner-ruled 2026-08-18, and it must not be silent.

Run: python3 app/api/tests/test_transport_retry.py    (no network, no database, no model)

**Why this file exists.** 松山's backfill died at row 400 of 3,324 on
`http.client.RemoteDisconnected: Remote end closed connection without response`, raised inside
`model.ask`'s `urlopen`. The relay was healthy either side of it, so the drop was transient, and
one blip cost 2,900 names their place in the queue. The ruled fix is three attempts, backoff,
**connection-level failures only**, with the count printed.

**A retry is the kind of thing that fails silently in both directions**, which is why every branch
below is asserted rather than a couple of happy paths:

- A retry that does not retry looks exactly like the old behaviour until the next dropped call, and
  by then the pass has died and nobody re-reads the client.
- A retry that retries *too much* is worse: asking three times about a 400 gets the same 400 three
  times and turns a clear error into a slow one, and re-asking a reply whose body would not parse
  is asking the model to change its mind about an answer it already gave.

So: the transient case retries and succeeds; the exhausted case raises the original failure rather
than something new; `HTTPError` is refused a retry even though it is a `URLError` subclass; an
unparseable body is refused a retry because it is an answer; and `RemoteDisconnected` — the exact
exception that killed 松山 — is named in its own test so the regression has a name.
"""

import http.client
import io
import json
import os
import socket
import sys
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from upto.classify import embed as embedder  # noqa: E402
from upto.classify import model  # noqa: E402
from upto.classify import transport  # noqa: E402


class FakeResponse:
    """Just enough of an HTTP response for `_fetch`: a context manager with `read()`."""

    def __init__(self, body: bytes):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def read(self) -> bytes:
        return self._body


class Door:
    """A stand-in for `urlopen` that hands out a scripted sequence of outcomes."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def __call__(self, request, timeout=None):
        self.calls += 1
        outcome = self.script.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return FakeResponse(outcome)


ANSWER = json.dumps({"response": "麵食"}).encode()


def http_error() -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        "http://model/api/generate", 400, "Bad Request", {}, io.BytesIO(b"{}")
    )


class TheRetry(unittest.TestCase):
    def setUp(self):
        self.real_urlopen = urllib.request.urlopen
        self.slept = []
        self.real_sleep = transport.time.sleep
        transport.time.sleep = self.slept.append
        transport.reset_retries()

    def tearDown(self):
        urllib.request.urlopen = self.real_urlopen
        transport.time.sleep = self.real_sleep
        transport.reset_retries()

    def door(self, script) -> Door:
        opened = Door(script)
        urllib.request.urlopen = opened
        return opened

    # --- it retries, and it counts ------------------------------------------------------

    def test_a_dropped_call_is_retried_and_the_answer_survives(self):
        opened = self.door([ConnectionResetError("reset"), ANSWER])
        self.assertEqual(model.ask("prompt"), "麵食")
        self.assertEqual(opened.calls, 2)
        self.assertEqual(transport.retries_spent(), 1)
        self.assertEqual(self.slept, [transport.BACKOFF_S[0]])

    def test_remote_disconnected_is_retried(self):
        """The exact failure that killed 松山 at row 400. Named so the regression has a name."""
        opened = self.door([http.client.RemoteDisconnected("closed without response"), ANSWER])
        self.assertEqual(model.ask("prompt"), "麵食")
        self.assertEqual(opened.calls, 2)
        self.assertEqual(transport.retries_spent(), 1)

    def test_a_timeout_is_retried(self):
        opened = self.door([socket.timeout("timed out"), ANSWER])
        self.assertEqual(model.ask("prompt"), "麵食")
        self.assertEqual(opened.calls, 2)

    def test_two_failures_then_success_uses_both_backoffs(self):
        opened = self.door(
            [urllib.error.URLError("no route"), ConnectionResetError("reset"), ANSWER]
        )
        self.assertEqual(model.ask("prompt"), "麵食")
        self.assertEqual(opened.calls, 3)
        self.assertEqual(transport.retries_spent(), 2)
        self.assertEqual(self.slept, list(transport.BACKOFF_S))

    # --- it stops, and it raises what actually happened ---------------------------------

    def test_it_is_bounded_and_raises_the_original_failure(self):
        """Three attempts, then the failure the caller always saw — not a wrapper.

        Raising a new exception type would have broken every caller's `except` and would have hidden
        which link failed. The pass still dies; it dies after three tries instead of one.
        """
        opened = self.door([ConnectionResetError("reset")] * transport.RETRIES)
        with self.assertRaises(ConnectionResetError):
            model.ask("prompt")
        self.assertEqual(opened.calls, transport.RETRIES)
        # Two sleeps for three attempts: the last failure is raised rather than waited on.
        self.assertEqual(transport.retries_spent(), transport.RETRIES - 1)
        self.assertEqual(len(self.slept), transport.RETRIES - 1)

    # --- it refuses to retry an answer --------------------------------------------------

    def test_an_http_error_is_not_retried(self):
        """A 400 is the server answering. `HTTPError` subclasses `URLError`, so this is a real trap."""
        opened = self.door([http_error(), ANSWER])
        with self.assertRaises(urllib.error.HTTPError):
            model.ask("prompt")
        self.assertEqual(opened.calls, 1)
        self.assertEqual(transport.retries_spent(), 0)
        self.assertEqual(self.slept, [])

    def test_an_unparseable_body_is_not_retried(self):
        """A reply that will not parse is an answer, and the model will not change its mind."""
        opened = self.door([b"not json at all", ANSWER])
        with self.assertRaises(ValueError):
            model.ask("prompt")
        self.assertEqual(opened.calls, 1)
        self.assertEqual(transport.retries_spent(), 0)

    def test_a_reply_without_the_expected_field_is_not_retried(self):
        opened = self.door([json.dumps({"error": "no such model"}).encode(), ANSWER])
        with self.assertRaises(KeyError):
            model.ask("prompt")
        self.assertEqual(opened.calls, 1)
        self.assertEqual(transport.retries_spent(), 0)

    # --- the question is not a request --------------------------------------------------

    def test_available_is_not_retried(self):
        """`available()` answers "no" instead of raising, and the ordinary case is the profile off.

        Retrying it would spend the backoff on the normal path — every invocation of a stack with
        the model profile down would pause before printing the same message.
        """
        opened = self.door([ConnectionResetError("reset")])
        self.assertFalse(model.available())
        self.assertEqual(opened.calls, 1)
        self.assertEqual(transport.retries_spent(), 0)
        self.assertEqual(self.slept, [])

    # --- the counter is a counter -------------------------------------------------------

    def test_reset_clears_the_counter(self):
        self.door([ConnectionResetError("reset"), ANSWER])
        model.ask("prompt")
        self.assertEqual(transport.retries_spent(), 1)
        transport.reset_retries()
        self.assertEqual(transport.retries_spent(), 0)

    # --- the embedding client, which the ruling covers for its own reason ----------------

    def test_a_dropped_embed_call_is_retried_and_the_vectors_survive(self):
        """The embedder matters more than it looks: one blip here costs a whole commit batch.

        Since the backfill began asking for all 25 names of a batch in one request, a dropped embed
        call loses 25 rows rather than one — which is why the owner extended the policy here rather
        than leaving it on the generator alone.
        """
        reply = json.dumps({"embeddings": [[0.1, 0.2], [0.3, 0.4]]}).encode()
        opened = self.door([ConnectionResetError("reset"), reply])
        got = embedder.embed(["甲", "乙"], model="stub-embed:test")
        self.assertEqual(got, [[0.1, 0.2], [0.3, 0.4]])
        self.assertEqual(opened.calls, 2)
        self.assertEqual(transport.retries_spent(), 1)

    def test_an_exhausted_embed_call_still_raises_embed_unavailable(self):
        """What this raises is unchanged — three attempts instead of one, same exception.

        `EmbedUnavailable` is what a caller catches to record a *skipped* pass rather than a broken
        one, so a retry that changed the type would turn a wait into a failure.
        """
        opened = self.door([ConnectionResetError("reset")] * transport.RETRIES)
        with self.assertRaises(embedder.EmbedUnavailable):
            embedder.embed(["甲"], model="stub-embed:test")
        self.assertEqual(opened.calls, transport.RETRIES)
        self.assertEqual(transport.retries_spent(), transport.RETRIES - 1)

    def test_the_count_is_one_number_across_both_clients(self):
        """The reason the policy is one module and not two copies.

        A pass that dropped one generation call and one embedding call spent **two** retries. Two
        separate counters would report one and one, and a reader chasing a flaky tunnel would have
        to add them up — or, more likely, would read whichever number the summary happened to print.
        """
        reply = json.dumps({"embeddings": [[0.1, 0.2]]}).encode()
        self.door([ConnectionResetError("reset"), ANSWER, ConnectionResetError("reset"), reply])
        model.ask("prompt")
        embedder.embed(["甲"], model="stub-embed:test")
        self.assertEqual(transport.retries_spent(), 2)

    def test_the_bound_is_three(self):
        """Pinned, because the ruling named the number and a drifting bound changes the cost."""
        self.assertEqual(transport.RETRIES, 3)
        self.assertEqual(len(transport.BACKOFF_S), transport.RETRIES - 1)


class TheServersOwnTimings(unittest.TestCase):
    """`ask` keeps the five timing fields every reply already carries (2026-08-18).

    Tested because the cheapest instrument is the easiest to break silently: nothing downstream
    reads these to make a decision, so a reply shape change or a stray `take_samples()` would leave
    the backfill working perfectly and its diagnostics blank. The pass prints them per batch, and a
    blank column looks like "the server stopped reporting" rather than "we stopped collecting".
    """

    def setUp(self):
        self.real_urlopen = urllib.request.urlopen
        model.time_sleep_patch = None
        transport.reset_retries()
        model.take_samples()

    def tearDown(self):
        urllib.request.urlopen = self.real_urlopen
        model.take_samples()

    def reply(self, **fields) -> bytes:
        body = {"response": "麵食"}
        body.update(fields)
        return json.dumps(body).encode()

    def test_the_fields_are_kept_and_taken_away(self):
        urllib.request.urlopen = Door([
            self.reply(load_duration=450_000_000, prompt_eval_count=214,
                       prompt_eval_duration=41_000_000, eval_count=8,
                       eval_duration=63_000_000, total_duration=600_000_000),
        ])
        model.ask("prompt")
        taken = model.take_samples()
        self.assertEqual(len(taken), 1)
        self.assertEqual(taken[0]["prompt_eval_count"], 214)
        self.assertEqual(taken[0]["load_duration"], 450_000_000)
        # Taken away, not copied: the next batch must not see this one's numbers.
        self.assertEqual(model.take_samples(), [])

    def test_samples_accumulate_across_calls(self):
        urllib.request.urlopen = Door([self.reply(prompt_eval_count=n) for n in (10, 20, 30)])
        for _ in range(3):
            model.ask("prompt")
        self.assertEqual([s["prompt_eval_count"] for s in model.take_samples()], [10, 20, 30])

    def test_a_reply_missing_the_fields_reads_as_zero_rather_than_raising(self):
        """A server that stops reporting timings must not stop the backfill."""
        urllib.request.urlopen = Door([self.reply()])
        self.assertEqual(model.ask("prompt"), "麵食")
        taken = model.take_samples()
        self.assertEqual(len(taken), 1)
        self.assertEqual(set(taken[0]), set(model.TIMING_FIELDS))
        self.assertEqual(sum(taken[0].values()), 0)

    def test_a_failed_call_records_no_sample(self):
        """Only an answered call has timings — a dropped one must not add a row of zeroes."""
        urllib.request.urlopen = Door([http_error()])
        with self.assertRaises(urllib.error.HTTPError):
            model.ask("prompt")
        self.assertEqual(model.take_samples(), [])


if __name__ == "__main__":
    unittest.main(verbosity=1)
