#!/usr/bin/env python3
"""A9's publication check — the three states, and the two ways a source can go wrong.

Run: python3 app/api/tests/test_publication_check.py    (no network, no database, no Airflow)

The comparison lives in `app/airflow/dags/_publication_check.py` and imports Airflow only inside
`make_check_task`, which is why this file can import it at all: the host has no Airflow.

**The tests worth reading are the ones about «n/a» rather than the ones about «fail».** A drift
detector that turns red on a changed hash is the easy half. The half that decides whether this
check is honest is what it does when it *cannot* compare — four of the five sources have exactly one
publication today, and a check that painted that green would be claiming a comparison it never made.
So: an unanswerable question is never a pass, and the two halves must be unanswerable *separately*
without the answerable one being lost.
"""

import os
import sys
import unittest

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "airflow", "dags"))

import _publication_check as check  # noqa: E402

A = "a" * 64
B = "b" * 64


def publication(identifier=2, signature=A, names=("統一編號", "登記名稱"), rows=1000):
    return {
        "id": identifier,
        "signature": signature,
        "names": list(names) if names is not None else None,
        "rows": rows,
    }


class TheThreeStatesAreDistinct(unittest.TestCase):
    """Green, skipped and red must never stand in for one another."""

    def test_same_shape_and_a_steady_row_count_passes(self):
        state, sentence = check.verdict("fda-97", publication(), publication(1, rows=1000))
        self.assertEqual(state, check.PASS)
        self.assertIn("shape unchanged", sentence)
        self.assertIn("not down", sentence)

    def test_no_previous_publication_is_not_a_pass(self):
        """Today's behaviour for four of the five sources. Green here would be a false claim."""
        state, sentence = check.verdict("taipei-foodtracer", publication(), None)
        self.assertEqual(state, check.NOT_APPLICABLE)
        self.assertIn("no previous publication", sentence)
        # The precondition is named, so the log says what would make the check possible.
        self.assertIn("republishes", sentence)

    def test_the_n_a_sentence_names_the_source_it_could_not_check(self):
        """Five DAGs share this code; a sentence that does not say which source is a sentence that
        sends the reader to the UI to find out."""
        _, sentence = check.verdict("gcis-restaurant-registry", publication(), None)
        self.assertIn("gcis-restaurant-registry", sentence)

    def test_a_changed_signature_fails(self):
        state, sentence = check.verdict(
            "fda-97", publication(signature=B), publication(1, signature=A))
        self.assertEqual(state, check.FAIL)
        self.assertIn("changed the shape", sentence)

    def test_a_collapsed_row_count_fails(self):
        state, sentence = check.verdict(
            "fda-97", publication(rows=700), publication(1, rows=1000))
        self.assertEqual(state, check.FAIL)
        self.assertIn("collapsed", sentence)
        self.assertIn("700", sentence)
        self.assertIn("1000", sentence)


class TheDriftAnswerNamesTheColumns(unittest.TestCase):
    """A hash that moved is not an answer anybody can act on."""

    def test_an_added_column_is_named(self):
        _, sentence = check.verdict(
            "fda-97",
            publication(signature=B, names=("統一編號", "登記名稱", "營業狀況")),
            publication(1, signature=A, names=("統一編號", "登記名稱")),
        )
        self.assertIn("營業狀況", sentence)

    def test_a_removed_column_is_named(self):
        _, sentence = check.verdict(
            "fda-97",
            publication(signature=B, names=("統一編號",)),
            publication(1, signature=A, names=("統一編號", "登記名稱")),
        )
        self.assertIn("vanished", sentence)
        self.assertIn("登記名稱", sentence)

    def test_a_reordering_is_a_change_of_shape_and_says_so(self):
        """D102 signs the *ordered* list, so a swap is real: a positional reader breaks on it.
        Naming no added and no removed column would read as a hash collision otherwise."""
        _, sentence = check.verdict(
            "fda-97",
            publication(signature=B, names=("登記名稱", "統一編號")),
            publication(1, signature=A, names=("統一編號", "登記名稱")),
        )
        self.assertIn("different order", sentence)


class TheRowCountLineIsOneSided(unittest.TestCase):
    def test_growth_is_never_a_failure(self):
        state, _ = check.verdict("fda-97", publication(rows=100000), publication(1, rows=1000))
        self.assertEqual(state, check.PASS)

    def test_a_drop_inside_the_line_passes_and_the_number_is_still_printed(self):
        """19% is not a failure and is still worth reading — a threshold that hides everything
        below it teaches nobody where it sits."""
        state, sentence = check.verdict("fda-97", publication(rows=810), publication(1, rows=1000))
        self.assertEqual(state, check.PASS)
        self.assertIn("19.0%", sentence)

    def test_exactly_the_threshold_fails(self):
        """«down 20% or more» — the boundary is stated as inclusive, so it is tested as inclusive."""
        state, _ = check.verdict("fda-97", publication(rows=800), publication(1, rows=1000))
        self.assertEqual(state, check.FAIL)

    def test_a_previous_count_of_zero_does_not_divide(self):
        state, sentence = check.verdict("fda-97", publication(rows=5), publication(1, rows=0))
        self.assertEqual(state, check.PASS)  # the shape half answered
        self.assertIn("0 rows", sentence)


class AnUnansweredHalfIsNotAPass(unittest.TestCase):
    """D102 backfills nothing, so `NULL` is ordinary on older publications and must not read as OK."""

    def test_a_null_signature_is_reported_as_not_compared(self):
        state, sentence = check.verdict(
            "fda-97", publication(signature=None), publication(1, signature=A))
        self.assertEqual(state, check.PASS)  # the row count still answered
        self.assertIn("shape NOT compared", sentence)
        self.assertIn("predates", sentence)

    def test_which_side_is_missing_is_named(self):
        _, sentence = check.verdict(
            "fda-97", publication(signature=A), publication(1, signature=None))
        self.assertIn("the previous publication", sentence)

    def test_both_halves_unanswerable_is_n_a_not_a_pass(self):
        """The case that would otherwise be a green task that compared nothing at all."""
        state, sentence = check.verdict(
            "fda-97",
            publication(signature=None, rows=None),
            publication(1, signature=None, rows=None),
        )
        self.assertEqual(state, check.NOT_APPLICABLE)
        self.assertIn("neither question could be answered", sentence)

    def test_one_answerable_half_is_enough_for_a_pass(self):
        state, _ = check.verdict(
            "fda-97",
            publication(signature=A, rows=None),
            publication(1, signature=A, rows=None),
        )
        self.assertEqual(state, check.PASS)

    def test_an_unanswerable_half_never_hides_an_answerable_failure(self):
        """The one that would be worst to get wrong: a missing signature must not swallow a
        collapsed row count."""
        state, sentence = check.verdict(
            "fda-97",
            publication(signature=None, rows=10),
            publication(1, signature=A, rows=1000),
        )
        self.assertEqual(state, check.FAIL)
        self.assertIn("collapsed", sentence)


class AMissingPublicationIsABugNotAQuietDay(unittest.TestCase):
    def test_stored_with_no_publication_row_fails(self):
        state, sentence = check.verdict("fda-97", None, None)
        self.assertEqual(state, check.FAIL)
        self.assertIn("bug", sentence)


class TheSourceKeysAreTheLedgersOwn(unittest.TestCase):
    """The trap this check has to survive: three of the four name-reference DAGs print a display
    label that is not the string the ledger stores, and keying off it would find zero rows — which
    would read as «no previous publication», a false n/a. Measured against the live ledger
    2026-08-19."""

    def test_all_five_publication_sources_are_mapped(self):
        self.assertEqual(len(check.SOURCES), 5)

    def test_the_keys_are_the_ledger_strings_and_not_the_display_labels(self):
        for key in ("fda-97", "taipei-foodtracer", "taipei-hygiene-grade",
                    "gcis-restaurant-registry", "fia-business-tax"):
            self.assertIn(key, check.SOURCES)
        for label in ("foodtracer-brands", "gradelist-storefronts", "gcis-status"):
            self.assertNotIn(label, check.SOURCES)

    def test_every_source_names_a_row_count_column_and_a_ledger_foreign_key(self):
        for key, (table, rows_column, foreign_key) in check.SOURCES.items():
            self.assertTrue(table.endswith("_publication"), key)
            self.assertTrue(rows_column.endswith("_rows"), key)
            self.assertTrue(foreign_key.endswith("_publication_id"), key)

    def test_an_unknown_source_is_refused_at_parse_time_not_at_run_time(self):
        """`make_check_task` is called while the DAG is being parsed, so a wrong key is an import
        error the DAG processor reports — not a task that fails at 03:20 in the morning."""
        with self.assertRaises(KeyError):
            check.make_check_task("foodtracer-brands")


if __name__ == "__main__":
    unittest.main(verbosity=2)
