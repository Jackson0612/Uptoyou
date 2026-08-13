#!/usr/bin/env python3
"""Ticket 10 — the fold, tested without a network or a database.

Run: python3 app/api/tests/test_weight_fold.py

D45's worked example is a test here because the example *is* the decision: a private zero
survives a commercial 1.5, or the veto is negotiable and the design has failed. The clamp
tests are D45's named debt; the exactness and ordering tests are D46's.
"""

import os
import sys
import unittest
from decimal import Decimal
from fractions import Fraction

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from upto.engine import Clamp, Contribution, fold  # noqa: E402


def contribution(id=1, place_id=7, channel="contextual", contributor="weather",
                 effect="0.8", reason="raining, 12 minutes' walk"):
    return Contribution(id=id, place_id=place_id, channel=channel,
                        contributor=contributor, effect=Decimal(effect), reason=reason)


class TestWorkedExample(unittest.TestCase):
    """D45's own numbers: 小林拉麵, three contributions."""

    def test_veto_is_not_bought_back(self):
        result = fold(7, [
            contribution(id=1, channel="contextual", contributor="weather", effect="0.8"),
            contribution(id=2, channel="private", contributor="preference", effect="0",
                         reason="avoids chilli, this place is 麻辣"),
            contribution(id=3, channel="commercial", contributor="coupon", effect="1.5",
                         reason="partner place"),
        ])
        self.assertEqual(result.weight, Decimal("0"))

    def test_no_contributions_means_weight_one(self):
        result = fold(7, [])
        self.assertEqual(result.weight, Decimal("1"))
        self.assertEqual(result.clamps, ())


class TestClamp(unittest.TestCase):
    """D45's debt: a row CHECK cannot see a product across rows, so the engine must."""

    def test_compounding_contextual_is_clamped_to_half(self):
        # D45's example, one factor further: 0.8³ = 0.512 still sits inside [0.5, 2], so the
        # clamp rightly leaves it alone — it takes a fourth 0.8 (0.4096) to cross the line
        # the channel may not cross, and that is where the clamp binds.
        result = fold(7, [
            contribution(id=i, contributor=f"c{i}", effect="0.8") for i in (1, 2, 3, 4)
        ])
        self.assertEqual(result.channel_products["contextual"], Decimal("0.4096"))
        self.assertEqual(result.weight, Decimal("0.5"))
        self.assertEqual(result.clamps, (
            Clamp(channel="contextual", raw=Decimal("0.4096"), clamped=Decimal("0.5")),
        ))

    def test_three_point_eights_stay_inside_range_unclamped(self):
        result = fold(7, [
            contribution(id=i, contributor=f"c{i}", effect="0.8") for i in (1, 2, 3)
        ])
        self.assertEqual(result.weight, Decimal("0.512"))
        self.assertEqual(result.clamps, ())

    def test_compounding_commercial_is_clamped_down(self):
        result = fold(7, [
            contribution(id=i, channel="commercial", contributor=f"c{i}", effect="1.5",
                         reason="partner place") for i in (1, 2)
        ])
        self.assertEqual(result.weight, Decimal("1.5"))
        self.assertEqual(result.clamps[0].raw, Decimal("2.25"))

    def test_unclamped_fold_reports_no_clamp(self):
        result = fold(7, [contribution()])
        self.assertEqual(result.clamps, ())

    def test_private_zero_cannot_be_clamped_back_up(self):
        # The clamp pulls a product into range; private's range starts at 0, so a veto is
        # inside range and the clamp never touches it. Stated as a test because the clamp
        # is the one mechanism in the fold that raises a number.
        result = fold(7, [
            contribution(id=1, channel="private", contributor="a", effect="0",
                         reason="cannot afford it"),
            contribution(id=2, channel="private", contributor="b", effect="0.5",
                         reason="too far tonight"),
        ])
        self.assertEqual(result.weight, Decimal("0"))
        self.assertEqual(result.clamps, ())


class TestOrder(unittest.TestCase):
    """D46: one total order — channel, contributor name, id — for fold and panel alike."""

    def test_display_order_is_channel_then_name_then_id(self):
        shuffled = [
            contribution(id=9, channel="commercial", contributor="coupon", effect="1.5",
                         reason="partner place"),
            contribution(id=4, channel="contextual", contributor="weather", effect="0.8"),
            contribution(id=2, channel="contextual", contributor="distance", effect="0.9",
                         reason="a long walk in the rain"),
            contribution(id=5, channel="private", contributor="preference", effect="0.5",
                         reason="had it yesterday"),
            contribution(id=3, channel="contextual", contributor="distance", effect="1.1",
                         reason="right around the corner"),
        ]
        result = fold(7, shuffled)
        self.assertEqual(
            [(c.channel, c.contributor, c.id) for c in result.contributions],
            [("private", "preference", 5),
             ("contextual", "distance", 2),
             ("contextual", "distance", 3),
             ("contextual", "weather", 4),
             ("commercial", "coupon", 9)],
        )

    def test_same_input_same_tuple_regardless_of_arrival_order(self):
        a = [contribution(id=i, contributor=f"c{i}", effect="0.9") for i in (3, 1, 2)]
        self.assertEqual(fold(7, a).contributions, fold(7, list(reversed(a))).contributions)


class TestExactness(unittest.TestCase):
    """D46: the fold multiplies exactly, and past its precision it raises rather than rounds."""

    def test_fold_matches_exact_rational_arithmetic(self):
        # Fifteen three-place factors — well past Python's default 28-digit context, which
        # is the silent rounding D46 warns about. Fraction arithmetic is exact by
        # construction, so agreement here means the fold is too.
        effects = ["0.8", "0.9", "1.1", "0.7", "1.9", "0.6", "1.2", "0.8",
                   "0.9", "1.1", "0.7", "1.3", "0.8", "0.9", "1.1"]
        result = fold(7, [
            contribution(id=i, contributor=f"c{i:02d}", effect=e)
            for i, e in enumerate(effects, start=1)
        ])
        exact = Fraction(1)
        for e in effects:
            exact *= Fraction(e)
        raw = result.channel_products["contextual"]
        self.assertEqual(Fraction(raw), exact)

    def test_weight_is_a_decimal(self):
        self.assertIsInstance(fold(7, [contribution()]).weight, Decimal)


class TestRecordValidation(unittest.TestCase):
    """D45's CHECKs mirrored at construction, and H8's sentence rule."""

    def test_private_may_not_lift(self):
        with self.assertRaises(ValueError):
            contribution(channel="private", effect="1.2", reason="x")

    def test_contextual_cannot_reach_zero(self):
        with self.assertRaises(ValueError):
            contribution(channel="contextual", effect="0.4")

    def test_commercial_may_not_suppress(self):
        with self.assertRaises(ValueError):
            contribution(channel="commercial", effect="0.9", reason="x")

    def test_effect_scale_is_three_decimal_places(self):
        with self.assertRaises(ValueError):
            contribution(effect="0.8005")

    def test_effect_must_be_decimal_not_float(self):
        with self.assertRaises(TypeError):
            Contribution(id=1, place_id=7, channel="contextual", contributor="weather",
                         effect=0.8, reason="x")

    def test_reason_is_required(self):
        with self.assertRaises(ValueError):
            contribution(reason="   ")

    def test_contributor_name_is_required(self):
        with self.assertRaises(ValueError):
            contribution(contributor="")

    def test_unknown_channel_is_refused(self):
        with self.assertRaises(ValueError):
            contribution(channel="editorial")

    def test_fold_is_per_place(self):
        with self.assertRaises(ValueError):
            fold(7, [contribution(place_id=8)])


if __name__ == "__main__":
    unittest.main(verbosity=2)
