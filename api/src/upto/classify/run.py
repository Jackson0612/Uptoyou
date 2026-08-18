"""D75's backfill: one township, materialised then classified, with provenance on every row.

Run inside the stack, with the model service up (it is behind a compose profile):

    docker compose --profile model up -d ollama
    docker compose exec api python -m upto.classify.run 63000010

**With D88's crib (owner-ruled 2026-08-18, the backfill configuration):**

    docker compose exec api python -m upto.classify.run 63000090 --rag --embed arctic --k 5

`--rag` asks through `classify_name_rag` with the k nearest labelled names from
`example_embedding` in the prompt, and the row's stored `category_prompt_version` becomes the
RAG one — so provenance says which prompt decided, without anyone recording it by hand (D39,
D80). The crib must be loaded for that embedder first (`python -m upto.classify.examples load
--embed arctic`); a crib built from a different `testset_v1.json` is **refused**, not used, for
the reason D88 gives.

**The asked name is excluded from its own retrieval, and here that is not about scoring.** The
crib is the teacher's frozen set — 200 松山 names with their labels — so re-running 松山 with
retrieval would hand the model **the answer key** for any name that is also a crib row, and the
category written to `place` would be a copy of the label rather than a verdict. `nearest(
exclude_name=...)` removes every copy of the asked string within the embedder (0019's UNIQUE),
which is what keeps a re-run a re-run. The evaluation path excludes for a different reason —
a score of the lookup rather than the classifier — and the two reasons want the same line.

Two passes, in this order and for a reason:

1. **Materialise (D76).** Every `reference_place` in the township that has no `place` row
   gets one — origin `reference`, the 登錄字號 and nothing else, which is D28's shape. The
   category then has one home, 0007's own columns.
2. **Classify.** Every place in that township not yet decided is sent to the model one at a
   time — asked about **the best name this project holds** (D80: storefront sign → single
   brand → registered name), validated against D38's ten values, and written **with the
   prompt version, the model name and the asked string** (D39's condition 3, plus 0015's
   `category_input`). A legal-entity verdict is written as a **decided absence** (D79):
   provenance present, category NULL, so the next pass skips it — the measured cost this
   replaces was ~1,060 re-asks, an hour of inference per re-run. An answer outside the
   list is still not written and not coerced — a refusal is not a decision.

**The model's absence is ordinary, not an error.** The service is off unless a backfill is
running, so this exits 3 and says so, having written nothing. Exit 0 means the pass ran —
including the pass that had nothing left to do.

**Committed in batches rather than at the end**, because 3,324 places is roughly seven hours
and a crash at hour six must not throw away hour one. Each batch is a transaction; a
re-run resumes at the first unclassified row, which is what makes this safe to interrupt.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone

from sqlalchemy import text

from upto.api_common import SINGLE_BRAND, STOREFRONT
from upto.classify.classify import Classified, NoSignal, classify_name, classify_name_rag
from upto.classify.model import MODEL, available, ask
from upto.classify.prompt import PROMPT_VERSION, RAG_PROMPT_VERSION
from upto.db import dispose_all, session_factory

BATCH = 25


class CribUnavailable(Exception):
    """The crib cannot be used for this run, and nothing has been written.

    Kept apart from a missing model service: that is exit 3 and ordinary (the profile is off),
    while a stale or absent crib is a thing someone has to go and load. Both leave the database
    untouched, so neither is a partial pass.
    """


async def crib_retriever(session, embed_key: str, k: int):
    """Return `async retrieve(name) -> list[tuple]`, or raise `CribUnavailable`.

    Everything that can be wrong is checked **before the first row is asked**, because a
    backfill that discovers on row 900 that its crib was stale has written 900 rows whose
    provenance says RAG and whose neighbours were nonsense.

    Imported lazily: a plain backfill does not pull the embedding client or the evaluation
    package in at all, and `--rag` is the only thing that needs either.
    """
    from upto.classify import embed as embedding  # noqa: PLC0415
    from upto.classify import examples as example_store  # noqa: PLC0415
    from upto.evaluate.score import load_testset  # noqa: PLC0415

    embed_model = embedding.resolve(embed_key)
    if not embedding.available(embed_model):
        raise CribUnavailable(
            "the embedding model {} is not reachable — it sits behind the same compose profile "
            "as the classifier, and a RAG backfill needs both: `docker compose --profile model "
            "up -d ollama`".format(embed_model)
        )

    # D88: the crib is a derived cache of the frozen set, and a round refuses one built from a
    # different file. A backfill has more at stake than a round — it writes to `place` — so it
    # refuses on the same rule rather than a looser one.
    _rows, digest = load_testset()
    stored = await example_store.stored_sha(session, embed_model)
    if stored is None:
        raise CribUnavailable(
            "example_embedding holds no {} rows — the crib has never been loaded for this "
            "embedder. `docker compose exec api python -m upto.classify.examples load --embed "
            "{}` first; `… examples status` lists what is loaded.".format(embed_model, embed_key)
        )
    if stored != digest:
        raise CribUnavailable(
            "example_embedding's {} rows were built from test set {} and the file now hashes to "
            "{} — a label was amended under the crib. Re-load it before backfilling.".format(
                embed_model, stored, digest
            )
        )

    async def retrieve(name: str) -> list:
        """The k nearest labelled names, nearest first, **never including this one**."""
        vector = embedding.embed([name], model=embed_model)[0]
        rows = await example_store.nearest(
            session, vector, embed_model, k=k, exclude_name=name
        )
        # (name, label, subtype) — the third slot is what `prompt._example_line` prints as
        # 「類別（細分類）」 when the store holds one, so passing it costs nothing and keeps the
        # backfill's prompt byte-identical to the evaluated one.
        return [(row["name"], row["label"], row.get("subtype")) for row in rows]

    return retrieve, embed_model


async def clear_superseded(session, township_code: str, version: str) -> int:
    """Rows generated by an older prompt are cleared so this pass re-does them.

    D39 says two prompt versions are compared by re-running rather than by trusting either;
    a column holding both answers a different question per row, which is the shape this
    project refuses everywhere else. The provenance goes with the value — all four columns
    or none, which 0007's CHECK enforces anyway.

    **The version is a parameter, so `--rag` clears the plain prompt's rows and a plain run
    clears the crib's — the same rule in both directions rather than one privileged prompt.**
    That is also what makes the ruled 松山 re-run a single command: the township's 3,290 v4 rows
    are cleared and re-decided under the crib, so `category_model` and
    `category_prompt_version` end up single-valued without anyone deleting anything by hand.
    **It is a real footgun and worth knowing before you type it:** pointing `--rag` at a
    township clears that township's existing verdicts. Nothing is lost that a completed pass
    does not replace, and an interrupted pass leaves the cleared rows pending, which the next
    run picks up (that is the same resumability the batching exists for) — but a run started
    by accident does spend the inference again.
    """
    cleared = (
        await session.execute(
            text(
                "update place p set category = null, category_model = null, "
                "category_prompt_version = null, category_generated_at = null, "
                "category_input = null "
                "from reference_place rp "
                "where rp.registry_no = p.registry_no and rp.township_code = :tc "
                "and p.category_prompt_version is not null "
                "and p.category_prompt_version <> :v returning p.id"
            ),
            {"tc": township_code, "v": version},
        )
    ).scalars().all()
    await session.commit()
    return len(cleared)


async def materialise(session, township_code: str) -> int:
    """D76: give the township's reference places their rows. Idempotent by 0007's index."""
    created = (
        await session.execute(
            text(
                "insert into place (origin, registry_no) "
                "select 'reference', rp.registry_no from reference_place rp "
                "where rp.publication_id = ("
                "  select id from place_publication order by detected_at desc limit 1"
                ") and rp.township_code = :tc "
                "and not exists ("
                "  select 1 from place p where p.origin = 'reference' "
                "  and p.registry_no = rp.registry_no"
                ") returning id"
            ),
            {"tc": township_code},
        )
    ).scalars().all()
    await session.commit()
    return len(created)


async def pending(session, township_code: str) -> list[tuple[int, str]]:
    """Places in this township not yet decided, each under the best name this project holds.

    **Undecided is `category_generated_at is null`, not `category is null`** — D79's decided
    absence carries provenance and no category, and re-asking it every pass is the measured
    hour this distinction exists to stop.

    **The name is D80's ladder: storefront sign → single brand → registered name** — the
    same precedence the screens read, because 悠旅生活事業股份有限公司 asked as itself is a
    legal entity, and asked as STARBUCKS COFFEE is a place with a category. The asked string
    goes into `category_input`, because the ladder's answer drifts as publications update
    and a stored verdict must say what it was a verdict about.
    """
    rows = (
        await session.execute(
            text(
                "select p.id, coalesce(storefront.name, brand.brand_name, rp.name) as name "
                "from place p "
                "join reference_place rp on rp.registry_no = p.registry_no "
                "left join lateral ("
                + STOREFRONT.format(registry="p.registry_no")
                + ") storefront on true "
                "left join lateral (" + SINGLE_BRAND.format(company="rp.name") + ") brand on true "
                "where p.origin = 'reference' and p.category_generated_at is null "
                "and rp.township_code = :tc "
                "and rp.publication_id = ("
                "  select id from place_publication order by detected_at desc limit 1"
                ") order by p.id"
            ),
            {"tc": township_code},
        )
    ).all()
    return [(row.id, row.name) for row in rows]


async def main(township_code: str, rag: bool = False, embed_key: str = "bge",
               k: int = 5) -> int:
    Session = session_factory()
    retrieve = None
    embed_model = None
    try:
        if not available():
            print(
                f"model {MODEL} is not reachable — the service is behind a compose profile "
                "and is off unless a backfill is running. Nothing was written.",
                file=sys.stderr,
            )
            return 3

        version = RAG_PROMPT_VERSION if rag else PROMPT_VERSION

        # Everything the crib needs is checked before a single row is materialised, so a stale
        # crib costs nothing at all rather than a cleared township waiting to be re-done.
        if rag:
            async with Session() as session:
                try:
                    retrieve, embed_model = await crib_retriever(session, embed_key, k)
                except CribUnavailable as failure:
                    print(str(failure), file=sys.stderr)
                    return 3

        async with Session() as session:
            created = await materialise(session, township_code)
            cleared = await clear_superseded(session, township_code, version)
            todo = await pending(session, township_code)
        print(
            f"township {township_code}: {created} rows created, {cleared} cleared from an "
            f"older prompt, {len(todo)} to classify with {version}"
            + (f", {k} examples each retrieved by {embed_model}" if rag else "")
        )

        done = no_signal = refused = 0
        for start in range(0, len(todo), BATCH):
            batch = todo[start : start + BATCH]
            results = []
            for place_id, name in batch:
                if retrieve is None:
                    outcome = classify_name(name, ask)
                else:
                    outcome = classify_name_rag(name, ask, await retrieve(name))
                if isinstance(outcome, Classified):
                    results.append((place_id, name, outcome.category, outcome.prompt_version))
                elif isinstance(outcome, NoSignal):
                    # A legal entity, not a place. D79: written as a decided absence —
                    # provenance and the asked string, category NULL — so the next pass
                    # skips it instead of paying for this answer again. Counted apart from
                    # a refusal because they mean opposite things.
                    results.append((place_id, name, None, outcome.prompt_version))
                    no_signal += 1
                else:
                    refused += 1
            async with Session() as session:
                for place_id, asked, category, version in results:
                    await session.execute(
                        text(
                            "update place set category = :c, category_model = :m, "
                            "category_prompt_version = :v, category_generated_at = :t, "
                            "category_input = :i where id = :id"
                        ),
                        {
                            "c": category,
                            "m": MODEL,
                            "v": version,
                            "t": datetime.now(timezone.utc),
                            "i": asked,
                            "id": place_id,
                        },
                    )
                await session.commit()
            done += sum(1 for r in results if r[2] is not None)
            seen = done + no_signal + refused
            print(
                f"  {seen}/{len(todo)}  written {done}  legal-entity {no_signal}  "
                f"unusable {refused}",
                flush=True,
            )

        print(
            f"done: {done} classified, {no_signal} decided legal entities (recorded, not "
            f"re-asked), {refused} unusable answers left pending"
        )
        return 0
    finally:
        await dispose_all()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="D75's backfill for one township, optionally with D88's crib."
    )
    parser.add_argument("township_code", help="the 8-digit 內政部 code, e.g. 63000090")
    parser.add_argument("--rag", action="store_true",
                        help="ask with the k nearest labelled names in the prompt (D88)")
    parser.add_argument("--embed", default="bge", dest="embed_key",
                        help="which embedder's crib to retrieve from: bge | qwen3e | arctic")
    parser.add_argument("--k", type=int, default=5,
                        help="how many neighbours to retrieve (1..20); ignored without --rag")
    arguments = parser.parse_args()
    if arguments.rag and not 1 <= arguments.k <= 20:
        # Refused rather than clamped, for the reason M10's runner refuses it: a silently
        # trimmed k would write provenance that disagreed with what was actually retrieved.
        parser.error("--k must be between 1 and 20; {} was asked for".format(arguments.k))
    raise SystemExit(asyncio.run(main(
        arguments.township_code, rag=arguments.rag, embed_key=arguments.embed_key,
        k=arguments.k,
    )))
