#!/usr/bin/env python3
"""D88's retrieval prompt, tested with no model, no network and no database.

    python3 app/api/tests/test_classify_rag.py

What is worth asserting here is the *shape of the experiment*, not whether cribs help — that
question belongs to an evaluation round against the frozen set, and no unit test can answer it.

Four things, and each one is a way the experiment could quietly stop measuring retrieval:

1. **The examples reach the prompt**, nearest first, as 「名稱：類別」 lines, above the ladder
   and below the category list. A crib that never rendered would produce a round scoring v3
   under a v5 filename.
2. **The base is v3, not v4.** v4's three additions measurably lost (qwen 51.0→50.0, gemma
   51.5→49.5), so the retrieval prompt is stacked on the better base — asserted by the v4-only
   sentences being absent, because a copy-paste from the wrong version is exactly the mistake
   that reads as a win.
3. **Validation is the shipped one.** `classify_name_rag` refuses what `classify_name`
   refuses, and stamps `RAG_PROMPT_VERSION` on every outcome — D39's condition 2 must not be
   softened by the branch that has examples.
4. **`gemini --rag` is refused before anything else happens.** The crib is the owner's gold
   labels and gold does not leave this machine (D88), so the refusal is argv-level and costs
   no key read, no network and no database.

Import discipline, same rule as `test_evaluate_score.py`: nothing reached from here may pull
SQLAlchemy at import time. The host Python has none, and D88's store is imported by
`run_round` inside the `--rag` branch alone for exactly that reason.
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
    RAG_PROMPT_VERSION,
    Refused,
    build_rag,
    classify_name_rag,
)
from upto.classify.prompt import INSTRUCTION, RAG_INSTRUCTION  # noqa: E402
from upto.evaluate import run_round  # noqa: E402

# Five neighbours in the shape `examples.nearest` returns them, nearest first: name, label,
# subtype. Every subtype is None because the frozen set carries none (0018) — the
# subtype-bearing branch is exercised separately below, against a synthetic crib.
EXAMPLES = [
    ("阿明麵店", "麵食", None),
    ("老捌麻辣食堂", "火鍋", None),
    ("春水堂人文茶館", "咖啡飲料", None),
    ("薔薇廳", "其他", None),
    ("旨王開發有限公司", NO_SIGNAL, None),
]


def answering(reply):
    return lambda prompt: reply


class TestTheRagPrompt(unittest.TestCase):
    def test_every_example_is_rendered_with_its_label(self):
        text = build_rag("一階堂", EXAMPLES)
        for name, label, _subtype in EXAMPLES:
            self.assertIn(f"{name}：{label}", text)

    def test_a_subtype_is_printed_beside_the_label(self):
        # 0018's case-book column: D38's ten do not change, and a finer tag rides along in
        # the crib alone. Synthetic, because the frozen set has no subtypes yet — this is the
        # branch that must already work when the first case book arrives.
        text = build_rag("某店", [("清心福全", "咖啡飲料", "手搖飲"), ("阿明麵店", "麵食", None)])
        self.assertIn("清心福全：咖啡飲料（手搖飲）", text)
        self.assertIn("阿明麵店：麵食", text)
        self.assertNotIn("阿明麵店：麵食（", text)

    def test_a_two_element_example_still_renders(self):
        # The frozen set's shape today; a caller that has no subtype column must not have to
        # invent one.
        self.assertIn("阿明麵店：麵食", build_rag("某店", [("阿明麵店", "麵食")]))

    def test_the_layer_is_never_printed(self):
        # Asymmetry with the subtype, and it is the ruling: a subtype is a fact about the
        # shop, a layer is how the score is read.
        text = build_rag("某店", EXAMPLES)
        for layer in ("sign", "brand", "registered", "招牌", "登記"):
            self.assertNotIn(layer, text[text.index("參考例") : text.index("判斷順序")])

    def test_the_examples_keep_the_order_they_were_retrieved_in(self):
        # Nearest first, and the prompt must not reorder them: the model reads top-down and
        # the retrieval order is the only ranking this design offers it.
        text = build_rag("一階堂", EXAMPLES)
        positions = [text.index(example[0]) for example in EXAMPLES]
        self.assertEqual(positions, sorted(positions))

    def test_the_examples_sit_between_the_category_list_and_the_ladder(self):
        text = build_rag("一階堂", EXAMPLES)
        self.assertLess(text.index("類別（只能是下列其中一個）"), text.index("參考例"))
        self.assertLess(text.index("參考例"), text.index("判斷順序"))

    def test_the_asked_name_is_the_last_thing_in_the_prompt(self):
        text = build_rag("一階堂", EXAMPLES)
        self.assertTrue(text.endswith("店名：一階堂\n類別："), repr(text[-40:]))

    def test_no_examples_still_builds(self):
        # A name whose every neighbour was excluded is a legitimate row, not a crash: the
        # prompt degrades to v3 rather than refusing to be built.
        text = build_rag("一階堂", [])
        self.assertIn("判斷順序", text)
        self.assertIn("店名：一階堂", text)

    def test_the_whole_category_list_is_offered(self):
        text = build_rag("某店", EXAMPLES)
        for value in CATEGORIES:
            self.assertIn(value, text)
        self.assertIn(NO_SIGNAL, text)

    def test_the_ladder_is_v3s_and_in_order(self):
        text = build_rag("某店", EXAMPLES)
        ladder = text[text.index("判斷順序") :]
        positions = [ladder.index(step) for step in ("自稱", "主食形式", "菜系", "其他")]
        self.assertEqual(positions, sorted(positions), "the ladder is out of order")

    def test_the_base_is_v3_and_not_v4(self):
        # v4's three additions, asserted absent. They are in the live INSTRUCTION — so this
        # also proves the two prompts have genuinely diverged rather than one aliasing the
        # other — and they measurably lost accuracy, which is why retrieval is not stacked
        # on top of them.
        for v4_only in ("忽略名稱裡的分店資訊", "主要賣的是飲品", "宴會館"):
            self.assertIn(v4_only, INSTRUCTION, "v4's text moved; this test needs re-deriving")
            self.assertNotIn(v4_only, RAG_INSTRUCTION)

    def test_the_two_versions_are_different_strings(self):
        self.assertNotEqual(RAG_PROMPT_VERSION, PROMPT_VERSION)


class TestValidationIsUnchanged(unittest.TestCase):
    def test_a_clean_answer_is_taken_and_stamped_with_the_rag_version(self):
        result = classify_name_rag("一階堂", answering("日式"), EXAMPLES)
        self.assertIsInstance(result, Classified)
        self.assertEqual(result.category, "日式")
        self.assertEqual(result.prompt_version, RAG_PROMPT_VERSION)

    def test_the_sentinel_is_still_its_own_outcome(self):
        result = classify_name_rag("旨王開發有限公司", answering(NO_SIGNAL), EXAMPLES)
        self.assertIsInstance(result, NoSignal)
        self.assertEqual(result.prompt_version, RAG_PROMPT_VERSION)

    def test_a_near_miss_is_refused_not_mapped(self):
        result = classify_name_rag("一階堂", answering("拉麵"), EXAMPLES)
        self.assertIsInstance(result, Refused)
        self.assertEqual(result.raw, "拉麵")
        self.assertEqual(result.prompt_version, RAG_PROMPT_VERSION)

    def test_garbage_is_refused(self):
        for raw in ("這家店看起來像是賣麵的", "", "？"):
            with self.subTest(raw=raw):
                self.assertIsInstance(
                    classify_name_rag("某店", answering(raw), EXAMPLES), Refused
                )

    def test_noise_around_a_valid_answer_is_still_stripped(self):
        result = classify_name_rag("某店", answering("「早餐」。"), EXAMPLES)
        self.assertIsInstance(result, Classified)
        self.assertEqual(result.category, "早餐")

    def test_an_empty_name_never_reaches_the_model(self):
        def explode(prompt):
            raise AssertionError("the model was asked about an empty name")

        self.assertIsInstance(classify_name_rag("   ", explode, EXAMPLES), Refused)

    def test_the_examples_actually_reach_the_model(self):
        seen = []
        classify_name_rag("一階堂", lambda prompt: seen.append(prompt) or "日式", EXAMPLES)
        self.assertIn("阿明麵店：麵食", seen[0])


class TestTheRunnerRefusesGemini(unittest.TestCase):
    """D88: the crib is the owner's gold, and gold does not leave this machine."""

    def test_gemini_with_rag_exits_two(self):
        def explode(*_args, **_kwargs):
            raise AssertionError("the refusal happened after something expensive")

        original = run_round.build_candidate
        run_round.build_candidate = explode
        try:
            self.assertEqual(run_round.main(["gemini", "--rag"]), 2)
            self.assertEqual(run_round.main(["--rag", "gemini"]), 2)
        finally:
            run_round.build_candidate = original

    def test_gemini_without_rag_is_still_reached(self):
        # The refusal must be about `--rag` and not about the candidate: a plain gemini round
        # is the hosted baseline and still runs.
        reached = []
        original = run_round.build_candidate
        run_round.build_candidate = lambda name: reached.append(name) or (_ for _ in ()).throw(
            run_round.UsageError("stopped here on purpose")
        )
        try:
            self.assertEqual(run_round.main(["gemini"]), 2)
        finally:
            run_round.build_candidate = original
        self.assertEqual(reached, ["gemini"])

    def test_an_unknown_flag_is_still_a_usage_error(self):
        self.assertEqual(run_round.main(["qwen", "--nope"]), 2)

    def test_the_rag_round_has_its_own_filename(self):
        plain = run_round.round_path("qwen")
        retrieved = run_round.round_path("qwen", RAG_PROMPT_VERSION)
        self.assertNotEqual(plain, retrieved)
        self.assertIn(RAG_PROMPT_VERSION, retrieved)

    def test_nothing_here_pulled_sqlalchemy(self):
        # D88's example store reaches SQLAlchemy and the host Python has none. `run_round`
        # imports it inside the `--rag` branch alone, so a plain round stays runnable here.
        self.assertNotIn("sqlalchemy", sys.modules)


if __name__ == "__main__":
    unittest.main(verbosity=2)
