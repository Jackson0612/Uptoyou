/**
 * A0b — the scaffold. One route, the product name, nothing else.
 *
 * No screen is built here: the home is the next ticket and waits on the owner
 * picking A or B on the comparison page. Nothing on this page fetches (§6).
 */
export default function App() {
  return (
    <main className="min-h-dvh grid place-items-center px-6">
      <div data-part="mark" className="text-center">
        <h1 className="text-display font-black tracking-tight">上桌了</h1>
        <p className="text-note text-muted mt-2 tracking-[0.18em] uppercase">Up to you</p>
      </div>
    </main>
  )
}
