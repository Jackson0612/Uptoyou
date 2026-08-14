"""D64's evaluation round: one candidate model, the 200 frozen names, one file of answers.

    docker compose --profile model up -d ollama
    docker compose exec api python -m upto.evaluate.run_round qwen   # or gemma, llama
    python3 -m upto.evaluate.run_round gemini          # host-side; the key never enters the stack

Four candidates: D64's local slate — `qwen` · `gemma` · `llama`, three contenders from three
makers, all self-hostable per D63 — plus `gemini`, the hosted baseline that enters the
evaluation and nothing else (D84's last line). All are asked
through `upto.classify.classify_name`, so a round measures **the shipped validation path**,
not a second copy of it written for the evaluation — an answer this runner accepts is exactly
an answer the backfill would have written, and an answer it refuses is a row the backfill
would have left pending.

**The round is a file, not a number.** Every row is kept — asked name, layer, the gold it was
asked under, the answer, the outcome — because a score with no rows behind it cannot be
argued with, and D64's rule is one public commit per round. Scoring is a separate module
reading this file: `python -m upto.evaluate.score <round-file>`.

**Resumable, and the resume rule is deliberately strict.** The file is written every 10
answers and the next run continues at the first unanswered row — 200 names at the probed
7.24 s is ~24 minutes for qwen, and a free-tier hosted round is bounded by a daily quota
rather than by time, so an interrupted round that had to start over would be a round nobody
runs twice. A stored answer is inherited **only** while it sits in an unbroken prefix and the
name at its index still reads the same; the frozen set is frozen against re-drawing, not
against the owner's corrections, and an answer about an amended string is not an answer about
this row.

**The model string is pinned before the round, never negotiated during it.** D84's instrument
walks an alias chain because it wants freshness; an evaluation wants the opposite, and a round
that silently changed model half-way would produce a score that is a score of nothing. If the
pinned model stops answering, the round saves and stops, and a stored round refuses to be
continued by a different model.

Exit codes: **0** the round is complete · **1** the candidate failed in a way that is not a
wait (the message says how) · **2** usage, a missing key, or a round file that disagrees with
what was asked for · **3** come back later — the model service is down or the daily quota is
spent — **and progress is saved**, which is the ordinary case rather than a failure, the same
distinction `ingest_run` draws between no change and failed.

No credential is ever printed, stored in the round file, or passed into a subprocess: the
Gemini key is read from `~/.keys/gemini_api_key` (override `UPTO_GEMINI_KEY_FILE`) and held
in memory for the run.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

from upto.classify.classify import Classified, NoSignal, classify_name
from upto.classify.prompt import NO_SIGNAL, PROMPT_VERSION
from upto.evaluate.score import TESTSET_PATH, load_testset

SAVE_EVERY = 10

# D64's local slate, owner-ruled 2026-08-14: three contenders, three makers, all under the
# 4 GB EC2 class's ~2.5 GB resident line (gemma3:4b failed that gate and was replaced by
# gemma2:2b). One CLI name per model; the string is pinned here and written into the round.
LOCAL_MODELS = {
    "qwen": "qwen2.5:3b-instruct-q4_K_M",
    "gemma": "gemma2:2b",
    "llama": "llama3.2:3b",
}
OLLAMA_URL = os.environ.get("UPTO_OLLAMA_URL", "http://ollama:11434").rstrip("/")
OLLAMA_TIMEOUT_S = int(os.environ.get("UPTO_OLLAMA_TIMEOUT", "180"))

# **Pinned, and no fallback chain — owner-ruled 2026-08-14 after measuring this account's free
# tier: `flash` and `3.5-flash` allow 20 requests a day, `flash-lite` allows 500.** A 200-name
# round does not fit in 20, so the chain D84's instrument uses would have spent its daily
# allowance on the first 20 names and finished the round on a *different* model — a score
# belonging to neither. The instrument wants freshness and availability; an evaluation wants
# one model string, fixed before the round and written into the file.
GEMINI_MODEL = "gemini-3.5-flash-lite"
GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"
GEMINI_KEY_FILE = os.environ.get("UPTO_GEMINI_KEY_FILE", "~/.keys/gemini_api_key")
GEMINI_TIMEOUT_S = int(os.environ.get("UPTO_GEMINI_TIMEOUT", "60"))
# 500 a day is room to spare for 200 names, so the gap is politeness against the per-minute
# allowance rather than rationing: 2 s puts a round at ~7 minutes of waiting.
GEMINI_SLEEP_S = float(os.environ.get("UPTO_GEMINI_SLEEP", "2"))
GEMINI_TRIES = 5


class ComeBackLater(Exception):
    """The candidate cannot answer now and will be able to later. Progress is saved: exit 3."""


class CandidateFailed(Exception):
    """The candidate failed in a way waiting will not fix: exit 1."""


class UsageError(Exception):
    """The run was asked for something it cannot do — a bad name, no key: exit 2."""


# --- where the rounds live ------------------------------------------------------------


def evaluation_dir(start: str | None = None) -> str:
    """The repo-root `evaluation/` directory, resolved without pointing above `app/`.

    `UPTO_EVALUATION_DIR` wins outright — it is what the container uses, where the checkout's
    shape is not visible. Otherwise walk up from this file for a repository root (a `.git`,
    or the private repo's `app/` + `doc/` pair); the same walk lands on the public repo's own
    root after D47's extract, because there `app/` *is* the root. Failing both, `./evaluation`
    under the current directory — a stated fallback rather than a guess that writes somewhere
    surprising.
    """
    override = os.environ.get("UPTO_EVALUATION_DIR")
    if override:
        return os.path.abspath(os.path.expanduser(override))
    here = start or os.path.dirname(os.path.abspath(__file__))
    path = here
    while True:
        if os.path.isdir(os.path.join(path, ".git")) or (
            os.path.isdir(os.path.join(path, "app")) and os.path.isdir(os.path.join(path, "doc"))
        ):
            return os.path.join(path, "evaluation")
        parent = os.path.dirname(path)
        if parent == path:
            return os.path.abspath("evaluation")
        path = parent


def round_path(candidate: str, prompt_version: str = PROMPT_VERSION) -> str:
    return os.path.join(evaluation_dir(), f"round_{candidate}_{prompt_version}.json")


def save(path: str, document: dict) -> None:
    """Write whole, then move into place — a crash mid-write must not eat the round so far."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = path + ".partial"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(document, handle, ensure_ascii=False, indent=1)
        handle.write("\n")
    os.replace(temporary, path)


# --- the resume decision, pure so it can be tested --------------------------------------


def resume_point(stored: list[dict], gold_rows: list[dict]) -> tuple[list[dict], int]:
    """Which stored answers survive, and where the next ask starts.

    Only an unbroken prefix is inherited, and only while the stored row's name still matches
    the set at that index. A gap means the file was hand-edited or a save was lost — asking
    around it would produce a round whose row order no longer means what the index says; a
    name change means the owner amended the set and that answer is about a different string.
    Both cases cost re-asking a suffix, which is the cheap half of the trade.
    """
    answered = {row["i"]: row for row in stored if isinstance(row.get("i"), int)}
    kept: list[dict] = []
    for index, gold_row in enumerate(gold_rows):
        row = answered.get(index)
        if row is None or row.get("name") != gold_row.get("name"):
            break
        kept.append(row)
    return kept, len(kept)


# --- the candidates ---------------------------------------------------------------------


class Local:
    """A local candidate, asked over Ollama's HTTP API. Standard library, like everything here."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.model = LOCAL_MODELS[name]

    def check(self) -> None:
        try:
            with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=10) as response:
                tags = json.load(response)
        except (urllib.error.URLError, OSError, ValueError) as error:
            raise ComeBackLater(
                f"the model service at {OLLAMA_URL} is not answering ({error}). It sits behind "
                "a compose profile and is off unless a backfill or a round is running: "
                "`docker compose --profile model up -d ollama`."
            )
        held = [entry.get("name", "") for entry in tags.get("models", [])]
        if not any(entry.startswith(self.model.split(":")[0]) for entry in held):
            raise ComeBackLater(
                f"{OLLAMA_URL} is up but does not hold {self.model} — pull it once: "
                f"`docker compose exec ollama ollama pull {self.model}`."
            )

    def ask(self, prompt: str) -> str:
        body = json.dumps(
            {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                # temperature 0 and a short budget: the answer is a few characters, and a
                # re-run of the same prompt version should land as close to identical as this
                # kind of tool gets. D39 admits it is not fully reproducible.
                "options": {"temperature": 0, "num_predict": 8},
            }
        ).encode()
        request = urllib.request.Request(
            f"{OLLAMA_URL}/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=OLLAMA_TIMEOUT_S) as response:
                return json.load(response)["response"]
        except (urllib.error.URLError, OSError, ValueError, KeyError) as error:
            raise ComeBackLater(f"{self.model} stopped answering: {error}")


class Gemini:
    """The hosted baseline: one pinned model, plain generation, no search grounding, temp 0.

    **Ungrounded on purpose, and not only because the free tier refuses grounding (D84).** The
    evaluation asks what a model knows about a name, which is the same question the local
    candidate is asked; handing one candidate a search engine would measure a different task
    and the two scores would not be comparable.
    """

    name = "gemini"

    def __init__(self, key: str) -> None:
        self._key = key  # held in memory for the run; never printed, never written
        self.model = GEMINI_MODEL
        self._last_call = 0.0

    def check(self) -> None:
        pass  # nothing to check without spending a call, and calls are the rationed thing

    def _post(self, prompt: str) -> str:
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0},
        }
        request = urllib.request.Request(
            GEMINI_ENDPOINT.format(self.model),
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": self._key},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=GEMINI_TIMEOUT_S) as response:
            reply = json.load(response)
        candidate = (reply.get("candidates") or [{}])[0]
        parts = candidate.get("content", {}).get("parts", [])
        return "\n".join(part["text"] for part in parts if "text" in part).strip()

    def ask(self, prompt: str) -> str:
        gap = GEMINI_SLEEP_S - (time.monotonic() - self._last_call)
        if gap > 0:
            time.sleep(gap)
        delay = 8.0
        last: Exception | None = None
        for attempt in range(GEMINI_TRIES):
            try:
                answer = self._post(prompt)
            except urllib.error.HTTPError as error:
                last = error
                if error.code not in (429, 500, 503):
                    detail = error.read().decode("utf-8", "replace")[:300]
                    raise CandidateFailed(f"HTTP {error.code} from the Gemini API: {detail}")
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
                # OSError is load-bearing on the host: its Python 3.9 raises socket.timeout,
                # which is an OSError and NOT TimeoutError until 3.10 — without it a mid-round
                # read timeout escaped the retry loop whole (measured: a round died at 40/200).
                last = error
            else:
                self._last_call = time.monotonic()
                return answer
            if attempt < GEMINI_TRIES - 1:
                print(f"  (rate-limited or unreachable, waiting {delay:.0f}s — "
                      f"attempt {attempt + 2} of {GEMINI_TRIES})", file=sys.stderr)
                time.sleep(delay)
                delay *= 2
        raise ComeBackLater(
            f"{self.model} refused {GEMINI_TRIES} times in a row ({last}) — on this account's "
            "free tier that is the daily allowance spent (measured: 500 requests a day for "
            "flash-lite). Answers so far are saved; re-run tomorrow and the round continues "
            "where it stopped."
        )


def read_key(path: str = GEMINI_KEY_FILE) -> str:
    expanded = os.path.expanduser(path)
    key = ""
    if os.path.exists(expanded):
        with open(expanded, encoding="utf-8") as handle:
            key = handle.read().strip()
    if not key:
        raise UsageError(
            f"no key at {expanded} (missing or empty) — save one there, chmod 600. It is never "
            "stored in this repository, never printed, and never written into a round file."
        )
    return key


def build_candidate(name: str):
    if name in LOCAL_MODELS:
        return Local(name)
    if name == "gemini":
        return Gemini(read_key())
    raise UsageError(
        f"unknown candidate {name!r} — it is one of {', '.join(LOCAL_MODELS)}, or `gemini`"
    )


# --- one row --------------------------------------------------------------------------


def answer_row(index: int, gold_row: dict, ask) -> dict:
    """Ask one name through the shipped validation path and record what came back.

    The three outcomes are the three `classify_name` returns and they are kept apart for the
    reason D79 keeps them apart in the database: a legal-entity verdict is a decision the
    model reached, a refusal is an answer nobody can use, and collapsing them would make the
    score unable to tell a confident wrong answer from a broken one.
    """
    outcome = classify_name(gold_row["name"], ask)
    row = {
        "i": index,
        "name": gold_row["name"],
        "layer": gold_row.get("layer"),
        "gold": gold_row.get("label"),
        "answer": None,
        "outcome": "refused",
    }
    if isinstance(outcome, Classified):
        row["answer"] = outcome.category
        row["outcome"] = "category"
    elif isinstance(outcome, NoSignal):
        # The sentinel is a label in the frozen set (D82), so it is recorded as the answer it
        # is — a verdict — and not as an absence the scorer would have to reconstruct.
        row["answer"] = NO_SIGNAL
        row["outcome"] = "no_signal"
    else:
        # The raw string is kept, truncated: a refusal that cannot be read back costs a full
        # re-run of the round to diagnose, and a round is minutes-to-a-day of work.
        row["raw"] = (outcome.raw or "")[:200]
    return row


def main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0].startswith("-"):
        print("usage: python -m upto.evaluate.run_round <qwen|gemma|llama|gemini>",
              file=sys.stderr)
        return 2
    name = argv[0]
    try:
        candidate = build_candidate(name)
    except UsageError as error:
        print(str(error), file=sys.stderr)
        return 2

    gold_rows, digest = load_testset()
    path = round_path(name)

    document = {
        "candidate": name,
        "model": getattr(candidate, "model", None),
        "prompt_version": PROMPT_VERSION,
        "testset": os.path.basename(TESTSET_PATH),
        "testset_sha256_at_run": digest,
        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "finished_at": None,
        "rows": [],
    }
    if os.path.exists(path):
        with open(path, encoding="utf-8") as handle:
            existing = json.load(handle)
        if existing.get("candidate") != name or existing.get("prompt_version") != PROMPT_VERSION:
            print(
                f"{path} holds a {existing.get('candidate')} round at prompt "
                f"{existing.get('prompt_version')}, and this is {name} at {PROMPT_VERSION}. "
                "Move it aside rather than mixing two rounds in one file.",
                file=sys.stderr,
            )
            return 2
        stored_model = existing.get("model")
        if stored_model and stored_model != candidate.model:
            print(
                f"{path} was answered by {stored_model} and this run would answer with "
                f"{candidate.model}. One round is one model — move the file aside and start a "
                "round for the new one.",
                file=sys.stderr,
            )
            return 2
        kept, start = resume_point(existing.get("rows", []), gold_rows)
        document = dict(existing, rows=kept, finished_at=None)
        document["model"] = candidate.model
        dropped = len(existing.get("rows", [])) - len(kept)
        print(f"resuming {path}: {start} answers kept"
              + (f", {dropped} dropped (a gap, or the set was amended under them)"
                 if dropped else "")
              + f", {len(gold_rows) - start} to ask")
    else:
        start = 0
        print(f"new round: {name} against {len(gold_rows)} names, prompt {PROMPT_VERSION}")

    try:
        candidate.check()
    except ComeBackLater as error:
        print(str(error), file=sys.stderr)
        return 3

    rows = document["rows"]
    status = 0
    try:
        for index in range(start, len(gold_rows)):
            rows.append(answer_row(index, gold_rows[index], candidate.ask))
            document["model"] = candidate.model
            if len(rows) % SAVE_EVERY == 0:
                save(path, document)
                decided = sum(1 for row in rows if row["outcome"] != "refused")
                print(f"  {len(rows)}/{len(gold_rows)}  decided {decided}  "
                      f"unusable {len(rows) - decided}", flush=True)
    except ComeBackLater as error:
        print(f"\n{error}", file=sys.stderr)
        status = 3
    except CandidateFailed as error:
        print(f"\n{error}", file=sys.stderr)
        status = 1
    except KeyboardInterrupt:
        print("\ninterrupted — answers so far are saved; re-run to continue", file=sys.stderr)
        status = 3

    if status == 0 and len(rows) == len(gold_rows):
        document["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    save(path, document)
    decided = sum(1 for row in rows if row["outcome"] != "refused")
    print(f"{len(rows)}/{len(gold_rows)} answered by {document['model']} — {decided} decided, "
          f"{len(rows) - decided} unusable. Written to {path}")
    if status == 0:
        print(f"score it: python -m upto.evaluate.score {path}")
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
