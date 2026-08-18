"""Write item 11's publication and its places, or discover the content is already held.

Item 10's writer is `store.py`, and the names are asymmetric because that one was written
when there was one ingest. They are separate modules rather than one because they share no
code: the statements, the key columns and the result each ingest reports are different, and a
single writer serving both would be one file pretending two schemas are one.

**What they do share is the mechanism, and it is the important half.** The publication is
claimed with `insert … on conflict (source, content_sha256) do nothing returning id`, so the
*database* decides whether the content is new. A prior `select` would be a race even with one
worker — a retry and a scheduled run can overlap — and it would also make the short-circuit a
discipline of the code rather than a property of the data, which is what D18 and H14 both
refuse.

**The claim is what gates the expensive work.** A caller that gets `None` back has learned,
for the price of one insert, that it must not decompress 99 MB (D34). Everything about this
module's shape follows from wanting that fact before the parse rather than after it.

**One transaction covers claim → write → counts.** A crash in the middle leaves no publication
row at all, which is better than a publication whose places are half-written and whose count
column says so.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from . import signature
from .fda import Archive, PlaceRow

# One executemany per chunk. A single 36,499-parameter-set statement is one round trip that
# either works or fails whole; chunking bounds how much is in flight at once. Still one
# transaction, so nothing about atomicity changes.
CHUNK = 5000

CLAIM_PUBLICATION = """
insert into place_publication
    (source, content_sha256, archive_stamp, detected_at, payload_bytes,
     entry_name, entry_bytes, scope, column_signature, column_names)
values
    (:source, :content_sha256, :archive_stamp, :detected_at, :payload_bytes,
     :entry_name, :entry_bytes, :scope, :column_signature, :column_names)
on conflict (source, content_sha256) do nothing
returning id
"""

LATEST_PUBLICATION = """
select id, content_sha256, archive_stamp, detected_at
from place_publication
where source = :source
order by detected_at desc, id desc
limit 1
"""

HELD_PUBLICATION = """
select id, content_sha256, archive_stamp, detected_at
from place_publication
where source = :source and content_sha256 = :content_sha256
"""

INSERT_PLACE = """
insert into reference_place
    (publication_id, registry_no, origin, name, name_raw, address, address_raw,
     business_no, township_code, township_name)
values
    (:publication_id, :registry_no, :origin, :name, :name_raw, :address, :address_raw,
     :business_no, :township_code, :township_name)
on conflict (publication_id, registry_no) do nothing
"""

RECORD_COUNTS = """
update place_publication
set place_rows = :place_rows, unresolved_township_rows = :unresolved_township_rows
where id = :publication_id
"""


@dataclass(frozen=True)
class HeldPublication:
    publication_id: int
    content_sha256: str
    archive_stamp: Optional[datetime]
    detected_at: datetime


class PlaceStore:
    """The database half, kept behind four methods so the run's sequencing can be tested.

    The sequencing — claim first, parse only if the claim succeeded — is the property this
    ticket turns on, and it is invisible from outside a running database unless the store can
    be stood in for. That is the only reason this is a class rather than four functions.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def latest(self, source: str) -> Optional[HeldPublication]:
        """The most recently detected publication, for the stamp-versus-hash comparison."""
        result = await self._session.execute(text(LATEST_PUBLICATION), {"source": source})
        return _held(result.fetchone())

    async def held(self, source: str, content_sha256: str) -> Optional[HeldPublication]:
        result = await self._session.execute(
            text(HELD_PUBLICATION), {"source": source, "content_sha256": content_sha256}
        )
        return _held(result.fetchone())

    async def claim(self, archive: Archive, scope: str) -> Optional[int]:
        """Insert the publication, or learn that this content is already held.

        `None` means the hash collided, which is the ordinary outcome on twenty-nine days out
        of thirty (D34) and is a success.
        """
        result = await self._session.execute(
            text(CLAIM_PUBLICATION),
            {
                "source": archive.source,
                "content_sha256": archive.content_sha256,
                "archive_stamp": archive.archive_stamp,
                "detected_at": archive.detected_at,
                "payload_bytes": archive.payload_bytes,
                "entry_name": archive.entry_name,
                "entry_bytes": archive.entry_bytes,
                "scope": scope,
                # D102 / M3: the CSV's own header, read at identify time. `NULL` on a
                # publication whose fetch predates the signature — nothing is backfilled.
                "column_signature": archive.column_signature or None,
                "column_names": signature.as_json(archive.column_names),
            },
        )
        return result.scalar()

    async def write(self, publication_id: int, rows: Sequence[PlaceRow]) -> int:
        """Write the places. Returns the number of rows offered, not the number accepted.

        The difference matters exactly once: under `--force-parse`, every row collides with the
        one already there and the database accepts none of them, which is H14's test passing.
        The caller reports both, so the two are never confused.
        """
        offered = 0
        for start in range(0, len(rows), CHUNK):
            batch = [
                {
                    "publication_id": publication_id,
                    "registry_no": row.registry_no,
                    "origin": row.origin,
                    "name": row.name,
                    "name_raw": row.name_raw,
                    "address": row.address,
                    "address_raw": row.address_raw,
                    "business_no": row.business_no,
                    "township_code": row.township_code,
                    "township_name": row.township_name,
                }
                for row in rows[start:start + CHUNK]
            ]
            if not batch:
                continue
            await self._session.execute(text(INSERT_PLACE), batch)
            offered += len(batch)
        return offered

    async def accepted(self, publication_id: int) -> int:
        """How many rows the publication actually holds — asked after the write, not inferred."""
        result = await self._session.execute(
            text("select count(*) from reference_place where publication_id = :id"),
            {"id": publication_id},
        )
        return int(result.scalar() or 0)

    async def record_counts(self, publication_id: int, place_rows: int, unresolved: int) -> None:
        await self._session.execute(
            text(RECORD_COUNTS),
            {
                "publication_id": publication_id,
                "place_rows": place_rows,
                "unresolved_township_rows": unresolved,
            },
        )

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        """End the transaction a no-op run opened. Nothing was written; nothing is wrong."""
        await self._session.rollback()


def _held(row) -> Optional[HeldPublication]:
    if row is None:
        return None
    return HeldPublication(
        publication_id=row.id,
        content_sha256=row.content_sha256,
        archive_stamp=row.archive_stamp,
        detected_at=row.detected_at,
    )
