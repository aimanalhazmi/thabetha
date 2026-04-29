# Implementation Plan: Voice-to-Debt Draft Polish

**Branch**: `012-ai-voice-debt-draft` | **Date**: 2026-04-29 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/012-ai-voice-debt-draft/spec.md`

## Summary

Replace the transcript-only voice debt draft stub with a production-shaped AI draft flow. The backend keeps the existing JSON transcript path, adds multipart audio input, transcribes Arabic/English audio through an injectable speech-to-text provider, reuses one transcript-to-draft service for both paths, enforces AI-tier access plus a per-user daily limit, deletes original audio after successful transcription, and returns a draft that requires explicit field confirmation before create-debt submission. The frontend adds a creditor-only AI voice draft control to the create-debt form, displays the transcript and extracted fields inline, requires confirmation/editing of every extracted field, and preserves the normal debtor resolution flow without profile matching.

## Technical Context

**Language/Version**: Python 3.12 backend; TypeScript strict frontend  
**Primary Dependencies**: FastAPI, Pydantic, Supabase/Postgres, Supabase Storage, React, Vite, lucide-react, OpenAI speech-to-text client behind a local provider interface  
**Storage**: Supabase Postgres for usage counters/draft metadata if persisted; private `voice-notes` bucket for temporary audio; in-memory repository equivalents for tests  
**Testing**: `pytest` with `FastAPI.TestClient` and `REPOSITORY_TYPE=memory`; Vitest/Testing Library if frontend test harness is already present, otherwise manual quickstart verification for UI  
**Target Platform**: Web application: FastAPI API server plus Vite React frontend  
**Project Type**: Full-stack web app  
**Performance Goals**: For accepted audio up to 60 seconds, primary voice-to-draft flow returns an editable draft within 30 seconds under normal local test conditions (SC-006). Unsupported format and over-duration failures return before transcription.  
**Constraints**: AI endpoints remain hard-gated by `profile.ai_enabled`; audio max 60 seconds; accepted formats are webm/mp3/wav/m4a; original audio is deleted after successful transcription; transcript is retained with the draft; no spoken debtor profile matching; every extracted field requires creditor confirmation or editing before debt creation; all new user-facing strings go through `frontend/src/lib/i18n.ts` in AR and EN.  
**Scale/Scope**: One AI endpoint evolved, one transcription provider family added, one create-debt UI surface added, one daily-limit mechanism shared by JSON and audio paths, one backend AI test file, and targeted frontend type/API/i18n updates.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Applicability | Status |
|-----------|---------------|--------|
| I. Bilateral Confirmation | Voice draft must not create a binding debt. It only prefills the existing create-debt form; debtor acceptance still starts after the creditor submits and the debt enters `pending_confirmation`. | Pass |
| II. Canonical 7-State Lifecycle | No new debt status or transition is introduced. Existing create-debt and debt lifecycle paths remain authoritative. | Pass |
| III. Commitment Indicator | No commitment indicator terminology or scoring changes. Voice drafts must not expose commitment data. | Pass |
| IV. Per-User Data Isolation | AI draft requests are scoped to the authenticated creditor. Transcripts, temporary audio, and usage counters are never visible to non-owners. | Pass |
| V. Arabic-First | Arabic/English transcription inputs are supported and all new frontend messages/errors land in `i18n.ts` for both locales. | Pass |
| VI. Supabase-First Stack | Temporary audio uses the existing private `voice-notes` bucket contract; any new persistence uses Supabase Postgres plus in-memory test parity. | Pass |
| VII. Schemas Source of Truth | `VoiceDebtDraft*` schemas in `backend/app/schemas/domain.py` and `VoiceDraft` in `frontend/src/lib/types.ts` must be updated together. | Pass |
| VIII. Audit Trail Per Debt | Drafting creates no debt event. If a debt is later created, existing create-debt event behavior applies. | Pass |
| IX. QR Identity | Voice drafts must not profile-match spoken names; QR/manual debtor resolution stays separate. | Pass |
| X. AI Paid-Tier Gating | `/api/v1/ai/debt-draft-from-voice` continues returning 403 unless `profile.ai_enabled` is true. | Pass |

**Post-Design Recheck**: Pass. Phase 0/1 design keeps all gates intact. The only persistence added is scoped usage/draft metadata and temporary audio handling; no lifecycle, RLS, or i18n exception is introduced.

## Project Structure

### Documentation (this feature)

```text
specs/012-ai-voice-debt-draft/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── voice-debt-draft.md
└── tasks.md              # Created later by /speckit-tasks
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── api/
│   │   └── ai.py                         # MODIFY: JSON/multipart dispatch, gating, daily limit responses
│   ├── core/
│   │   └── config.py                     # MODIFY: STT provider settings and daily-limit defaults
│   ├── repositories/
│   │   ├── base.py                       # MODIFY: AI usage + temporary voice note persistence contract
│   │   ├── memory.py                     # MODIFY: in-memory usage/draft support
│   │   └── postgres.py                   # MODIFY: Postgres usage/draft support if persistence added
│   ├── schemas/
│   │   └── domain.py                     # MODIFY: VoiceDebtDraft request/response schemas
│   └── services/
│       └── ai/
│           ├── __init__.py               # ADD
│           ├── draft_extract.py          # ADD: transcript-to-draft logic shared by both paths
│           ├── limits.py                 # ADD: AI daily-limit policy helper
│           ├── transcribe.py             # ADD: provider interface + real provider wiring
│           └── mock_transcribe.py        # ADD: deterministic test provider
└── tests/
    └── test_ai_voice_debt_draft.py       # ADD: gating, JSON, multipart, limits, deletion, no matching

frontend/
├── src/
│   ├── lib/
│   │   ├── api.ts                        # MODIFY: JSON and multipart voice draft helpers
│   │   ├── i18n.ts                       # MODIFY: AR/EN keys for voice draft UI/errors
│   │   └── types.ts                      # MODIFY: VoiceDraft field confirmation + raw transcript
│   └── pages/
│       └── DebtsPage.tsx                 # MODIFY: voice record/upload draft panel on create-debt form
└── tests/                                # OPTIONAL: add if existing Vitest harness is available

supabase/
└── migrations/
    └── 014_ai_voice_draft_usage.sql      # ADD if Postgres persistence is required for usage counters/drafts
```

**Structure Decision**: Existing full-stack layout remains unchanged. Backend changes stay in the current AI router, schemas, repository abstraction, and new `services/ai/` package. Frontend changes stay on the create-debt surface rather than the standalone AI page, because the spec requires the draft to be reviewed before debt creation.

## Complexity Tracking

No constitution violations or extra projects are required.
