"""One name, one answer — or a refusal that says why. Pure: the model arrives as a callable.

**A value outside D38's list is refused, never repaired.** D39's condition 2 is the only
part of this process that can fail, and a coercion step would delete it: a model answering
"拉麵" would silently become 麵食, a wrong row wearing a right shape. The refusal is
returned rather than raised, because a batch of 3,324 places must not stop at the first
surprise — D63 rules that a row failing validation is recorded as pending, not written.

**The model's own noise is stripped before validation, and that is not the same as coercion.**
Trailing punctuation, a stray 「類別：」 prefix, whitespace — removing those recovers the
answer the model gave. Mapping one category onto another would replace it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from upto.classify.categories import CATEGORIES, is_valid
from upto.classify.prompt import (
    NO_SIGNAL,
    PROMPT_VERSION,
    RAG_PROMPT_VERSION,
    build,
    build_rag,
)

# Noise the model wraps an answer in. Anything beyond this list is a different answer,
# not a dirtier one.
_STRIP = "。．.,，、：: \n\r\t「」『』\"'*"


@dataclass(frozen=True)
class Classified:
    name: str
    category: str
    prompt_version: str


@dataclass(frozen=True)
class NoSignal:
    """The string names a legal entity, not a place — ruled 2026-08-14, stored as NULL.

    **Distinct from `Refused`, and the distinction is the whole point of the outcome.** Both
    write nothing, and they mean opposite things: this one is a *decision* the model reached
    and 其他 would have misreported as knowledge; a refusal is an answer we could not use.
    Collapsing them would repeat the error `ingest_run` was built to avoid — an absence and a
    failure inferred from the same silence.
    """

    name: str
    prompt_version: str


@dataclass(frozen=True)
class Refused:
    name: str
    raw: str
    reason: str
    prompt_version: str


def _clean(raw: str) -> str:
    answer = raw.strip().strip(_STRIP)
    prefix = "類別"
    if answer.startswith(prefix):
        answer = answer[len(prefix) :].strip().strip(_STRIP)
    # A model that explains anyway puts the answer first; take the first line only.
    return answer.splitlines()[0].strip() if answer else answer


def _asked(name: str, prompt: str, ask: Callable[[str], str],
           version: str) -> Classified | NoSignal | Refused:
    """Everything after the prompt is built: ask, strip the noise, decide the outcome.

    Shared by both entry points rather than copied into the retrieval one, because the three
    outcomes *are* D39's condition 2 — a second copy of this would be a second place for the
    refusal to be softened, and the whole value of the check is that there is one.
    """
    if not name.strip():
        return Refused(name=name, raw="", reason="empty name", prompt_version=version)
    raw = ask(prompt)
    answer = _clean(raw)
    if answer == NO_SIGNAL:
        return NoSignal(name=name, prompt_version=version)
    if not is_valid(answer):
        return Refused(
            name=name,
            raw=raw,
            reason=f"answer is not one of D38's {len(CATEGORIES)} values",
            prompt_version=version,
        )
    return Classified(name=name, category=answer, prompt_version=version)


def classify_name(name: str, ask: Callable[[str], str]) -> Classified | NoSignal | Refused:
    """Ask the model about one name. `ask` takes the prompt text and returns the raw answer."""
    return _asked(name, build(name), ask, PROMPT_VERSION)


def classify_name_rag(
    name: str, ask: Callable[[str], str], examples: list[tuple[str, str]]
) -> Classified | NoSignal | Refused:
    """D88: the same ask, with retrieved neighbours in the prompt and its own version stamped.

    **Validation is the shipped one, unchanged.** Retrieval is the only variable under test,
    so an answer this accepts is exactly an answer the backfill would have written and an
    answer it refuses is a row the backfill would have left pending — the property that makes
    an evaluation round mean anything about deployment.

    The caller supplies the examples. This function never queries: `upto.classify.examples`
    owns the store and the leave-one-out exclusion, and a prompt builder that reached a
    database would make the pure half of this package impure for one experiment.
    """
    return _asked(name, build_rag(name, examples), ask, RAG_PROMPT_VERSION)
