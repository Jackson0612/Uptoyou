#!/usr/bin/env python3
"""D85's tax-registry ingest, tested without a network and without a database.

Run: python3 app/api/tests/test_fia_ingest.py
  — or inside the stack: docker compose exec api python /srv/tests/test_fia_ingest.py

The fixtures are built at run time: a zip holding a BOM-prefixed CSV with the file's sixteen
columns, its row-2 date stamp, and rows copied from the served file rather than invented (H25
is the hazard of a fixture nobody put a defect in). What the tests hold:

  * the stamp row is the second version signal, read as a date and never as data;
  * only the 統編 the reference list offers are kept, and the other 1.69M rows are not;
  * the four 行業 pairs land positionally, and an empty pair is NULL rather than a shift;
  * the hash short-circuit means an unchanged day does not decompress the 320 MB — held by
    handing in a parser that raises if it is ever called.
"""

import asyncio
import io
import os
import sys
import unittest
import zipfile
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from upto.ingest import fia  # noqa: E402
from upto.ingest import run_business_tax  # noqa: E402
from upto.ingest import runlog  # noqa: E402
from upto.ingest.fia import FiaUnavailable, parse_rows, parse_stamp  # noqa: E402

NOW = datetime(2026, 8, 14, 14, 0, tzinfo=timezone.utc)
STAMP = "14-AUG-26"

HEADER = (
    "營業地址,統一編號,總機構統一編號,營業人名稱,資本額,設立日期,組織別名稱,使用統一發票,"
    "行業代號,名稱,行業代號1,名稱1,行業代號2,名稱2,行業代號3,名稱3"
)


def row(business_no, name, address="臺北市松山區八德路四段1號", industries=(("562100", "餐館"),)):
    """One data row. `industries` is up to four (code, name) pairs, padded to four."""
    cells = [
        '"{}"'.format(address),
        business_no,
        "",
        '"{}"'.format(name),
        "100000",
        "1040413",
        "獨資",
        "N",
    ]
    padded = list(industries) + [("", "")] * (4 - len(industries))
    for code, industry_name in padded:
        cells.extend([code, industry_name])
    return ",".join(cells)


def csv_bytes(rows, header=HEADER, stamp=STAMP):
    lines = [header]
    if stamp is not None:
        # Row 2, exactly as the file writes it: the date in the first cell, fifteen empties.
        lines.append(stamp + "," * 15)
    lines.extend(rows)
    return ("﻿" + "\n".join(lines) + "\n").encode("utf-8")


def zip_bytes(payload, name="BGMOPEN1.csv", extra=None):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(zipfile.ZipInfo(name, date_time=(2026, 8, 14, 3, 30, 2)), payload)
        if extra is not None:
            archive.writestr(zipfile.ZipInfo(extra, date_time=(2026, 8, 14, 3, 30, 2)), b"second")
    return buffer.getvalue()


DEFAULT_ROWS = [
    row("38965019", "原味商行", industries=(("472927", "豆類製品零售"),)),
    row("61194605", "和興商店", industries=(("472913", "菸酒零售"), ("471913", "雜貨店"))),
    # Not on the reference list — 1.69M of the served file's rows are this row's shape, and
    # none of them may be stored.
    row("82554400", "啟輝環管企業社", address="南投縣中寮鄉永平路371號"),
]


def archive_of(rows=None, stamp=STAMP, name="BGMOPEN1.csv", extra=None, header=HEADER):
    payload = csv_bytes(DEFAULT_ROWS if rows is None else rows, header=header, stamp=stamp)
    return fia.read_archive(zip_bytes(payload, name=name, extra=extra), NOW)


WANTED = ["38965019", "61194605"]


class TheStampRow(unittest.TestCase):
    """Row 2 is the file's own statement of when the extract was cut — the second signal."""

    def test_the_published_shape_reads_as_a_date(self):
        self.assertEqual(parse_stamp("14-AUG-26"), date(2026, 8, 14))

    def test_the_month_table_does_not_depend_on_the_process_locale(self):
        """`%b` reads the locale, and a container whose locale is not C would fail to parse a
        date the file states plainly. The table is why that cannot happen."""
        self.assertEqual(parse_stamp("01-jan-27"), date(2027, 1, 1))

    def test_a_malformed_stamp_is_no_stamp_rather_than_a_refusal(self):
        for malformed in ("", "2026-08-14", "14-XXX-26", "14-AUG", "31-FEB-26", "aa-AUG-26"):
            self.assertIsNone(parse_stamp(malformed), malformed)

    def test_an_archive_carries_the_stamp_beside_the_hash(self):
        archive = archive_of()
        self.assertEqual(archive.file_stamp, date(2026, 8, 14))
        self.assertEqual(archive.stamp_label(), "2026-08-14")
        self.assertEqual(len(archive.content_sha256), 64)

    def test_an_unreadable_stamp_row_leaves_the_hash_doing_the_work(self):
        archive = archive_of(stamp="not a date")
        self.assertIsNone(archive.file_stamp)
        self.assertEqual(archive.stamp_label(), "no file stamp")

    def test_the_stamp_row_is_never_stored_as_a_business(self):
        result = parse_rows(archive_of().raw, WANTED)
        self.assertEqual(result.scanned, len(DEFAULT_ROWS), "the stamp row was counted as data")
        self.assertNotIn("", [kept.business_no for kept in result.rows])


class TheFilter(unittest.TestCase):
    """The storage ruling: only the 統編 the latest place publication knows."""

    def test_only_the_wanted_numbers_are_kept(self):
        result = parse_rows(archive_of().raw, WANTED)
        self.assertEqual([kept.business_no for kept in result.rows], WANTED)
        self.assertEqual(result.wanted, 2)
        self.assertEqual(result.scanned, 3)

    def test_the_unwanted_row_is_read_and_dropped_rather_than_stored(self):
        kept = {row.business_no for row in parse_rows(archive_of().raw, WANTED).rows}
        self.assertNotIn("82554400", kept, "a row outside the reference list was stored")

    def test_a_wanted_number_the_file_does_not_carry_is_simply_absent(self):
        result = parse_rows(archive_of().raw, WANTED + ["99999999"])
        self.assertEqual(len(result.rows), 2)
        self.assertEqual(result.wanted, 3)

    def test_an_empty_reference_list_is_refused_and_says_why(self):
        """Nothing to join to is item 11 not having run, and storing zero rows silently would
        read afterwards as a file that suddenly matched nothing."""
        with self.assertRaises(FiaUnavailable) as refusal:
            parse_rows(archive_of().raw, [])
        self.assertIn("item 11", str(refusal.exception))

    def test_a_file_matching_none_of_the_reference_numbers_is_a_failure(self):
        with self.assertRaises(FiaUnavailable):
            parse_rows(archive_of().raw, ["11111111"])

    def test_a_repeated_number_is_counted_and_the_first_row_wins(self):
        """統編 is unique in the served file — 0 duplicates in 1,711,012 rows, measured
        2026-08-14. Counted rather than raised, so the day that stops being true the verdict
        says so instead of the write failing."""
        rows = [row("38965019", "原味商行"), row("38965019", "另一家")]
        result = parse_rows(archive_of(rows=rows).raw, ["38965019"])
        self.assertEqual(len(result.rows), 1)
        self.assertEqual(result.rows[0].tax_name, "原味商行")
        self.assertEqual(result.duplicates, 1)
        self.assertIn("repeated", result.line())


class TheIndustryPairs(unittest.TestCase):
    def test_the_pairs_land_in_the_files_own_order(self):
        result = parse_rows(archive_of().raw, WANTED)
        second = result.rows[1]
        self.assertEqual(second.industries[0], fia.Industry("472913", "菸酒零售"))
        self.assertEqual(second.industries[1], fia.Industry("471913", "雜貨店"))

    def test_an_empty_pair_is_none_rather_than_an_empty_string(self):
        result = parse_rows(archive_of().raw, WANTED)
        first = result.rows[0]
        self.assertEqual(len(first.industries), 4)
        for absent in first.industries[1:]:
            self.assertIsNone(absent.code)
            self.assertIsNone(absent.name)

    def test_a_code_with_no_name_keeps_the_code(self):
        rows = [row("38965019", "原味商行", industries=(("472927", ""),))]
        kept = parse_rows(archive_of(rows=rows).raw, ["38965019"]).rows[0]
        self.assertEqual(kept.industries[0], fia.Industry("472927", None))

    def test_nothing_is_normalised_beyond_strip(self):
        """The address is the registered one and nothing joins on it, so folding its full-width
        digits would imply a matching that does not happen."""
        rows = [row("38965019", "原味商行", address="南投縣中寮鄉永平路３７１號")]
        kept = parse_rows(archive_of(rows=rows).raw, ["38965019"]).rows[0]
        self.assertEqual(kept.address, "南投縣中寮鄉永平路３７１號")


class TheArchive(unittest.TestCase):
    def test_an_empty_download_is_a_failure(self):
        with self.assertRaises(FiaUnavailable):
            fia.read_archive(b"", NOW)

    def test_a_body_that_is_not_a_zip_is_a_failure(self):
        with self.assertRaises(FiaUnavailable) as refusal:
            fia.read_archive(b"not a zip at all", NOW)
        self.assertIn("not a zip", str(refusal.exception))

    def test_a_second_entry_is_a_packaging_change_and_is_refused(self):
        with self.assertRaises(FiaUnavailable) as refusal:
            archive_of(extra="README.txt")
        self.assertIn("2 entries", str(refusal.exception))

    def test_a_missing_column_names_what_is_missing(self):
        broken = HEADER.replace("營業人名稱", "名稱X")
        with self.assertRaises(FiaUnavailable) as refusal:
            parse_rows(archive_of(header=broken).raw, WANTED)
        self.assertIn("營業人名稱", str(refusal.exception))

    def test_the_fetch_reports_a_transport_failure_as_this_sources_own(self):
        def refuse(_url):
            raise OSError("connection reset")

        with self.assertRaises(FiaUnavailable) as refusal:
            fia.fetch_archive(now=lambda: NOW, opener=refuse)
        self.assertIn("connection reset", str(refusal.exception))

    def test_only_strictness_is_relaxed_and_verification_stays_on(self):
        """Measured 2026-08-14 from the api container: this chain fails the strict default with
        `Missing Subject Key Identifier` and completes with that one flag cleared. What must not
        drift is the *rest* — a relaxation that also turned off hostname checking or trust would
        be a different decision wearing this one's comment."""
        import ssl  # noqa: PLC0415

        context = fia.tls_context()
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)
        if hasattr(ssl, "VERIFY_X509_STRICT"):
            self.assertFalse(context.verify_flags & ssl.VERIFY_X509_STRICT)


class FakeStore:
    """`BusinessTaxStore`'s methods, in memory. The sequencing is what is being tested."""

    def __init__(self, held=None, previous=None, wanted=None):
        self._held = held
        self.previous = previous
        self.wanted = wanted if wanted is not None else list(WANTED)
        self.written = []
        self.committed = False
        self.rolled_back = False
        self.counted = None

    async def latest(self, source):
        return self.previous

    async def held(self, source, content_sha256):
        return self._held

    async def reference_business_nos(self):
        return list(self.wanted)

    async def claim(self, archive, scope):
        return None if self._held is not None else 11

    async def write(self, publication_id, rows):
        self.written = list(rows)
        return len(rows)

    async def accepted(self, publication_id):
        return len(self.written)

    async def record_count(self, publication_id, tax_rows):
        self.counted = tax_rows

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rolled_back = True


class Held:
    def __init__(self, publication_id=5, content_sha256="a" * 64, file_stamp=None):
        self.publication_id = publication_id
        self.content_sha256 = content_sha256
        self.file_stamp = file_stamp


class TheSequencing(unittest.TestCase):
    """Claim first, parse only if the claim said the content is new."""

    def ingest(self, store, archive=None, **kwargs):
        return asyncio.run(
            run_business_tax.ingest_archive(store, archive or archive_of(), **kwargs)
        )

    def test_a_new_hash_parses_and_stores(self):
        store = FakeStore()
        verdict = self.ingest(store)
        self.assertTrue(verdict.stored and verdict.parsed)
        self.assertEqual(verdict.rows_held, 2)
        self.assertTrue(store.committed)

    def test_an_unchanged_day_never_decompresses_the_file(self):
        """The guarantee is invisible from outside, so the parser is the assertion."""

        def refuse(_raw, _wanted):
            raise AssertionError("the 320 MB CSV was parsed on a no-change day")

        store = FakeStore(held=Held())
        verdict = self.ingest(store, parse=refuse)
        self.assertFalse(verdict.parsed)
        self.assertTrue(store.rolled_back)
        self.assertFalse(store.committed)

    def test_force_parse_writes_into_the_publication_already_held(self):
        store = FakeStore(held=Held(publication_id=5))
        verdict = self.ingest(store, force_parse=True)
        self.assertTrue(verdict.parsed)
        self.assertFalse(verdict.stored, "a forced re-parse did not store a new publication")
        self.assertEqual(verdict.publication_id, 5)

    def test_the_reference_set_is_read_after_the_claim_not_before(self):
        """On a no-change day the reference query is not run either — one insert is the whole
        cost of learning there is nothing to do."""
        asked = []

        class Watching(FakeStore):
            async def reference_business_nos(self):
                asked.append(True)
                return list(self.wanted)

        self.ingest(Watching(held=Held()), parse=lambda raw, wanted: None)
        self.assertEqual(asked, [])


class TheDisagreement(unittest.TestCase):
    """Exit 2: the stamp and the hash contradict each other about whether anything changed."""

    def test_new_content_under_a_still_stamp_is_an_alarm(self):
        store = FakeStore(previous=Held(content_sha256="b" * 64, file_stamp=date(2026, 8, 14)))
        verdict = asyncio.run(run_business_tax.ingest_archive(store, archive_of()))
        self.assertTrue(verdict.stored)
        self.assertEqual(verdict.exit_code(), 2)
        self.assertIn("the content changed and the file's own stamp did not", verdict.alarms[0])

    def test_a_moved_stamp_over_unchanged_content_is_an_alarm(self):
        archive = archive_of()
        store = FakeStore(
            held=Held(content_sha256=archive.content_sha256),
            previous=Held(content_sha256=archive.content_sha256, file_stamp=date(2026, 7, 14)),
        )
        verdict = asyncio.run(run_business_tax.ingest_archive(store, archive))
        self.assertFalse(verdict.parsed)
        self.assertEqual(verdict.exit_code(), 2)
        self.assertIn("stamp moved", verdict.alarms[0])

    def test_the_two_signals_agreeing_is_exit_zero(self):
        archive = archive_of()
        store = FakeStore(previous=Held(content_sha256="b" * 64, file_stamp=date(2026, 7, 14)))
        verdict = asyncio.run(run_business_tax.ingest_archive(store, archive))
        self.assertEqual(verdict.alarms, [])
        self.assertEqual(verdict.exit_code(), 0)

    def test_a_first_run_has_nothing_to_disagree_with(self):
        verdict = asyncio.run(run_business_tax.ingest_archive(FakeStore(), archive_of()))
        self.assertEqual(verdict.alarms, [])


class TheRunRow(unittest.TestCase):
    def verdict(self, stored, alarms=()):
        return run_business_tax.Verdict(
            source=fia.SOURCE,
            content_sha256="a" * 64,
            stamp_label="2026-08-14",
            stored=stored,
            parsed=stored,
            publication_id=9,
            rows_held=14_500,
            alarms=list(alarms),
        )

    def test_a_stored_run_files_its_publication_under_the_seventh_column(self):
        record = run_business_tax.run_record(self.verdict(stored=True), NOW, "cli")
        self.assertEqual(record.outcome, runlog.STORED)
        self.assertEqual(record.column(), "business_tax_publication_id")
        self.assertEqual(record.rows_written, 14_500)

    def test_a_no_op_attaches_no_publication(self):
        record = run_business_tax.run_record(self.verdict(stored=False), NOW, "cli")
        self.assertEqual(record.outcome, runlog.NO_CHANGE)
        self.assertIsNone(record.publication_id)
        self.assertEqual(record.rows_written, 0)

    def test_an_alarm_is_not_a_failure_and_lands_in_detail(self):
        record = run_business_tax.run_record(
            self.verdict(stored=True, alarms=["DISAGREEMENT: something"]), NOW, "airflow"
        )
        self.assertEqual(record.outcome, runlog.STORED)
        self.assertIn("DISAGREEMENT", record.detail)
        self.assertEqual(record.invoked_by, "airflow")


if __name__ == "__main__":
    unittest.main(verbosity=2)
