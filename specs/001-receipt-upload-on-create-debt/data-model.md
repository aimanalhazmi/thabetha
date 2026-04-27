# Data Model: Receipt Upload on Create Debt

## Debt

Represents the financial obligation created by a creditor for a debtor.

### Existing Fields Used

- `id`: unique debt identifier.
- `creditor_id`: user that created the debt.
- `debtor_id`: debtor user identifier when known.
- `debtor_name`: debtor display name.
- `amount`, `currency`, `description`, `due_date`: core debt terms.
- `status`: canonical debt lifecycle state.
- `created_at`, `updated_at`, `paid_at`: timestamps used for display and retention logic.

### Relationships

- One debt has zero or more receipt attachments.
- One debt has many debt activity events.
- Only debt parties may view or attach receipts.

### State Impact

- Receipt upload does not change debt lifecycle status.
- When debt status becomes `paid`, receipt attachments enter archived retention until 6 months after `paid_at`.

## Receipt Attachment

Represents a receipt, invoice, or proof document attached to a debt.

### Fields

- `id`: unique attachment identifier.
- `debt_id`: parent debt identifier.
- `uploader_id`: user that uploaded the file.
- `attachment_type`: must be `invoice` for this feature.
- `file_name`: original or sanitized display filename.
- `content_type`: uploaded MIME type.
- `storage_path`: private storage object path, using `<debt_id>/<uuid>-<filename>` in the `receipts` bucket.
- `url`: signed temporary access URL returned to authorized debt parties.
- `url_expires_at`: derived timestamp for the 1-hour signed URL lifetime.
- `retention_state`: derived value: `available`, `archived`, or `retention_expired`.
- `retention_expires_at`: derived as `paid_at + 6 months` when the parent debt is paid.
- `created_at`: upload timestamp.

### Validation Rules

- Accepted file types: `image/*` and `application/pdf`.
- Unsupported file types are rejected before debt submission in the frontend.
- Files larger than 4 MB and no larger than 5 MB show a warning.
- Files larger than 5 MB are rejected before debt submission.
- Images with a long edge greater than 2048 px are resized client-side before upload.
- PDFs are not resized.

### State Rules

- `available`: parent debt is not paid; authorized debt parties can list and open a signed URL.
- `archived`: parent debt is paid and `paid_at` is less than or equal to 6 months ago; authorized debt parties can still list and open a signed URL.
- `retention_expired`: parent debt was paid more than 6 months ago; the attachment is no longer available through the user-facing receipt list.

## Debt Activity Event

Represents audit history visible to debt parties.

### Existing Fields Used

- `id`
- `debt_id`
- `actor_id`
- `event_type`
- `message`
- `metadata`
- `created_at`

### New Event Usage

- Successful receipt attachment writes an event such as `attachment_uploaded`.
- Event metadata includes attachment id, filename, content type, and attachment type.
- Debt creation continues to write the existing `debt_created` event.

## Debt Participant

Represents a user authorized to interact with a debt.

### Rules

- Creditor and debtor may view attachments for the debt.
- Authorized party checks must be enforced by backend repository methods and mirrored by storage RLS.
- Unrelated users must receive a forbidden response when listing or uploading attachments.
