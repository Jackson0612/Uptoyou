"""D39's prompt, version-controlled — condition 1, and the artifact §6 asks for by name.

**The version string is data, not decoration.** Every generated row records it (D39's
condition 3), so a category can always be traced to the exact instruction that produced it,
and two prompt versions are compared by re-running rather than by argument. **Changing any
text below changes the version**, in the same commit, or the provenance starts lying.

The ladder in the instruction is D39's tie-break, ruled 2026-08-14: D38's list mixes axes on
purpose — 早餐 is a time, 日式 is a cuisine, 麵食 is a form — so a 日式早午餐 shop satisfies
two values and something has to decide. Self-description wins first because it is the signal
the shop itself chose to publish, and it is the one the model can actually see.
"""

from __future__ import annotations

from upto.classify.categories import CATEGORIES

PROMPT_VERSION = "v1-2026-08-14"

INSTRUCTION = """你是分類器。把一家餐飲店的店名分到下列其中一類，只輸出類別四個字以內，不要解釋、不要標點。

類別（只能是這十個之一）：
{categories}

判斷順序，依序套用，第一個成立就停：
1. 店名自稱哪一種店，就是哪一類（例如帶「早餐店」就是早餐，即使賣的是日式的）。
2. 沒有自稱，看主食形式：麵食、飯食、火鍋、燒烤。
3. 形式看不出來，看菜系：日式、西式。
4. 完全沒有訊號（例如控股公司、投資公司、看不出賣什麼），就是其他。

店名：{name}
類別："""


def build(name: str) -> str:
    """The exact text sent to the model for one place."""
    return INSTRUCTION.format(categories="、".join(CATEGORIES), name=name)
