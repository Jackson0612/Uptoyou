import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import Preferences from './components/preferences/Preferences.tsx'

/**
 * One path, one screen — read once at boot, with no router library.
 *
 * **Why not a router:** adding `react-router` is a stack decision with a real cost (a dependency,
 * a build-size line, a second way to express navigation) and it belongs to `[OPEN-2]` — the owner
 * is ruling how a person moves through five destinations, and picking the mechanism first would
 * quietly answer half of his question. Two paths need no library; five destinations may. **This is
 * the placeholder the ruling replaces, not the answer to it.**
 *
 * The proxy already serves `index.html` for any unmatched path (`try_files $uri $uri/ /index.html`),
 * so `/preferences` reaches this file without an nginx change.
 *
 * **Nothing links here yet, deliberately.** The home screen is under A0c's fidelity gate — a pixel
 * diff against the owner-approved page — so an affordance added there would fail that gate before
 * the frame has been ruled.
 */
const screen = window.location.pathname.replace(/\/+$/, '') === '/preferences'
  ? <Preferences />
  : <App />

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {screen}
  </StrictMode>,
)
