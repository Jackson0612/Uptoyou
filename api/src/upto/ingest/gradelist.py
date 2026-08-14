"""The storefront source — 臺北市餐飲衛生分級評核: the only site-level name this project has.

Ruled 2026-08-14 (D78). An inspector stood in the shop and recorded the sign — 業者名稱店名 —
beside the same 食品業者登錄字號 the FDA rows carry, so the join is the registry number
itself and no name matching happens at all. Measured before ruling: 1,686 rows, zero missing
and zero duplicated registry numbers, 99.1% storefront-style names, 1,379 joining the
current FDA publication, 105 of them in 松山區.

The fetch, the identity and the TLS relaxation are `foodtracer`'s, imported rather than
copied — same host, same bare-CSV shape, same missing-SKI certificate chain. What is this
module's own is the parse: site rows rather than company pairs.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from typing import List

from .fda import normalise
from .foodtracer import FoodtracerUnavailable, Sheet, fetch_sheet, read_sheet  # noqa: F401

# data.taipei resource under dataset 59579c19… (臺北市通過餐飲衛生管理分級評核業者).
URL = (
    "https://data.taipei/api/frontstage/tpeod/dataset/resource.download"
    "?rid=c5646d80-9118-4439-b924-075f96371d75"
)

SOURCE = "taipei-hygiene-grade"
SCOPE = "店名 / 臺北市"

NAME_COLUMN = "業者名稱店名"
REGISTRY_COLUMN = "食品業者登錄字號"
GRADE_COLUMN = "評核結果"
REQUIRED_COLUMNS = (NAME_COLUMN, REGISTRY_COLUMN, GRADE_COLUMN)


class GradelistUnavailable(FoodtracerUnavailable):
    """The source did not answer usefully, or answered in a shape we do not know."""


@dataclass(frozen=True)
class StorefrontRow:
    """One site's sign, normalised, raw kept beside it (H24)."""

    registry_no: str
    name: str
    name_raw: str
    grade: str


@dataclass
class StorefrontResult:
    rows: List[StorefrontRow] = field(default_factory=list)
    scanned: int = 0

    def line(self) -> str:
        return "{} rows scanned, {} storefronts held".format(self.scanned, len(self.rows))


def fetch(now=None, opener=None) -> Sheet:
    """`foodtracer.fetch_sheet`, pointed at this dataset."""
    return fetch_sheet(now=now, opener=opener, source=SOURCE, url=URL)


def _require_columns(fieldnames) -> None:
    missing = [column for column in REQUIRED_COLUMNS if column not in (fieldnames or [])]
    if missing:
        raise GradelistUnavailable(
            "{}: the CSV is missing {} — found {}".format(SOURCE, missing, list(fieldnames or []))
        )


def parse_storefronts(raw: bytes) -> StorefrontResult:
    """Read the CSV down to its site rows. **The expensive call, and the only one.**

    Two refusals, both shape changes rather than dirty rows, measured absent from the file
    this was built against: a row with no registry number has no key and cannot be stored
    under 0014's primary key, and a **repeated** registry number would mean the file stopped
    being site-level — keeping either first-wins would store a guess wearing a fact's key.
    """
    stream = io.TextIOWrapper(io.BytesIO(raw), encoding="utf-8-sig", newline="")
    reader = csv.DictReader(stream)
    _require_columns(reader.fieldnames)
    result = StorefrontResult()
    seen = set()
    for row in reader:
        result.scanned += 1
        registry_no = (row.get(REGISTRY_COLUMN) or "").strip()
        if not registry_no:
            raise GradelistUnavailable(
                "{}: a row carries no {}".format(SOURCE, REGISTRY_COLUMN)
            )
        if registry_no in seen:
            raise GradelistUnavailable(
                "{}: registry number {} appears twice — the file was site-level "
                "(1,686 distinct of 1,686 measured 2026-08-14) and is not any more".format(
                    SOURCE, registry_no
                )
            )
        seen.add(registry_no)
        name_raw = (row.get(NAME_COLUMN) or "").strip()
        name = normalise(name_raw)
        if not name:
            raise GradelistUnavailable(
                "{}: row {} carries no {}".format(SOURCE, registry_no, NAME_COLUMN)
            )
        result.rows.append(
            StorefrontRow(
                registry_no=registry_no,
                name=name,
                name_raw=name_raw,
                grade=(row.get(GRADE_COLUMN) or "").strip(),
            )
        )
    if not result.rows:
        raise GradelistUnavailable(
            "{}: the CSV parsed to no rows — {} were read".format(SOURCE, result.scanned)
        )
    return result
