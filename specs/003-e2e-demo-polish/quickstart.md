# Quickstart — End-to-End Demo Polish

**Feature**: 003-e2e-demo-polish
**Audience**: Reviewer or implementer verifying the polish, the tests, and the demo script.
**Time**: ~10 minutes total (5 min for the demo, ~5 min for the inventory checks).

> **Note**: This quickstart is the *internal* verification harness for the Phase 4 deliverables. The *user-facing* demo script is the new `docs/demo-script.md` produced by this phase.

## Prerequisites

1. `supabase start` — local Auth + DB + Storage running.
2. Backend on `:8000` with `SEED_DEMO_DATA=true` in `backend/.env`.
3. Frontend on `:5173`.
4. Two demo Supabase Auth accounts created once via Inbucket (per `docs/demo-script.md` Step 0). Subsequent demo runs reuse them.

## Verification checklist

### A. Polish-pass UI sweep (the four pages)

For each of `/debts`, `/dashboard`, `/notifications`, `/qr`:

1. Open the page on a fresh login (no data yet) and assert the empty-state renders translated copy in **both** AR and EN. No blank panels.
2. Click a transition button (accept / mark-paid / confirm / approve-edit / cancel) and assert: button shows a loading indicator (`…` label, spinner, or `disabled`) for the in-flight window.
3. Disconnect the backend mid-action (`Ctrl+C` the uvicorn process) and click any transition button. Assert the resulting error toast / message is a translated human-readable string — **never** `500: Internal Server Error` or a raw stack trace.
4. Reconnect backend and verify the page recovers on next interaction.

**Pass condition (SC-003, SC-004)**: every visible error and every empty-state across the four pages renders translated copy.

### B. Demo script self-serve test (SC-001)

1. Hand `docs/demo-script.md` to a contributor who has never run the app.
2. Stopwatch starts when they read step 1.
3. Stopwatch stops when they verify step 10 ("Verify commitment indicator").
4. Repeat with two more contributors back-to-back.

**Pass condition**: median time under 5 minutes; zero contributors ask for help; zero raw errors observed.

### C. Edit-request branch self-serve test (SC-001 + US2)

Same as B, but at step 7 they "Request edit" instead of "Accept", then the creditor approves.

**Pass condition**: same — median under 5 minutes (with the extra branch step).

### D. Integration tests (SC-005)

```bash
cd backend
uv run pytest tests/test_e2e_demo_path.py -v
```

**Assert**:
- `test_canonical_happy_path` passes; debt sequence is exactly `pending_confirmation → active → payment_pending_confirmation → paid`; debtor's `commitment_score == 53` (50 + 3 early payment).
- `test_edit_request_branch` passes; debt sequence is `pending_confirmation → edit_requested → pending_confirmation → active → payment_pending_confirmation → paid`; final `commitment_score == 53`.
- Combined runtime under 5 seconds (per SC-005). Echo timing on the test summary line.

### E. Untranslated-strings inventory (SC-007)

Open the PR description and verify it contains a section titled "Phase 5 hand-off — untranslated strings" with each entry as a `path:line — "literal"` pair.

**Pass condition**: section exists; minimum 0 entries (acceptable if the four pages happen to be already fully translated — unlikely but possible).

### F. 800 ms latency spot-check (SC-002)

Manually click each transition button on the happy path and the edit-request branch; perceive whether the UI reflects the new state within ~1 second. If a transition feels visibly slow:

```bash
# in browser DevTools → Network tab, measure the relevant POST request.
# If > 800 ms, profile backend; otherwise, the frontend re-render is the bottleneck.
```

**Pass condition**: every transition feels under 1 second; no manual refresh required.

## Done when

A through F all pass. The PR description includes:
- Inventory section from E.
- Brief note on the median demo time from B and C.
- Test runtime from D.

## Backend regression check

```bash
cd backend
uv run pytest -q
```

**Assert**: full suite still green (the existing `test_late_payment_penalty_doubles_per_missed_reminder` was failing before this phase — that pre-existing failure is not introduced here and is not in scope).
