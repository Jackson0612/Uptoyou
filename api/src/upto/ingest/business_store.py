"""Write the status publication and its tuples, or discover the content is already held.

`brand_store`'s mechanism, two sources over. Separate for the standing reason: the
statements and key columns are this schema's own.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from . import signature
from .foodtracer import Sheet
from .gcis import StatusRow

CHUNK = 5000

CLAIM_PUBLICATION = """
insert into business_status_publication
    (source, content_sha256, detected_at, payload_bytes, scope,
     column_signature, column_names)
values
    (:source, :content_sha256, :detected_at, :payload_bytes, :scope,
     :column_signature, :column_names)
on conflict (source, content_sha256) do nothing
returning id
"""

HELD_PUBLICATION = """
select id, content_sha256, detected_at
from business_status_publication
where source = :source and content_sha256 = :content_sha256
"""

INSERT_ROW = """
insert into business_status_row
    (publication_id, business_no, name_raw, status)
values
    (:publication_id, :business_no, :name_raw, :status)
on conflict (publication_id, business_no, name_raw, status) do nothing
"""


@dataclass(frozen=True)
class HeldPublication:
    publication_id: int
    content_sha256: str
    detected_at: datetime


class BusinessStore:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def held(self, source: str, content_sha256: str) -> Optional[HeldPublication]:
        result = await self._session.execute(
            text(HELD_PUBLICATION), {"source": source, "content_sha256": content_sha256}
        )
        return _held(result.fetchone())

    async def claim(self, sheet: Sheet, scope: str) -> Optional[int]:
        result = await self._session.execute(
            text(CLAIM_PUBLICATION),
            {
                "source": sheet.source,
                "content_sha256": sheet.content_sha256,
                "detected_at": sheet.detected_at,
                "payload_bytes": sheet.payload_bytes,
                "scope": scope,
                # D102 / M3: the file's own shape, taken at identify time. `NULL` on a
                # publication whose fetch predates the signature — nothing is backfilled.
                "column_signature": sheet.column_signature or None,
                "column_names": signature.as_json(sheet.column_names),
            },
        )
        return result.scalar()

    async def write(self, publication_id: int, rows: Sequence[StatusRow]) -> int:
        offered = 0
        for start in range(0, len(rows), CHUNK):
            batch = [
                {
                    "publication_id": publication_id,
                    "business_no": row.business_no,
                    "name_raw": row.name_raw,
                    "status": row.status,
                }
                for row in rows[start:start + CHUNK]
            ]
            if not batch:
                continue
            await self._session.execute(text(INSERT_ROW), batch)
            offered += len(batch)
        return offered

    async def accepted(self, publication_id: int) -> int:
        result = await self._session.execute(
            text("select count(*) from business_status_row where publication_id = :id"),
            {"id": publication_id},
        )
        return int(result.scalar() or 0)

    async def record_count(self, publication_id: int, status_rows: int) -> None:
        await self._session.execute(
            text("update business_status_publication set status_rows = :n where id = :id"),
            {"n": status_rows, "id": publication_id},
        )

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()


def _held(row) -> Optional[HeldPublication]:
    if row is None:
        return None
    return HeldPublication(
        publication_id=row.id,
        content_sha256=row.content_sha256,
        detected_at=row.detected_at,
    )
