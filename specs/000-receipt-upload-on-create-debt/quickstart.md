# Quickstart: Receipt Upload on Create Debt

## Prerequisites

- Backend dependencies installed with `uv`.
- Frontend dependencies installed with `npm install` in `frontend/`.
- Local Supabase configured for manual storage verification when using `REPOSITORY_TYPE=postgres`.

## Backend Verification

Run the in-memory regression suite:

```bash
cd backend
uv run pytest
```

Expected new coverage:

- Create creditor and debtor demo profiles.
- `POST /api/v1/debts` creates a pending debt.
- `POST /api/v1/debts/{id}/attachments?attachment_type=invoice` accepts image/PDF uploads.
- `GET /api/v1/debts/{id}/attachments` returns the attachments to the debtor with signed access metadata.
- An unrelated user cannot list or upload attachments for the debt.
- `GET /api/v1/debts/{id}/events` includes `debt_created` and successful attachment events.

## Frontend Verification

Run static checks:

```bash
cd frontend
npm run typecheck
npm run build
```

Manual smoke path:

1. Start the backend and frontend development servers.
2. Sign in as a creditor-capable user.
3. Open the debt creation surface.
4. Select two valid receipt files: one image and one PDF.
5. Confirm a 4-5 MB file shows a warning.
6. Confirm a file larger than 5 MB is rejected before debt submission.
7. Submit the debt.
8. Verify the debt still appears if one receipt upload fails.
9. Open the debt as the debtor and confirm receipt filenames/previews are visible.
10. Open a receipt and confirm the access link is temporary rather than a raw storage path.

## Local Supabase Storage Check

When testing with Postgres/Supabase storage:

```bash
supabase start
supabase db reset
```

Verify receipt objects are stored in the private `receipts` bucket with path shape:

```text
<debt_id>/<uuid>-<filename>
```

Do not use the legacy `thabetha-attachments` bucket for this feature.

## Retention Check

After a debt reaches `paid`, receipt attachments should remain visible in archived retention for 6 months after `paid_at`. Each generated access URL still expires after 1 hour and must be regenerated on the next authorized list/open request.
