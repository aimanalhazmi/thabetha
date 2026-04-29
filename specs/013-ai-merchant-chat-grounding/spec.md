# Feature Specification: AI Merchant-Chat Grounding

**Feature Branch**: `013-ai-merchant-chat-grounding`
**Created**: 2026-04-29
**Status**: Draft
**Input**: User description: "Phase 13 — Merchant-chat grounding. Ground `POST /ai/merchant-chat` answers in the caller's actual ledger. The chatbot must be able to answer questions like 'who owes me the most?', 'did Ahmed pay me last month?', 'what's my overdue exposure?' without hallucinating, and must never expose debts the user is not a party to."

## Clarifications

### Session 2026-04-29

- Q: When a question would yield a large result set (e.g. 200+ debts), how should the assistant respond? → A: Return top N rows (by amount, then recency) plus exact aggregate count and totals; assistant explicitly says "showing top N of M".
- Q: How should relative time phrases like "last month" be resolved? → A: Calendar month in the caller's local timezone (e.g. asked any day in April 2026 local → "last month" = 2026-03-01..2026-03-31 local).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Grounded ledger Q&A for the caller (Priority: P1)

A paid-tier merchant (creditor) opens the AI chat surface and asks plain-language questions about their own ledger — outstanding balances, who owes the most, what was paid recently, what is overdue. The assistant answers using only data the caller is already authorised to see (their own debts and the debts of users they have a creditor/debtor relationship with), citing concrete numbers from the ledger rather than invented figures.

**Why this priority**: This is the entire feature. Without grounded answers anchored to real data, the chat is a generic LLM and offers no product value. It is also the prerequisite for the cross-user safety story (Story 2) — grounding is what makes refusal possible, because the data-access tools are scoped.

**Independent Test**: Seed a known ledger for a single user (e.g., 5 debts across `pending_confirmation`, `active`, `overdue`, `paid`). Send the three demo prompts ("who owes me the most?", "did Ahmed pay me last month?", "what's my overdue exposure?"). Verify each answer matches the seeded numbers exactly and references real debtor names/amounts from that ledger.

**Acceptance Scenarios**:

1. **Given** the caller has 3 active debts with debtors A (500 SAR), B (1,200 SAR), C (300 SAR), **When** they ask "who owes me the most?", **Then** the assistant responds with debtor B and the amount 1,200 SAR.
2. **Given** the caller has one debt with debtor "Ahmed" marked `paid` last month and another still `active`, **When** they ask "did Ahmed pay me last month?", **Then** the assistant confirms the paid debt with the date and amount.
3. **Given** the caller has 2 `overdue` debts totalling 800 SAR, **When** they ask "what's my overdue exposure?", **Then** the assistant returns 800 SAR and lists each overdue debt.
4. **Given** the caller asks a question with no relevant data in their ledger, **When** the model has no grounding to draw from, **Then** the response says "I don't have that information" rather than inventing one.

---

### User Story 2 - Cross-user data isolation (Priority: P1)

When a caller asks about another user's debts, finances, or activity that they are not a party to, the assistant must not return that data. Because the underlying data-access tools are scoped to the authenticated caller, the model has no way to retrieve data outside the caller's permitted view; the model must additionally refuse to speculate.

**Why this priority**: Equal-priority with Story 1 because grounding without isolation is a privacy regression. The product's defining promise is per-user data isolation; AI must not become a side channel.

**Independent Test**: Create two callers A and B with disjoint ledgers. Authenticated as A, ask "what does B owe to anyone?" and "show me B's debt with X". Verify no figures from B's ledger appear in the response and the assistant explicitly declines.

**Acceptance Scenarios**:

1. **Given** callers A and B have separate ledgers, **When** A asks the assistant about B's debts, **Then** no information from B's ledger is returned and the assistant responds with a refusal/no-data message.
2. **Given** caller A is not a party to a particular debt, **When** A asks for it by any identifier, **Then** the assistant cannot retrieve it and answers "I don't have that information".

---

### User Story 3 - Conversation continuity across turns (Priority: P2)

A merchant has a multi-turn conversation — they follow up with "and how much of that is overdue?" after the previous turn returned a list of receivables. The assistant maintains context across the most recent turns of the conversation so follow-ups feel natural, without the backend persisting any chat history.

**Why this priority**: Useful but not essential for the core value. The product still works as single-shot Q&A in P1.

**Independent Test**: Send a 2-turn exchange where turn 2 references "that" / "those" from turn 1. Verify the second answer correctly references the prior context and remains grounded in the caller's ledger.

**Acceptance Scenarios**:

1. **Given** a first turn that listed 3 active debts, **When** the caller asks "and which is the oldest?", **Then** the assistant identifies the correct debt from the prior list using its actual creation date.
2. **Given** more than 10 prior turns are sent by the client, **When** the assistant processes the request, **Then** only the most recent 10 turns inform the response.

---

### User Story 4 - Daily quota and tier gating (Priority: P2)

The chat is part of the paid AI tier and must be both gated by the per-user `ai_enabled` flag and rate-limited by a per-user daily call quota consistent with other AI endpoints. Users without AI access cannot reach the feature; users who exceed the quota receive a clear, translated message rather than silent failure.

**Why this priority**: Required for safe rollout (cost control, paid-tier integrity) but not part of the core grounding behaviour.

**Independent Test**: Toggle `ai_enabled` off → call returns 403 with translated copy. Toggle on → exhaust daily quota → next call returns a 429-equivalent translated message including a retry hint.

**Acceptance Scenarios**:

1. **Given** `ai_enabled = false`, **When** the caller invokes the chat, **Then** the request is denied with a translated "AI not enabled" message.
2. **Given** the caller has reached their daily quota, **When** they send another message, **Then** the response is a translated rate-limit notice that does not consume further quota.

---

### Edge Cases

- Caller asks about a debtor name that matches multiple debtors in their ledger → assistant disambiguates by listing matches with last-4 phone digits or amounts; does not silently pick one.
- Caller asks a question that requires aggregating across hundreds of debts → grounding tools return the top N rows (by amount, then recency) along with the exact total count and total sum; the assistant prefaces the answer with "showing top N of M" so the caller knows the list is abridged but the aggregate is exact.
- Caller asks for a debt by raw ID they are not party to → tool returns no data; assistant answers "I don't have that information" and does not echo the ID.
- Network/model failure mid-turn → user sees a translated transient-error message; quota is not consumed for failed turns.
- Caller asks in mixed Arabic/English → assistant responds in the same language as the question.
- Question requires no tool call at all (e.g., "what can you do?") → assistant answers from its own description without inventing ledger figures.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST answer merchant-chat questions only by grounding them in data retrieved through scoped data-access tools that operate as the authenticated caller.
- **FR-002**: The system MUST NOT return debt, profile, or activity data for any user the caller is not already authorised to see (i.e., not a creditor, debtor, or accepted group member of the underlying record).
- **FR-003**: When relevant data is unavailable, the assistant MUST state it does not have that information rather than fabricate values, names, dates, or amounts.
- **FR-004**: The assistant MUST be able to answer the three demonstration prompts ("who owes me the most?", "did <name> pay me <period>?", "what's my overdue exposure?") with figures matching the caller's actual ledger.
- **FR-005**: The system MUST expose a defined, finite set of grounding capabilities to the model: list debts (with filters), fetch a single debt by id, summarise the dashboard, and retrieve commitment-score history — each scoped to the caller.
- **FR-005a**: When a list-style grounding capability would return more rows than its configured cap, it MUST return only the top rows ordered by amount (descending) then recency, alongside the exact total row count and total sum, and the assistant MUST disclose the abridgement in the form "showing top N of M".
- **FR-006**: The system MUST accept the most recent N (default 10) turns of conversation history supplied by the client per request, and MUST NOT persist conversation history server-side beyond the request lifecycle.
- **FR-007**: The system MUST gate the chat endpoint on the caller's paid-AI flag and refuse with a clear, translated denial when disabled.
- **FR-008**: The system MUST enforce a per-user daily quota consistent with other AI endpoints in the product, and respond with a translated rate-limit message when exceeded.
- **FR-009**: The system MUST log each tool invocation (tool name and outcome) for observability without logging the arguments or returned ledger contents.
- **FR-010**: The assistant MUST respond in the same language (Arabic or English) as the caller's most recent question; bilingual responses are allowed only when the question itself mixes languages.
- **FR-011**: The system MUST refuse — at the model level — any request to reveal data about parties the caller is not associated with, even when the underlying tools would also block it.
- **FR-012**: The system MUST treat tool-returned amounts, dates, and names as the source of truth; the assistant MUST NOT alter, round, or translate amounts beyond locale-appropriate formatting.
- **FR-013**: The system MUST resolve relative time phrases (e.g. "last month", "this week", "today") to concrete date ranges anchored in the caller's local timezone using the Gregorian calendar — for example, "last month" maps to the full prior calendar month [first day 00:00, first day of current month 00:00) in local time. These resolved ranges MUST be the ones passed to grounding tools so answers remain reproducible and testable.

### Key Entities *(include if feature involves data)*

- **Chat turn**: A single user message plus assistant reply, with an implicit caller identity. Carries no persistent server identity.
- **Conversation window**: The trailing N turns supplied by the client on each request; the only chat memory the system uses.
- **Grounding tool**: A scoped capability the model can invoke (list debts, get debt, dashboard summary, commitment history). Each tool runs as the caller and inherits the same data-isolation rules as the rest of the product.
- **Tool invocation log entry**: An observability record of which tool was called and whether it succeeded — without arguments or returned ledger data.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Across the three demonstration prompts on a seeded ledger, 100% of returned numeric values (amounts, counts, dates) match the seeded ledger exactly.
- **SC-002**: In a cross-user leakage probe of at least 20 adversarial prompts, 0 prompts return any data point belonging to a user the caller is not associated with.
- **SC-003**: For prompts with no relevant data, at least 95% of responses explicitly state the information is unavailable rather than producing a fabricated answer.
- **SC-004**: 90% of merchant-chat responses on the demo prompts return within 5 seconds end-to-end on the local stack.
- **SC-005**: Disabled-tier callers receive a translated denial in 100% of attempts, and quota-exceeded callers receive a translated rate-limit message in 100% of attempts beyond the daily cap.
- **SC-006**: Multi-turn follow-ups that reference prior turns resolve correctly in at least 80% of a 25-prompt evaluation set.

## Assumptions

- The caller is an authenticated paid-tier user whose ledger is already accessible via the existing data-isolation rules; no new data-access pathway is introduced beyond what scoped tools expose.
- Conversation history is owned by the client; the backend remains stateless with respect to chat memory.
- The default conversation window is the last 10 turns; older turns are not considered.
- Streaming responses are not required for this phase; non-streaming replies are acceptable.
- The daily quota is per-user and shared with the broader AI tier's existing limit pattern; the exact number is configurable and not part of this spec.
- The Arabic-first product convention applies: any user-visible string introduced by this feature (denial, quota, error copy) lands in the central translation surface for both Arabic and English.
- The grounding tool set is intentionally small (list debts, get debt, dashboard summary, commitment history); broader analytics tools are out of scope for this phase.
- Time phrases use the Gregorian calendar in the caller's local timezone; Hijri-calendar interpretation is out of scope for this phase.
- Group debts follow the existing group-visibility rules already enforced elsewhere in the product; the chat does not relax or extend them.
