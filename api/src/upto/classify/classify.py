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
from upto.classify.prompt import PROMPT_VERSION, build

# Noise the model wraps an answer in. Anything beyond this list is a different answer,
# not a dirtier one.
_STRIP = "。．.,，、：: \n\r\t「」『』\"'*"


@dataclass(frozen=True)
class Classified:
    name: str
    category: str
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


def classify_name(name: str, ask: Callable[[str], str]) -> Classified | Refused:
    """Ask the model about one name. `ask` takes the prompt text and returns the raw answer."""
    if not name.strip():
        return Refused(name=name, raw="", reason="empty name", prompt_version=PROMPT_VERSION)
    raw = ask(build(name))
    answer = _clean(raw)
    if not is_valid(answer):
        return Refused(
            name=name,
            raw=raw,
            reason=f"answer is not one of D38's {len(CATEGORIES)} values",
            prompt_version=PROMPT_VERSION,
        )
    return Classified(name=name, category=answer, prompt_version=PROMPT_VERSION)
