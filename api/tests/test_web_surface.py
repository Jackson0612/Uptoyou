#!/usr/bin/env python3
"""The surface's rules, checked where each one is actually decidable.

Run: python3 app/api/tests/test_web_surface.py    (no network, no database, no browser)

**Rewritten 2026-08-18 for D104.** The surface was one `index.html` with a vendored Vue global
build, and this file's machinery matched it: HTML comments delimited "screens", and every rule was
read off that one document. Vite + React 19 + Tailwind 4 has no such document, so the old
apparatus is gone rather than adapted.

**Each rule now lives where it can be decided, and the two are not interchangeable.**

- **Source (`app/web/src`) for anything about what the code says.** H7's rule and D20's advisory-copy
  rule are properties of what was written, and source is readable.
- **Built output (`app/web/dist`) for anything about what a browser fetches.** §6's dead-wifi rule
  and the `@font-face` declarations are properties of the artefact nginx serves, and only the build
  produces them.

**Two things I measured before writing an assertion, and both changed it.**

**`dangerouslySetInnerHTML` appears in `dist/assets/*.js` once, from React itself.** So a built-output
scan for H7 can never pass, and H7 is checked in source only. This is the mirror of the reason H7 is
*not* checked in built output for the other direction: a minifier mangles nothing about a prop name,
but React shipping the string means the signal is not ours.

**Three external URLs appear in the built output and none of them is a network dependency** — a
`https://react.dev` link inside a React error template, `https://tailwindcss.com` in Tailwind's MIT
licence comment, and `http://www.w3.org/2000/svg` as an SVG namespace. **So §6 cannot be checked by
scanning for URLs.** It is checked at the places a browser actually fetches from: `<script src>`,
`<link href>`, `<img src>`, and CSS `url(...)`. A gate that failed on a licence comment would be
waved through the first time it fired, which is the same lesson as the font gate demanding a `═`
that appeared only in a CSS comment.

**D20's second half is written to arm itself rather than to wait.** *Weather appears on the home
screen and nowhere else* needs screens, and the scaffold has none. Rather than leave a comment for
someone to remember, the check asserts the half that is decidable today — **weather vocabulary
appears in no module other than a home module** — which passes on a scaffold that mentions weather
nowhere and starts biting the moment a second module mentions it. The positive half (*the home does
show it*) prints as not-yet-assertable and names what it waits for.
"""

import os
import re
import sys
import unittest

WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "web")
SRC = os.path.join(WEB, "src")
DIST = os.path.join(WEB, "dist")

# D20's first half: the surface may state, never advise.
ADVISORY = ["建議", "推薦", "最好", "不如", "應該去", "別去", "值得一試", "首選"]

# D20's second half. The vocabulary is the weather's, not a restaurant's — 「晴光市場」 is a place
# name and must not read as weather, which is why the list is phrases and measures rather than
# single characters.
WEATHER_WORDS = ["降雨機率", "體感溫度", "weather_code", "weather_text", "氣溫", "濕度", "舒適度"]

# A module is "the home" by name. Kept deliberately loose — `Home.tsx`, `home/index.tsx`,
# `screens/home/Weather.tsx` all count — because the rule is about which screen, not which file.
HOME_HINT = re.compile(r"(^|[/\\])home([/\\.]|$)", re.I)

LINE_COMMENT = re.compile(r"//[^\n]*")
BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
CSS_COMMENT = re.compile(r"/\*.*?\*/", re.S)

FETCHED_ATTR = re.compile(r"""<(?:script|link|img|source|video|audio|iframe)\b[^>]*?
                              \b(?:src|href)\s*=\s*["']([^"']+)["']""", re.I | re.X)
CSS_URL = re.compile(r"url\(\s*['\"]?([^'\")]+)['\"]?\s*\)")
FONT_FACE = re.compile(r"@font-face\s*\{([^}]*)\}", re.I)


def source_files(extensions=(".tsx", ".ts", ".jsx", ".js")) -> list[str]:
    """Every hand-written module under `src`. `node_modules` and `dist` are not source."""
    found = []
    for root, dirs, files in os.walk(SRC):
        dirs[:] = [d for d in dirs if d not in ("node_modules", "dist")]
        for name in files:
            if name.endswith(extensions):
                found.append(os.path.join(root, name))
    return sorted(found)


def read(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def code_of(path: str) -> str:
    """A module with its comments removed.

    Comments are stripped for the same reason the font derivation strips them: a rule that fires on
    a comment *describing* the rule is a rule that gets disabled. String literals are deliberately
    **kept** — copy lives in them, so D20's vocabulary must still see them.
    """
    text = read(path)
    return LINE_COMMENT.sub(" ", BLOCK_COMMENT.sub(" ", text))


def dist_files(extension: str) -> list[str]:
    found = []
    for root, _dirs, files in os.walk(DIST):
        for name in files:
            if name.endswith(extension):
                found.append(os.path.join(root, name))
    return sorted(found)


def built() -> bool:
    return os.path.isdir(DIST) and bool(dist_files(".html"))


class TheBuildIsPresentOrTheReasonIsStated(unittest.TestCase):
    def test_dist_exists_or_the_rules_needing_it_say_so(self):
        """`dist/` is gitignored, so a fresh clone has none until `npm run build` has run.

        This is stated as its own check rather than skipped inside the others, because "the rules
        about the served artefact did not run" must be one visible line and not four quiet ones.
        """
        if built():
            return
        print("\nweb surface: app/web/dist is absent — the rules about the SERVED artefact did not "
              "run (§6's fetch points, the @font-face declarations). Build it with "
              "`docker compose build proxy`, or `npm run build` in app/web, and re-run. The source "
              "rules below ran regardless.", file=sys.stderr)


class NoDangerousInnerHtml(unittest.TestCase):
    """H7, in source, because the built output cannot answer it."""

    def test_it_is_never_used(self):
        offenders = []
        for path in source_files():
            if "dangerouslySetInnerHTML" in code_of(path):
                offenders.append(os.path.relpath(path, WEB))
        self.assertEqual(
            offenders, [],
            "H7: dangerouslySetInnerHTML appears in {} — the surface renders text as text. Every "
            "string on it comes from a government file or another person's typing.".format(
                ", ".join(offenders)),
        )

    def test_the_check_reads_source_and_not_the_bundle(self):
        """Pinned, because the obvious 'improvement' is to scan `dist` too, and it cannot work.

        React's own runtime contains the string, so a built-output scan fails on an innocent build.
        Measured 2026-08-18: one occurrence in `dist/assets/*.js` on a surface that does not use it.
        """
        if not built():
            self.skipTest("dist absent")
        bundles = "".join(read(path) for path in dist_files(".js"))
        self.assertIn(
            "dangerouslySetInnerHTML", bundles,
            "React's runtime no longer carries this string, so a built-output scan for H7 may have "
            "become possible — re-measure before assuming either way",
        )

    def test_the_check_can_fail(self):
        self.assertIn("dangerouslySetInnerHTML",
                      LINE_COMMENT.sub(" ", 'a = {dangerouslySetInnerHTML: {__html: x}}'))

    def test_a_comment_mentioning_it_does_not_trip_the_check(self):
        """Both comment forms, because a rule that fires on its own documentation gets deleted."""
        for comment in ("// never use dangerouslySetInnerHTML here",
                        "/* dangerouslySetInnerHTML is banned by H7 */"):
            stripped = LINE_COMMENT.sub(" ", BLOCK_COMMENT.sub(" ", comment))
            self.assertNotIn("dangerouslySetInnerHTML", stripped, comment)


class TheSurfaceStatesAndDoesNotAdvise(unittest.TestCase):
    """D20's first half, over the copy in source."""

    def test_no_advisory_copy(self):
        offenders = []
        for path in source_files():
            code = code_of(path)
            for word in ADVISORY:
                if word in code:
                    offenders.append("{}: {}".format(os.path.relpath(path, WEB), word))
        self.assertEqual(offenders, [], "D20: the surface may state, never advise — " +
                         "; ".join(offenders))

    def test_the_vocabulary_is_not_empty(self):
        """A rule with an empty word list passes everything. H34's shape."""
        self.assertGreater(len(ADVISORY), 5)


class WeatherStaysOnTheHomeScreen(unittest.TestCase):
    """D20's second half, armed rather than deferred — see the module docstring."""

    def modules_mentioning_weather(self) -> dict:
        found = {}
        for path in source_files():
            code = code_of(path)
            hits = [word for word in WEATHER_WORDS if word in code]
            if hits:
                found[os.path.relpath(path, WEB)] = hits
        return found

    def test_no_module_outside_the_home_mentions_weather(self):
        elsewhere = {
            path: hits for path, hits in self.modules_mentioning_weather().items()
            if not HOME_HINT.search(path)
        }
        self.assertEqual(
            elsewhere, {},
            "D20: weather belongs to the home screen and nowhere else; found it in " +
            ", ".join("{} ({})".format(path, "/".join(hits)) for path, hits in elsewhere.items()),
        )

    def test_the_positive_half_says_what_it_waits_for(self):
        """*The home does show it* cannot be asserted before a home screen exists.

        Printed rather than skipped silently, and it needs no maintenance: the moment a home module
        mentions weather this assertion starts passing on its own, and the moment a non-home module
        does, the check above fails.
        """
        mentions = self.modules_mentioning_weather()
        if any(HOME_HINT.search(path) for path in mentions):
            return
        print("\nweb surface: no module mentions weather yet, so D20's positive half (the home "
              "screen DOES show it) is not yet assertable. It arms itself when a home module "
              "does — nothing to remember.", file=sys.stderr)


class NothingIsFetchedFromAnotherHost(unittest.TestCase):
    """§6's dead-wifi rule, at the points a browser actually fetches from."""

    def fetch_points(self) -> list[tuple[str, str]]:
        points = []
        for path in dist_files(".html"):
            for url in FETCHED_ATTR.findall(read(path)):
                points.append((os.path.relpath(path, WEB), url))
        for path in dist_files(".css"):
            for url in CSS_URL.findall(CSS_COMMENT.sub(" ", read(path))):
                points.append((os.path.relpath(path, WEB), url))
        return points

    def test_every_fetch_point_is_local(self):
        if not built():
            self.skipTest("dist absent")
        points = self.fetch_points()
        self.assertTrue(points, "no fetch points found at all — the scan is looking in the wrong "
                                "place, which would pass for the wrong reason")
        remote = [(where, url) for where, url in points
                  if re.match(r"[a-z]+:", url) and not url.startswith("data:")]
        self.assertEqual(
            remote, [],
            "§6: the surface must work on a dead wifi, so every asset ships with it; found " +
            ", ".join("{} → {}".format(where, url) for where, url in remote),
        )

    def test_a_bare_url_in_a_comment_or_a_message_is_not_a_violation(self):
        """The measured false alarm this check was written around.

        `dist` contains `https://react.dev` (a React error template), `https://tailwindcss.com`
        (a licence comment) and `http://www.w3.org/2000/svg` (an XML namespace). None is fetched.
        A scan for URLs would fail on all three, and a gate that cries wolf gets waved through.
        """
        if not built():
            self.skipTest("dist absent")
        everything = "".join(read(path) for path in dist_files(".js") + dist_files(".css"))
        self.assertRegex(everything, r"https?://",
                         "no external URL strings at all — if that is now true the note above is "
                         "stale, but the check below must still target fetch points")
        self.assertEqual(
            [], [url for _w, url in self.fetch_points() if url.startswith("http")],
            "a fetch point genuinely points at another host",
        )


class TheVendoredFaces(unittest.TestCase):
    """Every `@font-face` the build emits, and the two things each must get right."""

    def faces(self) -> list[dict]:
        found = []
        for path in dist_files(".css"):
            for block in FONT_FACE.findall(CSS_COMMENT.sub(" ", read(path))):
                entry = {}
                for declaration in block.split(";"):
                    if ":" in declaration:
                        key, _, value = declaration.partition(":")
                        entry[key.strip().lower()] = value.strip()
                found.append(entry)
        return found

    def test_at_least_one_face_ships(self):
        if not built():
            self.skipTest("dist absent")
        self.assertTrue(self.faces(), "the build emitted no @font-face at all")

    def test_every_face_declares_a_weight_range_not_a_single_weight(self):
        """**The source faces are variable and their default instances are not Regular.**

        Noto Sans TC is `wght 100–900` defaulting to **Thin**, and an `@font-face` without the range
        renders the whole surface hairline — that has happened here. Noto Serif TC is `wght 200–900`
        defaulting to **ExtraLight**, so the ranges differ per face and a shared constant would be
        wrong for one of them. What is asserted is therefore the shape — two numbers — rather than a
        value.
        """
        if not built():
            self.skipTest("dist absent")
        for face in self.faces():
            family = face.get("font-family", "?")
            weight = face.get("font-weight", "")
            self.assertRegex(
                weight, r"^\d+\s+\d+$",
                "{}: font-weight is {!r}; a variable face needs its range declared, or the "
                "browser renders the face's default instance — Thin for the sans, ExtraLight for "
                "the serif".format(family, weight),
            )

    def test_the_sans_declares_the_range_its_source_face_actually_has(self):
        if not built():
            self.skipTest("dist absent")
        sans = [f for f in self.faces() if "sans" in f.get("font-family", "").lower()]
        self.assertTrue(sans, "no sans face found among {}".format(
            [f.get("font-family") for f in self.faces()]))
        for face in sans:
            self.assertEqual(face.get("font-weight"), "100 900",
                             "the sans source face is wght 100–900; declaring anything else claims "
                             "a weight it has not got")

    def test_every_face_points_at_a_file_that_actually_shipped(self):
        """A face whose `src` 404s degrades silently to a fallback — no error, wrong glyphs."""
        if not built():
            self.skipTest("dist absent")
        for face in self.faces():
            for url in CSS_URL.findall(face.get("src", "")):
                self.assertTrue(url.startswith("/"), "{} is not an absolute served path".format(url))
                on_disk = os.path.join(DIST, url.lstrip("/"))
                self.assertTrue(os.path.exists(on_disk),
                                "{} is declared and did not ship — the browser would fall back "
                                "silently".format(url))


if __name__ == "__main__":
    unittest.main(verbosity=1)
