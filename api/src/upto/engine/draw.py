"""D108's draw — the round's randomness is committed at open and revealed on the first tap.

*Written 2026-08-19 on the owner's ruling (「採用」, D108 at `34e8e61`).*

**The problem this solves.** Every member rolls, all the rolls are shown, and exactly one decides.
The previous concept drew a deciding member at round open and named them before any dice; it was
sound on fairness and had a liveness hole — **if the named member never tapped, the round could not
close**, and D91 forbids re-drawing once dice are visible, so there was no honest fallback.

**The mechanism.** At round open the server draws a 32-byte `seed`, stores it, and publishes only
`sha256(seed)`. **Places are proposed after the round opens**, so the server committed to its
randomness *before it knew what the places would be* — that is what makes the commitment
unforgeable rather than merely hidden, and it is the whole argument. Every member's pair, and which
member's pair decides, are derived from that seed. At close the seed is revealed and anyone can
recompute the lot and check it against the commitment.

**Why the liveness hole disappears rather than shrinking.** The outcome exists from the moment the
round opens, so **the round can close on the first tap by anyone**. A member who never taps sees
their own die never animate and changes nothing. There is no timer, nobody waits on anybody, and no
fallback has to be justified — which is a property the previous design could not have at any price.

**What must never happen: the seed reaching a payload before close.** A member holding the seed can
compute the winner and then choose whether to tap, which is exactly the preference D91 forbids —
the same last-revealer attack that ruled out per-member commit–reveal. `outcome_seed` is server-side
only until the round is closed, and `api_common` is where that is enforced rather than here.

**Bias, taken seriously because this is the fairness core.** `byte % 6` is not uniform: 256 is not a
multiple of 6, so values 0–3 come up once more often than 4–5 over the byte range. The skew is small
and it is *free* to remove, so it is removed — this module rejects bytes at or above the largest
multiple of the range and walks on. `int(digest) % 36` would also have been defensible at a bias
around 2**-250, but "defensible bias" is a sentence nobody should have to evaluate about a die.

Run the tests: `python3 app/api/tests/test_draw.py` (no network, no database)
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

SEED_BYTES = 32

# Domain separation. Two different questions asked of one seed must never be able to return the same
# stream — if the decider and a member's pair were derived from the same message, a member id that
# happened to collide with the decider label would tie them together. The labels are bytes rather
# than str so the message is exactly what it looks like.
LABEL_DECIDER = b"decider"
LABEL_MEMBER = b"member:"


def new_seed() -> bytes:
    """A fresh 32-byte seed. `secrets`, never `random` — this decides where people eat."""
    return secrets.token_bytes(SEED_BYTES)


def commitment(seed: bytes) -> str:
    """`sha256(seed)`, hex. This is the only thing that may leave the server before close."""
    return hashlib.sha256(seed).hexdigest()


def _stream(seed: bytes, message: bytes) -> bytes:
    """An HMAC block for one question, extended deterministically if a caller drains it.

    Extension is by counter rather than by re-hashing the previous block, so block *n* can be
    derived without deriving 1..n-1 — which keeps a recomputation by hand (the evaluator's, per the
    ruling) a matter of one HMAC per value rather than a chain.
    """
    block = hmac.new(seed, message, hashlib.sha256).digest()
    counter = 0
    while True:
        yield_from = block
        for byte in yield_from:
            yield byte
        counter += 1
        block = hmac.new(seed, message + b"|" + str(counter).encode(), hashlib.sha256).digest()


def _below(seed: bytes, message: bytes, bound: int, skip: int = 0) -> int:
    """A uniform integer in `[0, bound)`, by rejection over the HMAC stream.

    `skip` consumes that many accepted values first, which is how two dice come out of one question
    without deriving two questions: die 1 is the first accepted value, die 2 the second. **Rejected
    bytes are not counted** — only accepted ones — because a recomputation has to be able to follow
    the same path, and "how many bytes did we throw away" is not something a person can guess.
    """
    if bound < 1:
        raise ValueError("bound must be at least 1")
    limit = (256 // bound) * bound  # the largest multiple of `bound` that fits in a byte
    seen = 0
    for byte in _stream(seed, message):
        if byte >= limit:
            continue  # would skew the low end of the range; walk on rather than fold it in
        if seen == skip:
            return byte % bound
        seen += 1
    raise AssertionError("unreachable: the stream is unbounded")  # pragma: no cover


def pair_for_member(seed: bytes, member_id: int) -> tuple[int, int]:
    """The two dice this member's tap reveals. Fixed at open, unaffected by who taps or when."""
    message = LABEL_MEMBER + str(member_id).encode()
    return (_below(seed, message, 6) + 1, _below(seed, message, 6, skip=1) + 1)


def deciding_member(seed: bytes, member_ids: list[int]) -> int:
    """Which member's pair counts.

    **Sorted, always.** The caller's ordering must not be able to change the outcome — a list that
    arrived in `rolled_at` order would make the decider depend on who tapped first, which is the
    very thing the commitment exists to prevent. Sorting makes the answer a function of the *set*.
    """
    if not member_ids:
        raise ValueError("a round with no members has no decider")
    ordered = sorted(set(member_ids))
    return ordered[_below(seed, LABEL_DECIDER, len(ordered))]


def deciding_pair(seed: bytes, member_ids: list[int]) -> tuple[int, int]:
    """The round's dice: the deciding member's own pair, never a separate draw.

    So «the stored result's dice equal that member's pair» is true by construction rather than by a
    second derivation that could disagree with the first.
    """
    return pair_for_member(seed, deciding_member(seed, member_ids))


def verify(seed_hex: str, commitment_hex: str) -> bool:
    """Does a revealed seed match what was published at open? The whole claim, in one line."""
    try:
        seed = bytes.fromhex(seed_hex)
    except ValueError:
        return False
    return hmac.compare_digest(commitment(seed), commitment_hex)
