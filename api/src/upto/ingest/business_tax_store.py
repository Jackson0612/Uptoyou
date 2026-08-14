"""Write the tax publication and its matched rows, or discover the content is already held.

`fda_store`'s mechanism — the claim decides newness, one transaction covers claim → write →
count — with one method the earlier stores have no use for: `reference_business_nos`, which
reads the set of 統編 the parse is allowed to keep. **That set is read from the database at run
time and never configured**, because it is a fact about what item 11 last stored rather than a
setting anybody should be able to disagree with.

Separate from the sibling stores for the standing reason: the statements and the key columns
are this schema's own, and one writer serving two schemas is one file pretending they are one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import List, Optional, Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .fia import INDUSTRY_COLUMNS, TaxArchive, TaxRow

# One executemany per chunk, as in `fda_store`: about 14.5k rows arrive, and chunking bounds
# how much is in flight without changing the fact that it is all one transaction.
CHUNK = 5000

CLAIM_PUBLICATION = """
insert into business_tax_publication
    (source, content_sha256, file_stamp, detected_at, payload_bytes,
     entry_name, entry_bytes, scope)
values
    (:source, :content_sha256, :file_stamp, :detected_at, :payload_bytes,
     :entry_name, :entry_bytes, :scope)
on conflict (source, content_sha256) do nothing
returning id
"""

LATEST_PUBLICATION = """
select id, content_sha256, file_stamp, detected_at
from business_tax_publication
where source = :source
order by detected_at desc, id desc
limit 1
"""

HELD_PUBLICATION = """
select id, content_sha256, file_stamp, detected_at
from business_tax_publication
where source = :source and content_sha256 = :content_sha256
"""

# The filter set, and the whole of the storage ruling in one statement: the 統編 of the latest
# place publication. `distinct` because one business may hold several 食品業者登錄 sites, and
# `is not null` because a reference row without a 統編 has nothing to offer this join.
REFERENCE_BUSINESS_NOS = """
select distinct business_no
from reference_place
where business_no is not null
  and publication_id = (select id from place_publication order by detected_at desc limit 1)
"""

INSERT_ROW = """
insert into business_tax_row
    (publication_id, business_no, tax_name, address,
     industry_code, industry_name, industry_code_1, industry_name_1,
     industry_code_2, industry_name_2, industry_code_3, industry_name_3)
values
    (:publication_id, :business_no, :tax_name, :address,
     :industry_code, :industry_name, :industry_code_1, :industry_name_1,
     :industry_code_2, :industry_name_2, :industry_code_3, :industry_name_3)
on conflict (publication_id, business_no) do nothing
"""


@dataclass(frozen=True)
class HeldPublication:
    publication_id: int
    content_sha256: str
    file_stamp: Optional[date]
    detected_at: datetime


class BusinessTaxStore:
    """The database half, behind the methods the run's sequencing needs — and no more.

    A class rather than functions for `fda_store`'s reason: the property this ingest turns on
    is *claim first, parse only if the claim succeeded*, and that is invisible from outside a
    running database unless the store can be stood in for.
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

    async def reference_business_nos(self) -> List[str]:
        """Every 統編 the latest place publication carries. The parse keeps these and no others.

        An empty answer is returned as it is rather than dressed up: the parse refuses on it,
        with a message saying item 11 has to have run first, which is the true diagnosis.
        """
        result = await self._session.execute(text(REFERENCE_BUSINESS_NOS))
        return [row[0] for row in result.fetchall()]

    async def claim(self, archive: TaxArchive, scope: str) -> Optional[int]:
        """Insert the publication, or learn that this content is already held.

        `None` means the hash collided, which is the ordinary outcome on the days the publisher
        has cut no new extract, and is a success.
        """
        result = await self._session.execute(
            text(CLAIM_PUBLICATION),
            {
                "source": archive.source,
                "content_sha256": archive.content_sha256,
                "file_stamp": archive.file_stamp,
                "detected_at": archive.detected_at,
                "payload_bytes": archive.payload_bytes,
                "entry_name": archive.entry_name,
                "entry_bytes": archive.entry_bytes,
                "scope": scope,
            },
        )
        return result.scalar()

    async def write(self, publication_id: int, rows: Sequence[TaxRow]) -> int:
        """Write the matched rows. Returns rows *offered*, not rows accepted.

        The difference matters under `--force-parse`, where every row collides with the one
        already there and the database accepts none of them. The caller reports both numbers,
        so the two are never confused.
        """
        offered = 0
        for start in range(0, len(rows), CHUNK):
            batch = [_parameters(publication_id, row) for row in rows[start:start + CHUNK]]
            if not batch:
                continue
            await self._session.execute(text(INSERT_ROW), batch)
            offered += len(batch)
        return offered

    async def accepted(self, publication_id: int) -> int:
        """How many rows the publication actually holds — asked after the write, not inferred."""
        result = await self._session.execute(
            text("select count(*) from business_tax_row where publication_id = :id"),
            {"id": publication_id},
        )
        return int(result.scalar() or 0)

    async def record_count(self, publication_id: int, tax_rows: int) -> None:
        await self._session.execute(
            text("update business_tax_publication set tax_rows = :n where id = :id"),
            {"n": tax_rows, "id": publication_id},
        )

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        """End the transaction a no-op run opened. Nothing was written; nothing is wrong."""
        await self._session.rollback()


def _parameters(publication_id: int, row: TaxRow) -> dict:
    """One row's parameters. The four 行業 pairs stay positional — see 0017's note."""
    parameters = {
        "publication_id": publication_id,
        "business_no": row.business_no,
        "tax_name": row.tax_name,
        "address": row.address,
    }
    # Every slot is named first, so a row carrying fewer than four pairs writes NULLs rather
    # than raising on a parameter the statement asked for and nobody supplied.
    for index in range(len(INDUSTRY_COLUMNS)):
        suffix = "" if index == 0 else "_{}".format(index)
        parameters["industry_code" + suffix] = None
        parameters["industry_name" + suffix] = None
    for index, industry in enumerate(row.industries):
        suffix = "" if index == 0 else "_{}".format(index)
        parameters["industry_code" + suffix] = industry.code
        parameters["industry_name" + suffix] = industry.name
    return parameters


def _held(row) -> Optional[HeldPublication]:
    if row is None:
        return None
    return HeldPublication(
        publication_id=row.id,
        content_sha256=row.content_sha256,
        file_stamp=row.file_stamp,
        detected_at=row.detected_at,
    )
