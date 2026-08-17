#!/usr/bin/env python3
"""D92's three layers, no network and no database — the pure half.

Run: python3 app/api/tests/test_naming.py

What it holds: the address parse reads 區／路／段／號 out of a normalised address and nothing
else; the bracket drops 區's suffix and keeps the road's class; the layer-three house number
appears only where layer two still collides; an unparseable address keeps the bare base rather
than an empty bracket (nothing is invented); one site alone never gains a bracket.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from upto.naming import derive_names, location, strip_registry_footnote  # noqa: E402

FAILURES = []


def check(name, condition, detail=""):
    if condition:
        print("ok   " + name)
    else:
        FAILURES.append(name)
        print("FAIL " + name + ("  — " + detail if detail else ""))


# --- the parse
loc = location("臺北市內湖區舊宗路1段120號")
check("district", loc.district == "內湖區", repr(loc))
check("road", loc.road == "舊宗路", repr(loc))
check("section", loc.section == "1段", repr(loc))
check("number", loc.number == "120號", repr(loc))
check("where line", loc.where_line == "內湖區舊宗路1段", repr(loc.where_line))
check("bracket short", loc.bracket(False) == "內湖舊宗路1段", repr(loc.bracket(False)))
check("bracket with number", loc.bracket(True) == "內湖舊宗路1段120號", repr(loc.bracket(True)))

loc = location("臺北市大安區新生南路3段88之2號")
check("之 number", loc.number == "88之2號", repr(loc))
loc = location("臺北市松山區市民大道6段131號1樓")
check("大道 road", loc.road == "市民大道" and loc.section == "6段", repr(loc))
loc = location("臺北市萬華區昆明街92之4號")
check("street, no section", loc.road == "昆明街" and loc.section is None, repr(loc))
check("where line without section", loc.where_line == "萬華區昆明街", repr(loc.where_line))
loc = location("臺北市大安區瑞安街142巷2之1號")
check("lane skipped, number kept", loc.number == "2之1號" and loc.road == "瑞安街", repr(loc))
loc = location("臺北市信義區松山路11號地下1樓商業空間G2-1號")
check("floor noise after number ignored", loc.number == "11號", repr(loc))
loc = location("x")
check("garbage parses to nothing", loc.where_line is None and loc.bracket(False) is None, repr(loc))
loc = location("10491臺北市中山區南京東路2段86號")
check("postcode prefix stripped", loc.district == "中山區" and loc.road == "南京東路", repr(loc))

# --- layer two: siblings on different roads
names = derive_names(
    "麥當勞",
    {
        "A": "臺北市內湖區舊宗路1段120號",
        "B": "臺北市大安區信義路2段88號",
    },
)
check("layer two A", names["A"] == "麥當勞（內湖舊宗路1段）", repr(names))
check("layer two B", names["B"] == "麥當勞（大安信義路2段）", repr(names))

# --- layer three: same road and section, so the number joins — only for the colliding pair
names = derive_names(
    "鼎泰豐",
    {
        "A": "臺北市大安區信義路2段194號",
        "B": "臺北市大安區信義路2段277號",
        "C": "臺北市信義區松高路11號",
    },
)
check("layer three A", names["A"] == "鼎泰豐（大安信義路2段194號）", repr(names))
check("layer three B", names["B"] == "鼎泰豐（大安信義路2段277號）", repr(names))
check("layer two survives for the lone one", names["C"] == "鼎泰豐（信義松高路）", repr(names))

# --- unparseable address: bare base, not an empty bracket
names = derive_names("麥當勞", {"A": "臺北市內湖區舊宗路1段120號", "B": "x"})
check("unparseable keeps bare base", names["B"] == "麥當勞", repr(names))
check("its sibling still bracketed", names["A"] == "麥當勞（內湖舊宗路1段）", repr(names))

# --- one site alone never gains a bracket
names = derive_names("阿宗麵線", {"A": "臺北市萬華區峨眉街8之1號"})
check("single site bare", names["A"] == "阿宗麵線", repr(names))

# --- R-6: registry footnotes at the head of the name are read out; nothing else is
check("無市招 stripped", strip_registry_footnote("(無市招)52巷3姊妹麵攤") == "52巷3姊妹麵攤")
check("重複登錄 stripped", strip_registry_footnote("(重複登錄)豪吐司早餐店") == "豪吐司早餐店")
check("footnote alone stays", strip_registry_footnote("(餐飲業)") == "(餐飲業)")
check("unknown marker untouched", strip_registry_footnote("(新開)小吃店") == "(新開)小吃店")
check("D92 bracket untouched", strip_registry_footnote("麥當勞（內湖舊宗路1段）") == "麥當勞（內湖舊宗路1段）")
check("None passes through", strip_registry_footnote(None) is None)

if FAILURES:
    print("\n{} failing: {}".format(len(FAILURES), ", ".join(FAILURES)))
    sys.exit(1)
print("\nnaming: D92's three layers hold — {} checks".format(
    open(__file__).read().count("\ncheck(")))
