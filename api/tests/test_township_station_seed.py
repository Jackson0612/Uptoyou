#!/usr/bin/env python3
"""Ticket 06's seed, checked without a database.

Run: python3 app/api/tests/test_township_station_seed.py

The seed is data, so the tests are about the claims the data makes: that all twelve
townships are present, that the tiebreak D26 rules was actually applied where it applies,
that the three townships holding no station are D32's three and carry their measurement, and
that the self-check refuses rather than loading something plausible.

**A township where the tiebreak really applies is tested by name**, which the ticket asks for
specifically. 士林區 holds five stations; a seed that picked any of the other four would pass
a test that only counted rows.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from upto.seed import township_station as seed  # noqa: E402


class Completeness(unittest.TestCase):
    def test_all_twelve_townships(self):
        self.assertEqual(len(seed.MAPPINGS), 12)

    def test_every_township_resolves_to_exactly_one_station(self):
        by_code = {}
        for mapping in seed.MAPPINGS:
            self.assertNotIn(mapping.township_code, by_code, "two rows for one township")
            by_code[mapping.township_code] = mapping
        self.assertEqual(len(by_code), 12)

    def test_codes_are_the_taipei_range(self):
        # 臺北市 is 63000; its townships run 63000010 through 63000120, so the prefix is five
        # digits and not six — six passes for 63000010 and fails for 63000100, which is what
        # this assertion did when first written.
        for mapping in seed.MAPPINGS:
            self.assertRegex(
                mapping.township_code,
                r"^63000\d{3}$",
                "{} is not a 臺北市 township code".format(mapping.township_code),
            )

    def test_self_check_passes_as_shipped(self):
        seed.check_self_consistent()


class Tiebreak(unittest.TestCase):
    """D26: where a township holds several stations, the lowest altitude wins."""

    def test_shilin_picks_the_lowest_of_five(self):
        # 社子 11 m against 天母 35, 科教館 60, 文化大學 424, 平等 426. A seed that picked any
        # other one would satisfy a test that merely counted rows.
        mapping = self.by_name("士林區")
        self.assertEqual(mapping.station_id, "C0A980")
        self.assertEqual(mapping.resolution, "lowest_altitude")

    def test_beitou_picks_the_lowest_of_five(self):
        mapping = self.by_name("北投區")
        self.assertEqual(mapping.station_id, "C2AA10")

    def test_wenshan_drops_the_freeway_sensor(self):
        """Altitude drops 國三甲005K in favour of 文山, as a side effect rather than a rule."""
        mapping = self.by_name("文山區")
        self.assertEqual(mapping.station_id, "C0AC80")

    def test_nangang_keeps_its_freeway_sensor(self):
        """It is the only instrument in the district, so the same rule keeps it."""
        mapping = self.by_name("南港區")
        self.assertEqual(mapping.station_id, "CAA040")
        self.assertIn("only instrument", mapping.source_note)

    def test_every_tiebreak_names_the_losers(self):
        for mapping in seed.MAPPINGS:
            if mapping.resolution == "lowest_altitude":
                self.assertTrue(
                    mapping.source_note and "beat" in mapping.source_note,
                    "{} won a tiebreak without naming what it beat".format(mapping.township_name),
                )

    def by_name(self, name):
        return next(m for m in seed.MAPPINGS if m.township_name == name)


class OfflineThree(unittest.TestCase):
    """D32: 中山, 大同, 萬華 hold no station and were resolved once, offline."""

    def test_exactly_three_and_they_are_the_named_three(self):
        names = sorted(m.township_name for m in seed.MAPPINGS if m.resolution == "offline_centroid")
        self.assertEqual(names, sorted(["中山區", "大同區", "萬華區"]))

    def test_each_carries_its_measurement(self):
        for mapping in seed.OFFLINE:
            self.assertIsNotNone(mapping.distance_km)
            self.assertIsNotNone(mapping.margin_km)
            self.assertIn("TWD97", mapping.source_note, "the datum has to be recorded, not implied")

    def test_no_margin_is_marginal(self):
        """D32 rests on this: the narrowest margin is 680 m, so a slightly wrong centroid
        does not change a winner. If a future re-measurement narrows one, this fails."""
        for mapping in seed.OFFLINE:
            self.assertGreaterEqual(float(mapping.margin_km), 0.6)

    def test_the_seed_records_that_they_were_resolved_offline(self):
        for mapping in seed.OFFLINE:
            self.assertEqual(mapping.resolution, "offline_centroid")


class SelfCheckRefuses(unittest.TestCase):
    """A township with no mapping must be a loud failure at load time, not a null at read."""

    def setUp(self):
        self.original = seed.MAPPINGS

    def tearDown(self):
        seed.MAPPINGS = self.original

    def test_a_missing_township_is_refused(self):
        seed.MAPPINGS = self.original[:-1]
        with self.assertRaises(seed.SeedRefused):
            seed.check_self_consistent()

    def test_a_duplicate_township_is_refused(self):
        seed.MAPPINGS = self.original + [self.original[0]]
        with self.assertRaises(seed.SeedRefused):
            seed.check_self_consistent()

    def test_an_offline_row_without_its_distance_is_refused(self):
        broken = seed.Mapping("63000040", "中山區", "C0AH70", "松山", "offline_centroid")
        seed.MAPPINGS = [m for m in self.original if m.township_code != "63000040"] + [broken]
        with self.assertRaises(seed.SeedRefused):
            seed.check_self_consistent()

    def test_a_code_matched_row_carrying_a_distance_is_refused(self):
        """Evidence attached to a row that did not need it is a claim nobody checked."""
        broken = seed.Mapping("63000010", "松山區", "C0AH70", "松山", "town_code", distance_km=1.0)
        seed.MAPPINGS = [m for m in self.original if m.township_code != "63000010"] + [broken]
        with self.assertRaises(seed.SeedRefused):
            seed.check_self_consistent()


class NoRuntimeArithmetic(unittest.TestCase):
    def test_the_module_computes_no_distance(self):
        """D26 and D32 both turn on this: the mapping is a lookup, and the file is the result
        of the calculation rather than the calculation."""
        source = open(seed.__file__, encoding="utf-8").read()
        for forbidden in ("math.", "sqrt", "radians", "haversine", "cos(", "sin("):
            self.assertNotIn(forbidden, source, "{} suggests run-time geometry".format(forbidden))


if __name__ == "__main__":
    unittest.main(verbosity=2)
