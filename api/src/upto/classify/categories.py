"""D38's closed list, and the validation D39 makes the whole process rest on.

Ten values, declared in D38 and copied here once. **A value outside this tuple is rejected,
never coerced** — D39's condition 2, and the reason the generation step has a test that can
fail at all. Coercing a near-miss ("拉麵" → 麵食) would quietly turn a wrong answer into a
plausible one, which is the H23 shape this whole schema keeps meeting.
"""

from __future__ import annotations

# D38, ruled 2026-08-14. The order is the order a scaffold would render them: forms first,
# then kinds, then the two that are about the clock and the cup, then the fallback.
CATEGORIES: tuple[str, ...] = (
    "麵食",
    "飯食",
    "小吃",
    "火鍋",
    "燒烤",
    "日式",
    "西式",
    "早餐",
    "咖啡飲料",
    "其他",
)


def is_valid(value: str) -> bool:
    return value in CATEGORIES
