"""A1 / D17 / D25 — erase what nobody agreed to keep, and what the retention window has passed.

Run inside the stack:

    docker compose exec api python -m upto.privacy.erase          # do it
    docker compose exec api python -m upto.privacy.erase --dry-run  # count only, delete nothing

**Why this exists as a job and not as a rule.** D17 makes persistence opt-in and D25 says a member
who revokes it must have the version history *erased, not merely closed*. H22 is only mitigated
when that erasure **runs** — a column recording the intention closes nothing. So this is scheduled
(`airflow/dags/preference_erasure.py`), and a privacy obligation that depended on someone
remembering to type a command would be the wrong shape.

**Two rules, and they are different rules rather than one with two dates.**

1. **`persist = false` rows are erased.** The member said "use this now, do not remember it". The
   row is written (so the round in force can read it and so the choice has provenance rather than
   being an absence), then removed.
2. **Rows older than the retention window are erased** — twelve months, one per pay cycle (D25).

**Neither rule may delete a row a round pinned, and the database is what enforces that.**
`weight_contribution.preference_id` is `ON DELETE RESTRICT` (revision 0022, D24's pattern), so a
version some round read cannot be removed however old it is. D25 says this in as many words:
*retention is a target, not a guarantee* — versions nothing points at are erased on schedule,
versions that were actually used outlive the window. **So this job filters those rows out itself
rather than letting the delete fail:** a job that raises on the first pinned row erases nothing
after it, which would turn a partial obligation into no obligation at all. The count of rows it
had to leave behind is printed, because "erased 40, left 3 that rounds still reference" is a true
statement about a privacy obligation and "erased 40" is not.

**Expiry is not deletion and this job does not touch it.** A budget band stops *contributing* at
month end (D25) and the member is prompted to re-affirm — the value stays visible on their own
screen, flagged `expired`, which is what `GET /circles/{id}/preferences` returns it for. Deleting
an expired band would remove the thing the re-affirmation prompt is meant to show.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import text

from upto.db import dispose_all, session_factory

# Twelve months, one per pay cycle (D25). Named rather than inlined: it is a policy number, and a
# policy number in the middle of a statement is a number nobody finds when the policy changes.
RETENTION = "12 months"

# `not exists` rather than a left join: the question is "does anything point at this row", and the
# planner can stop at the first hit. The subquery is what keeps a pinned version alive — the FK
# would refuse the delete anyway, and refusing mid-batch would abandon the rest of the work.
UNPINNED = (
    "not exists (select 1 from weight_contribution wc where wc.preference_id = preference.id)"
)

NOT_KEPT = "delete from preference where persist = false and {} returning id".format(UNPINNED)

EXPIRED_WINDOW = (
    "delete from preference where valid_from < now() - interval '{}' and {} returning id".format(
        RETENTION, UNPINNED
    )
)

# What had to be left behind, so the report is a true statement rather than a flattering one.
PINNED_NOT_KEPT = "select count(*) from preference where persist = false and not ({})".format(
    UNPINNED
)
PINNED_OVER_WINDOW = (
    "select count(*) from preference where valid_from < now() - interval '{}' and not ({})".format(
        RETENTION, UNPINNED
    )
)

COUNT_NOT_KEPT = "select count(*) from preference where persist = false and {}".format(UNPINNED)
COUNT_OVER_WINDOW = (
    "select count(*) from preference where valid_from < now() - interval '{}' and {}".format(
        RETENTION, UNPINNED
    )
)


async def run(dry_run: bool = False) -> int:
    Session = session_factory()
    try:
        async with Session() as session:
            if dry_run:
                not_kept = (await session.execute(text(COUNT_NOT_KEPT))).scalar()
                over_window = (await session.execute(text(COUNT_OVER_WINDOW))).scalar()
            else:
                not_kept = len((await session.execute(text(NOT_KEPT))).all())
                over_window = len((await session.execute(text(EXPIRED_WINDOW))).all())
            left_not_kept = (await session.execute(text(PINNED_NOT_KEPT))).scalar()
            left_over_window = (await session.execute(text(PINNED_OVER_WINDOW))).scalar()
            if not dry_run:
                await session.commit()
        verb = "would erase" if dry_run else "erased"
        print(
            "{} {} not-kept row(s) and {} past the {} window; left {} and {} that rounds still "
            "reference (D24's key, D25's 'retention is a target')".format(
                verb, not_kept, over_window, RETENTION,
                left_not_kept, left_over_window,
            ),
            flush=True,
        )
        return 0
    finally:
        await dispose_all()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="count what would go and delete nothing")
    arguments = parser.parse_args()
    return asyncio.run(run(dry_run=arguments.dry_run))


if __name__ == "__main__":
    sys.exit(main())
