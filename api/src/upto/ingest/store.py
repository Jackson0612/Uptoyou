"""Write a Publication, or discover it is not new and say so quietly.

H14 is the hazard this file exists for: **an ingest that cannot be run twice.** The hourly
schedule guarantees the same content arrives repeatedly — about twenty of twenty-four daily
forecast runs carry nothing new (D42) — so "already have it" is the *normal* outcome and has
to be a silent success rather than an error or a duplicate row.

The mechanism is the unique constraint on (dataset_id, content_sha256), not a prior SELECT.
A check-then-insert is a race even with one worker, because a retry and a scheduled run can
overlap; `ON CONFLICT DO NOTHING` lets the database decide, which is the writer-that-is-not-
the-application argument PostgreSQL was chosen on (D5).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .cwa import FORECAST_DATASET, Publication


@dataclass(frozen=True)
class StoreResult:
    dataset_id: str
    content_sha256: str
    stored: bool          # False means the content was already held — a silent success
    publication_id: int | None
    rows_written: int

    def line(self) -> str:
        """One log line. A no-op has to read as success, not as a warning."""
        if not self.stored:
            return "{}: no change (hash {}…) — nothing published since the last run".format(
                self.dataset_id, self.content_sha256[:12]
            )
        return "{}: stored publication {} with {} readings (hash {}…)".format(
            self.dataset_id, self.publication_id, self.rows_written, self.content_sha256[:12]
        )


INSERT_PUBLICATION = """
insert into {table} (dataset_id, content_sha256, detected_at, payload_bytes)
values (:dataset_id, :content_sha256, :detected_at, :payload_bytes)
on conflict (dataset_id, content_sha256) do nothing
returning id
"""

INSERT_FORECAST_READING = """
insert into forecast_reading
    (publication_id, township, element, measure, slot_start, slot_end, value)
values (:publication_id, :township, :element, :measure, :slot_start, :slot_end, :value)
on conflict (publication_id, township, element, measure, slot_start) do nothing
"""

INSERT_OBSERVATION_READING = """
insert into observation_reading
    (publication_id, station_id, station_name, county, town, town_code, observed_at, element, value)
values (:publication_id, :station_id, :station_name, :county, :town, :town_code, :observed_at, :element, :value)
on conflict (publication_id, station_id, element, observed_at) do nothing
"""


async def store_publication(session: AsyncSession, publication: Publication) -> StoreResult:
    forecast = publication.dataset_id == FORECAST_DATASET
    table = "forecast_publication" if forecast else "observation_publication"

    inserted = await session.execute(
        text(INSERT_PUBLICATION.format(table=table)),
        {
            "dataset_id": publication.dataset_id,
            "content_sha256": publication.content_sha256,
            "detected_at": publication.detected_at,
            "payload_bytes": publication.payload_bytes,
        },
    )
    publication_id = inserted.scalar()

    if publication_id is None:
        # Already held. Nothing is written and nothing is wrong.
        await session.commit()
        return StoreResult(publication.dataset_id, publication.content_sha256, False, None, 0)

    if forecast:
        rows = [
            {
                "publication_id": publication_id,
                "township": row.township,
                "element": row.element,
                "measure": row.measure,
                "slot_start": row.slot_start,
                "slot_end": row.slot_end,
                "value": row.value,
            }
            for row in publication.forecast_rows
        ]
        statement = INSERT_FORECAST_READING
    else:
        rows = [
            {
                "publication_id": publication_id,
                "station_id": row.station_id,
                "station_name": row.station_name,
                "county": row.county,
                "town": row.town,
                "town_code": row.town_code,
                "observed_at": row.observed_at,
                "element": row.element,
                "value": row.value,
            }
            for row in publication.observation_rows
        ]
        statement = INSERT_OBSERVATION_READING

    if rows:
        await session.execute(text(statement), rows)
    await session.commit()
    return StoreResult(publication.dataset_id, publication.content_sha256, True, publication_id, len(rows))
