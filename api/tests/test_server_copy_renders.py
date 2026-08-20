#!/usr/bin/env python3
"""Every character the server sends to a member must exist in the shipped font subset.

Run: python3 app/api/tests/test_server_copy_renders.py    (no network, no database, no browser)

**Why this test exists, and it is not the font's fault.** `tools/font_subset_check.py` asks whether
the shipped subset covers *the surface's own copy* — and that question it answers correctly. But a
`detail=` string in `upto/rounds.py` reaches the screen without ever passing through `app/web/`, so
it is outside the aim of that gate, and **a character outside the aim leaves no gap in the output**:
the gate prints "472 needed, 3812 committed" and passes, and the sentence arrives on the phone with a
hole in it. Found on a 1440x900 screenshot by the frontend session, 2026-08-19, on a screen that was
otherwise correct.

Same shape as `ui_characters()` reading `index.html` after D104 reduced it to a shell, and as the
footprint probe that listed the services it expected: **an omission with no shape is not something a
reader can notice.** So this test gives it one.

**It does not fix the font, and it must not be read as trying to.** Widening the derivation is with
the orchestrator; **the two characters below are known-missing and are the baseline, not an
exemption**. The baseline is checked in *both* directions, which is what keeps it from rotting:

  * a NEW missing character fails the test — a member-facing sentence written tomorrow cannot ship
    blank without this saying so;
  * a baseline character that is now PRESENT also fails the test, saying the derivation widened and
    this list should shrink. A baseline nobody is forced to revisit becomes a permanent excuse.

**Scope: `detail=` strings in the modules that serve HTTP, and nothing else.** Deliberately not every
CJK character in the package — `upto/classify/prompt.py` talks to a model, `upto/ingest/*` matches
publisher values, and `upto/naming.py`'s regex character classes contain `鿿` as a *range bound* and
`『』＆．` as separators. None of those render, and widening the font to cover pattern internals
would grow the file for nothing.
"""

import ast
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, "..", "src", "upto")
CHARSET = os.path.join(HERE, "..", "..", "web", "public", "fonts", "charset-sub.txt")

# The modules that build HTTP responses. A module added here that serves member-facing copy and is
# not in this tuple is unchecked, which is the one way this test can be silently narrowed.
SERVING = ("rounds.py", "preferences.py", "live.py", "api_common.py", "auth.py", "main.py")

# **Known missing as of 2026-08-19, and checked in both directions.** Character -> where it is.
# When the font derivation widens to cover server copy, this dict goes to empty and the test tells
# you to empty it.
KNOWN_MISSING = {
    "或": "rounds.py — 「池子是空的，或每一家的權重都是零，擲不出結果。」",
    "趟": "rounds.py — 「{}已經在 {} 記下這一趟了。」",
}


def shipped_characters():
    with open(CHARSET, encoding="utf-8") as handle:
        return set(handle.read()) - {"\n", "\r"}


def is_cjk(character):
    point = ord(character)
    return (0x3000 <= point <= 0x303F or 0x3400 <= point <= 0x4DBF
            or 0x4E00 <= point <= 0x9FFF or 0xF900 <= point <= 0xFAFF
            or 0xFF00 <= point <= 0xFFEF)


def member_facing_strings():
    """Every `detail=` string literal in the serving modules, with its file and line."""
    found = []
    for name in SERVING:
        path = os.path.join(SOURCE, name)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for keyword in node.keywords:
                if keyword.arg != "detail":
                    continue
                # Walked rather than matched: a `detail=` is often an f-string or a `.format()`
                # template, so the literal pieces are nested inside the expression.
                for piece in ast.walk(keyword.value):
                    if isinstance(piece, ast.Constant) and isinstance(piece.value, str):
                        found.append((name, piece.lineno, piece.value))
    return found


class TheServerNeverSendsACharacterTheFontCannotDraw(unittest.TestCase):
    def setUp(self):
        self.shipped = shipped_characters()
        self.strings = member_facing_strings()

    def test_the_charset_file_is_where_this_test_thinks_it_is(self):
        """If the path moves, every assertion below passes vacuously — which is the failure mode
        this whole file is about."""
        self.assertGreater(len(self.shipped), 1000, CHARSET)

    def test_there_is_something_to_check(self):
        """A refactor that moved every message out of `detail=` would make this file silently
        useless, and a silent pass is exactly H34's shape."""
        self.assertGreater(len(self.strings), 10)

    def test_no_member_facing_character_is_missing_beyond_the_known_baseline(self):
        missing = {}
        for name, line, text in self.strings:
            for character in text:
                if is_cjk(character) and character not in self.shipped:
                    missing.setdefault(character, set()).add("{}:{}".format(name, line))
        surprises = {c: sorted(w) for c, w in missing.items() if c not in KNOWN_MISSING}
        self.assertEqual(
            surprises, {},
            "a member-facing string uses a character the shipped font subset does not contain, so "
            "it will render as a blank gap on the product and no other gate will say so. Either "
            "reword, or widen the font derivation (orchestrator) and add it below: " + repr(surprises))

    def test_every_baseline_character_is_still_actually_missing(self):
        """The direction that stops the baseline rotting into a permanent excuse. When the font
        derivation widens, this fails and tells you to shorten the list."""
        healed = sorted(c for c in KNOWN_MISSING if c in self.shipped)
        self.assertEqual(
            healed, [],
            "these characters are now IN the shipped subset, so the font derivation has widened — "
            "remove them from KNOWN_MISSING in this file: " + "".join(healed))

    def test_every_baseline_character_is_still_actually_used(self):
        """And the other way the list rots: a string reworded away leaves an entry claiming a
        problem that no longer exists."""
        used = {c for _, _, text in self.strings for c in text}
        stale = sorted(c for c in KNOWN_MISSING if c not in used)
        self.assertEqual(
            stale, [],
            "these characters are no longer in any member-facing string, so their baseline entries "
            "are stale — remove them: " + "".join(stale))


if __name__ == "__main__":
    unittest.main(verbosity=2)
