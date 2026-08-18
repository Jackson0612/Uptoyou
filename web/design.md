# design.md — the grounding file for this surface

**Read this before writing any component in `app/web/`.** It holds the tokens, the type ladder, the
named parts and the rules that bind every screen. A build spec references parts from here **by
name** and adds only what is specific to its screen, so the job is composition, not invention.

**Stack, from `D104`:** Vite · React 19 · Tailwind 4 · shadcn/ui, built into the proxy image.
`D3`'s no-build-step rule is superseded.

**This file is derived.** It carries parts and numbers, not arguments; the reasoning lives in the
decision record under the D-number stamped on each section. **When a decision is amended, the
decision is amended first and this file follows** — if the two disagree, this file is the stale one.

---

## 0 · The one thing to understand before installing anything

**shadcn/ui's defaults are the look this project already rejected once.** Rounded corners, soft
shadows, muted grays, a single low-contrast accent — that is the house style of every AI-built
interface, and it is what the four-round loop produced and the owner threw out.

> **shadcn is adopted for its behaviour, not its appearance.** Take the accessibility, the keyboard
> handling, the focus management, the composition. **Restyle every part to the tokens below before
> it renders once.** A part that ships with its default skin is a defect, not a starting point.

**Concretely: `--radius` is `0`, there are no shadows except the hard offset in §3, and the palette
is replaced wholesale.** If a component looks like the shadcn documentation, it is wrong.

---

## 1 · Colour — Tailwind tokens

**There is one colour scheme. Light.** Owner-ruled 2026-08-18 — see the box at the end of this
section before adding a dark variant of anything.

Declared once as CSS custom properties and exposed to Tailwind via `@theme`. **Do not introduce a
colour outside this table, and never pick an on-colour by eye** — every `on-*` is whichever of
ink/paper measured higher on that ground.

| token | Tailwind | value |
|---|---|---|
| ink | `--color-ink` | `#101114` |
| paper | `--color-paper` | `#FFFDF7` |
| muted | `--color-muted` | `#5A5C63` |
| hot | `--color-hot` | `#FF875C` |
| hot-ink | `--color-hot-ink` | `#D95204` |
| cobalt | `--color-cobalt` | `#2547E8` |
| jade | `--color-jade` | `#00A870` |
| sun | `--color-sun` | `#FFC300` |

**On-colours:** `on-hot` `on-jade` `on-sun` = `#101114`; `on-cobalt` = `#FFFDF7`.

**`hot` is a GROUND. `hot-ink` is the same accent as TEXT or a MARK. They are not interchangeable**
— owner-ruled 2026-08-18, the reference demo's orange:

| use | token | measured | floor |
|---|---|---|---|
| pinned bar, badge fill, the count tag — ground with ink on it | `hot` `#FF875C` | **7.98** | 4.5 |
| the headline's second line — large text on paper | `hot-ink` `#D95204` | **4.00** | 3.0 |
| **focus ring, the star, any mark on paper** | `hot-ink` | **4.00** | 3.0 |
| ~~`hot` used as text or a mark on paper~~ | — | **2.33** | **fails** |

**The focus ring must take `hot-ink`.** On `hot` it is 2.33 against a 3.0 graphic floor, and **no
visual review can catch that** — a focus ring only exists while something is tabbed to.

**The reference itself fails this pair**: its display headline sets that orange on cream at 2.33.
We take its colour and not its mistake.

### The flood — the landed reveal's ground

| face | ground | on-flood |
|---|---|---|
| hot | `#FF875C` | `#101114` |
| cobalt | `#2547E8` | `#FFFDF7` |
| jade | `#00A870` | `#101114` |
| sun | `#FFC300` | `#101114` |

### The die is an object, not a surface

`pip #101114` · `pipred #FF4438` · `diefill #FFFDF7` · `dieedge #101114`.

**`pipred` stays its own token even though the accent no longer flips.** It had two reasons and now
has one: **a die is an object and its pips are red.** The second reason — that a scheme-flipping
accent measured 2.74 on the bone face — died with the dark scheme, and is recorded here as spent so
a later reader does not find half an argument and conclude the token is redundant.

### Floors, re-measured whenever a value moves

Body text on any ground **≥ 4.5**. A purely graphical pair (a pip on a die face, a chip, a focus
ring) **≥ 3.0**. **Nine pairs stand, measured once each.**

**`--radius: 0`** — set it in the shadcn theme, not per component.

---

> ### There is no dark mode, and this is the ruling that removed it
>
> **Owner-ruled 2026-08-18: dark mode is dropped.** `color-scheme: light` — **declared explicitly,
> not omitted**, or form controls and scrollbars still follow the OS and the removal is half-done in
> the one place nobody screenshots.
>
> **It was never chosen.** It arrived in the first `app/` commit — the boot skeleton, 2026-08-11 —
> as `color-scheme: light dark` with a `prefers-color-scheme` block, and no decision record ever
> mentioned it. **It is the anti-default list's own failure case**: an unconsidered default that
> slipped through because it predated the list.
>
> **What it cost while it lasted:** every colour pair measured twice, forever; every gate run doubled
> across three widths; a flood-luminance ceiling that existed only for the dark scheme; a separate
> pip token; and **the olive compromise — in dark, the sun face read olive rather than yellow**,
> which degraded the product's central idea (the winning face's colour owning the screen) in one of
> its four states.
>
> **What removing it costs, stated rather than hidden:** someone choosing dinner at night gets a
> bright screen — and the flood ruling itself said this product is used *「often at night, often in
> bed」*. Some readers expect an app to follow the system setting and read its refusal as unfinished.
>
> **Do not re-add a dark variant of a token to be helpful.** If dark mode returns it is a design
> project — a photographic home on a near-black ground is a different product, and it would need
> designing rather than inverting.

## 2 · Type

Two vendored families: **`UpTo Sans`** (Noto Sans TC, variable, `font-weight: 100 900` **declared** —
the face's default instance is Thin and without the range the whole surface renders hairline) and
**`UpTo Serif`** (Noto Serif TC subset, display only; its source face defaults to **ExtraLight**,
so it is declared `font-weight: 200 900` — the same hazard as the sans's Thin).

**`UpTo Serif` must ship in `app/web`. It does not yet.** The approved page draws its headline in it
from a proposal-only subset; the shipped set is sans-only, so a React build would fall back to a
system serif on the largest object on the screen. **Subsetting it against the home's characters and
teaching the subset gate's manifest a second face is part of the home build, not of the scaffold.**

**There is no third face.** An earlier version of this section named `Archivo Black` for Latin
numerals; **nothing loads it and nothing ever did** — the approved page draws `36,499` in `UpTo
Sans` at weight 900, and that is the rule.

**The declared fallback chain is part of the design:** `"Noto Sans TC", "PingFang TC",
"Microsoft JhengHei", "Noto Sans SC", "PingFang SC", "Microsoft YaHei", "Noto Sans CJK TC",
system-ui, -apple-system, sans-serif`. The vendored face cannot draw 89 characters its source face
lacks (88 live names, 0.24%); the chain draws them. **Determinism, not coverage** — it does not
guarantee the glyph exists on the reader's machine.

### The ladder — Tailwind text tokens

| token | 430 | 900 | 2560 | used for |
|---|---|---|---|---|
| `text-answer` | 44 | 72 | 112 | the winner's name on the landed reveal, nothing else |
| `text-display` | 32 | 40 | 52 | a screen's own heading |
| `text-sum` | 32 | 40 | 50 | the dice total |
| `text-temp` | 30 | 34 | 40 | the outdoor temperature, nothing else |
| `text-lead` | 20 | 21 | 24 | a block's lead line, a column head, the bar's label |
| `text-body` | 16 | 17 | 20 | rows, names, controls, fields |
| `text-note` | 13 | 13.5 | 15 | captions, keys, provenance, units |

**The invariant, tested at every width with no ties:**
`answer > display ≥ sum > temp > lead > body > note`.
Build each as a `clamp()` whose **floor and ceiling both obey the ordering** — a ladder that holds
only at the ceiling is the defect this table exists to prevent.

**A section heading takes `text-display`; it does not take the screen's `h1` size.** The mechanism
block's heading sitting on display rank once made an `h1` smaller than an `h2` beneath it.

**A display headline may be serif and two-tone** — ink with one phrase in `hot` — on the home entry.
**Weights:** 900 display/lead/winner, 400 body/note, 500 control labels. **No italics** — neither
face has a true one and a synthesised italic is a tell.

---

## 3 · Space, rule, radius, depth

- **Radius `0`. Everywhere.** The single exemption is `.pip`, which stays round because a die's pips
  are round; squaring them makes the face read as a grid. Nothing else.
- **No soft shadows and no cards.** Separation is colour or a rule.
- **One depth effect exists: a hard offset shadow**, `6px 6px 0 var(--color-ink)`, on images and on
  a raised block. No blur, no alpha. This is the only shadow in the system.
- **Rule weights, and only these three:** `3px ink` between a colour block and what pins over it;
  `1.5px ink` between rows and table rows; `2px ink` around a field or a ghost control.
- **Content column:** `min(1200px, 88vw)` — measured **83%** of a 1440 viewport.
- **Block padding:** `16 / 20 / 24 px` vertical. **Spacing steps:** `4 · 8 · 12 · 16 · 20 · 24 · 32`.

---

## 4 · The parts — which come from shadcn, which do not

**Anything marked *custom* has no shadcn equivalent worth bending to it.** Do not install a
component to obtain a part in this column; write it.

| part | source | notes |
|---|---|---|
| `FIELD` | **shadcn `Input`** | restyle: height 48/52/56, `2px ink` border, radius 0, paper ground, `text-body`, muted placeholder. Focus `outline: 2px solid hot; offset 1px`. |
| `GHOST` | **shadcn `Button`** `variant="outline"` | transparent ground, `2px ink` border, radius 0, `text-body`, same height as `FIELD`. |
| `PRIMARY` | **shadcn `Button`** `variant="default"` | ink ground, paper text, radius 0. **Disabled drops the ground entirely** — transparent, muted label, **dashed** ink border, `cursor: not-allowed`. Fading a fill measured **2.75:1** and failed the floor. |
| `TABLE` | **shadcn `Table`** | header `text-note` muted; rows `text-body`; `1.5px ink` row rules; numerals right-aligned `tabular-nums`; a `CHIP` in the first column. |
| `PICKER` | **shadcn `Select`** | the district picker. Restyle the trigger to `FIELD`; radius 0 on the content panel too. |
| `BADGE` | **shadcn `Badge`** | the home entry's eyebrow. `2px ink` border, radius 0, `text-note`. |
| `BLOCK` | **custom** | full-bleed flat colour band, `width: 100vw`, no radius/shadow/border. Ground is one of the palette; text is that ground's `on-*`. Blocks stack edge to edge — **the colour change is the separation**. |
| `BAR` | **custom** | pinned primary control, `fixed inset-x-0 bottom-0`, `3px ink` top rule, content box 56 + 10 padding, `--bar-h: calc(76px + env(safe-area-inset-bottom))`. **At most one per screen.** Every screen carrying one sets `main { padding-bottom: calc(var(--bar-h) + 16px) }`. |
| `ROW` | **custom** | one place in a list. `min-height` 56/60/68, `1.5px ink` bottom rule (last row none), name `text-body`, a `CHIP` at the left. Rows never alternate ground. |
| `CHIP` | **custom** | `12 × 12 px` square, radius 0, `1.5px ink` border, filled from the `FACES = [hot, cobalt, jade, sun]` cycle keyed by pool seat. **Identity, never quantity** — no share, weight or count. |
| `COLLAGE` | **custom** | the home entry's four images (`D95`), 2×2 offset, each `2px ink` border + the §3 hard offset shadow, radius 0. Every image carries `alt` describing what is actually in the frame. |
| `DIE` | **custom** | the 3-D cube. One variable, `--die`, at 132/180/240 px; the `translateZ` that closes the six faces **derives from it** — change the value, never the derivation. |

**The fill follows reversibility, not the part (`R-2`, `R-11`).** A control carrying a safe,
reversible act may be filled. **A control carrying an irreversible act is a ghost at rest** and
fills only once armed, at which moment whatever else was filled drops to ghost. **The rule is *at
most one* filled control per screen, asserted over every reachable state** — a screen may rest with
**none**, carrying a primary *shape* (an ink border, no ground) instead. **A disabled control is
never "filled".**

---

## 5 · Motion

1. **The flood** transitions background and colour over `.45s ease-out`. Nothing else about the
   landing animates.
2. **A bar's state change** is an opacity and label cross-fade of **120 ms**. Its box does not move,
   resize or slide.
3. **`prefers-reduced-motion: reduce`** removes the tumble and both transitions; **the end states
   still apply, instantly.**

**Nothing scroll-triggered, no entrance animation on a block, nothing springy.** Disable shadcn's
default enter/exit animations where they are not one of the three above.

---

## 6 · Rules that bind every screen, whatever the stack

A change here is not a design decision and cannot be made from this file.

- **The surface may state; it may never advise.** No recommendation UI, ever. `D20`
- **Weather appears on the home entry and nowhere else.** `D20`
- **No restaurant name on the home entry.** `D94`
- **Nothing before the roll shows a share, weight or per-place count**, in any reachable state. `B1`
- **The result is decided before a frame animates**, the answer is genuinely hidden while the dice
  move, and the landing shifts **0.00 px** — the answer holds its space via `opacity 0 → 1`, and
  **the hit row is gated by font-weight**. `D91` **Do not refactor this.**
- **No external asset.** Nothing fetches from another host; it renders with the wi-fi off. **This
  survives the build step: Vite must inline or emit local assets only, and no CDN font.**
- **`dangerouslySetInnerHTML` is never used.** (React's form of the old `v-html` prohibition.)

---

## 7 · The anti-default list — scoped to *unconsidered* defaults

**Scope, and it is a correction.** This list catches a default that arrived because nobody chose it.
**It does not rule out a family.** The family check convicted a warm-cream-and-serif direction that
the owner's own reference belongs to — a cliché is a thing done often because it works, and testing
for one is not testing for quality. **That half of the list is dead; do not resurrect it.**

What still counts as a defect:

1. **A shipped shadcn default skin** — rounded, soft-shadowed, gray. §0.
2. **Rounded cards floating on a ground with a soft shadow.** Radius is 0; the only shadow is hard.
3. **A gradient anywhere.** There are none.
4. **Emoji or icon fonts as UI.** The dice are real pips; the picker's caret is CSS.
5. **A weather or a metric printed larger than the thing the product exists to answer.** The ladder
   makes this structurally impossible — check it, do not trust it.
6. **Saturated colour spread across the screen instead of concentrated.** Measured: the reference
   holds high-saturation pixels to **10.8%** of the frame; a home at **36.7%** is the state the
   owner rejected. **Target: keep it under 20% and moving toward the reference.**
7. **A screen with no imagery where imagery is what carries the subject.** `D95`

---

## 8 · What each screen is measured against

**From now the gate is the owner-approved comparison page, pixel-for-pixel, not conformance to a
palette ruling.** The reference wall stays as the standing bar: reveal ↔ Wheel of Names, round sheet
↔ Rallly's poll panel, home ↔ the La Maison demo and Gumroad, device ↔ Splitwise. **A marketing page
is not a product screen** — where one is cited, only its colour energy and type scale are borrowed.

---

## 9 · Writing a check against this surface

**A probe that asserts a mechanism it did not read is not a check — it is a coincidence.** Four
measurement errors were made against this page in one day, by two people, every one the same shape.
One was a **false pass** that let a real defect through.

| the assumption | what the page actually does |
|---|---|
| the answer is hidden with `visibility` | **`opacity: 0 → 1`**, holding its box — which is what makes the shift 0.00 px. `checkVisibility()` **ignores opacity by spec**. |
| the hit row is hidden like the answer | it is gated by **`font-weight`**. An opacity probe cannot see it leak. |
| a custom property's value is a length | `getPropertyValue` returns the **declared `clamp(...)` string**. Resolve it by applying it to a probe element. |
| a filled control is a `<button>` | the pinned bar puts the fill on the **container**, with a transparent button inside. |

Two more that mislead the same way: **`innerText` is empty inside a closed `<details>`** though its
box exists; and **a disabled control is not a faded filled one** — the treatment drops the ground.

**Tailwind 4 tree-shakes any theme variable no utility references, and this produces a confident
false reading.** A probe asking for `--color-pipred` before any component uses it gets an **empty
string**, not the value — `getPropertyValue` returns nothing, the probe inherits, and pairs come
back at exactly **1.00** as though the palette were broken. **The palette is fine; the token is not
in the built CSS yet.** To verify a token before a screen consumes it, force its emission with a
throwaway component, measure, delete it, and confirm `dist` is clean afterwards.

**And pair a flood against its `on-flood` token, not against `paper`.** Measuring the wrong partner
returned 2.33 / 1.99 where the real pairs are 7.98 / 9.31 — the page was right both times.

**Under React, add one:** a stable hook for every part named in §4 — `data-part="bar"`,
`data-part="row"`, and so on. **Class names will change every time the styling changes; the gate
must not.**

---

## 10 · Working rules for this directory

- **There is a build step now.** After any change, rebuild the proxy image and bring it up, or you
  are looking at the old page. A stale image does not announce itself.
- **Judge the built page, not the source.** Screenshot at **430 / 900 / 1440 / 2560**. 1440 is in
  the list because it is the reference's own viewport. **One scheme — see §1.**
- **The surface's tests live outside this directory and are not yours to edit.** Send the needed
  change to whoever owns that file.
- **The rendered weight is asserted**, not assumed — see §2 on both faces defaulting to their
  thinnest instance.
