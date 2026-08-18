#!/usr/bin/env python3
"""A1's private preference contributor — the pure half.

Run: python3 app/api/tests/test_preference_contributor.py    (no network, no database)

The tests worth reading are the two absences. A place with **no category** must produce nothing,
because only 6.2% of the reference list has one today and treating unknown as avoided would zero
most of the city; and a category the member said nothing about must produce nothing rather than a
factor of 1, because D43's no-record-no-effect is what keeps the reveal panel silent about places a
preference never touched.
"""

import os
import sys
import unittest
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from upto.engine.preference import (  # noqa: E402
    AVOID_EFFECT,
    CONTRIBUTOR_NAME,
    REASON_VISIBILITY,
    avoid_contribution,
)


class AnAvoidedCategory(unittest.TestCase):
    def test_it_zeroes_the_place(self):
        """D45: contributions multiply, so zero is the only factor no later one recovers. A veto
        that can be bought back is not a veto."""
        record = avoid_contribution(1, 42, "火鍋", {"火鍋"})
        self.assertIsNotNone(record)
        self.assertEqual(record.effect, Decimal("0"))
        self.assertEqual(record.effect, AVOID_EFFECT)

    def test_it_is_a_private_contribution_by_the_named_contributor(self):
        """D46: the contributor's name is data, not a class attribute — renaming it rewrites how
        historical rounds sort."""
        record = avoid_contribution(1, 42, "火鍋", {"火鍋"})
        self.assertEqual(record.channel, "private")
        self.assertEqual(record.contributor, CONTRIBUTOR_NAME)

    def test_the_reason_names_the_category(self):
        """It is read by the represented member and by nobody else, and the preference row already
        states the same fact — so withholding it from its only reader buys nothing."""
        record = avoid_contribution(1, 42, "燒烤", {"燒烤", "火鍋"})
        self.assertIn("燒烤", record.reason)

    def test_the_reason_names_no_member(self):
        """A row that identifies a person is the exposure §3.0 is built against, whatever the
        visibility column says."""
        record = avoid_contribution(7, 42, "燒烤", {"燒烤"})
        self.assertNotIn("7", record.reason)

    def test_it_carries_the_place_and_the_synthetic_id_it_was_given(self):
        record = avoid_contribution(9, 314, "日式", {"日式"})
        self.assertEqual(record.id, 9)
        self.assertEqual(record.place_id, 314)

    def test_one_avoided_category_among_several_still_fires(self):
        record = avoid_contribution(1, 42, "小吃", {"小吃", "西式", "早餐"})
        self.assertIsNotNone(record)

    def test_the_visibility_this_channel_takes_is_not_the_table(self):
        """`weight_contribution` will carry a CHECK refusing `table` for a private row; this names
        the value the contributor's rows are written with so the two cannot disagree."""
        self.assertEqual(REASON_VISIBILITY, "represented_member")
        self.assertNotEqual(REASON_VISIBILITY, "table")


class TheTwoAbsences(unittest.TestCase):
    def test_a_place_with_no_category_produces_nothing(self):
        """Measured 2026-08-18: 2,267 of 36,499 reference rows carry a category, because one
        township has been classified. Treating unknown as avoided would zero most of the city.
        Same choice the loader already makes for a circle-local place with no township (D28):
        the absence of a fact is not evidence against the place."""
        self.assertIsNone(avoid_contribution(1, 42, None, {"火鍋"}))

    def test_a_category_the_member_said_nothing_about_produces_nothing(self):
        """D43's no-record-no-effect. Returning a factor of 1 would be arithmetically identical
        and would put a row on the reveal panel for a place no preference touched."""
        self.assertIsNone(avoid_contribution(1, 42, "火鍋", {"燒烤"}))

    def test_an_empty_avoided_set_produces_nothing(self):
        self.assertIsNone(avoid_contribution(1, 42, "火鍋", set()))

    def test_no_category_and_no_preferences_produces_nothing(self):
        self.assertIsNone(avoid_contribution(1, 42, None, set()))


class TheSetIsTakenAsGiven(unittest.TestCase):
    def test_a_list_works_as_well_as_a_set(self):
        """The loader builds it from a query; forcing it to hand over a set would be this module
        knowing something about the caller."""
        self.assertIsNotNone(avoid_contribution(1, 42, "西式", ["西式", "早餐"]))

    def test_a_tuple_works_too(self):
        self.assertIsNotNone(avoid_contribution(1, 42, "西式", ("西式",)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
