#!/usr/bin/env python3
"""Every character the server sends to a member must exist in the shipped font subset.

Run:  python3 app/api/tests/test_server_copy_renders.py            (the tests)
      python3 app/api/tests/test_server_copy_renders.py --gate     (one verdict line, for the hook)

No network, no database, no browser, and **no `fonttools`** — the last one is load-bearing, because
this runs in the pre-commit hook and the hook must work on a bare clone. `tools/subset_fonts.py`
needs `fonttools` and `brotli`; `tools/server_copy.py`, which both it and this file import, does not.

**Why this exists, and it was never the font's fault.** `tools/font_subset_check.py` asks whether the
shipped subset covers *the surface's own copy*, and answers that correctly. A `detail=` in
`upto/rounds.py` reaches the screen without passing through `app/web/`, so it was outside the aim —
and a character outside the aim leaves no gap in the output. The gate printed "472 needed, 3812
committed" and passed while 「池子是空的，␣每一家的權重都是零…」 arrived on the product with a hole in
it. Found on a 1440x900 screenshot by the frontend session, 2026-08-19; the derivation now reads the
API's copy too (5f51d8e), and this is the gate that keeps it true.

**One definition, two consumers.** The rule for *what a member can read* lives in
`tools/server_copy.py` and nowhere else: `tools/subset_fonts.py` derives the charset from it and this
file checks against it. The first version of this test carried its own list of six module names, which
was narrower — it would have missed a message in any module not on the list — and two definitions of
"member-facing" in two files is a drift waiting to happen. That was raised before the shared module
was written and the module is the answer to it.
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, "..", "..", "..")
CHARSET = os.path.join(REPO, "app", "web", "public", "fonts", "charset-sub.txt")

sys.path.insert(0, os.path.join(REPO, "tools"))

import server_copy  # noqa: E402

# **Empty, and that is the state to keep it in.** It held 或 and 趟 from 2026-08-19 until the
# derivation widened on 2026-08-20 — a baseline for characters known to be missing while somebody
# else's fix was in flight. It is checked in both directions below: a new missing character fails,
# and an entry here that is no longer missing also fails. An empty dict is the healthy reading.
KNOWN_MISSING = {}


def shipped():
    with open(CHARSET, encoding="utf-8") as handle:
        return set(handle.read()) - set("\n\r\t")


def missing():
    """{character: [file:line, …]} for every member-facing character the font cannot draw."""
    covered = shipped()
    absent = {}
    for path, line, text in server_copy.strings():
        for character in text:
            if character not in covered:
                where = "{}:{}".format(os.path.basename(path), line)
                absent.setdefault(character, set()).add(where)
    return {c: sorted(w) for c, w in absent.items()}


class TheServerNeverSendsACharacterTheFontCannotDraw(unittest.TestCase):
    def test_nothing_is_missing_beyond_the_known_baseline(self):
        surprises = {c: w for c, w in missing().items() if c not in KNOWN_MISSING}
        self.assertEqual(
            surprises, {},
            "a member-facing string uses a character the shipped font subset cannot draw, so it "
            "will render as a blank gap on the product and no other gate will say so. Fix by "
            "rebuilding the subset — `python3 tools/subset_fonts.py --build` — or reword: "
            + repr(surprises))

    def test_every_baseline_entry_is_still_actually_missing(self):
        """The direction that stops a baseline becoming a permanent excuse. It is what emptied this
        list when the derivation widened."""
        healed = sorted(c for c in KNOWN_MISSING if c not in missing())
        self.assertEqual(
            healed, [],
            "these characters are no longer missing, so the derivation has caught up — remove them "
            "from KNOWN_MISSING in this file: " + "".join(healed))

    def test_the_charset_file_is_where_this_test_thinks_it_is(self):
        """If the path moves, every assertion above passes vacuously — which is the failure mode this
        whole file is about, arriving through the back door."""
        self.assertGreater(len(shipped()), 1000, CHARSET)

    def test_there_is_something_to_check(self):
        """A refactor that moved every message out of `detail=` would leave this file passing and
        checking nothing. `server_copy.strings()` refuses an empty result itself; this asserts the
        number is a plausible one rather than merely non-zero."""
        self.assertGreater(len(server_copy.strings()), 20)

    def test_this_file_reads_the_shared_definition_and_not_its_own(self):
        """The property is that `missing()` gets its strings from `tools/server_copy.py`, so that
        changing what counts as member-facing changes the derivation and this gate together.

        **Asserted behaviourally, because the first version of this test scanned its own source for
        the token `HTTPException` — a token its own assertion contained.** It could never pass: the
        instrument's subject included the instrument. Third one of that family in two days, after a
        gate that read prose instead of code and a probe that listed the services it expected.
        """
        real = server_copy.strings
        try:
            server_copy.strings = lambda *a, **k: [("sentinel.py", 1, "\u9f49")]
            self.assertEqual(sorted(missing()), ["\u9f49"],
                             "missing() did not follow server_copy.strings, so this file has a "
                             "second source of member-facing strings")
        finally:
            server_copy.strings = real


def gate():
    """One verdict line, for the pre-commit hook. Exit 1 on any character the font cannot draw.

    **It prints even when there is nothing wrong**, because a silent pass is H34's shape and this
    gate's whole subject is a check that was passing while the product was broken.
    """
    absent = {c: w for c, w in missing().items() if c not in KNOWN_MISSING}
    total = len(server_copy.strings())
    if absent:
        print("server copy: REFUSED — {} character(s) a member can read that the shipped font "
              "cannot draw:".format(len(absent)))
        for character, where in sorted(absent.items()):
            print("  {}  U+{:04X}  {}".format(character, ord(character), ", ".join(where)))
        print("  rebuild the subset (`python3 tools/subset_fonts.py --build`, needs fonttools) or "
              "reword. A missing glyph is a blank gap on the product, never an error.")
        return 1
    note = "" if not KNOWN_MISSING else " ({} known-missing tolerated)".format(len(KNOWN_MISSING))
    print("server copy: {} member-facing strings, every character drawable{}".format(total, note))
    return 0


if __name__ == "__main__":
    if "--gate" in sys.argv:
        raise SystemExit(gate())
    unittest.main(verbosity=2)
