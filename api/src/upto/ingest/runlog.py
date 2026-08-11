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

PUBLICATION_COLUMNS = {
    "F-D0047-061": "forecast_publication_id",
    "O-A0001-001": "observation_publication_id",
}
# Item 11's source string is longer and varies with the scope, so it is matched by prefix.
PLACE_COLUMN = "place_publication_id"

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
        """Which nullable foreign key this run's publication belongs in (D24's pattern)."""
        if self.publication_id is None:
            return None
        return PUBLICATION_COLUMNS.get(self.source, PLACE_COLUMN)


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
