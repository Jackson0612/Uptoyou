#!/usr/bin/env python3
"""D39's generator, tested without a model, a network or a database.

Run: python3 app/api/tests/test_classify.py

The model is a callable, so every case here is a *stated* model behaviour: the clean answer,
the answer wrapped in the noise a real model produced during the probe, and the answers that
must be refused. **The refusal tests are the point** — D39's condition 2 is the only part of
this process that can fail, and a coercion would delete it while looking like a fix.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from upto.classify import (  # noqa: E402
    CATEGORIES,
    NO_SIGNAL,
    Classified,
    NoSignal,
    PROMPT_VERSION,
    Refused,
    build,
    classify_name,
)


def answering(reply):
    return lambda prompt: reply


class TestAcceptance(unittest.TestCase):
    def test_a_clean_answer_is_taken(self):
        result = classify_name("啟祥早餐店", answering("早餐"))
        self.assertIsInstance(result, Classified)
        self.assertEqual(result.category, "早餐")
        self.assertEqual(result.prompt_version, PROMPT_VERSION)

    def test_noise_around_a_valid_answer_is_stripped(self):
        for raw in ("早餐。", " 早餐\n", "類別：早餐", "「早餐」", "早餐\n（因為店名有早餐店）"):
            with self.subTest(raw=raw):
                result = classify_name("啟祥早餐店", answering(raw))
                self.assertIsInstance(result, Classified, raw)
                self.assertEqual(result.category, "早餐")

    def test_every_listed_value_is_acceptable(self):
        for value in CATEGORIES:
            self.assertIsInstance(classify_name("某店", answering(value)), Classified, value)


class TestNoSignal(unittest.TestCase):
    """Ruled 2026-08-14: a legal entity is a decided outcome, not a category and not a failure."""

    def test_the_sentinel_is_its_own_outcome(self):
        result = classify_name("安心食品服務股份有限公司", answering(NO_SIGNAL))
        self.assertIsInstance(result, NoSignal)
        self.assertEqual(result.prompt_version, PROMPT_VERSION)

    def test_the_sentinel_is_not_one_of_the_ten(self):
        # If it ever joined D38's list it would become something a person could pick, and
        # 其他 would go back to meaning two things at once.
        self.assertNotIn(NO_SIGNAL, CATEGORIES)

    def test_noise_around_the_sentinel_is_stripped_too(self):
        self.assertIsInstance(classify_name("某公司", answering("「法人」。")), NoSignal)

    def test_it_is_not_a_refusal(self):
        # Same effect on the database, opposite meanings — the distinction ingest_run draws
        # between no change and failed, applied one table over.
        self.assertNotIsInstance(classify_name("某公司", answering(NO_SIGNAL)), Refused)


class TestRefusal(unittest.TestCase):
    """A wrong answer stays wrong — the one thing D39's process can catch."""

    def test_a_near_miss_is_refused_not_mapped(self):
        result = classify_name("一階堂", answering("拉麵"))
        self.assertIsInstance(result, Refused)
        self.assertEqual(result.raw, "拉麵")

    def test_an_explanation_instead_of_an_answer_is_refused(self):
        result = classify_name("某店", answering("這家店看起來像是賣麵的"))
        self.assertIsInstance(result, Refused)

    def test_an_empty_answer_is_refused(self):
        self.assertIsInstance(classify_name("某店", answering("")), Refused)

    def test_an_empty_name_never_reaches_the_model(self):
        def explode(prompt):
            raise AssertionError("the model was asked about an empty name")

        self.assertIsInstance(classify_name("   ", explode), Refused)


class TestPrompt(unittest.TestCase):
    def test_the_prompt_carries_the_list_and_the_name(self):
        text = build("老捌麻辣食堂")
        self.assertIn("老捌麻辣食堂", text)
        for value in CATEGORIES:
            self.assertIn(value, text)

    def test_the_ladder_is_in_the_prompt_in_order(self):
        # D39's tie-break is an instruction, not a convention held by whoever wrote the code.
        # Searched inside the ladder block alone: every value also appears in the list above
        # it, and an index over the whole prompt measures the wrong occurrence.
        text = build("某店")
        ladder = text[text.index("判斷順序") :]
        positions = [ladder.index(step) for step in ("自稱", "主食形式", "菜系", "其他")]
        self.assertEqual(positions, sorted(positions), "the ladder is out of order")

    def test_the_version_is_stamped_on_every_outcome(self):
        self.assertEqual(classify_name("某店", answering("早餐")).prompt_version, PROMPT_VERSION)
        self.assertEqual(classify_name("某店", answering("？")).prompt_version, PROMPT_VERSION)


if __name__ == "__main__":
    unittest.main(verbosity=2)
