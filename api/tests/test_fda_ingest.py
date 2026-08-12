#!/usr/bin/env python3
"""Item 11's ingest, tested without a network and without a database.

Run: python3 app/api/tests/test_fda_ingest.py
  — or inside the stack: docker compose exec api python /srv/tests/test_fda_ingest.py

The fixtures are built at run time: a zip, holding a BOM-prefixed CSV, with the same five
columns and the same defects the real file carries. **The dirty values are copied out of the
real file rather than invented** (H25 is the hazard of a fixture nobody put a defect in), and
the two 台/臺 name pairs below are two real rows measured on 2026-08-11:

    台北市文山區景興國小            /  臺北市文山區景興國小
    台北市萬華區西園路二段140巷…    /  臺北市萬華區西園路二段140巷…

The two addresses that resolve to no township are real as well, and they are the reason
D31's "township parses at 100.0%" is now 99.99%.
"""

import asyncio
import io
import os
import ssl
import sys
import unittest
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from upto.ingest import fda  # noqa: E402
from upto.ingest import run_places  # noqa: E402
from upto.ingest import runlog  # noqa: E402

TAIPEI = timezone(timedelta(hours=8))
NOW = datetime(2026, 8, 11, 14, 0, tzinfo=timezone.utc)
STAMP = (2026, 8, 3, 10, 41, 40)

HEADER = "公司或商業登記名稱,公司統一編號,業者地址,食品業者登錄字號,登錄項目"


def row(name, address, registry_no, business_no="12345678", category="餐飲場所"):
    return '"{}","{}","{}","{}","{}"'.format(name, business_no, address, registry_no, category)


def csv_bytes(rows, header=HEADER, bom=True):
    body = "\r\n".join([header] + list(rows)) + "\r\n"
    return (b"\xef\xbb\xbf" if bom else b"") + body.encode("utf-8")


def zip_bytes(payload, name="97_2.csv", stamp=STAMP, extra=None):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(zipfile.ZipInfo(name, date_time=stamp), payload)
        if extra is not None:
            archive.writestr(zipfile.ZipInfo(extra, date_time=stamp), b"second entry")
    return buffer.getvalue()


DEFAULT_ROWS = [
    row("福利麵包食品有限公司", "台北市信義區菸廠路88號B1", "A-111820764-00022-1"),
    # Full-width digits and letters, copied from the real file: 11.9% of rows carry them.
    row("全家便利商店股份有限公司", "臺北市中正區忠孝西路一段４９號Ｂ１", "A-123060248-13440-5"),
    # Not 餐飲場所 — the file holds four categories and only one is this ingest's.
    row("某工廠股份有限公司", "台北市內湖區內湖路一段331號", "A-100000000-00001-1", category="工廠/製造場所"),
    # Not 臺北市. 新北市 begins with 新 and must not be caught by D27's 北市 short form.
    row("外縣市餐廳", "新北市板橋區文化路一段1號", "A-100000000-00002-2"),
]


def archive_of(rows=None, stamp=STAMP, bom=True, name="97_2.csv", extra=None):
    payload = csv_bytes(DEFAULT_ROWS if rows is None else rows, bom=bom)
    return fda.read_archive(zip_bytes(payload, name=name, stamp=stamp, extra=extra), NOW)


class Normalisation(unittest.TestCase):
    """One function at the boundary, never in a query (H24)."""

    def test_full_width_digits_and_letters_are_folded(self):
        self.assertEqual(fda.normalise("基隆路一段１６３號Ｂ１"), "基隆路一段163號B1")

    def test_the_ideographic_space_is_folded(self):
        self.assertEqual(fda.normalise("忠孝東路　四段"), "忠孝東路 四段")

    def test_the_city_is_spelled_one_way_afterwards(self):
        self.assertEqual(fda.normalise("台北市大安區"), "臺北市大安區")

    def test_a_word_that_merely_contains_the_character_is_left_alone(self):
        """The admitted cost of the token list, asserted so it stays visible.

        A blanket 台→臺 would rewrite 舞台 and 平台 — names, not administrative units — and a
        normaliser that corrupts a business name to make an address match is worse than one
        that misses a city nobody in this scope has.
        """
        self.assertEqual(fda.normalise("舞台餐廳"), "舞台餐廳")
        self.assertEqual(fda.normalise("平台食品"), "平台食品")


class TownshipFromAddress(unittest.TestCase):
    """D27: the township is read out of the address text. No coordinate is involved."""

    def test_the_district_resolves_to_its_internal_affairs_code(self):
        parsed = fda.taipei_township(fda.normalise("台北市信義區菸廠路88號B1"))
        self.assertTrue(parsed.in_city)
        self.assertEqual(parsed.name, "信義區")
        self.assertEqual(parsed.code, "63000020")
        self.assertIsNone(parsed.reason)

    def test_both_spellings_of_the_city_reach_the_same_code(self):
        first = fda.taipei_township(fda.normalise("台北市文山區興隆路3段298號"))
        second = fda.taipei_township(fda.normalise("臺北市文山區興隆路3段298號"))
        self.assertEqual(first.code, second.code)
        self.assertEqual(first.code, "63000080")

    def test_an_address_with_no_district_is_reported_rather_than_resolved(self):
        """Both of these are real rows. D31 said 100.0%; the file says 99.99%."""
        for address in ("台北市長安東路一段58號", "台北市羅斯福路五段211巷24號1樓"):
            parsed = fda.taipei_township(fda.normalise(address))
            self.assertTrue(parsed.in_city, address)
            self.assertIsNone(parsed.code)
            self.assertEqual(parsed.reason, fda.NO_TOWNSHIP_IN_ADDRESS)

    def test_a_district_outside_the_reference_table_is_its_own_reason(self):
        parsed = fda.taipei_township(fda.normalise("臺北市板橋區文化路一段1號"))
        self.assertTrue(parsed.in_city)
        self.assertIsNone(parsed.code)
        self.assertEqual(parsed.reason, fda.TOWNSHIP_NOT_IN_REFERENCE)

    def test_the_short_city_form_does_not_swallow_new_taipei(self):
        self.assertTrue(fda.taipei_township("北市信義區松高路11號").in_city)
        self.assertFalse(fda.taipei_township("新北市板橋區文化路一段1號").in_city)

    def test_a_leading_postcode_does_not_block_the_parse(self):
        """Measured absent from every 餐飲場所 row on 2026-08-11; handled because D27 names it."""
        parsed = fda.taipei_township(fda.normalise("110台北市信義區松高路11號"))
        self.assertEqual(parsed.code, "63000020")

    def test_the_codes_are_the_seeded_ones_and_there_are_twelve(self):
        """A second copy of the twelve codes would drift invisibly, so there is one."""
        from upto.seed import township_station as seed

        self.assertEqual(len(fda.TOWNSHIP_CODES), 12)
        self.assertEqual(
            fda.TOWNSHIP_CODES,
            {mapping.township_name: mapping.township_code for mapping in seed.MAPPINGS},
        )


class ArchiveIdentity(unittest.TestCase):
    """D35: the publication is the hash of the fetched bytes, and the stamp is the label."""

    def test_the_hash_is_sha256_shaped_and_stable(self):
        raw = zip_bytes(csv_bytes(DEFAULT_ROWS))
        first = fda.read_archive(raw, NOW)
        second = fda.read_archive(raw, NOW)
        self.assertEqual(len(first.content_sha256), 64)
        self.assertEqual(first.content_sha256, second.content_sha256)

    def test_different_bytes_are_a_different_publication(self):
        changed = DEFAULT_ROWS[1:]
        self.assertNotEqual(
            archive_of().content_sha256, archive_of(rows=changed).content_sha256
        )

    def test_identifying_a_publication_never_decompresses_the_csv(self):
        """The whole of D34's cheap check: an unchanged day must not touch the 99 MB.

        The proof is a zip whose entry is not a CSV at all. If identity needed the content,
        this could not produce a hash and a stamp — and it does both.
        """
        broken = zip_bytes(b"\x00\x01 not a csv at all \xff")
        archive = fda.read_archive(broken, NOW)
        self.assertEqual(len(archive.content_sha256), 64)
        self.assertEqual(archive.archive_stamp.year, 2026)
        with self.assertRaises(UnicodeDecodeError):
            fda.parse_places(broken)

    def test_the_stamp_carries_a_zone(self):
        archive = archive_of()
        self.assertIsNotNone(archive.archive_stamp.tzinfo, "H17: a stamp without a zone is the hazard")
        self.assertEqual(archive.archive_stamp.utcoffset(), timedelta(hours=8))
        self.assertEqual(archive.stamp_label(), "2026-08-03 10:41:40+0800")

    def test_the_zip_epoch_is_an_absent_stamp_rather_than_a_date_in_1980(self):
        archive = archive_of(stamp=(1980, 1, 1, 0, 0, 0))
        self.assertIsNone(archive.archive_stamp)
        self.assertEqual(archive.stamp_label(), "no archive stamp")

    def test_the_entry_is_named_and_measured(self):
        archive = archive_of()
        self.assertEqual(archive.entry_name, "97_2.csv")
        self.assertGreater(archive.entry_bytes, 0)
        self.assertGreater(archive.payload_bytes, 0)

    def test_a_second_entry_is_refused_rather_than_guessed(self):
        with self.assertRaises(fda.FdaUnavailable):
            archive_of(extra="97_3.csv")

    def test_a_body_that_is_not_a_zip_is_a_failure(self):
        with self.assertRaises(fda.FdaUnavailable):
            fda.read_archive(b"<html>maintenance</html>", NOW)

    def test_an_empty_body_is_a_failure_not_an_empty_success(self):
        with self.assertRaises(fda.FdaUnavailable):
            fda.read_archive(b"", NOW)

    def test_a_failed_fetch_is_a_failure_and_not_a_no_op(self):
        def explode(url):
            raise OSError("connection reset")

        with self.assertRaises(fda.FdaUnavailable):
            fda.fetch_archive(now=lambda: NOW, opener=explode)

    def test_a_fetch_is_identified_without_being_parsed(self):
        raw = zip_bytes(csv_bytes(DEFAULT_ROWS))
        archive = fda.fetch_archive(now=lambda: NOW, opener=lambda url: raw)
        self.assertEqual(archive.detected_at, NOW)
        self.assertEqual(archive.source, fda.SOURCE)
        self.assertEqual(archive.raw, raw)


class Parsing(unittest.TestCase):
    def test_a_bom_prefixed_csv_parses_rather_than_renaming_its_first_column(self):
        """H24: `csv` does not raise on a BOM, it hands back a first column nobody can name."""
        parsed = fda.parse_places(zip_bytes(csv_bytes(DEFAULT_ROWS, bom=True)))
        self.assertTrue(parsed.rows)
        self.assertEqual(parsed.rows[0].name, "福利麵包食品有限公司")

    def test_only_dining_rows_in_taipei_are_kept(self):
        parsed = fda.parse_places(zip_bytes(csv_bytes(DEFAULT_ROWS)))
        self.assertEqual(parsed.scanned, 4)
        self.assertEqual(parsed.in_city, 2)
        self.assertEqual(len(parsed.rows), 2)

    def test_every_row_records_its_origin(self):
        """D28, D30: a place is always a row of ours and carries where it came from."""
        parsed = fda.parse_places(zip_bytes(csv_bytes(DEFAULT_ROWS)))
        for place in parsed.rows:
            self.assertEqual(place.origin, "reference")

    def test_the_address_is_stored_normalised_with_the_raw_string_beside_it(self):
        parsed = fda.parse_places(zip_bytes(csv_bytes(DEFAULT_ROWS)))
        wide = next(p for p in parsed.rows if p.registry_no == "A-123060248-13440-5")
        self.assertEqual(wide.address, "臺北市中正區忠孝西路一段49號B1")
        self.assertEqual(wide.address_raw, "臺北市中正區忠孝西路一段４９號Ｂ１")
        self.assertEqual(wide.township_code, "63000050")

    def test_a_place_with_no_township_is_stored_and_reported(self):
        """D28: it costs the row its weather nudge and nothing else. Dropping it is the hazard."""
        rows = [row("某小吃店", "台北市長安東路一段58號", "A-100000000-00003-3")]
        parsed = fda.parse_places(zip_bytes(csv_bytes(rows)))
        self.assertEqual(len(parsed.rows), 1)
        self.assertIsNone(parsed.rows[0].township_code)
        self.assertIsNone(parsed.rows[0].township_name)
        self.assertEqual(len(parsed.unresolved), 1)
        self.assertEqual(parsed.unresolved[0].reason, fda.NO_TOWNSHIP_IN_ADDRESS)
        self.assertEqual(parsed.unresolved[0].address_raw, "台北市長安東路一段58號")

    def test_a_missing_column_is_a_failure_naming_what_is_missing(self):
        header = "公司或商業登記名稱,公司統一編號,業者地址,登錄項目"
        payload = csv_bytes(['"甲","1","台北市信義區一號","餐飲場所"'], header=header)
        with self.assertRaises(fda.FdaUnavailable) as caught:
            fda.parse_places(zip_bytes(payload))
        self.assertIn("食品業者登錄字號", str(caught.exception))

    def test_a_row_with_no_registry_number_is_a_failure_rather_than_an_invented_key(self):
        rows = [row("某小吃店", "台北市信義區松高路11號", "")]
        with self.assertRaises(fda.FdaUnavailable):
            fda.parse_places(zip_bytes(csv_bytes(rows)))

    def test_a_file_with_no_taipei_dining_rows_is_a_failure_not_an_empty_success(self):
        rows = [row("外縣市餐廳", "新北市板橋區文化路一段1號", "A-1-1")]
        with self.assertRaises(fda.FdaUnavailable):
            fda.parse_places(zip_bytes(csv_bytes(rows)))


class TwoSpellingsOfOneName(unittest.TestCase):
    """H24, and the ticket asks for this test by name: no row is silently lost.

    Both pairs are real rows from the file. The point is not that normalisation is pretty — it
    is that a join or a filter written against the raw column returns *some* rows, which is why
    nothing fails and why 0.8% of a table can go missing without a test noticing.
    """

    PAIRS = [
        ("台北市文山區景興國小", "臺北市文山區景興國小", "台北市文山區興隆路二段", "臺北市文山區興隆路二段"),
        (
            "台北市萬華區西園路二段140巷攤販臨時集中場",
            "臺北市萬華區西園路二段140巷攤販臨時集中場",
            "台北市萬華區西園路二段140巷",
            "臺北市萬華區西園路二段140巷",
        ),
    ]

    def parsed(self):
        rows = []
        for index, (name_a, name_b, address_a, address_b) in enumerate(self.PAIRS):
            rows.append(row(name_a, address_a + "1號", "A-900000000-0000{}-1".format(index * 2)))
            rows.append(row(name_b, address_b + "1號", "A-900000000-0000{}-2".format(index * 2 + 1)))
        return fda.parse_places(zip_bytes(csv_bytes(rows)))

    def test_no_row_is_lost(self):
        parsed = self.parsed()
        self.assertEqual(len(parsed.rows), 2 * len(self.PAIRS))
        for place in parsed.rows:
            self.assertIsNotNone(place.township_code, place.address_raw)

    def test_two_spellings_of_one_name_match_each_other_after_normalisation(self):
        by_name = {}
        for place in self.parsed().rows:
            by_name.setdefault(place.name, []).append(place)
        self.assertEqual(len(by_name), len(self.PAIRS), "one name should mean one group")
        for group in by_name.values():
            self.assertEqual(len(group), 2)

    def test_matching_on_the_raw_name_is_what_loses_rows(self):
        """The failure this exists to prevent, asserted rather than described."""
        raw_names = {place.name_raw for place in self.parsed().rows}
        self.assertEqual(len(raw_names), 2 * len(self.PAIRS))

    def test_the_raw_string_survives_beside_the_normalised_one(self):
        raw = {place.name_raw for place in self.parsed().rows}
        self.assertIn("台北市文山區景興國小", raw)
        self.assertIn("臺北市文山區景興國小", raw)


@dataclass
class FakePrevious:
    publication_id: int
    content_sha256: str
    archive_stamp: Optional[datetime]
    detected_at: datetime = NOW


class FakeStore:
    """Stands in for `PlaceStore`. The sequencing is what is under test, not the SQL."""

    def __init__(self, previous=None, claim_id=7, held_id=None):
        self.previous = previous
        self.claim_id = claim_id
        self.held_id = held_id
        self.written = []
        self.counts = None
        self.committed = False
        self.rolled_back = False
        self.claimed = None

    async def latest(self, source):
        return self.previous

    async def claim(self, archive, scope):
        self.claimed = (archive.content_sha256, scope)
        return self.claim_id

    async def held(self, source, content_sha256):
        if self.held_id is None:
            return None
        return FakePrevious(self.held_id, content_sha256, None)

    async def write(self, publication_id, rows):
        self.written.append((publication_id, list(rows)))
        return len(rows)

    async def accepted(self, publication_id):
        return sum(len(rows) for _, rows in self.written)

    async def record_counts(self, publication_id, place_rows, unresolved):
        self.counts = (publication_id, place_rows, unresolved)

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rolled_back = True


def refuse_to_parse(raw):
    raise AssertionError("the CSV was parsed on a run that found nothing new")


class Sequencing(unittest.TestCase):
    """The ticket's hardest checkbox: an unchanged day must not parse 99 MB."""

    def test_unchanged_content_does_not_parse_and_is_a_silent_success(self):
        archive = archive_of()
        store = FakeStore(
            previous=FakePrevious(3, archive.content_sha256, archive.archive_stamp),
            claim_id=None,
        )
        verdict = asyncio.run(
            run_places.ingest_archive(store, archive, parse=refuse_to_parse)
        )
        self.assertFalse(verdict.parsed)
        self.assertFalse(verdict.stored)
        self.assertEqual(verdict.alarms, [], "a no-op is not a warning (D34, D42)")
        self.assertEqual(verdict.exit_code(), 0)
        self.assertIn("no change", verdict.line())
        self.assertIn("not parsed", verdict.line())
        self.assertTrue(store.rolled_back)
        self.assertFalse(store.committed)
        self.assertEqual(store.written, [])

    def test_new_content_parses_and_writes(self):
        archive = archive_of()
        store = FakeStore(previous=None, claim_id=7)
        verdict = asyncio.run(run_places.ingest_archive(store, archive))
        self.assertTrue(verdict.stored)
        self.assertTrue(verdict.parsed)
        self.assertEqual(verdict.publication_id, 7)
        self.assertEqual(verdict.rows_offered, 2)
        self.assertEqual(verdict.rows_held, 2)
        self.assertTrue(store.committed)
        self.assertEqual(store.counts, (7, 2, 0))
        self.assertEqual(store.claimed[1], fda.SCOPE, "the publication records what its rows cover")

    def test_force_parse_writes_against_the_publication_already_held(self):
        """H14 needs the short-circuit disabled, so the *constraint* is what is under test."""
        archive = archive_of()
        store = FakeStore(
            previous=FakePrevious(3, archive.content_sha256, archive.archive_stamp),
            claim_id=None,
            held_id=3,
        )
        verdict = asyncio.run(run_places.ingest_archive(store, archive, force_parse=True))
        self.assertTrue(verdict.parsed)
        self.assertFalse(verdict.stored, "no new publication was created")
        self.assertEqual(store.written[0][0], 3, "the rows must be offered to the held publication")

    def test_the_unresolved_report_names_the_rows_and_counts_them_all(self):
        rows = [
            row("某小吃店", "台北市長安東路一段58號", "A-1-1"),
            row("另一家", "台北市羅斯福路五段211巷24號1樓", "A-1-2"),
            row("正常的", "台北市信義區松高路11號", "A-1-3"),
        ]
        archive = archive_of(rows=rows)
        store = FakeStore(previous=None, claim_id=7)
        verdict = asyncio.run(run_places.ingest_archive(store, archive))
        report = verdict.township_report()
        self.assertTrue(report)
        self.assertIn("2 of 3", report[0])
        self.assertIn(fda.NO_TOWNSHIP_IN_ADDRESS, report[0])
        self.assertIn("台北市長安東路一段58號", " ".join(report))
        self.assertEqual(store.counts, (7, 3, 2))

    def test_a_run_with_every_township_resolved_reports_nothing(self):
        archive = archive_of()
        store = FakeStore(previous=None, claim_id=7)
        verdict = asyncio.run(run_places.ingest_archive(store, archive))
        self.assertEqual(verdict.township_report(), [])


class StampVersusHash(unittest.TestCase):
    """D34's alarm: the stamp is the label, the hash is what catches it lying."""

    def held(self, archive, stamp=None):
        return FakePrevious(3, archive.content_sha256, archive.archive_stamp if stamp is None else stamp)

    def test_both_signals_moving_together_is_not_an_alarm(self):
        archive = archive_of()
        previous = FakePrevious(3, "0" * 64, datetime(2026, 7, 3, 9, 16, 50, tzinfo=TAIPEI))
        self.assertEqual(run_places.disagreements(archive, previous, True), [])

    def test_neither_signal_moving_is_not_an_alarm(self):
        archive = archive_of()
        self.assertEqual(run_places.disagreements(archive, self.held(archive), False), [])

    def test_content_changing_while_the_stamp_stands_still_is_an_alarm(self):
        archive = archive_of()
        previous = FakePrevious(3, "0" * 64, archive.archive_stamp)
        alarms = run_places.disagreements(archive, previous, True)
        self.assertEqual(len(alarms), 1)
        self.assertIn("DISAGREEMENT", alarms[0])
        self.assertIn("stamp did not", alarms[0])

    def test_the_stamp_moving_while_the_content_stands_still_is_an_alarm(self):
        archive = archive_of()
        previous = self.held(archive, stamp=datetime(2026, 7, 3, 9, 16, 50, tzinfo=TAIPEI))
        alarms = run_places.disagreements(archive, previous, False)
        self.assertTrue(any("stamp moved" in alarm for alarm in alarms))

    def test_a_revert_to_content_already_held_is_an_alarm(self):
        archive = archive_of()
        previous = FakePrevious(3, "0" * 64, archive.archive_stamp)
        alarms = run_places.disagreements(archive, previous, False)
        self.assertTrue(any("reverted" in alarm for alarm in alarms))

    def test_the_first_run_of_all_cannot_disagree_with_anything(self):
        self.assertEqual(run_places.disagreements(archive_of(), None, True), [])

    def test_an_alarm_makes_the_run_report_a_non_zero_code_after_storing(self):
        archive = archive_of()
        store = FakeStore(previous=FakePrevious(3, "0" * 64, archive.archive_stamp), claim_id=7)
        verdict = asyncio.run(run_places.ingest_archive(store, archive))
        self.assertTrue(verdict.stored, "the rows are written before the alarm is raised")
        self.assertEqual(verdict.exit_code(), 2)


class TheRunRow(unittest.TestCase):
    """Ticket 09's row, and the half of it that needs no database: the mapping.

    `run_places` recorded nothing at all until 2026-08-12, so every one of item 11's runs —
    including the daily no-ops D34 schedules — left no trace. These assert what each outcome
    maps to; `test_place_ingest_integration.py` asserts that the rows actually insert, which is
    where revision 0005's CHECKs get to have an opinion.
    """

    STARTED = datetime(2026, 8, 12, 3, 0, tzinfo=timezone.utc)

    def record(self, verdict, invoked_by="airflow"):
        return run_places.run_record(verdict, self.STARTED, invoked_by)

    def stored_verdict(self):
        archive = archive_of()
        store = FakeStore(previous=None, claim_id=7)
        return asyncio.run(run_places.ingest_archive(store, archive))

    def no_op_verdict(self):
        archive = archive_of()
        store = FakeStore(
            previous=FakePrevious(3, archive.content_sha256, archive.archive_stamp),
            claim_id=None,
        )
        return asyncio.run(run_places.ingest_archive(store, archive, parse=refuse_to_parse))

    def test_a_stored_run_records_its_publication_and_what_landed(self):
        record = self.record(self.stored_verdict())
        self.assertEqual(record.source, fda.SOURCE)
        self.assertEqual(record.outcome, runlog.STORED)
        self.assertEqual(record.publication_id, 7)
        self.assertEqual(record.column(), runlog.PLACE_COLUMN, "D24: item 11's own column")
        self.assertEqual(record.rows_written, 2)
        self.assertEqual(record.started_at, self.STARTED)
        self.assertEqual(record.invoked_by, "airflow")
        self.assertIn("stored publication 7", record.detail)

    def test_a_no_op_is_recorded_as_no_change_and_not_as_an_absence(self):
        """D42's silent success is still a run, and `no_change` is not `failed`."""
        record = self.record(self.no_op_verdict())
        self.assertEqual(record.outcome, runlog.NO_CHANGE)
        self.assertEqual(record.rows_written, 0)
        self.assertIn("no change", record.detail)

    def test_a_no_op_attaches_no_publication_even_though_its_verdict_names_one(self):
        """The subtlety, and revision 0005 refuses the alternative.

        A no-op's verdict carries the *previous* publication's id so its line can name what is
        still current. `ck_ingest_run_stored_has_publication` ties having a publication to the
        outcome being `stored`, so the row must not carry it — and it would be a false claim
        anyway, since this run wrote none of those rows.
        """
        verdict = self.no_op_verdict()
        self.assertEqual(verdict.publication_id, 3, "the verdict does name it")
        record = self.record(verdict)
        self.assertIsNone(record.publication_id)
        self.assertIsNone(record.column(), "no column may be filled on a run that stored nothing")

    def test_a_forced_re_parse_is_a_no_change_that_wrote_nothing(self):
        """H14's scenario: rows are offered, the constraint accepts none, so none were written."""
        archive = archive_of()
        store = FakeStore(
            previous=FakePrevious(3, archive.content_sha256, archive.archive_stamp),
            claim_id=None,
            held_id=3,
        )
        verdict = asyncio.run(run_places.ingest_archive(store, archive, force_parse=True))
        self.assertTrue(verdict.parsed)
        self.assertEqual(verdict.rows_offered, 2, "it did offer them")
        record = self.record(verdict)
        self.assertEqual(record.outcome, runlog.NO_CHANGE)
        self.assertEqual(record.rows_written, 0)
        self.assertIsNone(record.publication_id)

    def test_a_disagreement_is_still_a_stored_run_and_keeps_the_alarm_in_the_detail(self):
        """Exit code 2 is not an outcome — the rows are written before the alarm is raised."""
        archive = archive_of()
        store = FakeStore(previous=FakePrevious(3, "0" * 64, archive.archive_stamp), claim_id=7)
        verdict = asyncio.run(run_places.ingest_archive(store, archive))
        self.assertEqual(verdict.exit_code(), 2)
        record = self.record(verdict)
        self.assertEqual(record.outcome, runlog.STORED)
        self.assertEqual(record.publication_id, 7)
        self.assertIn("DISAGREEMENT", record.detail, "a row that reads as ordinary hides this")

    def test_the_invoker_is_carried_rather_than_guessed(self):
        self.assertEqual(self.record(self.stored_verdict(), invoked_by="cli").invoked_by, "cli")


class TlsPosture(unittest.TestCase):
    def test_verification_is_the_full_default_including_strictness(self):
        """Item 10 has to relax VERIFY_X509_STRICT for CWA's chain. This endpoint does not,
        which was measured rather than assumed — so the exception is not copied here."""
        context = fda.tls_context()
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)
        if hasattr(ssl, "VERIFY_X509_STRICT"):
            expected = ssl.create_default_context().verify_flags & ssl.VERIFY_X509_STRICT
            self.assertEqual(context.verify_flags & ssl.VERIFY_X509_STRICT, expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
