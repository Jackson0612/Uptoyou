"""Item 11 — the 食藥署 食品業者登錄 reference ingest: fetch, identify, and only then parse.

One source, one table, no join (D31). The file is a 17 MB zip carrying a ~99 MB CSV of
827,784 rows across four 登錄項目 categories; what this module keeps is the `餐飲場所`
rows whose address is in 臺北市.

**A publication is identified by the hash of the fetched bytes** (D35). The archive's own
stamp is kept beside it as the human-readable label item 14 shows, never as the key — a
stamp can move while the data stands still, and it can stand still while the data moves.

**The expensive half is deliberately behind the cheap half.** `fetch_archive` reads the
zip's central directory, which costs nothing, and never decompresses; `parse_places` is the
only thing here that touches the 99 MB, and the caller must not reach it until the database
has said the hash is new (D34: about twenty-nine of thirty daily runs publish nothing, and
those must not parse). The two functions are separate for that reason and not for tidiness.

**No credential.** D33 counts the sources and item 11 is the one needing none — the file is
an open download. That is why nothing here is handed a key, and why the failure messages have
nothing to hide.

**Normalisation happens here, at the boundary, and never in a query** (H24). The same file
spells one city two ways — 36,488 rows say 台北市 and 11 say 臺北市, measured 2026-08-11 —
and 12.3% of `餐飲場所` addresses carry full-width digits. A filter written against the raw
column finds 11 of 36,499 rows and looks like it worked. Every row keeps its raw string
beside the normalised one, so a mismatch can be investigated without re-fetching.

**Measured 2026-08-11, and two of these numbers contradict D31 rather than confirming it.**
The served file had moved on from the one D31 and D34 measured: stamp `2026-08-03 10:41:40`
against `2026-07-03 09:16:50`, a new sha256, 827,784 rows against 824,696, `餐飲場所`
233,269 against 232,212, and 臺北市 `餐飲場所` **36,499 against 36,620**. The stamp and the
hash moved together, which is the agreement D34 wanted to see. **The township parse is
99.99%, not D31's 100.0%** — two rows name no district at all, and they are the reason the
unresolved report below exists rather than being a formality:

    台北市長安東路一段58號
    台北市羅斯福路五段211巷24號1樓
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
import ssl
import urllib.request
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, List, Optional

from ..seed.township_station import MAPPINGS as SEEDED_TOWNSHIPS

URL = "https://data.fda.gov.tw/data/opendata/export/97/csv"

# The publisher's own dataset number, and it names the *file* rather than the slice kept from
# it. That distinction is load-bearing: the hash covers the whole archive — every category,
# nationwide — so a source string naming 餐飲場所 would describe the rows and misdescribe the
# thing being identified. What the rows cover is recorded separately, as SCOPE.
SOURCE = "fda-97"
SCOPE = "餐飲場所 / 臺北市"

CATEGORY = "餐飲場所"
CITY = "臺北市"

# D28's three origins; every row this module produces is the first one (D28, D30).
ORIGIN_REFERENCE = "reference"

# The five columns, as the file names them. Read from the header rather than by position,
# and the header is only readable at all because the file is decoded `utf-8-sig` — a BOM
# leaves `csv` handing back a first column called `﻿公司或商業登記名稱`, so the lookup
# raises KeyError on one column while the other four work, which reads as a typo rather than
# as an encoding fault (H24).
NAME_COLUMN = "公司或商業登記名稱"
BUSINESS_NO_COLUMN = "公司統一編號"
ADDRESS_COLUMN = "業者地址"
REGISTRY_COLUMN = "食品業者登錄字號"
CATEGORY_COLUMN = "登錄項目"
REQUIRED_COLUMNS = (
    NAME_COLUMN,
    BUSINESS_NO_COLUMN,
    ADDRESS_COLUMN,
    REGISTRY_COLUMN,
    CATEGORY_COLUMN,
)

# The archive stamp is naive in the zip, and the publisher is in Taiwan. H17: a stamp whose
# zone is unknown is the hazard, so the zone is attached here rather than left to whatever
# the reader assumes.
TAIPEI = timezone(timedelta(hours=8))

# zipfile's own "no date" value. A 1980 stamp is a missing stamp wearing a date, and storing
# it as if it were a publication time would put a false label on the row item 14 shows.
ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)

REQUEST_TIMEOUT = 300

# Full-width to half-width. 12.3% of `餐飲場所` addresses carry at least one — 基隆路一段
# １６３號Ｂ１ — and two addresses differing only in digit width are two rows that should
# have been one.
FULLWIDTH_FOLD = {codepoint: codepoint - 0xFEE0 for codepoint in range(0xFF01, 0xFF5F)}
FULLWIDTH_FOLD[0x3000] = 0x20  # the ideographic space

# 台 → 臺, on administrative names only, as H24's mitigation words it. **A blanket
# replacement is the wrong fix and this list is the cost of not making it**: 舞台, 吧台, 台鐵
# and 平台 are not administrative names, and folding them would corrupt a business name to
# make an address match. A token that is not on this list is not folded, which means a city
# outside it keeps two spellings — acceptable while the ingest keeps 臺北市 only, and the
# first thing to extend if it ever goes nationwide.
ADMINISTRATIVE_FOLD = (
    ("台北", "臺北"),
    ("台中", "臺中"),
    ("台南", "臺南"),
    ("台東", "臺東"),
    ("台西", "臺西"),
    ("台灣", "臺灣"),
)

# D27's geocode, and it is not a second copy of the codes. The twelve 內政部 鄉鎮市區代碼 are
# already stated once, in ticket 06's seed, which is pure data with its sqlalchemy import
# deferred precisely so it can be read without a database. A second table here would be two
# files claiming one fact, and the drift would be invisible.
TOWNSHIP_CODES = {
    mapping.township_name: mapping.township_code for mapping in SEEDED_TOWNSHIPS
}

# Why a row has no township, kept as two reasons rather than one. The first is the source's
# address being short; the second is our reference table not covering it — a nationwide row
# reaching here would be the second, and reading it as the first would blame the publisher.
NO_TOWNSHIP_IN_ADDRESS = "no_township_in_address"
TOWNSHIP_NOT_IN_REFERENCE = "township_not_in_reference"

_POSTCODE = re.compile(r"^\d{3,5}")
# 北市 is D27's other short form. It cannot swallow 新北市, because the match is anchored and
# 新北市 starts with 新 — checked, because an unanchored version would have silently pulled
# 新北市 rows into 臺北市.
_CITY_PREFIX = re.compile(r"^(?:臺北市|北市)")
# Taipei's twelve are all two characters plus 區. Non-greedy and bounded, so 長安東路 cannot
# be read as a district name.
_DISTRICT = re.compile(r"^(.{1,3}?區)")


class FdaUnavailable(RuntimeError):
    """The source did not answer usefully, or answered in a shape we do not know.

    A run that hits this **failed**; it did not no-op. The distinction is the whole of D34's
    schedule: twenty-nine runs a month legitimately store nothing, so an actual failure has
    to be distinguishable from the ordinary case rather than sharing its exit code.
    """


@dataclass(frozen=True)
class Archive:
    """One fetch, identified but not yet parsed.

    `raw` is the compressed bytes, kept only so the caller can parse them *if* the hash turns
    out to be new. It is excluded from the repr and from equality: a 17 MB blob in a log line
    is worse than no log line.
    """

    source: str
    content_sha256: str
    archive_stamp: Optional[datetime]
    entry_name: str
    entry_bytes: int
    payload_bytes: int
    detected_at: datetime
    raw: bytes = field(default=b"", repr=False, compare=False)

    def stamp_label(self) -> str:
        """What item 14 shows. A publication with no stamp says so rather than showing a date."""
        if self.archive_stamp is None:
            return "no archive stamp"
        return self.archive_stamp.strftime("%Y-%m-%d %H:%M:%S%z")


@dataclass(frozen=True)
class PlaceRow:
    """One 餐飲場所 site in 臺北市, normalised, with its raw strings kept beside it (H24)."""

    registry_no: str
    name: str
    name_raw: str
    address: str
    address_raw: str
    business_no: Optional[str]
    township_code: Optional[str]
    township_name: Optional[str]
    origin: str = ORIGIN_REFERENCE


@dataclass(frozen=True)
class Unresolved:
    """A row that will be stored with no township, and reported for it (D28)."""

    registry_no: str
    address_raw: str
    reason: str


@dataclass(frozen=True)
class Township:
    in_city: bool
    code: Optional[str] = None
    name: Optional[str] = None
    reason: Optional[str] = None


@dataclass
class ParseResult:
    rows: List[PlaceRow] = field(default_factory=list)
    unresolved: List[Unresolved] = field(default_factory=list)
    scanned: int = 0
    in_city: int = 0

    def line(self) -> str:
        return "{} rows scanned, {} in {} {}, {} with no township".format(
            self.scanned, self.in_city, CITY, CATEGORY, len(self.unresolved)
        )


# H33's second trap, mitigated here 2026-08-18. The 食品業者登錄 file carries private-use-area
# codepoints inside its name column: `A-200168458-00001-2` reads 松日日式料理店 in both the FDA
# file and the 食材登錄 file and still fails a byte comparison, because the FDA string ends in
# `U+F57F`. A PUA codepoint has no agreed meaning — it renders as whatever the publisher's own
# font decided — so it is not part of the name, and it breaks the one join that has to work on
# exact strings: `foodtracer`'s company column exists to equal `reference_place.name` (that
# module's own header says so). Stripped at the boundary, with the raw string kept beside it as
# H24 requires, so nothing is lost and the corrupted codepoint stays investigable.
#
# **The BMP block only** — U+E000–U+F8FF. Planes 15 and 16 hold PUA too and are not stripped,
# because nothing has been measured carrying them and a strip nobody can point at a row for is
# a guess. Measured 2026-08-18: 16 of 36,499 stored `reference_place.name` carry a BMP PUA
# codepoint, 0 addresses do.
_PRIVATE_USE = re.compile("[\ue000-\uf8ff]")


def normalise(text: Optional[str]) -> str:
    """One function, applied at the boundary, before any row is written (H24).

    Full-width folded, administrative 台 folded to 臺, private-use codepoints dropped (H33),
    whitespace collapsed. The BOM is not handled here because it is handled where it belongs —
    in the decode.

    **If dropping the PUA would leave nothing, the folded string is kept as it was.** An empty
    name is not a safer wrong answer than a corrupted one: it would join to every other empty
    name and it would read as a row with no name at all. Same rule as R-6's footnote strip in
    `upto.naming` — a strip that empties the field does not fire.
    """
    if not text:
        return ""
    folded = text.translate(FULLWIDTH_FOLD)
    for written, canonical in ADMINISTRATIVE_FOLD:
        folded = folded.replace(written, canonical)
    stripped = _PRIVATE_USE.sub("", folded)
    if stripped.strip():
        folded = stripped
    return " ".join(folded.split())


def taipei_township(address: str) -> Township:
    """Read the township out of the address text — never from a coordinate (D27).

    Takes an address that has already been through `normalise`, so both spellings of the city
    and both digit widths have already collapsed. A leading postcode is stripped here rather
    than in `normalise`: the postcode is in the way of the parse, not wrong in the row, and
    the stored address should still be the address the source published. **Measured absent
    from every 餐飲場所 row on 2026-08-11** — it is handled because D27 names it, not because
    it was seen.
    """
    body = _POSTCODE.sub("", address).lstrip()
    if not _CITY_PREFIX.match(body):
        return Township(in_city=False)
    rest = _CITY_PREFIX.sub("", body, count=1).lstrip()
    match = _DISTRICT.match(rest)
    if match is None:
        return Township(in_city=True, reason=NO_TOWNSHIP_IN_ADDRESS)
    name = match.group(1)
    code = TOWNSHIP_CODES.get(name)
    if code is None:
        return Township(in_city=True, name=name, reason=TOWNSHIP_NOT_IN_REFERENCE)
    return Township(in_city=True, code=code, name=name)


def tls_context() -> ssl.SSLContext:
    """The default context, strictness included — and that is a measurement, not an oversight.

    Item 10 has to switch `VERIFY_X509_STRICT` off, because CWA's chain carries a CA
    certificate with no Subject Key Identifier. **This endpoint does not need that**: its
    chain is a Sectigo OV one, and a fetch from the host with the flag forced on returned 200
    on 2026-08-11. Copying item 10's relaxation here would turn a narrow, argued exception
    into a habit, on an endpoint that never asked for it.
    """
    return ssl.create_default_context()


def _download(target: str) -> bytes:
    request = urllib.request.Request(target, headers={"User-Agent": "upto-ingest/1.0"})
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT, context=tls_context()) as response:
        return response.read()


def _single_entry(archive: zipfile.ZipFile) -> zipfile.ZipInfo:
    entries = archive.infolist()
    if len(entries) != 1:
        # Three fetches have each carried exactly one entry, `97_2.csv`. A second one means
        # the packaging changed, and guessing which entry is the data is how a wrong table
        # gets written with nothing to notice it.
        raise FdaUnavailable(
            "{}: the archive carries {} entries, not one — {}".format(
                SOURCE, len(entries), [entry.filename for entry in entries]
            )
        )
    return entries[0]


def _archive_stamp(entry: zipfile.ZipInfo) -> Optional[datetime]:
    if tuple(entry.date_time) == ZIP_EPOCH:
        return None
    return datetime(*entry.date_time, tzinfo=TAIPEI)


def read_archive(raw: bytes, detected_at: datetime, source: str = SOURCE) -> Archive:
    """Identify a fetch without decompressing it.

    The hash is of the compressed bytes, which is what D35 chose and what its cost bullet
    admits: a recompression of identical data would mint a false publication, and the stamp is
    right in exactly that case, which is the argument for storing both. The gain is that
    identity costs a directory read rather than a 99 MB parse.
    """
    if not raw:
        raise FdaUnavailable("{}: the download was empty".format(source))
    digest = hashlib.sha256(raw).hexdigest()
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entry = _single_entry(archive)
            stamp = _archive_stamp(entry)
            name, size = entry.filename, entry.file_size
    except zipfile.BadZipFile:
        raise FdaUnavailable("{}: the download is not a zip archive".format(source)) from None
    return Archive(
        source=source,
        content_sha256=digest,
        archive_stamp=stamp,
        entry_name=name,
        entry_bytes=size,
        payload_bytes=len(raw),
        detected_at=detected_at,
        raw=raw,
    )


def fetch_archive(
    now: Optional[Callable[[], datetime]] = None,
    opener: Optional[Callable[[str], bytes]] = None,
    source: str = SOURCE,
) -> Archive:
    """Fetch the archive and identify it. Does not parse, and does not touch a database.

    There is no conditional GET to attempt — the endpoint returns no `Last-Modified`, no
    `ETag` and no `Content-Length` (D34), re-checked 2026-08-11 and still true — so the fetch
    is the only way to learn anything and the 17 MB is unavoidable.
    """
    clock = now or (lambda: datetime.now(timezone.utc))
    download = opener or _download
    try:
        raw = download(URL)
    except Exception as failure:  # noqa: BLE001 — any transport failure is one failure here
        # No credential is in play (D33), so unlike item 10 nothing has to be hidden. The
        # message names the source rather than the URL because the URL adds no information a
        # reader of this log does not already have.
        raise FdaUnavailable(
            "{}: fetch failed — {}: {}".format(source, type(failure).__name__, failure)
        ) from None
    return read_archive(raw, clock(), source=source)


def _require_columns(fieldnames) -> None:
    missing = [column for column in REQUIRED_COLUMNS if column not in (fieldnames or [])]
    if missing:
        raise FdaUnavailable(
            "{}: the CSV is missing {} — found {}".format(SOURCE, missing, list(fieldnames or []))
        )


def parse_places(raw: bytes) -> ParseResult:
    """Decompress and read the CSV. **The expensive call, and the only one.**

    Streamed rather than loaded: `ZipFile.open` plus `TextIOWrapper` hands `csv` one row at a
    time, which is the property D31 chose CSV over JSON for — a 99 MB file read in constant
    memory instead of parsed whole before the first record exists.
    """
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entry = _single_entry(archive)
        with archive.open(entry.filename) as binary:
            # `utf-8-sig`, because the file carries a leading BOM and `csv` does not raise on
            # it — it renames the first column instead (H24).
            stream = io.TextIOWrapper(binary, encoding="utf-8-sig", newline="")
            return _parse_stream(stream)


def _parse_stream(stream) -> ParseResult:
    reader = csv.DictReader(stream)
    _require_columns(reader.fieldnames)
    result = ParseResult()
    for row in reader:
        result.scanned += 1
        if (row.get(CATEGORY_COLUMN) or "").strip() != CATEGORY:
            continue
        address_raw = (row.get(ADDRESS_COLUMN) or "").strip()
        address = normalise(address_raw)
        township = taipei_township(address)
        if not township.in_city:
            continue
        result.in_city += 1
        registry_no = (row.get(REGISTRY_COLUMN) or "").strip()
        if not registry_no:
            # The key D35 pins a row by. 827,784 rows carried one, all distinct (measured
            # 2026-08-11), so this is a shape change rather than a dirty row, and it is not
            # something to work around by inventing a key.
            raise FdaUnavailable(
                "{}: a {} row carries no {}".format(SOURCE, CATEGORY, REGISTRY_COLUMN)
            )
        name_raw = (row.get(NAME_COLUMN) or "").strip()
        business_no = (row.get(BUSINESS_NO_COLUMN) or "").strip()
        if township.reason is not None:
            # Stored anyway, with no township. D28: a place with no township takes no weather
            # contribution, which is neutral rather than a penalty — so the row costs its
            # nudge and nothing else. Dropping it would be the silent loss H24 is about.
            result.unresolved.append(Unresolved(registry_no, address_raw, township.reason))
        result.rows.append(
            PlaceRow(
                registry_no=registry_no,
                name=normalise(name_raw),
                name_raw=name_raw,
                address=address,
                address_raw=address_raw,
                # 統編 stays text: some begin with 0 (D31), and an integer column would eat
                # the leading digit and produce a number that still looks like a 統編.
                business_no=business_no or None,
                township_code=township.code,
                # The code and the name move together, so a name with no code cannot exist
                # in the table for a reader to mistake for a resolved township. Where the
                # district was read but is not one of the twelve, the district text is in the
                # unresolved report's address rather than on the row.
                township_name=township.name if township.code else None,
            )
        )
    if not result.rows:
        raise FdaUnavailable(
            "{}: the CSV parsed to no {} rows in {} — {} rows were read".format(
                SOURCE, CATEGORY, CITY, result.scanned
            )
        )
    return result
