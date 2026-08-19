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

**The four `flood-*` tokens stay separate even though they now hold the same values as the
accents.** They are different facts that happen to coincide: `hot` is the accent, `flood-hot` is the
ground the entire viewport takes when the hot face wins. **Today is the proof.** The owner changed
the accent from red to orange; had the two been one token, the reveal's flood — the product's
signature moment — would have changed silently as a side effect of a decision about a button. **The
same argument that keeps `pipred` separate keeps these four.** Collapsing them is a design ruling,
not tidying.

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
> **Deleting the blocks is not the removal. Tailwind 4 ships a built-in `dark` variant driven by
> `prefers-color-scheme`, and shadcn's own parts carry `dark:` utilities** — `button` `input`
> `select` `badge` among them. **Delete our blocks without redefining that variant and those
> utilities are handed straight back to the OS setting**: a live rule that fires on a reader's
> laptop and never on ours. `@custom-variant dark` therefore points at `[data-scheme="dark"]`,
> which nothing sets, so the utilities compile and can never match. **That line is load-bearing and
> reads as dead code — the next person to tidy it is the person who re-enables dark mode by
> accident.**
>
> **Verify a removal by rendering, not by grepping.** The check that counts is the page rendering
> **pixel-identical under emulated light, dark and no-preference**. Asserting that the source no
> longer contains the word would not have caught the variant.
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
| `TABLE` | **shadcn `Table`** | header `text-note` muted; rows `text-body`; `1.5px ink` row rules; numerals right-aligned `tabular-nums`; a `CHIP` in the first column. **Operator state only — see §4b.** |
| `ALLOC36` | **custom** | the 36 cells in each place's face colour, drawn from the shares the evidence table prints. **It is the round's real allocation, not an illustration** — so it carries no 「示意」 caveat. **Operator state only — see §4b.** |
| `PICKER` | **shadcn `Select`** | the district picker. Restyle the trigger to `FIELD`; radius 0 on the content panel too. |
| `BADGE` | **shadcn `Badge`** | the home entry's eyebrow. `2px ink` border, radius 0, `text-note`. |
| `BLOCK` | **custom** | full-bleed flat colour band, `width: 100vw`, no radius/shadow/border. Ground is one of the palette; text is that ground's `on-*`. Blocks stack edge to edge — **the colour change is the separation**. |
| `BAR` | **custom** | pinned primary control, `fixed inset-x-0 bottom-0`, `3px ink` top rule, content box 56 + 10 padding, `--bar-h: calc(76px + env(safe-area-inset-bottom))`. **At most one per screen.** Every screen carrying one sets `main { padding-bottom: calc(var(--bar-h) + 16px) }`. |
| `ROW` | **custom** | one place in a list. `min-height` 56/60/68, `1.5px ink` bottom rule (last row none), name `text-body`, a `CHIP` at the left. Rows never alternate ground. |
| `CHIP` | **custom** | `12 × 12 px` square, radius 0, `1.5px ink` border, filled from the `FACES = [hot, cobalt, jade, sun]` cycle keyed by pool seat. **Identity, never quantity** — no share, weight or count. |
| `COLLAGE` | **custom** | the home entry's images (`D95`), 2×2 offset, each `2px ink` border + the §3 hard offset shadow, radius 0. **A pool of ten, four visible, one cell swapping every 10 s** (owner-ruled 2026-08-18) — the geometry never moves, only the photograph inside a fixed box. Every image carries `alt` naming the dish and describing the frame, and **the `alt` swaps with the image**. **A picture that cannot be named truthfully does not ship** (owner-ruled 2026-08-18: the menu is drawn only from dishes the generator renders truthfully, and breadth across `D38`'s ten categories chooses it — not taste in food). Rotation, loading, pool order and the `HC` gate: `idea & img/evaluator/spec-home-collage-rotation.md`. |
| `DIE` | **custom** | the 3-D cube. One variable, `--die`, at **140**/180/240 px; the `translateZ` that closes the six faces **derives from it** — change the value, never the derivation. **140, not 132, ruled 2026-08-19** (frontend found the conflict; the recommendation was its): 132 is **17.37%** of 760 against `R-D9`'s **18%** floor, so the token contradicted the gate it is measured by. 136.8 px is the exact floor and 140 clears it at 18.42% with margin for a border. **The floor was not moved to fit the token** — a target adjusted to pass its own test measures nothing, and 18% came from R-D9's measurement of the reference. Parked-width note: 430 is out of scope under §7b, so this changes nothing today; it is fixed now because a known contradiction left in this file is one the next reader has to rediscover. |

### §4b · The reveal has two states, and they are not a permission toggle over one design — `D105`

**Member state — what a person in the circle sees after the roll:** the winner, the dice, **one line
「三十六格已按權重分配」**, and the bar. **No per-place shares. No reasons. No table. No allocation
grid.**

**Operator state — demo and operator only, gated on a flag on the `device_secret`, set at issue
(`python -m upto.issue <circle_id> <nickname> --operator`), never on a URL flag:** everything above
**plus** `TABLE` and `ALLOC36`. **The role rides the credential, not the person** — `D12` keeps
`principal` holding an id and a stamp and nothing else — so the response shape is chosen by which
credential authenticated, and no parameter can carry it. The operator holds a seat like any member.

**Why, and it is the same argument as `B1`'s veto carried past the roll:** a narrow exclusion with an
obvious cause — 麻辣火鍋 at 0/36 — is **one guess in a five-person circle**. Publishing the shares
after the roll leaks precisely what the anonymity machinery exists to protect, and it leaks it to
the four people best placed to use it.

**Two consequences for how this is built and measured, and both are easy to get wrong:**

1. **`R-D9`'s answer-region targets apply to the MEMBER state.** Its non-negotiable clause — *the
   evidence table's first data row stays above the fold* — **has no object in member state, because
   there is no table.** With nothing below it, the answer region can be **more generous than 40 /
   45 / 50%**, not less. That is a gain, not a loosening.
2. **`D91`'s regression splits.** *Zero layout shift* and *the answer hidden mid-tumble* apply to
   **both** states. *The evidence table fully drawn while the dice move* and *the hit row at
   neighbour weight until it lands* apply to the **operator** state only — **members have no table
   for a hit row to leak from.**

**The cost, stated because nobody else will say it:** the home promises 「每一個數字都查得到出處」
and the reveal is where that promise was kept. **A member can now no longer check it.** The claim
becomes something the product does rather than something a user can verify, and its visible proof
lives in demo mode. That is a real trade and D105 makes it deliberately; it is not an oversight to
be quietly repaired by leaking a share back into the member view.

---

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

### Ambient loops — the fourth rule, added 2026-08-18

**An infinite animation is allowed only where the thing it animates is itself continuous.** Weather
is continuous; a slowly rotating collage is a rhythm; a button is neither. **Three conditions, all
required:**

1. **It must not move layout.** Everything animates on `transform` and `opacity` inside a **fixed
   box**, so a state change — a different weather condition, a different photograph — **shifts zero
   pixels**.
2. **Its period is 1.5 s or slower.** The surface's ambient set: 1.5 s rain, 3.2 s flash, 5 s halo,
   6–8 s drift, 14 s rotation, 10 s collage swap.
3. **`prefers-reduced-motion: reduce` stops all of it on a legible frame** — not a blank one. A
   stopped sun keeps its halo; a stopped collage keeps a photograph.

**A loop that fails any of the three is an entrance animation wearing a longer duration**, and §5's
rule 2 already refuses those.

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

## 7b · DEMO SCOPE — owner-ruled 2026-08-19, and it overrides the widths everywhere below

**「先捨棄手機，目前在趕進度，像 lawcidity 一樣有個 demo 網頁就好」.**

**The target is one width: 1440 — the approved page's own viewport.** Every spec in
`idea & img/evaluator/` states numbers at 430 / 900 / 2560; **while this section stands, only the
1440 column is built and only the 1440 column is gated.** The others are not deleted from the specs,
because deleting them is how they come back as guesswork.

**What this is and is not.** It is a portfolio demo — a page that shows the mechanism and the data
pipeline to someone assessing the work. It is **not** the shipped product. The product's real use is
five friends on five phones deciding where to eat, and a desktop-only build cannot do that job. That
cost is accepted deliberately, on a deadline, by the owner.

**Carried, not lost — the phone findings that were open when this landed:**

- **430's vertical rhythm compounds tighter than the approved page** — every gap ~1–2 px smaller,
  reaching **7.7 px at the collage** (inside ±8 px, at its edge), and aligning the frames still
  leaves 11.08% differing, so the smaller type tiers diverge as well as move.
  `gate-a0c-fidelity.md` holds the measurement.
- **`D89`** (the round screen responsive from 760 px) and **`R-D9`**'s 430 targets are **parked, not
  reversed.**

**Flip condition — one line, so nobody has to reconstruct it:** the day the product is aimed at
phones again, re-run `gate-a0c-fidelity.md` at 430 first. **The 430 drift is a known open defect and
must not be rediscovered as a surprise.** A build that has only ever been gated at 1440 has not been
shown to work on a phone; it has been shown to photograph well on a laptop.

**Do not read a green 1440 gate as a green product.**

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

**A screenshot-identity test is invalid on a page with ambient motion — and this bit after the test
had already been used to prove something.** Comparing two renders by `md5`, the check that proved
the dark scheme was gone, **stopped working the moment the weather icon was added**: an animated
page never produces two byte-identical frames, so it reported a difference that was the animation
frame rather than the colour scheme. **Run scheme- and state-identity comparisons with
`reduced_motion: "reduce"`** — that stops the loops on their legible frame and leaves only the
difference under test.

**Deleting a variant prefix is a specificity change, not a no-op — and this one is aimed at the
React port, where it will happen again.** Stripping `html[data-variant="a"]` dropped a rule from
`(0,2,2)` to `(0,1,1)`, where it **lost to a `:nth-child` selector at `(0,2,1)`** that it had
previously beaten. Four equal images became **370 / 328 / 328 / 370**, two overrunning their column
by 62 px. **Visible in the render, invisible in the diff.** Every `dark:` and `data-*` prefix that
comes off during a rewrite can hand a rule to a competitor it used to outrank, silently.

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
