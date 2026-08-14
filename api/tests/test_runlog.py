#!/usr/bin/env python3
"""`upto.ingest.runlog`'s source-to-column mapping. No network, no database.

**This file exists because nothing tested `runlog` at all.** It was written for ticket 09, is
imported by every runner, and decides which of D24's four nullable foreign keys a run's publication
is filed under — and until 2026-08-12 an unregistered source was filed into item 11's column by a
`dict.get` default rather than refused.

What is *not* here: `record()` itself, which writes a row and commits, so it belongs with the
integration tests that have a database. This file covers the part that is pure arithmetic on a
string, which is also the part that was wrong.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from upto.ingest import fda, foodtracer, runlog  # noqa: E402


def run(source, publication_id=7):
    return runlog.RunRecord(
        source=source,
        started_at=runlog.now(),
        outcome=runlog.STORED,
        publication_id=publication_id,
    )


class EverySourceIsRegistered(unittest.TestCase):
    def test_the_four_known_sources_each_get_their_own_column(self):
        self.assertEqual(run("O-A0001-001").column(), "observation_publication_id")
        self.assertEqual(run("F-D0047-061").column(), "forecast_publication_id")
        self.assertEqual(run("fda-97").column(), runlog.PLACE_COLUMN)
        self.assertEqual(run("taipei-foodtracer").column(), "brand_publication_id")

    def test_the_columns_are_distinct(self):
        """D24 gives each source its own nullable key. Two sources sharing one column would make
        the run unanswerable in exactly the direction ticket 09 exists to fix."""
        columns = list(runlog.PUBLICATION_COLUMNS.values())
        self.assertEqual(len(columns), len(set(columns)), "two sources share a column")

    def test_item_elevens_source_string_has_not_drifted(self):
        """`runlog` writes `"fda-97"` out rather than importing it, because every runner imports
        `runlog` and it must not depend on any of them. That duplicate is what this guards: rename
        `fda.SOURCE` and the mapping silently stops covering it."""
        self.assertIn(
            fda.SOURCE,
            runlog.PUBLICATION_COLUMNS,
            "fda.SOURCE is {!r} and runlog does not register it — the duplicated literal has "
            "drifted, and an item 11 run would now be refused".format(fda.SOURCE),
        )

    def test_the_brand_sources_string_has_not_drifted(self):
        """The same duplicate, one source over: `foodtracer.SOURCE` is written out in `runlog`."""
        self.assertIn(
            foodtracer.SOURCE,
            runlog.PUBLICATION_COLUMNS,
            "foodtracer.SOURCE is {!r} and runlog does not register it".format(foodtracer.SOURCE),
        )


class AnUnknownSourceIsRefused(unittest.TestCase):
    def test_it_raises_rather_than_defaulting(self):
        """The mutation this kills: `PUBLICATION_COLUMNS.get(self.source, PLACE_COLUMN)`. Under it
        this call returns `place_publication_id` and a fourth source's publication is filed as item
        11's, which no later query can detect."""
        with self.assertRaises(runlog.UnknownSource):
            run("partner-seed-v1").column()

    def test_the_message_names_the_source_and_the_fix(self):
        """An exception nobody can act on sends the reader to the source anyway, which is the cost
        this project keeps paying for terse errors."""
        with self.assertRaises(runlog.UnknownSource) as refusal:
            run("partner-seed-v1").column()
        message = str(refusal.exception)
        self.assertIn("partner-seed-v1", message)
        self.assertIn("PUBLICATION_COLUMNS", message)

    def test_a_run_holding_no_publication_is_not_refused(self):
        """The control. Without it the rule above is satisfied by refusing everything, and a no-op
        — D42 made that the *ordinary* outcome, about twenty of twenty-four daily runs — carries no
        publication and no column, whatever its source. An unregistered source with nothing to file
        still has nothing to file."""
        self.assertIsNone(run("O-A0001-001", publication_id=None).column())
        self.assertIsNone(run("partner-seed-v1", publication_id=None).column())


if __name__ == "__main__":
    unittest.main(verbosity=0)
