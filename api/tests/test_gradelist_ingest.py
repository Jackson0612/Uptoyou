#!/usr/bin/env python3
"""The storefront ingest (D78) — parse and ledger mapping. No network, no database.

Run: python3 app/api/tests/test_gradelist_ingest.py

The parse's two refusals are the point: a row with no registry number has no key, and a
repeated registry number means the file stopped being site-level — both are shape changes
answered loudly, never first-wins. The sequencing itself is `run_brands`' and is tested
there; what this file holds of the runner is the one seam that differs — the shared fetch
raises the *parent* exception class, and the runner must catch it.
"""

import os
import sys
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from upto.ingest import gradelist, runlog  # noqa: E402
from upto.ingest.foodtracer import FoodtracerUnavailable  # noqa: E402
from upto.ingest.gradelist import GradelistUnavailable, parse_storefronts  # noqa: E402
from upto.ingest.run_storefronts import Verdict, run_record  # noqa: E402

HEADER = "行政區域代碼,業者名稱店名,食品業者登錄字號,地址,評核結果"

NOW = datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc)


def row(name, registry_no, grade="優", district="63000010"):
    return "{},{},{},臺北市某路1號,{}".format(district, name, registry_no, grade)


def csv_bytes(rows, header=HEADER):
    return ("﻿" + "\n".join([header] + rows) + "\n").encode("utf-8")


class Parsing(unittest.TestCase):
    def test_a_site_row_is_kept_whole(self):
        result = parse_storefronts(csv_bytes([row("五花馬-松山機場", "A-154060356-00002-9")]))
        self.assertEqual(result.scanned, 1)
        kept = result.rows[0]
        self.assertEqual(kept.registry_no, "A-154060356-00002-9")
        self.assertEqual(kept.name, "五花馬-松山機場")
        self.assertEqual(kept.grade, "優")

    def test_the_name_is_normalised_and_the_raw_survives(self):
        result = parse_storefronts(csv_bytes([row("五花馬　松山１號店", "A-1")]))
        self.assertEqual(result.rows[0].name, "五花馬 松山1號店")
        self.assertEqual(result.rows[0].name_raw, "五花馬　松山１號店")

    def test_a_row_with_no_registry_number_is_a_failure_not_a_guess(self):
        with self.assertRaises(GradelistUnavailable):
            parse_storefronts(csv_bytes([row("某店", "")]))

    def test_a_repeated_registry_number_is_a_failure_naming_the_number(self):
        raw = csv_bytes([row("某店", "A-1"), row("同一家又來", "A-1")])
        with self.assertRaises(GradelistUnavailable) as failure:
            parse_storefronts(raw)
        self.assertIn("A-1", str(failure.exception))

    def test_a_missing_column_is_a_failure_naming_what_is_missing(self):
        raw = csv_bytes([row("某店", "A-1")], header=HEADER.replace("評核結果", "結果"))
        with self.assertRaises(GradelistUnavailable) as failure:
            parse_storefronts(raw)
        self.assertIn("評核結果", str(failure.exception))

    def test_a_row_with_no_name_is_a_failure(self):
        with self.assertRaises(GradelistUnavailable):
            parse_storefronts(csv_bytes([row("", "A-1")]))

    def test_an_empty_file_is_a_failure_not_an_empty_success(self):
        with self.assertRaises(GradelistUnavailable):
            parse_storefronts(csv_bytes([]))


class TheExceptionSeam(unittest.TestCase):
    def test_the_refusals_are_catchable_as_the_shared_fetchs_class(self):
        # The runner catches `FoodtracerUnavailable` because the shared fetch raises it;
        # this holds only while the subclassing holds, so it is stated as a test.
        self.assertTrue(issubclass(GradelistUnavailable, FoodtracerUnavailable))


class RunRow(unittest.TestCase):
    def verdict(self, stored):
        return Verdict(
            source=gradelist.SOURCE,
            content_sha256="a" * 64,
            stored=stored,
            parsed=stored,
            publication_id=9,
            names_held=1686,
        )

    def test_a_stored_run_files_its_publication_under_the_storefront_column(self):
        record = run_record(self.verdict(stored=True), NOW, "cli")
        self.assertEqual(record.outcome, runlog.STORED)
        self.assertEqual(record.column(), "storefront_publication_id")
        self.assertEqual(record.rows_written, 1686)

    def test_a_no_op_attaches_no_publication(self):
        record = run_record(self.verdict(stored=False), NOW, "cli")
        self.assertEqual(record.outcome, runlog.NO_CHANGE)
        self.assertIsNone(record.publication_id)


if __name__ == "__main__":
    unittest.main(verbosity=2)
