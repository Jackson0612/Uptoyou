"""Write the storefront publication and its names, or discover the content is already held.

`brand_store`'s mechanism, one source over: the claim decides newness, one transaction
covers claim → write → count, and the module is separate because the statements and key
columns are this schema's own.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .foodtracer import Sheet
from .gradelist import StorefrontRow

CHUNK = 5000

CLAIM_PUBLICATION = """
insert into storefront_publication
    (source, content_sha256, detected_at, payload_bytes, scope)
values
    (:source, :content_sha256, :detected_at, :payload_bytes, :scope)
on conflict (source, content_sha256) do nothing
returning id
"""

HELD_PUBLICATION = """
select id, content_sha256, detected_at
from storefront_publication
where source = :source and content_sha256 = :content_sha256
"""

INSERT_NAME = """
insert into storefront_name
    (publication_id, registry_no, name, name_raw, grade)
values
    (:publication_id, :registry_no, :name, :name_raw, :grade)
on conflict (publication_id, registry_no) do nothing
"""


@dataclass(frozen=True)
class HeldPublication:
    publication_id: int
    content_sha256: str
    detected_at: datetime


class StorefrontStore:
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
            },
        )
        return result.scalar()

    async def write(self, publication_id: int, rows: Sequence[StorefrontRow]) -> int:
        offered = 0
        for start in range(0, len(rows), CHUNK):
            batch = [
                {
                    "publication_id": publication_id,
                    "registry_no": row.registry_no,
                    "name": row.name,
                    "name_raw": row.name_raw,
                    "grade": row.grade,
                }
                for row in rows[start:start + CHUNK]
            ]
            if not batch:
                continue
            await self._session.execute(text(INSERT_NAME), batch)
            offered += len(batch)
        return offered

    async def accepted(self, publication_id: int) -> int:
        result = await self._session.execute(
            text("select count(*) from storefront_name where publication_id = :id"),
            {"id": publication_id},
        )
        return int(result.scalar() or 0)

    async def record_count(self, publication_id: int, name_rows: int) -> None:
        await self._session.execute(
            text("update storefront_publication set name_rows = :n where id = :id"),
            {"n": name_rows, "id": publication_id},
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
