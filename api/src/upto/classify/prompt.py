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

PROMPT_VERSION = "v2-2026-08-14"

# The sentinel is deliberately not one of D38's ten. It is what the model says when the
# string it was handed names a legal entity rather than a place people eat at — measured
# 2026-08-14 to be 40.2% of the source's rows (D31) — and it maps to a stored NULL, which
# D58 already rules is a stated absence. **其他 therefore keeps its real meaning**: a place
# whose food does not fit the nine, rather than a row nobody could read.
NO_SIGNAL = "法人"

INSTRUCTION = """你是分類器。輸入是食品業者登錄的登記名稱，可能是店名，也可能只是公司的法人名稱。只輸出一個答案，不要解釋、不要標點。

類別（只能是下列其中一個）：
{categories}、{no_signal}

判斷順序，依序套用，第一個成立就停：
0. 這個名稱只是法人或控股公司、看不出是哪一家店（例如「安心食品服務股份有限公司」、「旨王開發有限公司」），就答「{no_signal}」。名稱裡有食物或店的線索就不算，繼續往下。
1. 店名自稱哪一種店，就是哪一類（例如帶「早餐店」就是早餐，即使賣的是日式的）。
2. 沒有自稱，看主食形式：麵食、飯食、火鍋、燒烤。
3. 形式看不出來，看菜系：日式、西式。
4. 看得出是一家店、但不屬於上面任何一類，才是其他。

店名：{name}
類別："""


def build(name: str) -> str:
    """The exact text sent to the model for one place."""
    return INSTRUCTION.format(
        categories="、".join(CATEGORIES), no_signal=NO_SIGNAL, name=name
    )
