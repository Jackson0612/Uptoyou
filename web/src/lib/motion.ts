/**
 * `motion`, kept small on purpose — D104 amendment (`115ad08`), approved on a stated size budget.
 *
 * **`domAnimation`, not `domMax`.** The minimal feature set carries animations, variants and the
 * basic gestures; it does **not** carry layout animation or drag, and this surface wants neither.
 * `domMax` is roughly a third larger for two features nothing here uses.
 *
 * **`strict` is the part that makes the budget real rather than remembered.** Under `strict`, a
 * `motion.div` anywhere in the tree throws at render instead of quietly pulling the full feature
 * bundle in beside the lazy one. So the promise 「we only ship the small half」 is enforced by the
 * build, not by everyone remembering to type `m.` — which is exactly the kind of rule that decays.
 *
 * **Statically imported, never fetched.** `LazyMotion` also accepts `() => import(...)`, which
 * would split the features into a chunk the browser asks for at runtime. §6's dead-wifi rule is
 * about external assets, but a screen that needs a second request before it can animate is a screen
 * that behaves differently on a slow connection, and the whole point of A7 is what a person sees in
 * the first two seconds. One bundle, one request, no second act.
 */
export { LazyMotion, domAnimation, m, useReducedMotion, useAnimate } from 'motion/react'
