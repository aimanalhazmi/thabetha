# Feature Specification: Surface Groups in MVP Navigation (UC9 Part 1)

**Feature Branch**: `008-groups-mvp-surface`
**Created**: 2026-04-28
**Status**: Draft
**Input**: User description: "Read the plan in docs/spec-kit/implementation-plan.md and do only Phase 8 — Surface Groups in MVP nav (UC9 part 1)"

## Clarifications

### Session 2026-04-28

- Q: When the owner transfers ownership to another accepted member, does the recipient need to confirm, or does it take effect immediately? → A: Immediate transfer on owner's action; new owner is notified and can transfer back or leave if unwanted.
- Q: When a creditor creates a debt and tags it to a group, who is notified? → A: Only the parties (creditor and debtor); non-party group members see the new debt on the group surface without a push notification.
- Q: After a debt is created, can its group tag be changed or removed? → A: Editable while the debt is non-binding (`pending_confirmation` or `edit_requested`) by the creditor; locked once the debtor accepts.
- Q: When the owner deletes an empty group, what happens to its outstanding pending invitations? → A: Silently revoked together with the group; invitations disappear from invitees' lists with no notification.
- Q: After a group is created, can its name be changed? → A: The owner can rename the group at any time; all members see the new name immediately.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Create a group and invite friends or family (Priority: P1)

A user (e.g. a head of household, a friend organising a shared lunch tab, a small co-op) wants to create a named group, invite people they know by email or phone, and have a shared space where debts between members are visible to all accepted members. Today the underlying capability exists in the backend but no entry point exists in the application's main navigation, so the feature is invisible to users.

**Why this priority**: Without group creation and invitation, no other group capability is reachable. This is the foundational on-ramp for every other story in this feature; an MVP that ships only this story already provides standalone value (a named circle that people can join), even if no debts are tagged to it yet.

**Independent Test**: A logged-in user opens the app, navigates to Groups, creates a group called "Family", invites a second user by email, and sees the invitation listed as pending. The invited user receives the invitation in their own Groups view. Value delivered: a working invite flow visible end-to-end.

**Acceptance Scenarios**:

1. **Given** a logged-in user with the groups feature enabled, **When** they open the main navigation, **Then** they see a "Groups" entry alongside their existing entries.
2. **Given** a user on the Groups list page, **When** they choose "Create group" and enter a name, **Then** the group is created with them as the owner and they are listed as the only accepted member.
3. **Given** the owner of a freshly created group, **When** they invite a known user by email or phone, **Then** the invited user sees a pending invitation in their own Groups area.
4. **Given** a user with a pending invitation, **When** they accept it, **Then** they become an accepted member of the group and can see other accepted members.
5. **Given** a user with a pending invitation, **When** they decline it, **Then** the invitation is removed from their list and they do not appear as a member of the group.

---

### User Story 2 - Tag a debt to a shared group at creation time (Priority: P2)

When a creditor is creating a debt and both parties (creditor and debtor) are accepted members of the same group, the creditor can optionally attach the debt to that group. The debt then becomes visible to other accepted members of the group, in line with the relaxed-privacy rule that applies inside groups.

**Why this priority**: This is what makes group membership *useful*. Story 1 is a working surface, but Story 2 is what gives groups a reason to exist for shared expenses. It is P2 because it depends on Story 1 (the user must be in a group first) and because the underlying debt-creation flow already works without it.

**Independent Test**: Two users who are both accepted members of group G. User A (creditor) creates a debt against User B (debtor). On the create-debt form, A selects group G from a group selector. A third member of G, User C, opens the group's detail page and sees the new debt listed.

**Acceptance Scenarios**:

1. **Given** two users in the same accepted group, **When** the creditor opens the create-debt form with that debtor selected, **Then** an optional group selector appears listing the shared group(s).
2. **Given** the creditor selects a group on the create-debt form, **When** they submit the debt, **Then** the debt is associated with that group and shows in the group's debt list.
3. **Given** the creditor and debtor share no accepted group, **When** the creditor opens the create-debt form, **Then** the group selector is hidden.
4. **Given** a debt that is *not* tagged to a group, **When** any third party views any group, **Then** that debt is not visible to them — personal debts remain private.

---

### User Story 3 - View debts shared inside a group (Priority: P2)

Any accepted member of a group can open the group's detail view and see the list of debts that are tagged to that group, regardless of whether they are personally a party to those debts. This is the same relaxed-privacy contract already documented in the product rules: members of a group can see each other's group-tagged debts.

**Why this priority**: Without Story 3, Story 2's "tag a debt to a group" has no visible payoff. P2 because it ships together with Story 2 — neither is meaningful alone.

**Independent Test**: Group G has three accepted members A, B, C. A debt exists between A and B, tagged to G. C opens the group detail page and sees the debt with the parties' names and the amount.

**Acceptance Scenarios**:

1. **Given** an accepted group member, **When** they open a group detail page, **Then** they see all debts tagged to that group, including ones they are not a party to.
2. **Given** a non-member, **When** they attempt to view a group's detail page, **Then** they cannot see the group's debts.
3. **Given** a user with a pending (not yet accepted) invitation, **When** they attempt to view the group's debts, **Then** they cannot see them.

---

### User Story 4 - Leave a group, transfer ownership, or delete an empty group (Priority: P3)

Members can step away from groups they no longer wish to be part of. The owner has additional duties: they cannot simply leave (because someone has to be in charge), so they either transfer ownership to another member or delete the group outright; deletion is only allowed when the group has no debts attached to it.

**Why this priority**: This is the lifecycle-completeness story. P3 because most users will not need it on day one and the ones who do can still benefit from Stories 1–3 in the meantime; however it matters before the feature is considered shipped, otherwise users get permanently stuck in test groups.

**Independent Test**: A non-owner member of a group selects "Leave group" and is removed from the member list. Separately, the owner of an empty group selects "Delete group" and the group is removed; the owner of a non-empty group sees that delete is unavailable until either the debts are settled or ownership is transferred.

**Acceptance Scenarios**:

1. **Given** a non-owner member of a group, **When** they choose "Leave group" and confirm, **Then** they are removed from the group and lose access to its debts.
2. **Given** the owner of a group with at least one other member, **When** they attempt to leave, **Then** they are prompted to transfer ownership first.
3. **Given** the owner of a group with no debts attached, **When** they choose "Delete group" and confirm, **Then** the group is removed for all members.
4. **Given** the owner of a group that has at least one debt attached, **When** they attempt to delete the group, **Then** the action is blocked with a clear explanation that debts must be settled or detached first.

---

### User Story 5 - Opt in or out of the groups feature (Priority: P3)

Users can toggle the groups feature on or off from their settings. New accounts have it on by default. Existing users who would rather keep their app simple can hide the Groups navigation entry without losing any data.

**Why this priority**: This is the safety valve and the rollout lever. P3 because the default is "on", so most users will never touch it; but it is required to give the feature a graceful introduction for existing testers and to satisfy the implementation plan's pre-answered clarification.

**Independent Test**: A user with groups enabled toggles the feature off in Settings; the Groups entry disappears from the navigation. Toggling it back on restores the entry without data loss.

**Acceptance Scenarios**:

1. **Given** a user with the groups feature enabled, **When** they open Settings and disable groups, **Then** the Groups navigation entry disappears.
2. **Given** a user with the groups feature disabled, **When** they re-enable it, **Then** the Groups entry reappears and all their previously-joined groups are still listed.
3. **Given** a brand-new account, **When** the user signs up, **Then** the groups feature is on by default.

---

### Edge Cases

- **Member cap reached**: The 20th accepted member of a group already exists; an attempt to invite a 21st must fail with a clear "this group is full" message in both languages. Existing pending invites that would push the group over the cap on acceptance must also be handled — the simplest contract is that pending invites do not count toward the cap, and acceptance fails if the cap has been reached at acceptance time.
- **Invite to self**: A user attempts to invite their own email/phone. The invite must be rejected client-side and server-side with a translated error.
- **Duplicate invite**: A user is already a pending invitee or accepted member; re-inviting them must not create a duplicate row and must surface the existing state to the inviter.
- **Inviting a user who has not yet signed up**: Out of scope for this phase. Invitations target known platform users only — by email/phone matched against existing profiles. If no match is found, the inviter is told that the recipient must sign up first.
- **Debt tagged to a group, then one party leaves the group**: The debt remains as it was; visibility for the leaver of any group-only debts they were not a party to is revoked. The debt itself does not disappear and does not change state; the leaver continues to see debts they are personally a party to (because that visibility comes from being a party, not from group membership).
- **Group deletion attempt with debts attached**: Blocked. The owner is shown a list of attached debts and offered the next steps (settle, or transfer ownership and let someone else handle it later).
- **Owner accepts their own invite**: Not applicable — the creator of a group is implicitly the first accepted member; no self-invite flow exists.
- **Group selector on create-debt when both parties share *multiple* accepted groups**: The selector lists all of them; the creditor picks one; selecting "none" leaves the debt personal.
- **Disabling the groups feature while still owning groups**: The user keeps their data; existing memberships are preserved server-side and the navigation entry simply disappears. Re-enabling restores the surface.
- **Pending invites visible to other members**: A pending invitee should *not* appear in the member list shown to existing members until they accept — only accepted members are listed. The owner can see their own outstanding invites in a separate "Pending invites" list to manage them.

## Requirements *(mandatory)*

### Functional Requirements

#### Navigation and feature flag

- **FR-001**: System MUST surface a "Groups" entry in the main navigation for users who have the groups feature enabled, in both supported languages, with the existing visual style of other navigation entries.
- **FR-002**: System MUST default the groups feature to enabled for newly created user profiles.
- **FR-003**: System MUST allow a user to toggle the groups feature on or off from their settings, and the navigation entry MUST update accordingly without requiring a re-login.
- **FR-004**: System MUST preserve a user's group memberships when the feature is toggled off; re-enabling MUST restore visibility of those memberships unchanged.

#### Group lifecycle

- **FR-005**: System MUST allow any user with the groups feature enabled to create a group by providing a non-empty name, regardless of whether their account type is creditor, debtor, or both.
- **FR-006**: System MUST record the group creator as the owner and as the first accepted member.
- **FR-006a**: System MUST allow the current owner of a group to rename it at any time, subject to the same non-empty-name validation used at creation; renames take effect immediately for all accepted members and any pending invitees.
- **FR-007**: System MUST allow the owner of a group with no debts attached to delete the group, removing it for all accepted members and any pending invitees.
- **FR-007a**: System MUST silently revoke any outstanding pending invitations to a group at the moment the group is deleted; revoked invitations MUST disappear from the affected invitees' lists, and no notification MUST be sent to invitees about the deletion.
- **FR-008**: System MUST block deletion of a group that has any debts attached, and MUST tell the owner why and what they can do about it.
- **FR-009**: System MUST prevent the owner from leaving a group while remaining the owner; the owner MUST first transfer ownership to another accepted member, after which they MAY leave like any other member.
- **FR-009a**: System MUST treat ownership transfer as a unilateral action by the current owner: selecting any accepted member as the new owner takes effect immediately on confirmation, with no acceptance step required from the recipient.
- **FR-009b**: System MUST notify the new owner that they have become the owner of the group, so they can choose to transfer ownership onward or leave if the role is unwanted.
- **FR-010**: System MUST allow any non-owner accepted member to leave a group at will; on leaving, the user immediately loses visibility of group-only debts they were not personally a party to.

#### Membership and invitations

- **FR-011**: System MUST allow the owner of a group to invite users to that group by email or phone number, matched against existing platform profiles only.
- **FR-012**: System MUST reject an invitation aimed at a recipient who is not yet a platform user, with a clear message asking the inviter to share the app with that recipient first.
- **FR-013**: System MUST reject duplicate invitations: if the recipient is already a pending invitee or accepted member, the system MUST surface the existing state instead of creating a duplicate.
- **FR-014**: System MUST reject an invitation a user attempts to send to themselves.
- **FR-015**: System MUST allow an invited user to accept or decline their pending invitation from their own Groups area.
- **FR-016**: System MUST cap accepted membership at 20 members per group; an invitation acceptance that would exceed this cap MUST be rejected with a translated "group is full" message, leaving the invitation in a clear terminal state.
- **FR-017**: System MUST allow each accepted member to see the list of *accepted* members of the group, but MUST NOT expose the list of pending invitees to non-owners.
- **FR-018**: System MUST allow the owner to view and revoke their own outstanding pending invitations.

#### Debts inside a group

- **FR-019**: System MUST offer an optional group selector on the create-debt flow only when the creditor and debtor share at least one accepted group.
- **FR-020**: System MUST list every group the creditor and debtor share when more than one shared group exists, allowing the creditor to pick one.
- **FR-021**: System MUST treat group tagging as optional: leaving the selector unset MUST result in a personal (private) debt, identical to today's behaviour.
- **FR-022**: System MUST make a debt tagged to a group visible to all accepted members of that group, on the group's detail surface, including the parties' names and amount.
- **FR-022a**: System MUST send debt-creation notifications only to the debt's parties (creditor and debtor), regardless of whether the debt is group-tagged; non-party group members MUST NOT receive a push or in-app notification when a new group-tagged debt is created. Non-party members surface the new debt by opening the group's detail view.
- **FR-022b**: System MUST allow the creditor to change or remove the group tag on a debt while the debt is still non-binding (status `pending_confirmation` or `edit_requested`). The selector offered at edit time MUST follow the same rule as at creation: only groups in which both parties are accepted members are eligible.
- **FR-022c**: System MUST lock the group tag once the debtor has accepted the debt (status `active` or any later state); the tag MUST NOT be changeable or removable thereafter. Group members who gained or lost visibility under FR-022b's edit window experience the change immediately on the group surface; the change does not retroactively notify non-party members.
- **FR-023**: System MUST keep debts that are *not* tagged to a group strictly private to creditor and debtor, never surfacing them to other group members.
- **FR-024**: System MUST prevent non-members and pending invitees from seeing any of a group's debts.
- **FR-025**: System MUST preserve the existing visibility of a personal debt to its parties when the debt is or becomes group-tagged: parties always see their own debts, regardless of group membership state.

#### Bilingual and accessibility expectations

- **FR-026**: System MUST present every new visible string in both supported languages from day one of release; no monolingual surfaces.
- **FR-027**: System MUST keep the term "commitment indicator" (and its bilingual counterpart) wherever a member's standing is shown inside a group; it MUST NOT introduce any new "score" or "rating" terminology.

#### Out of scope (explicitly)

- **FR-028**: System MUST NOT compute or apply auto-netting of group debts in this phase; settlement of group debts continues to follow the existing per-debt flow until a later phase delivers auto-netting.
- **FR-029**: System MUST NOT allow inviting non-users via SMS or email signup link in this phase; recipient must already be a platform user.

### Key Entities *(include if feature involves data)*

- **Group**: A named circle of users (max 20 accepted members) with one owner. Lifecycle: created → active → either deleted by owner (when empty) or persists indefinitely. Visibility of debts inside the group is relaxed compared to personal debts.
- **Group membership**: The relationship between a user and a group, with a status of *pending invite*, *accepted*, *declined*, or *left*. Only *accepted* members count toward the cap and have visibility of group debts. Owner is a special accepted member; there is exactly one owner per group at any time.
- **Group invitation**: A pending invitation issued by the owner to an existing platform user (matched on email or phone). It resolves to *accepted*, *declined*, or *revoked-by-owner*. Pending invites do not consume member-cap slots until acceptance.
- **Group-tagged debt**: An ordinary debt that has been associated with a group at creation. The tag affects only visibility (group members see it); it does not change the debt lifecycle, parties, or amounts. Untagged debts remain personal and private.
- **User-level groups setting**: A per-user flag that controls whether the Groups navigation entry is shown. Defaults to enabled for new accounts. Toggling it does not destroy memberships; it only hides the surface.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new user with the feature enabled can find and open the Groups area from the main navigation in under 5 seconds, with no documentation required.
- **SC-002**: A user can create a group, invite a second user by email, have that user accept, and see them as an accepted member, all in under 2 minutes from a cold start.
- **SC-003**: At least 95% of attempted invitations to existing platform users either succeed (recipient sees the invite) or fail with a translated, actionable error within 3 seconds.
- **SC-004**: A debt tagged to a group at creation appears on every accepted member's group detail view within 5 seconds of creation, without requiring a manual refresh.
- **SC-005**: An invitation aimed at a 21st accepted member is rejected with a clear, translated "group is full" message in 100% of cases.
- **SC-006**: A non-member who attempts to view a group's debts (whether by direct navigation or any other means) sees zero of that group's debts in 100% of cases.
- **SC-007**: Toggling the groups feature off in settings hides the Groups navigation entry in under 2 seconds and preserves the user's group memberships such that re-enabling restores them with zero data loss.
- **SC-008**: 100% of new strings introduced by this feature are present in both supported languages on first release; the project's bilingual lint guard MUST report zero raw, untranslated strings.

## Assumptions

- The underlying group endpoints already exist on the backend and behave as documented in the implementation plan; this feature is primarily an interface and lifecycle-completion piece. Where small additions are required (leave, decline-invite, owner-deletes-empty-group), they are bounded extensions of the existing surface, not a redesign.
- Recipient resolution for invitations matches against existing platform profiles only; no SMS or email-based "invite to install" flow is in scope.
- Auto-netting is intentionally out of scope and will be delivered as a follow-up phase. Settlement of debts inside groups continues to use the existing per-debt mark-paid / confirm-payment flow.
- The 20-member cap is a soft product choice, not a technical limit. It is set high enough for realistic family or friend groups while keeping the visibility surface manageable.
- The default-on choice for the feature flag is acceptable because the navigation entry is unobtrusive and the feature carries no privacy risk for users who never use it.
- The "members can see each other's group-tagged debts" rule is established by the constitution and product rules; this spec does not re-litigate that decision and assumes users invited into a group understand they are agreeing to that visibility.
- The existing reminders and commitment-indicator behaviour for individual debts continues unchanged when a debt is tagged to a group.
- Notifications for group events (you have a new invite, you were added, your invite was accepted) reuse the existing in-app notification surface; no new channel is being introduced here.
