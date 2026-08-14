"""Record that a run happened, whatever it found.

Ticket 09 needs a run that wrote nothing to be answerable, and D42 made writing nothing the
ordinary outcome — about twenty of item 10's twenty-four daily forecast runs. Before this
existed those runs were unrecoverable: item 10 had run roughly two dozen times and left seven
publications, and nothing said what the other runs did.

**A failure is not a no-op and the two are stored differently.** *no_change* means the source
answered and republished nothing; *failed* means it did not answer usefully. Inferred from an
absence they are indistinguishable, which is how a broken ingest looks healthy for a week.

**The row is written after the attempt, in its own transaction.** A run that fails must still
leave a record, so this cannot ride on the transaction the store rolled back.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

PLACE_COLUMN = "place_publication_id"

# D24's pattern: one nullable foreign key per source, so a run points at its own publication and
# at nothing else. **Every source is registered here by name, and an unregistered one is refused.**
#
# This was a `.get(source, PLACE_COLUMN)` fallback until 2026-08-12, and the comment above
# `PLACE_COLUMN` claimed item 11's source was "matched by prefix" — a mechanism that never existed.
# `fda.SOURCE` is `"fda-97"`: short, fixed, and reached only because it was the default. With three
# sources the fallback is invisible; the fourth one added without registering it would have been
# filed into item 11's column silently, which is H23's *degrades quietly* shape and worse than an
# error, because a wrong row cannot be told apart from a right one afterwards.
#
# `"fda-97"` is written out rather than imported from `upto.ingest.fda`: this module is imported by
# every runner and must not depend on any of them. **The duplicate can drift, and `test_runlog.py`
# asserts it has not.**
PUBLICATION_COLUMNS = {
    "F-D0047-061": "forecast_publication_id",
    "O-A0001-001": "observation_publication_id",
    "fda-97": PLACE_COLUMN,
    "taipei-foodtracer": "brand_publication_id",
}


class UnknownSource(LookupError):
    """A run carries a publication but its source is not registered above.

    Raised rather than defaulted. The caller cannot recover — there is no column this row belongs
    in — and guessing one writes a fact that reads as true. Registering a new source is one line;
    that friction is the point.
    """


STORED = "stored"
NO_CHANGE = "no_change"
FAILED = "failed"


@dataclass
class RunRecord:
    source: str
    started_at: datetime
    outcome: str
    rows_written: int = 0
    detail: str | None = None
    publication_id: int | None = None
    invoked_by: str | None = None

    def column(self) -> str | None:
        """Which nullable foreign key this run's publication belongs in (D24's pattern).

        `None` when the run holds no publication — a no-op and a failure both do, and revision
        0005's `ck_ingest_run_stored_has_publication` is what makes that structural rather than
        conventional.
        """
        if self.publication_id is None:
            return None
        try:
            return PUBLICATION_COLUMNS[self.source]
        except KeyError:
            raise UnknownSource(
                "no publication column is registered for source {!r}. Add it to "
                "PUBLICATION_COLUMNS; this is refused rather than defaulted because a "
                "publication filed under the wrong source cannot be told from a correct "
                "one afterwards.".format(self.source)
            ) from None


def now() -> datetime:
    return datetime.now(timezone.utc)


async def record(session, run: RunRecord) -> int:
    """Write the run row and return its id. Commits, because the caller may be about to exit."""
    from sqlalchemy import text

    column = run.column()
    columns = ["source", "started_at", "finished_at", "outcome", "rows_written", "detail", "invoked_by"]
    values = [":source", ":started_at", ":finished_at", ":outcome", ":rows_written", ":detail", ":invoked_by"]
    parameters = {
        "source": run.source,
        "started_at": run.started_at,
        "finished_at": now(),
        "outcome": run.outcome,
        # The CHECK refuses rows on a run that stored nothing, so the value is not merely
        # cosmetic — passing a count through on a no-op would fail the insert.
        "rows_written": run.rows_written if run.outcome == STORED else 0,
        "detail": run.detail,
        "invoked_by": run.invoked_by,
    }
    if column:
        columns.append(column)
        values.append(":publication_id")
        parameters["publication_id"] = run.publication_id

    statement = "insert into ingest_run ({}) values ({}) returning id".format(
        ", ".join(columns), ", ".join(values)
    )
    result = await session.execute(text(statement), parameters)
    run_id = result.scalar()
    await session.commit()
    return run_id
