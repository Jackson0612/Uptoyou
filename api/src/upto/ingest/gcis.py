"""The registry-status source — 商業登記(依營業項目別)-餐館業: the negative signal.

Ruled 2026-08-14 (D81). The FDA file provably keeps closed shops (93 of 松山區's 364
joinable rows are dead in this roster and still served), so this roster is kept for one
question only: **which 統編 the registry itself records as no longer operating.** The join
is `reference_place.business_no`, exact; no name from here is ever shown to anyone.

The fetch is `foodtracer.fetch_sheet` pointed at this dataset — a third government endpoint
whose chain carries the same missing-SKI CA defect, measured 2026-08-14 in the container
(strict context: CERTIFICATE_VERIFY_FAILED; relaxed: 200). Per-endpoint and measured,
never a habit; the endpoint also 406es a HEAD, so the GET is the only probe there is.

What the parse keeps is the distinct `(統編, 商業名稱, 登記狀態)` tuples:

  * The 統編 repeats — 2,189 of 206,611, sometimes across genuinely different businesses —
    so the tuple, not the number, is the unit. Reading a verdict out of the tuples is the
    read side's job and its rule lives with the read (see `live.py`).
  * The status is stored **verbatim, never normalised**: 歇業／撤銷 carries a full-width
    slash that is part of the label, and folding it would quietly split the read side's
    allowlist from the stored value.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from typing import List

from .foodtracer import FoodtracerUnavailable, Sheet, fetch_sheet, read_sheet  # noqa: F401

URL = "https://data.gcis.nat.gov.tw/od/file?oid=9D204D9C-9052-402F-B2B4-8B2DDC8F6835"

SOURCE = "gcis-restaurant-registry"
SCOPE = "登記狀態 / 全國餐館業"

BUSINESS_NO_COLUMN = "統一編號"
NAME_COLUMN = "商業名稱"
STATUS_COLUMN = "登記狀態"
REQUIRED_COLUMNS = (BUSINESS_NO_COLUMN, NAME_COLUMN, STATUS_COLUMN)


class GcisUnavailable(FoodtracerUnavailable):
    """The source did not answer usefully, or answered in a shape we do not know."""


@dataclass(frozen=True)
class StatusRow:
    business_no: str
    name_raw: str
    status: str


@dataclass
class StatusResult:
    rows: List[StatusRow] = field(default_factory=list)
    scanned: int = 0
    numbers: int = 0

    def line(self) -> str:
        return "{} rows scanned, {} distinct tuples across {} numbers".format(
            self.scanned, len(self.rows), self.numbers
        )


def fetch(now=None, opener=None) -> Sheet:
    """`foodtracer.fetch_sheet`, pointed at this dataset."""
    return fetch_sheet(now=now, opener=opener, source=SOURCE, url=URL)


def _require_columns(fieldnames) -> None:
    missing = [column for column in REQUIRED_COLUMNS if column not in (fieldnames or [])]
    if missing:
        raise GcisUnavailable(
            "{}: the CSV is missing {} — found {}".format(SOURCE, missing, list(fieldnames or []))
        )


def parse_statuses(raw: bytes) -> StatusResult:
    """Read the CSV down to its distinct tuples. **The expensive call, and the only one.**

    A row with no 統編 has nothing to join and is skipped rather than refused — unlike the
    storefront list this file is not site-level and carries no key of ours; three rows with
    an empty status existed on the measured file and are kept (an empty status is not in
    any dead set, so they quietly stay visible, which is the safe direction).
    """
    stream = io.TextIOWrapper(io.BytesIO(raw), encoding="utf-8-sig", newline="")
    reader = csv.DictReader(stream)
    _require_columns(reader.fieldnames)
    result = StatusResult()
    seen = set()
    for row in reader:
        result.scanned += 1
        business_no = (row.get(BUSINESS_NO_COLUMN) or "").strip()
        if not business_no:
            continue
        name_raw = (row.get(NAME_COLUMN) or "").strip()
        status = (row.get(STATUS_COLUMN) or "").strip()
        key = (business_no, name_raw, status)
        if key in seen:
            continue
        seen.add(key)
        result.rows.append(StatusRow(business_no=business_no, name_raw=name_raw, status=status))
    result.numbers = len({row.business_no for row in result.rows})
    if not result.rows:
        raise GcisUnavailable(
            "{}: the CSV parsed to no rows — {} were read".format(SOURCE, result.scanned)
        )
    return result
