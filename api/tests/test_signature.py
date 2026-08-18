#!/usr/bin/env python3
"""D102's column signature — the hash rule, and the two derivations.

Run: python3 app/api/tests/test_signature.py    (no network, no database)

The tests worth reading are the ones about what must *not* collide: two different headers that a
sloppier join would hash alike, and a JSON payload signed twice by decoders that walked its keys
in different orders.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from upto.ingest import signature  # noqa: E402


class TheHash(unittest.TestCase):
    def test_the_same_header_signs_the_same(self):
        first, _ = signature.from_csv_header(["a", "b", "c"])
        second, _ = signature.from_csv_header(["a", "b", "c"])
        self.assertEqual(first, second)
        self.assertEqual(len(first), 64)

    def test_a_renamed_column_signs_differently(self):
        self.assertNotEqual(
            signature.from_csv_header(["a", "b"])[0],
            signature.from_csv_header(["a", "B"])[0],
        )

    def test_an_added_column_signs_differently(self):
        self.assertNotEqual(
            signature.from_csv_header(["a", "b"])[0],
            signature.from_csv_header(["a", "b", "c"])[0],
        )

    def test_reordered_columns_sign_differently_for_csv(self):
        """A CSV's column order is part of its shape: a positional reader breaks on a swap."""
        self.assertNotEqual(
            signature.from_csv_header(["a", "b"])[0],
            signature.from_csv_header(["b", "a"])[0],
        )

    def test_a_name_containing_the_separator_character_cannot_forge_another_header(self):
        """The reason the join is a unit separator and not a comma.

        With a comma, `("a,b", "c")` and `("a", "b,c")` join to the same string and hash alike —
        two different shapes reading as one, which is the failure this column exists to catch.
        """
        self.assertNotEqual(
            signature.from_csv_header(["a,b", "c"])[0],
            signature.from_csv_header(["a", "b,c"])[0],
        )

    def test_no_columns_is_an_empty_signature_not_a_hash_of_nothing(self):
        """`sha256("")` is a real, memorable-looking hex string. Returning it would make "no
        signature taken" indistinguishable from a file whose header was empty."""
        self.assertEqual(signature.digest([]), "")
        self.assertEqual(signature.from_csv_header([])[0], "")


class TheTwoDerivations(unittest.TestCase):
    def test_json_keys_are_sorted_before_hashing(self):
        """Two decoders walking the same object in different orders must agree."""
        one, names = signature.from_json_keys({"b": 1, "a": 2})
        two, _ = signature.from_json_keys({"a": 2, "b": 1})
        self.assertEqual(one, two)
        self.assertEqual(names, ["a", "b"])

    def test_a_json_record_and_a_csv_header_of_the_same_names_agree(self):
        """One column, one comparison rule: a reader does not need to know which kind of source
        theirs is. The CSV names have to be in sorted order for this to hold, which is the whole
        of the difference between the two functions."""
        self.assertEqual(
            signature.from_json_keys({"a": 1, "b": 2})[0],
            signature.from_csv_header(["a", "b"])[0],
        )

    def test_an_absent_record_signs_empty_rather_than_raising(self):
        self.assertEqual(signature.from_json_keys(None), ("", []))
        self.assertEqual(signature.from_json_keys({}), ("", []))


class TheStoredColumn(unittest.TestCase):
    def test_names_become_a_json_array(self):
        self.assertEqual(signature.as_json(["a", "b"]), '["a", "b"]')

    def test_cjk_names_are_not_escaped(self):
        """The headers here are Chinese. `\\u5e97` in a stored column is unreadable in psql."""
        self.assertEqual(signature.as_json(["店名"]), '["店名"]')

    def test_an_empty_list_is_null_not_an_empty_array(self):
        """"No signature taken" and "a file with no columns" are different facts."""
        self.assertIsNone(signature.as_json([]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
