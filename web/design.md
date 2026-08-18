# design.md — the grounding file for this surface

**Read this before writing any CSS or markup in `app/web/`.** It is the single first read: it holds
the tokens, the type ladder, the named parts and the rules that bind every screen. A build spec
references parts from here **by name** and adds only what is specific to its screen — so the job is
composition, not invention.

**This file is derived.** It carries parts and numbers, not arguments. The reasoning behind every
value lives in the project's decision record under the D-number stamped on each section. **When a
decision is amended, the decision is amended first and this file follows** — so if this file and the
record disagree, this file is the stale one.

| | |
|---|---|
| **Direction** | 六面 · Six Flat Faces |
| **Sections stamped** | `D101 · 2026-08-18` unless noted |
| **New component** | needs a spec entry before it is built. There is no such thing as a one-off. |

---

## 1 · Colour tokens — `D101 · 2026-08-18`

Declared on `:root` in `index.html`. **Do not introduce a colour that is not in this table**, and do
not pick an on-colour by eye — every `--on-*` below is whichever of ink/paper measured higher on
that ground.

### Light

| token | value | | token | value |
|---|---|---|---|---|
| `--ink` | `#101114` | | `--on-hot` | `#101114` |
| `--paper` | `#FFFDF7` | | `--on-cobalt` | `#FFFDF7` |
| `--muted` | `#5A5C63` | | `--on-jade` | `#101114` |
| `--hot` | `#FF4438` | | `--on-sun` | `#101114` |
| `--cobalt` | `#2547E8` | | | |
| `--jade` | `#00A870` | | | |
| `--sun` | `#FFC300` | | | |

### Dark

| token | value | | token | value |
|---|---|---|---|---|
| `--ink` | `#FFFDF7` | | `--hot` | `#F34F44` |
| `--paper` | `#101114` | | `--cobalt` | `#314FDC` |
| `--muted` | `#A8ABB3` | | `--jade` | `#0A9E6D` |
| | | | `--sun` | `#F0BB0F` |

On-colours are unchanged from light: `--on-hot` `--on-jade` `--on-sun` are `#101114`,
`--on-cobalt` is `#FFFDF7`.

### The flood — the landed reveal's ground

| face | light | dark | on-flood (dark) |
|---|---|---|---|
| hot | `#FF4438` | `#950900` | `#FFFDF7` |
| cobalt | `#2547E8` | `#0026DB` | `#FFFDF7` |
| jade | `#00A870` | `#005338` | `#FFFDF7` |
| sun | `#FFC300` | `#5B4500` | `#FFFDF7` |

**The dark values are not the raw hues and must not be "fixed" to match them.** Ceiling: a landed
dark flood's relative luminance is **≤ 0.08**. `--flood-sun` reads olive rather than yellow at that
ceiling; that is the ruled outcome, measured, not a bug.

### The die is an object, not a surface

`--pip` `#101114` · `--pipred` `#FF4438` · `--diefill` `#FFFDF7` · `--dieedge` `#101114` —
**identical in both schemes.** The die does not invert; same paint, lights off. `--pipred` is its
own token and is never replaced by an accent that flips.

### Floors, re-measured whenever a value here moves

Body text on any ground **≥ 4.5**. A purely graphical pair (a pip on a die face, a chip) **≥ 3.0**.
Thirteen pairs are in the standing set; the thirteenth is the pinned bar against a landed flood of
the same family, where the bar takes `--ink` ground with `--paper` text.

---

## 2 · Type — `spec: Direction D structural · 2026-08-18`

One vendored family, `Noto Sans TC`, variable, `font-weight: 100 900` **declared** — the face's
default instance is Thin, and without the range the whole surface renders hairline while every
geometric check still passes. `Archivo Black` is loaded for **Latin numerals only**.

**The declared fallback chain is part of the design, not a nicety:**
`"Noto Sans TC", "PingFang TC", "Microsoft JhengHei", "Noto Sans SC", "PingFang SC", "Microsoft YaHei",`
`"Noto Sans CJK TC", system-ui, -apple-system, sans-serif` — Traditional faces first, then a declared
Simplified/Japanese tail.
The vendored face cannot draw 89 characters that its own source face lacks — 88 live place names,
0.24% — and the chain is what draws them. **Determinism, not coverage:** it converts undeclared OS
font-linking into a declared chain; it does not guarantee the glyph exists on the reader's machine.

### The ladder

**Use only these for text. No inline `font-size` outside the ladder.**

| token | 430 | 900 | 2560 | used for |
|---|---|---|---|---|
| `--t-answer` | 44 | 72 | 112 | the winner's name on the landed reveal, nothing else |
| `--t-display` | 32 | 40 | 52 | a screen's own heading inside a colour block |
| `--t-sum` | 24 | 40 | 50 | the dice total |
| `--t-temp` | 30 | 34 | 40 | the outdoor temperature, nothing else |
| `--t-lead` | 20 | 21 | 24 | a block's lead line, a column head, the bar's label |
| `--t-body` | 16 | 17 | 20 | rows, names, controls, fields |
| `--t-note` | 13 | 13.5 | 15 | captions, keys, provenance, units |

**The invariant, tested at every width with no ties:**

```
--t-answer > --t-display ≥ --t-sum > --t-temp > --t-lead > --t-body > --t-note
```

Build each as a `clamp()` whose **floor and ceiling both obey the ordering**. A ladder that holds
only at the ceiling is the defect this table exists to prevent: a fixed size and a fluid size cross
at some width, and nothing in the source shows you where.

Weights: **900** for display, lead and the winner; **400** for body and note; **500** for a
control's label. No italics anywhere — the face has no true italic and a synthesised one is a tell.

---

## 3 · Space, rule and radius — `D101 · 2026-08-18`

- **Radius is `0`.** Everywhere. There is no rounded thing on this surface.
- **There are no shadows and no cards.** Separation is colour or a rule, never elevation.
- **Rule weights, and only these three:** `3px --ink` between a colour block and what pins over it
  (the bar's top edge); `1.5px --ink` between rows and table rows; `2px --ink` around a field or a
  ghost control.
- **Content column:** `390 / 736 / 1344 px` max-width, centred, at 430 / 900 / 2560.
- **Block padding:** `16 / 20 / 24 px` vertical.
- **Spacing steps:** `4 · 8 · 12 · 16 · 20 · 24 · 32`. Nothing between them.

---

## 4 · The parts

Implement each once; reuse it. **A screen does not invent a variant.** Values are 430 / 900 / 2560
where they change.

### `BLOCK` — a full-bleed flat colour band
`width: 100vw`, no radius, no shadow, no border. Ground is one of `--cobalt` · `--sun` · `--jade` ·
`--hot` · `--paper`; text is that ground's `--on-*`. Inner content centred in the content column.
Vertical padding per §3. **Blocks stack edge to edge with no gap and no rule between them** — the
colour change is the separation.

### `BAR` — the pinned primary control
`position: fixed; left: 0; right: 0; bottom: 0`. Ground `--hot`, text `--on-hot`, zero radius, full
width, **3px `--ink` top rule**. Content box **56px** plus **10px** padding top and bottom:

```
--bar-h: calc(76px + env(safe-area-inset-bottom));
```

Label at `--t-lead`, weight 900, centred. **Exactly one `BAR` per screen, and it is the only filled
control on that screen.** Every screen carrying one sets:

```
main { padding-bottom: calc(var(--bar-h) + 16px); }
```

**On a landed reveal whose flood is the hot family, the `BAR` takes `--ink` ground and `--paper`
text** so it does not vanish into the ground.

### `ROW` — one place in a list
`min-height` **56 / 60 / 68 px**. **1.5px `--ink` bottom rule**; the last row has none. Name at
`--t-body`. Vertical padding 10px. Carries a `CHIP` at its left. Rows never alternate ground.

### `CHIP` — a place's face colour
**12 × 12 px** square, zero radius, `1.5px --ink` border, filled from the
`FACES = ["hot","cobalt","jade","sun"]` cycle keyed by pool seat. **12px** left of the name,
optically centred on its first line. It is a square because the radius is zero.
**It carries an identity and no quantity** — never a share, a weight or a count.

### `FIELD` — a text input
Height **48 / 52 / 56 px**, ground `--paper`, **2px `--ink` border**, zero radius, text `--t-body`,
`--muted` placeholder. Focus: `outline: 2px solid var(--hot); outline-offset: 1px`. Its label sits
above at `--t-note` in `--muted`, and **that label is the only place its word appears on the
screen** — a column head and a field label never repeat the same word.

### `GHOST` — a secondary control
Transparent ground, **2px `--ink` border**, zero radius, `--ink` text at `--t-body`, same height as
`FIELD`. Any number per screen. Focus as `FIELD`.

### `TABLE` — the evidence table
Header row `--t-note` in `--muted`; data rows `--t-body`; **1.5px `--ink`** row rules; numerals
right-aligned with `font-variant-numeric: tabular-nums`; a `CHIP` in the first column matching the
pool's. Caption below at `--t-note`.

### `DIE` — the tumbling cube
One variable drives everything: `--die` at **132 / 180 / 240 px**. The `translateZ` that closes the
six faces into a cube **derives from `--die`** — change the value, never the derivation, or the
faces stop closing. Landed dice occupy **≥ 18%** of viewport height at 430.

---

## 5 · Motion

1. **The flood** transitions `background-color` and `color` over `.45s ease-out`. Nothing else about
   the landing animates.
2. **The `BAR`'s state change** is an opacity and label cross-fade of **120 ms**. The bar's box does
   not move, resize or slide.
3. **`prefers-reduced-motion: reduce`** removes the tumble and both transitions above. **The end
   states still apply, instantly** — the flood still floods, the bar still changes state.

**Nothing scroll-triggered. No entrance animation on a colour block. Nothing springy.** This surface
has no scroll narrative to reveal, and a block that fades in on load is a default tell.

---

## 6 · Rules that bind every screen, regardless of direction

These are not style. A change here is not a design decision and cannot be made from this file.

- **The surface may state; it may never advise.** No recommendation UI, ever. `D20`
- **Weather appears on the home screen and nowhere else.** `D20`
- **No restaurant name on the home screen.** `D94`
- **Nothing before the roll shows a share, a weight or a per-place count**, in any reachable state.
  `B1`
- **The result is decided before a single frame animates**, the answer is genuinely hidden while the
  dice move, and the landing shifts **0.00 px** — the mechanism is
  `visibility: hidden → visible`, so the answer holds its space the whole time. `D91`
  **Do not refactor this.** Anything that reserves space around it is fine; anything that inserts
  the answer into the layout is not.
- **No external asset.** Nothing on this surface fetches from another host. It renders with the
  wi-fi off.
- **`v-html` is never bound.**

---

## 7 · The anti-default list

Every one of these was measured as a failure mode on this project before the current direction. A
build that hits one is wrong even if it grades well elsewhere.

1. **Warm cream ground near `#F4F1EA` + high-contrast serif display + terracotta accent.** The most
   common AI-design default; the surface's previous direction was all three and was thrown out for
   it.
2. **Near-black ground with one acid accent.** Cleared here by a light-first ground and five hues
   rather than one.
3. **Broadsheet hairlines.** Our rules are 3px and 1.5px, not hairlines.
4. **Rounded cards floating on a ground with a soft shadow.** Radius is zero and there are no cards.
5. **A weather or a metric printed larger than the thing the product exists to answer.** The ladder
   in §2 makes this structurally impossible; check it, do not trust it.
6. **A gradient anywhere.** There are none. Flat means flat.
7. **Emoji or icon fonts as UI.** The dice are built from real pips; the selector caret is CSS.

---

## 8 · What each screen is measured against

The bar is finished commercial products, compared at the same viewport and the same kind of screen.
**A marketing page is not a product screen**: where one is cited, only its colour energy and type
scale are borrowed, never its layout or density.

| screen | compared against | what is borrowed |
|---|---|---|
| **reveal / the roll** | Wheel of Names | its proportions — the randomiser takes ~65% of viewport height. Ours targets 40 / 45 / 50% because ours must also keep the evidence table on screen, which the reference has no equivalent of. |
| **round sheet** | Rallly's poll panel | row pitch and per-row state in a dense group list. Its vote rows sit at a ~57px pitch at phone width; ours specify 56px. |
| **home** | Gumroad, with Duolingo as the control check | flat colour fields, zero radius, hard rules, display type scale, and exactly one filled control on the screen. |
| **device / first run** | Splitwise's split colour fields | two flat colour fields meeting at a hard edge, a heading over a two-line body, no radius, no gutter. |

**Everything else is reported as a distance, not as a pass or a fail.**

---

## 9 · Working rules for this directory

- **Nothing here is bind-mounted.** After any edit to `app/web/` or `app/proxy/upto.conf`, rebuild
  the proxy image and bring it up, or you are looking at the old page. A stale image does not
  announce itself.
- **Judge the built page, not the source.** Screenshot at **430 / 900 / 2560** in **both colour
  schemes**. 430 alone is not enough for CJK legibility; 900 and 430 both sit below the layout's
  large tiers, so 2560 is not optional either.
- **The surface's own tests** (`test_web_surface.py`, `test_web_contrast.py`) live outside this
  directory and are not yours to edit. When a legitimate change here breaks an assertion, send the
  needed change to whoever owns that file.
- **The rendered weight is asserted**, not assumed — see §2 on the Thin default instance.
