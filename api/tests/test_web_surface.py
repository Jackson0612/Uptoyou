#!/usr/bin/env python3
"""D20 and H7, asserted against the front end's actual text.

Run: python3 app/api/tests/test_web_surface.py    (no network, no database, no browser)

It lives under `api/tests` because there is one test root and this runs with the rest of
tier 1; it reads `app/web/` and touches nothing else.

**Why a test and not a comment.** D20 states the rule — *the surface may state, never
advise* — and then names how it will be broken: "The failure will not happen at design
time; it will happen months later when someone improves the UI copy." A rule whose stated
failure mode is a well-meaning later edit is a rule that needs something that fails.

**The trap this file walked into first.** `index.html` quotes 建議選近一點的店 in a comment,
as the example of what may not be written. A scan of the whole file therefore fails on the
prohibition itself — the same shape as an earlier test that asserted the word "preference"
was absent from a refusal whose job was to say "whose preference". So the scan is over the
**user-visible surface only**: comments are stripped first, because a comment cannot appear
on a screen and the explanation must be allowed to name the thing it forbids.
"""

import os
import re
import sys
import unittest

WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "web")
HOME = os.path.join(WEB, "index.html")

# Recommendation vocabulary. Not a spell-check: each of these turns a fact into a position
# on where somebody should eat, which D20 rules is a reason wearing a hat.
ADVISORY = ["建議", "推薦", "最好", "不如", "適合", "應該去", "別去", "考慮", "值得"]

# D20's other half: weather belongs to the home screen and no other.
#
# **Widened 2026-08-12, because the list only knew the labels already on the home screen.** It held
# 降雨 · 體感 · 濕度 · 風速 · 氣溫 — which is what this page happens to print, not what a person
# writes. Five ordinary sentences were tried against it and **all five got through**: 今天天氣不錯,
# 外面下雨, 氣象預報說, 溫度很高, 很悶熱. H29 fixed *where* the scan looks; this fixes what it knows,
# and the two together are what the rule needed. `test_the_vocabulary_catches_ordinary_sentences`
# below keeps it from narrowing again quietly.
#
# **Single characters are deliberately absent.** 熱, 冷 and 涼 would each be a weather word and a
# food word at once — 熱炒, 冷麵, 涼麵 are all restaurants, and a scan that fails on the name of a
# noodle shop teaches people to route around the gate.
WEATHER_WORDS = [
    "降雨", "體感", "濕度", "風速", "氣溫", "天氣", "下雨", "氣象", "溫度", "悶熱",
    "預報", "觀測", "紫外線", "weather", "temperature", "forecast", "rain", "humid",
]

# Sentences a well-meaning later edit would plausibly write onto the propose screen. Not a wishlist:
# each one got past the old vocabulary, so this list is the record of what was missed.
ORDINARY_WEATHER_SENTENCES = [
    "今天天氣不錯", "外面下雨", "氣象預報說", "溫度很高", "很悶熱",
    "紫外線很強", "根據觀測資料",
]

# **Named screens, not files** — H29, ruled 2026-08-12. This used to be `{"index.html"}` and the
# unit of enforcement was therefore a file. D3 rules Vue with no build step, so the second screen
# arrives as markup inside `index.html`; under the old rule it landed inside the allowlist and the
# check passed without examining it. Not red — quiet, which is worse, because the passing count
# goes up as screens are added.
WEATHER_MAY_APPEAR_IN = {"home"}

# The block delimiters, as declared in the comment at the top of `index.html`'s body: comments
# reading `screen: NAME` / `/screen` / `chrome` / `/chrome`.
#
# **Delimiters are resolved before anything else looks at the file, and that is not tidiness.**
# Writing this the obvious way — one regex per block, run straight over the source — broke twice
# in ten minutes, both times on the explanatory comment that documents the convention:
#
#   1. it spelled a delimiter out in full, and an HTML comment **ends at its first close and does
#      not nest**, so the outer comment terminated early and the rest of the paragraph became page
#      content. That was a real rendering defect, not a test artefact.
#   2. it mentioned the `main` element by name in prose, and the search for the real element
#      matched inside the comment instead.
#
# So: one pass turns every comment into either a sentinel or whitespace, and every pattern below
# runs on the result. A comment can then say anything at all without moving the boundaries.
SCREEN_OPEN = re.compile(r"<!--\s*screen:\s*([a-z0-9-]+)\s*-->\Z", re.S)
SCREEN_CLOSE = re.compile(r"<!--\s*/screen\s*-->\Z", re.S)
CHROME_OPEN = re.compile(r"<!--\s*chrome\s*-->\Z", re.S)
CHROME_CLOSE = re.compile(r"<!--\s*/chrome\s*-->\Z", re.S)
COMMENT = re.compile(r"<!--.*?-->", re.S)

SCREEN_BLOCK = re.compile(r"\x00screen:([a-z0-9-]+)\x00(.*?)\x00/screen\x00", re.S)
CHROME_BLOCK = re.compile(r"\x00chrome\x00(.*?)\x00/chrome\x00", re.S)
MAIN = re.compile(r"<main\b[^>]*>(.*?)</main>", re.S | re.I)


def read(path):
    """One place that closes the handle — bare `open(...).read()` leaves a ResourceWarning
    in every run's output, and warnings nobody reads are how a real one gets missed."""
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def visible_text(path):
    """The file with anything a user cannot read removed: HTML comments, JS line comments,
    and the stylesheet. What is left is the surface D20 governs.

    **The `<script>` block is deliberately still in here**, so the advisory scan reaches string
    literals — `error.value = '建議…'` would reach a screen, and stripping the script to tidy the
    scan would open exactly that hole.
    """
    source = read(path)
    source = re.sub(r"<!--.*?-->", " ", source, flags=re.S)
    source = re.sub(r"<style\b.*?</style>", " ", source, flags=re.S | re.I)
    source = re.sub(r"^\s*//.*$", " ", source, flags=re.M)
    return source


def strip_non_markup(fragment):
    """Comments, stylesheet and script removed. Used for the per-screen work, where the script
    has to go: it is not inside any screen block, and it legitimately contains `weather_text`
    and `/api/weather`.

    **The cost of that, stated rather than hidden:** the per-screen weather scan therefore does
    not see JS strings. A screen whose weather text is assembled in JavaScript rather than written
    in markup would pass. `visible_text` above still covers the script for the advisory scan, so
    the hole is specific to the weather half, and closing it needs the rendered DOM rather than a
    file — which is the browser check `CLAUDE.md` documents, not this file's job.
    """
    fragment = re.sub(r"<!--.*?-->", " ", fragment, flags=re.S)
    fragment = re.sub(r"<style\b.*?</style>", " ", fragment, flags=re.S | re.I)
    fragment = re.sub(r"<script\b.*?</script>", " ", fragment, flags=re.S | re.I)
    return fragment


def resolved(path):
    """The file with every comment replaced by a sentinel (if it is a delimiter) or by whitespace
    (if it is prose). See the note above the patterns for the two defects this exists to stop."""

    def swap(match):
        comment = match.group(0)
        opening = SCREEN_OPEN.match(comment)
        if opening:
            return "\x00screen:{}\x00".format(opening.group(1))
        if SCREEN_CLOSE.match(comment):
            return "\x00/screen\x00"
        if CHROME_OPEN.match(comment):
            return "\x00chrome\x00"
        if CHROME_CLOSE.match(comment):
            return "\x00/chrome\x00"
        return " "

    return COMMENT.sub(swap, read(path))


def body_of(path):
    """The markup inside the `main` element, or `None`. Comments are already resolved, so a
    comment naming the element cannot be mistaken for it."""
    found = MAIN.search(resolved(path))
    return None if found is None else found.group(1)


def regions(path):
    """Every delimited region of a page, as `(label, fragment)`.

    `chrome` is returned under its own label rather than merged into a screen, because it renders
    on all of them and is therefore held to the strictest rule of any screen.
    """
    body = body_of(path)
    if body is None:
        return []
    found = [("chrome", m.group(1)) for m in CHROME_BLOCK.finditer(body)]
    return found + [(m.group(1), m.group(2)) for m in SCREEN_BLOCK.finditer(body)]


def undeclared_markup(path):
    """What is inside the `main` element but in neither a screen nor a chrome block, with the
    blocks and the non-markup removed. **This returning anything is the failure H29 describes**:
    markup the per-screen check cannot see, which the old per-file rule allowed silently."""
    body = body_of(path)
    if body is None:
        return None
    remainder = CHROME_BLOCK.sub(" ", SCREEN_BLOCK.sub(" ", body))
    return strip_non_markup(remainder).replace("\x00", " ")


class TheSurfaceStatesAndDoesNotAdvise(unittest.TestCase):
    def test_no_advisory_copy_on_the_home_screen(self):
        text = visible_text(HOME)
        for word in ADVISORY:
            self.assertNotIn(
                word,
                text,
                "D20: the surface may state, never advise. {!r} makes the product take a "
                "position on where to eat, which is one step from admitting it acts on "
                "one.".format(word),
            )

    def test_the_prohibition_itself_is_still_written_down(self):
        """The opposite property, and it is the one that keeps the rule legible: stripping
        comments must not have stripped the reason. If someone deletes the D20 block to make
        the scan simpler, this fails."""
        source = read(HOME)
        self.assertIn("D20", source)
        self.assertIn("never advise", source)
        self.assertNotIn("建議", visible_text(HOME), "sanity: the example must be in a comment")
        self.assertIn("建議", source, "the comment naming the forbidden copy has been removed")


class ScreensAreFindable(unittest.TestCase):
    """H29's mitigation, and the part that has to come first: **the check must fail when it
    cannot identify its subject.** Everything in the next class scans per screen, and a scanner
    that silently matches nothing reports success in the same words as one that held."""

    def test_every_page_declares_at_least_one_screen(self):
        for name in sorted(os.listdir(WEB)):
            if not name.endswith(".html"):
                continue
            found = regions(os.path.join(WEB, name))
            screens = [label for label, _ in found if label != "chrome"]
            self.assertTrue(
                screens,
                "H29: {} declares no `<!-- screen: NAME -->` block. Either the delimiters were "
                "removed or a page was added without them, and in both cases the D20 scan below "
                "now examines nothing while still passing.".format(name),
            )

    def test_no_markup_sits_outside_a_declared_block(self):
        """The assertion that makes a new screen impossible to add unseen. Without it the
        delimiters are decoration: someone appends a propose screen after `<!-- /screen -->`,
        every scan below skips it, and nothing complains."""
        for name in sorted(os.listdir(WEB)):
            if not name.endswith(".html"):
                continue
            leftover = undeclared_markup(os.path.join(WEB, name))
            self.assertIsNotNone(leftover, "{} has no <main> element to scan".format(name))
            self.assertEqual(
                leftover.strip(),
                "",
                "H29: {} has markup inside <main> that is in neither a screen nor a chrome "
                "block, so the D20 scan cannot see it: {!r}".format(name, leftover.strip()[:200]),
            )

    def test_the_home_screen_is_one_of_them(self):
        """Names, not positions. `WEATHER_MAY_APPEAR_IN` allowlists `home` by name, so a rename
        would otherwise turn the allowlist into a no-op and the home screen would start failing
        the weather rule instead — a confusing way to learn about a typo."""
        labels = {label for label, _ in regions(HOME)}
        self.assertIn("home", labels, "the home screen block is named something else: {}".format(labels))


class WeatherStaysOnTheHomeScreen(unittest.TestCase):
    def test_no_other_screen_mentions_weather(self):
        """D20 names the screens that must say nothing: round-opening, proposing, rolling —
        including D16's hour confirmation, which shows the hour and not the forecast.

        **`chrome` is scanned rather than exempted.** It renders on every screen, so a weather
        word there is a weather word on the propose screen.
        """
        for name in sorted(os.listdir(WEB)):
            if not name.endswith(".html"):
                continue
            for label, fragment in regions(os.path.join(WEB, name)):
                if label in WEATHER_MAY_APPEAR_IN:
                    continue
                text = strip_non_markup(fragment)
                for word in WEATHER_WORDS:
                    self.assertNotIn(
                        word,
                        text,
                        "D20: {} in {} may not mention weather ({!r})".format(label, name, word),
                    )

    def test_the_home_screen_does_show_it(self):
        """Without this, the rule above is satisfied by a product with no weather anywhere,
        and the test suite would report success for the wrong reason.

        Scanned inside the home screen's own block rather than over the file, so it also proves
        the delimiters bracket the thing they claim to.
        """
        home = dict(regions(HOME)).get("home", "")
        text = strip_non_markup(home)
        self.assertIn("降雨機率", text)
        self.assertIn("體感", text)

    def test_the_vocabulary_catches_ordinary_sentences(self):
        """**The list has to know the words a person writes, not the labels this page prints.**

        H29 fixed where the scan looks. It said nothing about what the scan knows, and the answer
        was: not much. The five sentences that opened `ORDINARY_WEATHER_SENTENCES` all got past the
        original vocabulary, which held only the metric labels already on the home screen — so the
        per-screen machinery was guarding a door with the lock on the wrong side.

        This is the assertion that stops the list narrowing again. Deleting a word from
        `WEATHER_WORDS` to quieten a false positive now fails here rather than silently shrinking
        what D20 covers.
        """
        for sentence in ORDINARY_WEATHER_SENTENCES:
            self.assertTrue(
                any(word in sentence for word in WEATHER_WORDS),
                "D20's vocabulary does not catch {!r}, so that sentence could be written onto the "
                "propose screen and the suite would stay green".format(sentence),
            )

    def test_the_vocabulary_does_not_catch_restaurant_names(self):
        """The other side, and the reason single characters are excluded. A gate that fails on 涼麵
        is a gate people learn to bypass, and a bypassed gate protects nothing."""
        for name in ["涼麵", "熱炒一百", "冷藏櫃", "風味小館", "溫州大餛飩"]:
            hits = [word for word in WEATHER_WORDS if word in name]
            self.assertEqual(
                hits, [], "{!r} is a place name and would be read as weather: {}".format(name, hits)
            )


class NoVHtml(unittest.TestCase):
    """H7: Vue escapes everything except `v-html`, so keeping it absent makes the audit one
    greppable word.

    **Scanned over the raw file, comments included** — a commented-out `v-html` is one
    uncomment away from being live, so stripping comments here would be the wrong fix. What
    separates a use from a mention is the **equals sign**: live is `v-html="…"`, while the
    comment that forbids it writes the bare word. Matching on the bare word failed on the
    prohibition itself, which is the third time in this project a test asserting a token's
    absence has been tripped by the sentence explaining why it is forbidden.
    """

    USE = re.compile(r"v-html\s*=")

    def test_v_html_is_never_bound(self):
        for name in sorted(os.listdir(WEB)):
            if not name.endswith(".html"):
                continue
            path = os.path.join(WEB, name)
            source = read(path)
            hit = self.USE.search(source)
            # A boolean assertion with a line number, not assertNotIn: the latter prints the
            # entire file into the failure, which buries the one line that matters.
            self.assertIsNone(
                hit,
                "H7: {} binds v-html at line {}".format(
                    name, source[: hit.start()].count("\n") + 1 if hit else "?"
                ),
            )

    def test_the_rule_is_still_written_in_the_file(self):
        source = read(HOME)
        self.assertIn("v-html", source, "H7's prohibition has been deleted from the page")
        self.assertIn("H7", source)


class NoNetworkDependency(unittest.TestCase):
    def test_no_external_script_or_style(self):
        """§6 grades the demo on surviving dead venue wifi, and D3 vendors Vue for that
        reason. A CDN tag added later would pass every other test in this file."""
        source = read(HOME)
        for reference in re.findall(r'(?:src|href)\s*=\s*["\']([^"\']+)', source):
            self.assertFalse(
                reference.startswith("http://") or reference.startswith("https://"),
                "an external asset would not survive a dead network: {}".format(reference),
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
