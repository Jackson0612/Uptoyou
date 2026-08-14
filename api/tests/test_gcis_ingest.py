#!/usr/bin/env python3
"""The registry-status ingest (D81) — parse and ledger mapping. No network, no database.

Run: python3 app/api/tests/test_gcis_ingest.py

What the parse must hold: the tuple is the unit (統編 reuse is measured real, so a number
may carry several names and statuses and all of them survive), the status is stored
verbatim (the full-width slash in 歇業／撤銷 is the label, not a width accident), and a
row with no 統編 is skipped rather than refused — this file joins on our key, it does not
carry one.
"""

import os
import sys
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from upto.ingest import gcis, runlog  # noqa: E402
from upto.ingest.foodtracer import FoodtracerUnavailable  # noqa: E402
from upto.ingest.gcis import GcisUnavailable, parse_statuses  # noqa: E402
from upto.ingest.run_business_status import Verdict, run_record  # noqa: E402

HEADER = '"統一編號","商業名稱","商業地址","登記狀態","備註"'

NOW = datetime(2026, 8, 14, 10, 0, tzinfo=timezone.utc)


def row(no, name, status):
    return '"{}","{}","某市某路1號","{}",""'.format(no, name, status)


def csv_bytes(rows, header=HEADER):
    return ("﻿" + "\n".join([header] + rows) + "\n").encode("utf-8")


class Parsing(unittest.TestCase):
    def test_a_tuple_is_kept_whole_and_verbatim(self):
        result = parse_statuses(csv_bytes([row("00509924", "霓霓爸爸的麵線", "歇業／撤銷")]))
        kept = result.rows[0]
        self.assertEqual(kept.business_no, "00509924")
        self.assertEqual(kept.status, "歇業／撤銷", "the full-width slash is part of the label")

    def test_one_number_may_carry_several_businesses(self):
        # Measured on 2026-08-14: 2,189 numbers repeat, 1,714 with mixed statuses, and the
        # same number can name two genuinely different businesses. Both rows must survive.
        raw = csv_bytes(
            [
                row("00346828", "元氣堂養生館", "歇業／撤銷"),
                row("00346828", "祿記商號", "核准設立"),
            ]
        )
        result = parse_statuses(raw)
        self.assertEqual(len(result.rows), 2)
        self.assertEqual(result.numbers, 1)

    def test_an_exactly_repeated_tuple_is_stored_once(self):
        raw = csv_bytes([row("00000001", "某店", "停業"), row("00000001", "某店", "停業")])
        self.assertEqual(len(parse_statuses(raw).rows), 1)

    def test_a_row_with_no_number_is_skipped_not_refused(self):
        raw = csv_bytes([row("", "無統編的列", "核准設立"), row("00000001", "某店", "停業")])
        result = parse_statuses(raw)
        self.assertEqual(result.scanned, 2)
        self.assertEqual(len(result.rows), 1)

    def test_an_empty_status_is_kept_and_harmless(self):
        # Three existed on the measured file. Kept: an empty status is in no dead set, so
        # the number stays visible, which is the safe direction.
        result = parse_statuses(csv_bytes([row("00000001", "某店", "")]))
        self.assertEqual(result.rows[0].status, "")

    def test_a_missing_column_is_a_failure_naming_what_is_missing(self):
        raw = csv_bytes([row("00000001", "某店", "停業")], header=HEADER.replace("登記狀態", "狀態"))
        with self.assertRaises(GcisUnavailable) as failure:
            parse_statuses(raw)
        self.assertIn("登記狀態", str(failure.exception))

    def test_an_empty_file_is_a_failure_not_an_empty_success(self):
        with self.assertRaises(GcisUnavailable):
            parse_statuses(csv_bytes([]))

    def test_the_refusals_are_catchable_as_the_shared_fetchs_class(self):
        self.assertTrue(issubclass(GcisUnavailable, FoodtracerUnavailable))


class RunRow(unittest.TestCase):
    def verdict(self, stored):
        return Verdict(
            source=gcis.SOURCE,
            content_sha256="a" * 64,
            stored=stored,
            parsed=stored,
            publication_id=9,
            rows_held=206_611,
        )

    def test_a_stored_run_files_its_publication_under_the_sixth_column(self):
        record = run_record(self.verdict(stored=True), NOW, "cli")
        self.assertEqual(record.outcome, runlog.STORED)
        self.assertEqual(record.column(), "business_status_publication_id")

    def test_a_no_op_attaches_no_publication(self):
        record = run_record(self.verdict(stored=False), NOW, "cli")
        self.assertEqual(record.outcome, runlog.NO_CHANGE)
        self.assertIsNone(record.publication_id)


if __name__ == "__main__":
    unittest.main(verbosity=2)
