#!/usr/bin/env python3
"""H30's missing half: the suite computes contrast, so the next silent pair goes red.

Run: python3 app/api/tests/test_web_contrast.py    (no network, no database, no browser)

H30's finding was a border at 1.26:1 that looked right, was equally wrong in both modes,
and hid because nothing measured it. The token split (`--line` decoration / `--edge`
control boundary) fixed that instance; this file is the half the entry admitted was not
built — nothing computed contrast, so the *next* nudge to a colour could fail the same
way. Every ratio below is read from `index.html`'s own token blocks, never from a copy,
so restyling the palette re-runs the check against what actually ships.

Thresholds are WCAG 2.1: 4.5:1 for text (1.4.3), 3:1 for the boundary of a control
(1.4.11). **Decoration is deliberately not held to a contrast floor** — that principle
came out of H30, where treating one decorative token as if it had a job was how the
one-token mistake started, and it outlives the tokens it was learned on.

**Retargeted 2026-08-18 for direction D; the file's shape is unchanged and that is the
point.** D87 is retired, so `--accent`, `--raised`, `--edge` and `--line` are gone and the
four-hue set (`hot` · `cobalt` · `jade` · `sun`) with its `on-*`, `flood-*` and `onflood-*`
companions took their place. Two `:root` blocks are still parsed from the shipped file,
every token is still asserted present in both, every pair is still measured against a
floor, and the self-mutant test still proves the measurement can fail. Only the contents
moved — the spec came from the frontend session, which measured every pair above its floor
on the proposal pages.

**Two things about the numbers, so they do not read as mistakes.** The `flood-*` tokens
differ by mode on purpose: in light mode they equal their hues, and in dark mode they are
four separate darker values chosen so a landed flood lifts the room about 11× rather than
up to 96× — `--flood-sun` therefore reads olive rather than yellow, and that was ruled
deliberately. And `--pipred` stays one value in both modes, for the reason recorded beside
its pair below.
"""

import os
import re
import sys
import unittest

WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "web")
HOME = os.path.join(WEB, "index.html")

RETIRED_TOKENS = ("ink", "paper", "muted", "line", "edge", "raised", "accent",
                  "pip", "pipred", "diefill")

RETIRED_PAIRS = [
    ("ink", "paper", 4.5, "body text on the page"),
    ("ink", "raised", 4.5, "body text on a card"),
    ("muted", "paper", 4.5, "secondary text on the page"),
    ("muted", "raised", 4.5, "secondary text on a card"),
    ("paper", "ink", 4.5, "button label on a filled button"),
    ("accent", "paper", 4.5, "the winner and the dice on the page"),
    ("accent", "raised", 4.5, "the hit row inside the allocation table"),
    ("edge", "paper", 3.0, "an unselected pill's only boundary"),
    ("edge", "raised", 3.0, "the same boundary if pills move onto a card"),
    ("pipred", "diefill", 3.0, "the red 1 and 4 pips on a die face"),
    ("pip", "diefill", 3.0, "a black pip on a die face"),
]

TOKENS = (
    "ink", "paper", "muted",
    # The four hues, and for each one the text colour that sits on it.
    "hot", "cobalt", "jade", "sun",
    "on-hot", "on-cobalt", "on-jade", "on-sun",
    # The landing flood, and the text colour that sits on the flood.
    "flood-hot", "flood-cobalt", "flood-jade", "flood-sun",
    "onflood-hot", "onflood-cobalt", "onflood-jade", "onflood-sun",
    # D91's dice.
    "pip", "pipred", "diefill",
)

# (foreground, background, floor, where the pair actually meets on the page)
PAIRS = [
    ("ink", "paper", 4.5, "body text on the page"),
    ("paper", "ink", 4.5, "label on a filled control"),
    ("muted", "paper", 4.5, "secondary text"),
    ("on-hot", "hot", 4.5, "text on the roll bar"),
    ("on-cobalt", "cobalt", 4.5, "text on the greeting block"),
    ("on-jade", "jade", 4.5, "text on a jade field"),
    ("on-sun", "sun", 4.5, "readings on the weather block"),
    ("onflood-hot", "flood-hot", 4.5, "the winner's name on a hot flood"),
    ("onflood-cobalt", "flood-cobalt", 4.5, "the winner's name on a cobalt flood"),
    ("onflood-jade", "flood-jade", 4.5, "the winner's name on a jade flood"),
    ("onflood-sun", "flood-sun", 4.5, "the winner's name on a sun flood"),
    # D91: pips are graphical objects, not text, so the UI floor applies. The red pip has its
    # own token, --pipred, one value in both modes — a UI accent on a dark page must flip
    # lighter, while the die face does not, because a die is an object rather than a surface.
    # Paint on a die is the same paint with the lights off. Measured 3.36 light / 3.43 dark.
    ("pipred", "diefill", 3.0, "the red 1 and 4 pips on a die face"),
    ("pip", "diefill", 3.0, "a black pip on a die face"),
]


def hex_tokens(css_block: str) -> dict:
    """The custom properties of one `:root` block, name → #rrggbb."""
    found = {}
    for name, value in re.findall(r"--([a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{6})", css_block):
        found[name] = value
    return found


def load_modes() -> tuple[dict, dict]:
    """The two `:root` blocks that declare **colours**, light first.

    **Not the first two blocks, and the difference is a false alarm this test raised once.** It
    took `blocks[0]` and `blocks[1]`, which held while the file had exactly two `:root` blocks —
    and broke the moment direction D's port added a third for non-colour tokens (spacing, type
    scale). The middle block declares no hex value, so the dark palette moved to index 2 and the
    test reported "index.html declares neither palette" about a file that declared D's perfectly
    well. A gate that cries wolf gets waved through, so the selection now asks the question it
    actually means: which blocks carry colours.
    """
    with open(HOME, encoding="utf-8") as handle:
        text = handle.read()
    blocks = [hex_tokens(block) for block in re.findall(r":root\s*\{([^}]*)\}", text)]
    coloured = [block for block in blocks if block]
    if len(coloured) != 2:
        raise AssertionError(
            "expected exactly two `:root` blocks declaring colours (light, then dark); found "
            "{} of {} blocks with hex values. Two modes is the assumption every pair here rests "
            "on — a third palette is a design change, not a test failure.".format(
                len(coloured), len(blocks)
            )
        )
    return coloured[0], coloured[1]


def luminance(colour: str) -> float:
    channels = [int(colour.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(a: str, b: str) -> float:
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


D_MARKER = "hot"


def spec_for(tokens: dict) -> tuple:
    """Which palette the shipped file actually declares — D's, or D87's on the way out.

    **This selection exists for one handover and is scheduled for deletion.** D87 is retired and
    direction D replaces it, but the palette lives in `app/web/index.html` (the frontend session's
    file) while this test lives here (backend's), so for the length of one commit the two cannot
    move together. Rather than leave the suite red across that gap — a red suite teaches people to
    ignore it — the test asserts *whichever complete palette is present* and refuses a file that
    declares neither.

    **How to know it is time to delete `RETIRED_*` and this function:** `--accent` no longer
    appears in `index.html`. At that point the D87 branch is unreachable and keeping it is how a
    test file starts describing a design nobody ships.
    """
    if D_MARKER in tokens:
        return TOKENS, PAIRS
    if "accent" in tokens:
        return RETIRED_TOKENS, RETIRED_PAIRS
    raise AssertionError(
        "index.html declares neither palette: no --hot (direction D) and no --accent (D87). "
        "A file with no recognised palette is not a passing file — it is an unmeasured one."
    )


class EveryLoadBearingPairClearsItsFloor(unittest.TestCase):
    def test_both_modes(self):
        for mode_name, tokens in zip(("light", "dark"), load_modes()):
            expected_tokens, expected_pairs = spec_for(tokens)
            for token in expected_tokens:
                self.assertIn(token, tokens, f"{mode_name}: --{token} missing from :root")
            for fg, bg, floor, where in expected_pairs:
                ratio = contrast(tokens[fg], tokens[bg])
                self.assertGreaterEqual(
                    round(ratio, 2), floor,
                    f"{mode_name}: --{fg} on --{bg} is {ratio:.2f}:1, needs {floor}:1 — {where}",
                )

    def test_the_check_can_fail(self):
        """A mutant pair under the floor must be caught — the check checks itself."""
        self.assertLess(contrast("#8f887b", "#a69d90"), 3.0)


if __name__ == "__main__":
    unittest.main(verbosity=1)
