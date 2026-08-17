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
(1.4.11). `--line` is deliberately absent — it is decoration, and holding decoration to a
contrast floor is how H30's one-token mistake started.
"""

import os
import re
import sys
import unittest

WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "web")
HOME = os.path.join(WEB, "index.html")

TOKENS = ("ink", "paper", "muted", "line", "edge", "raised", "accent", "pip", "pipred", "diefill")

# (foreground, background, floor, where the pair actually meets on the page)
PAIRS = [
    ("ink", "paper", 4.5, "body text on the page"),
    ("ink", "raised", 4.5, "body text on a card"),
    ("muted", "paper", 4.5, "secondary text on the page"),
    ("muted", "raised", 4.5, "secondary text on a card"),
    ("paper", "ink", 4.5, "button label on a filled button"),
    ("accent", "paper", 4.5, "the winner and the dice on the page"),
    ("accent", "raised", 4.5, "the hit row inside the allocation table"),
    ("edge", "paper", 3.0, "an unselected pill's only boundary"),
    ("edge", "raised", 3.0, "the same boundary if pills move onto a card"),
    # D91: pips are graphical objects, not text, so the UI floor applies. The red pip has its
    # own token, --pipred, one value in both modes — --accent flips lighter in dark (a UI accent
    # on a dark page must) while the die face does not (an object, not a surface), and the two
    # light values stacked measured 2.74:1. Paint on a die is the same paint with the lights off.
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
    with open(HOME, encoding="utf-8") as handle:
        text = handle.read()
    blocks = re.findall(r":root\s*\{([^}]*)\}", text)
    if len(blocks) < 2:
        raise AssertionError("expected a light and a dark `:root` block in index.html")
    return hex_tokens(blocks[0]), hex_tokens(blocks[1])


def luminance(colour: str) -> float:
    channels = [int(colour.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(a: str, b: str) -> float:
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


class EveryLoadBearingPairClearsItsFloor(unittest.TestCase):
    def test_both_modes(self):
        for mode_name, tokens in zip(("light", "dark"), load_modes()):
            for token in TOKENS:
                self.assertIn(token, tokens, f"{mode_name}: --{token} missing from :root")
            for fg, bg, floor, where in PAIRS:
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
