# Phase 0 Research: Receipt Upload on Create Debt

## Decision: Use a reusable attachment uploader in the existing debt surface

**Rationale**: `frontend/src/pages/DebtsPage.tsx` currently owns the create-debt form and visible debt cards. A reusable `AttachmentUploader` component keeps validation, file previews, upload progress, and retry behavior in one place while allowing later reuse if a dedicated `/debts/:id` route is added.

**Alternatives considered**:

- Inline all upload logic inside `DebtsPage.tsx`: simpler initially, but it would duplicate retry and display behavior.
- Build a new debt details route first: better long-term routing, but larger than Phase 1 and not required to close the MVP receipt gap.

## Decision: Create debt first, then upload receipts one-by-one

**Rationale**: The existing API creates a debt independently from attachments. Creating the debt first avoids coupling debt persistence to file upload reliability. Sequential uploads simplify per-file error reporting and preserve a retry list when one file fails.

**Alternatives considered**:

- Parallel uploads: faster, but harder to present deterministic progress/failure messaging and not necessary for the small 1-N receipt MVP flow.
- Include files directly in debt creation: would require a new multipart debt contract and larger backend changes.
- Roll back the debt if any upload fails: violates the spec requirement that debt creation remains successful.

## Decision: Validate file type and size before submission; resize image files before upload

**Rationale**: Client-side validation gives immediate feedback and prevents known-invalid uploads. The 5 MB hard cap and 4 MB warning come from the Phase 1 plan. Resizing images with browser File/Canvas APIs avoids adding a new frontend dependency.

**Alternatives considered**:

- Backend-only validation: still required as defense in depth later, but poor UX and wastes bandwidth.
- Third-party image compression package: unnecessary for max-long-edge resizing and would add dependency surface.
- Resize PDFs: out of scope; PDFs are uploaded unchanged if they pass size/type validation.

## Decision: Update the upload helper to support `FormData`

**Rationale**: `frontend/src/lib/api.ts` currently assigns `Content-Type: application/json` whenever a body is present. Multipart uploads must let the browser set the boundary. The safest implementation is to skip the JSON content type when `body instanceof FormData`, or add a small upload helper that shares auth header injection.

**Alternatives considered**:

- Bypass `apiRequest` directly in the component: duplicates auth/session behavior.
- Manually set multipart boundary: brittle and incorrect in browsers.

## Decision: Align backend attachments with canonical receipt storage and signed URLs

**Rationale**: The endpoint exists, but current repository code uses mock URLs and an `attachments/` path. Project docs require private `receipts` bucket storage at `<debt_id>/<uuid>-<filename>` and signed URLs only. The plan therefore includes backend alignment even though the route is already present.

**Alternatives considered**:

- Leave current mock URL behavior: fails debtor viewing and security requirements.
- Return raw storage paths and sign client-side: exposes storage implementation and conflicts with the backend contract that returns signed access.

## Decision: Model retention as derived from the parent debt payment state

**Rationale**: The clarified rule says receipts stay available until the debt is paid and are archived for 6 months after payment. Existing debts already have `status` and `paid_at`, so retention state can be computed from the parent debt without a migration for Phase 1. Physical deletion or scheduled purge can remain a later housekeeping task.

**Alternatives considered**:

- Add `retention_state` columns immediately: explicit but unnecessary for Phase 1 and adds migration work.
- Store archive state only in the frontend: insufficient for API tests and any non-frontend consumer.
- Treat signed link expiry as retention expiry: incorrect; a 1-hour signed link is access-token lifetime, not file retention.

## Decision: Add backend integration coverage using the in-memory repository

**Rationale**: The roadmap requires `FastAPI.TestClient` tests with `REPOSITORY_TYPE=memory`. The test should create creditor/debtor profiles, create a debt, upload two invoice attachments, list them as the debtor, verify unauthorized access fails, and check attachment event visibility.

**Alternatives considered**:

- Supabase-only manual verification: useful for storage, but not acceptable as the only regression coverage.
- Frontend-only smoke test: current frontend has no test harness and cannot validate backend authorization/events.
