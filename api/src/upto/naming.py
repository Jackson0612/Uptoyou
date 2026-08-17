"""D92 — a chain's branches are named in three layers, and the format says which layer answered.

Pure functions, no database: the SQL hands over a base name, its source and the registered
address; this module decides what a person reads. **One:** a storefront sign is shown as it
is — it is the branch's own registered sign and needs no derivation. **Two:** no sign and the
base name (brand or registered) is shared by other sign-less sites of the same company, so the
name is derived from the registered address as `品牌（行政區＋路名＋段）` — the bracket is the
provenance: it says "we derived this from an address the registry records", where a hyphen
would assert an official store name nobody published. **Three:** still colliding, so the house
number joins the parenthetical. Nothing here invents: every character in the bracket is copied
from the stored address (D84's lesson — a plausible branch name is exactly what this surface
must not produce). Owner-ruled 2026-08-18: composed here, in the API, never in the browser —
the same place appears in the search, the pool and the reveal, and only the API holds the set
that says whether a name collides.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Mapping, Optional

# Addresses arrive already normalised by `fda.normalise` (full-width folded, 台→臺, so 段
# numerals are Arabic and the city reads 臺北市). The parse is deliberately shallow: city,
# district, road (up to the road-class suffix), section, lane, alley, house number. Anything
# it cannot read is simply absent — a partial bracket is honest, an invented one is not.
_ADDRESS = re.compile(
    r"^(?:\d{3,6})?\s*"
    r"(?:臺北市)?"
    r"(?P<district>[一-鿿]{1,3}區)?"
    r"(?P<road>[一-鿿\dA-Za-z]+?(?:大道|路|街|道))?"
    r"(?P<section>\d+段)?"
    r"(?P<lane>\d+巷)?"
    r"(?P<alley>\d+弄)?"
    r"(?P<number>\d+(?:之\d+)?號)?"
)


@dataclass(frozen=True)
class Location:
    district: Optional[str]  # 中山區
    road: Optional[str]  # 南京東路
    section: Optional[str]  # 2段
    number: Optional[str]  # 86號 / 88之2號

    @property
    def where_line(self) -> Optional[str]:
        """B6's second line: 區＋路＋段, the place a person recognises. None when nothing parsed."""
        parts = [self.district, self.road, self.section]
        joined = "".join(p for p in parts if p)
        return joined or None

    def bracket(self, with_number: bool) -> Optional[str]:
        """D92's parenthetical: 區 loses its suffix (內湖 not 內湖區), the road keeps its class
        (信義路, so 民生東 does not stand for 民生東路), Arabic 段, then optionally the number."""
        district = self.district[:-1] if self.district and self.district.endswith("區") else self.district
        parts = [district, self.road, self.section]
        if with_number:
            parts.append(self.number)
        joined = "".join(p for p in parts if p)
        return joined or None


def location(address: Optional[str]) -> Location:
    match = _ADDRESS.match(address or "")
    if match is None:
        return Location(None, None, None, None)
    return Location(
        match.group("district"),
        match.group("road"),
        match.group("section"),
        match.group("number"),
    )


def derive_names(base: str, addresses: Mapping[str, str]) -> dict[str, str]:
    """Names for a set of sign-less sites that share one base name.

    `addresses` maps a site key (the registry number) to its stored address. Every site gets
    the layer-two bracket; the sites whose layer-two bracket is still shared move to layer
    three (house number). A site whose address yields nothing keeps the bare base — a bracket
    with nothing in it would be a lie about provenance.
    """
    if len(addresses) < 2:
        return {key: base for key in addresses}
    located = {key: location(addr) for key, addr in addresses.items()}
    layer_two = {key: loc.bracket(with_number=False) for key, loc in located.items()}
    counts: dict[Optional[str], int] = {}
    for bracket in layer_two.values():
        counts[bracket] = counts.get(bracket, 0) + 1
    out = {}
    for key, loc in located.items():
        bracket = layer_two[key]
        if bracket is not None and counts[bracket] > 1:
            bracket = loc.bracket(with_number=True)
        out[key] = "{}（{}）".format(base, bracket) if bracket else base
    return out


def where_lines(addresses: Iterable[tuple[str, Optional[str]]]) -> dict[str, Optional[str]]:
    return {key: location(addr).where_line for key, addr in addresses}
