/**
 * Lint calibration fixtures — 20 deliberate violations of the i18n lint rules.
 * Used by `npm run lint:calibration` to verify ≥ 95% catch rate (SC-003).
 * These are NEVER imported by production code. Kept in tests/ so Vite excludes them.
 */

// L1 — bare text node
const L1a = () => <button>Submit</button>;                               // violation 1
const L1b = () => <p>Loading…</p>;                                       // violation 2
const L1c = () => <span>Error occurred</span>;                           // violation 3
const L1d = () => <h1>Dashboard</h1>;                                    // violation 4
const L1e = () => <label>Full Name</label>;                              // violation 5

// L2 — bare aria-label
const L2a = () => <button aria-label="Close dialog" />;                  // violation 6
const L2b = () => <input aria-describedby="hint text" />;               // violation 7

// L3 — bare alt
const L3a = () => <img alt="Profile photo" src="/img.png" />;            // violation 8

// L4 — bare title prop
const L4a = () => <input title="Required field" />;                      // violation 9
const L4b = () => <abbr title="As soon as possible">ASAP</abbr>;        // violation 10

// L5 — bare placeholder
const L5a = () => <input placeholder="Enter your name" />;               // violation 11
const L5b = () => <input placeholder="Email address" />;                 // violation 12

// L6 — bare <title> child (document title)
const L6a = () => (
  <title>Settings Page</title>                                            // violation 13
);

// L7 — bare meta content
const L7a = () => (
  <meta name="description" content="Track your debts" />                 // violation 14
);
const L7b = () => (
  <meta property="og:title" content="Thabetha — debt tracker" />        // violation 15
);

// L8 — document.title assignment
function L8a() {
  document.title = 'Debt Tracker';                                       // violation 16 (not caught by JSX rule — grep/runtime check)
  return null;
}

// L9 — template literal without expressions in JSX
const L9a = () => <button>{`Submit form`}</button>;                      // violation 17
const L9b = () => <span>{`Loading data`}</span>;                         // violation 18

// Extra L1 variants for headcount
const extra1 = () => <div>Welcome back</div>;                            // violation 19
const extra2 = () => <button>Sign out</button>;                          // violation 20

export {};
