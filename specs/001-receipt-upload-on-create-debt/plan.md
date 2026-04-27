# Implementation Plan: Receipt Upload on Create Debt

**Branch**: `001-receipt-upload-on-create-debt` | **Date**: 2026-04-27 | **Spec**: [spec.md](./spec.md)  
**Input**: Feature specification from `specs/001-receipt-upload-on-create-debt/spec.md`

## Summary

Add optional multi-file receipt upload to the existing create-debt flow. The frontend will validate images/PDFs, warn at 4 MB, reject files over 5 MB, resize oversized images to a 2048 px long edge, create the debt first, then upload each accepted receipt as `attachment_type=invoice`. The backend endpoint already exists, but the implementation must align it with the canonical `receipts` bucket, signed 1-hour access URLs, attachment audit events, and the clarified retention rule: receipts remain available until the debt is paid and are archived for 6 months after payment.

## Technical Context

**Language/Version**: Python >=3.12 backend; TypeScript 5.7 / React 19 frontend  
**Primary Dependencies**: FastAPI, Pydantic v2, psycopg, Supabase client/storage, python-multipart; React, Vite, react-router-dom, lucide-react, @supabase/supabase-js  
**Storage**: Supabase Postgres tables `debts`, `attachments`, `debt_events`; private Supabase Storage bucket `receipts`; in-memory repository for tests  
**Testing**: `pytest` with `FastAPI.TestClient` and `REPOSITORY_TYPE=memory`; frontend `npm run typecheck` / `npm run build` plus manual smoke because no frontend test harness exists yet  
**Target Platform**: Browser frontend served by Vite/build output; FastAPI backend behind `/api/v1`  
**Project Type**: Web application with separate `backend/` API and `frontend/` client  
**Performance Goals**: Receipt validation happens before submit; debt with two receipts is visible within 5 seconds after successful creation; generated receipt access links expire after 1 hour  
**Constraints**: Arabic-first strings in `frontend/src/lib/i18n.ts`; no permanent public receipt URLs; allowed file types are `image/*` and `application/pdf`; 5 MB hard cap per selected file; image long edge max 2048 px before upload; debt creation must not roll back if receipt upload fails; receipt files retained until paid and archived for 6 months after payment  
**Scale/Scope**: Small MVP surface: one create-debt form, reusable attachment component, existing attachment endpoints, one backend integration test path, and current debt list/details surface in `DebtsPage.tsx`

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The active `.specify/memory/constitution.md` still contains placeholder text, so the enforceable project gates are taken from `docs/spec-kit/constitution.md` and the Phase 1 roadmap notes.

| Gate | Status | Plan Alignment |
|------|--------|----------------|
| Bilateral debt lifecycle preserved | PASS | Debt still starts at `pending_confirmation`; attachments do not change debt status. |
| Canonical debt states unchanged | PASS | No new debt state is introduced. Receipt archive state is derived from attachment/debt retention, not debt lifecycle. |
| Per-user data isolation | PASS | Attachment endpoints continue to call `repo.get_authorized_debt(user.id, debt_id)` and storage paths remain debt-scoped. |
| Arabic-first UI | PASS | New user-facing strings are added to `frontend/src/lib/i18n.ts` in AR and EN. |
| Supabase-first storage | PASS | Receipts use private `receipts` bucket, path `<debt_id>/<uuid>-<filename>`, and signed URLs only. |
| Schema/type lockstep | PASS | Any `AttachmentOut` response additions are reflected in `frontend/src/lib/types.ts`. |
| Audit trail | PASS | Debt creation already emits `debt_created`; each successful receipt attachment will emit a debt event. |
| Required tests | PASS | Add a `FastAPI.TestClient` integration test covering create debt -> upload invoice attachment -> list attachments -> events. |

## Project Structure

### Documentation (this feature)

```text
specs/001-receipt-upload-on-create-debt/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── receipt-attachments.openapi.yaml
└── tasks.md
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── api/debts.py
│   ├── core/config.py
│   ├── repositories/base.py
│   ├── repositories/memory.py
│   ├── repositories/postgres.py
│   └── schemas/domain.py
└── tests/
    ├── conftest.py
    └── test_debt_lifecycle.py

frontend/
├── src/
│   ├── components/
│   │   └── AttachmentUploader.tsx
│   ├── lib/
│   │   ├── api.ts
│   │   ├── i18n.ts
│   │   └── types.ts
│   └── pages/
│       └── DebtsPage.tsx
└── package.json

supabase/
└── migrations/
```

**Structure Decision**: Use the existing web application split. Keep debt creation and the current debt details/list surface in `frontend/src/pages/DebtsPage.tsx`, introduce `frontend/src/components/AttachmentUploader.tsx` for create-flow and retry reuse, and update backend repository methods only where the existing attachment contract lacks signed URL, canonical storage path, audit event, or retention behavior.

## Phase 0 Research

Research output is captured in [research.md](./research.md). All technical unknowns are resolved; no `NEEDS CLARIFICATION` markers remain.

## Phase 1 Design Artifacts

- Data model: [data-model.md](./data-model.md)
- API contract: [contracts/receipt-attachments.openapi.yaml](./contracts/receipt-attachments.openapi.yaml)
- Manual quickstart: [quickstart.md](./quickstart.md)
- Agent context: [AGENTS.md](../../AGENTS.md) updated to point to this plan

## Post-Design Constitution Check

The design still passes the gates above. The only backend behavior change near debt lifecycle is receipt retention derived from `Debt.status == paid` and `paid_at`; it does not create a new debt transition. The API contract keeps authorization at the existing debt-party boundary and requires signed URLs rather than object bytes or permanent public links.

## Complexity Tracking

No constitution violations or additional project complexity are introduced.
