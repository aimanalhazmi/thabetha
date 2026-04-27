# Thabetha / ثبتها — Spec-Kit Handoff

Snapshot of the Thabetha project at **2026-04-27**, structured for a clean handoff to another model and for continued development with [spec-kit](https://github.com/github/spec-kit).

The canonical product docs live one directory up in [`../`](../) and are still authoritative for vision, lifecycle, and MVP scope. The files here describe **current implementation reality** — what is shipped, where it lives, and what a fresh contributor needs to know.

## Contents

| File | What it answers |
|---|---|
| [`constitution.md`](./constitution.md) | Non-negotiable principles. Read first. |
| [`project-status.md`](./project-status.md) | What is done, in progress, pending, out of scope. |
| [`use-cases.md`](./use-cases.md) | UC1–UC10 with implementation status, endpoints, gaps. |
| [`database-schema.md`](./database-schema.md) | Tables, enums, indexes, RLS, migrations 001–007. |
| [`api-endpoints.md`](./api-endpoints.md) | Every backend endpoint, request/response, transitions. |
| [`frontend-surface.md`](./frontend-surface.md) | Pages, routes, role gating, i18n. |
| [`spec-kit-plan.md`](./spec-kit-plan.md) | Candidate spec-kit features for the next iteration. |

## How to use this folder with spec-kit

1. Treat [`constitution.md`](./constitution.md) as the project's spec-kit **Constitution** — drop it (or symlink it) into `.specify/memory/constitution.md` so `/specify` and `/plan` honour the rules automatically.
2. Pick the next feature from [`spec-kit-plan.md`](./spec-kit-plan.md), then run `/specify` → `/plan` → `/tasks` against it. The candidate features are intentionally written as one-line problem statements, not prescriptive plans.
3. When implementation lands, update [`project-status.md`](./project-status.md) and the relevant row in [`use-cases.md`](./use-cases.md). Both files are the heartbeat of this folder; everything else changes only when migrations or routes change.
4. If you change the DB or an endpoint, update the corresponding section in [`database-schema.md`](./database-schema.md) / [`api-endpoints.md`](./api-endpoints.md) in the same PR.

## Source-of-truth pointers

- Backend Pydantic enums and DTOs: `backend/app/schemas/domain.py`
- Backend routes: `backend/app/api/router.py` and siblings
- DB migrations: `supabase/migrations/001..007_*.sql`
- Frontend types (manually mirrored from backend): `frontend/src/lib/types.ts`
- i18n strings: `frontend/src/lib/i18n.ts`
- Repository abstraction: `backend/app/repositories/{base,memory,postgres}.py`

## Project-level docs (unchanged, still authoritative)

- [`../product-requirements.md`](../product-requirements.md) — problem, solution, UC list.
- [`../product-requirements-ar.md`](../product-requirements-ar.md) — Arabic mirror.
- [`../debt-lifecycle.md`](../debt-lifecycle.md) — canonical state machine.
- [`../mvp-scope.md`](../mvp-scope.md) — MoSCoW.
- [`../pages-and-use-cases.md`](../pages-and-use-cases.md) — page → actor → UC.
- [`../user-flows.md`](../user-flows.md) — creditor / debtor / shared flows.
- [`../roadmap.md`](../roadmap.md) — hackathon, post-MVP, future.
- [`../local-development.md`](../local-development.md) — local Supabase setup.
- [`../supabase.md`](../supabase.md) — Auth, DB, Storage, RLS, CLI.
