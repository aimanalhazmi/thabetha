"""Abstract repository interface.

All routers depend on this interface, not on a specific implementation.
Currently two implementations exist: InMemoryRepository (tests/demo) and
PostgresRepository (local Supabase / production).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal

from fastapi import UploadFile

from app.core.security import AuthenticatedUser
from app.schemas.domain import (
    AttachmentOut,
    AttachmentType,
    BusinessProfileIn,
    BusinessProfileOut,
    CommitmentScoreEventOut,
    CreditorDashboardOut,
    DebtChangeRequest,
    DebtCreate,
    DebtEditApproval,
    DebtEventOut,
    DebtorDashboardOut,
    DebtOut,
    GroupCreate,
    GroupInviteIn,
    GroupMemberOut,
    GroupOut,
    NotificationOut,
    NotificationPreferenceIn,
    NotificationPreferenceOut,
    PaymentConfirmationOut,
    PaymentIntentOut,
    PaymentRequest,
    PayOnlineOut,
    ProfileOut,
    ProfileUpdate,
    SettlementCreate,
    SettlementOut,
)
from app.services.whatsapp.provider import SendResult, StatusUpdate


class Repository(ABC):
    # ── Profiles ──────────────────────────────────────────────────────

    @abstractmethod
    def ensure_profile(self, user: AuthenticatedUser) -> ProfileOut: ...

    @abstractmethod
    def get_profile(self, user_id: str) -> ProfileOut: ...

    @abstractmethod
    def update_profile(self, user: AuthenticatedUser, payload: ProfileUpdate) -> ProfileOut: ...

    @abstractmethod
    def upsert_business_profile(self, owner_id: str, payload: BusinessProfileIn) -> BusinessProfileOut: ...

    @abstractmethod
    def current_business_profile(self, owner_id: str) -> BusinessProfileOut | None: ...

    # ── QR tokens ─────────────────────────────────────────────────────

    @abstractmethod
    def rotate_qr_token(self, user_id: str, ttl_minutes: int = 10) -> dict[str, object]: ...

    @abstractmethod
    def current_qr_token(self, user_id: str) -> dict[str, object]: ...

    @abstractmethod
    def resolve_qr_token(self, token: str) -> ProfileOut: ...

    # ── Debts ─────────────────────────────────────────────────────────

    @abstractmethod
    def create_debt(self, creditor_id: str, payload: DebtCreate) -> DebtOut: ...

    @abstractmethod
    def list_debts_for_user(self, user_id: str) -> list[DebtOut]: ...

    @abstractmethod
    def get_authorized_debt(self, user_id: str, debt_id: str) -> DebtOut: ...

    @abstractmethod
    def accept_debt(self, user_id: str, debt_id: str) -> DebtOut: ...

    @abstractmethod
    def request_debt_change(self, user_id: str, debt_id: str, payload: DebtChangeRequest) -> DebtOut: ...

    @abstractmethod
    def approve_edit_request(self, user_id: str, debt_id: str, payload: DebtEditApproval) -> DebtOut: ...

    @abstractmethod
    def reject_edit_request(self, user_id: str, debt_id: str, message: str | None = None) -> DebtOut: ...

    @abstractmethod
    def mark_paid(self, user_id: str, debt_id: str, payload: PaymentRequest) -> PaymentConfirmationOut: ...

    @abstractmethod
    def confirm_payment(self, user_id: str, debt_id: str) -> DebtOut: ...

    @abstractmethod
    def cancel_debt(self, user_id: str, debt_id: str, message: str | None = None) -> DebtOut: ...

    # ── Events & attachments ──────────────────────────────────────────

    @abstractmethod
    def list_events(self, user_id: str, debt_id: str) -> list[DebtEventOut]: ...

    # Attachment implementations must only expose files to users who can view
    # the parent debt. Uploads should persist a canonical storage path, emit an
    # `attachment_uploaded` debt event, and return a URL that expires after the
    # configured receipt TTL. Paid debts move receipt metadata to `archived`
    # until the configured retention window ends; expired attachments should not
    # be returned from user-facing lists.
    @abstractmethod
    async def add_attachment(self, user_id: str, debt_id: str, attachment_type: AttachmentType, file: UploadFile) -> AttachmentOut: ...

    @abstractmethod
    def list_attachments(self, user_id: str, debt_id: str) -> list[AttachmentOut]: ...

    # ── Dashboards ────────────────────────────────────────────────────

    @abstractmethod
    def debtor_dashboard(self, user_id: str) -> DebtorDashboardOut: ...

    @abstractmethod
    def creditor_dashboard(self, user_id: str) -> CreditorDashboardOut: ...

    # ── Notifications ─────────────────────────────────────────────────

    @abstractmethod
    def list_notifications(self, user_id: str) -> list[NotificationOut]: ...

    @abstractmethod
    def read_notification(self, user_id: str, notification_id: str) -> NotificationOut: ...

    @abstractmethod
    def set_notification_preference(self, user_id: str, payload: NotificationPreferenceIn) -> NotificationPreferenceOut: ...

    @abstractmethod
    def list_commitment_score_events(self, user_id: str) -> list[CommitmentScoreEventOut]: ...

    # ── WhatsApp delivery state ───────────────────────────────────────

    @abstractmethod
    def mark_whatsapp_attempted(self, notification_id: str, result: SendResult) -> None: ...

    @abstractmethod
    def apply_whatsapp_status(self, update: StatusUpdate) -> bool: ...

    @abstractmethod
    def get_whatsapp_state(self, notification_id: str) -> dict[str, object] | None: ...

    @abstractmethod
    def get_merchant_notification_preference(
        self, creditor_id: str, debtor_id: str
    ) -> NotificationPreferenceOut | None: ...

    # ── Groups ────────────────────────────────────────────────────────

    @abstractmethod
    def create_group(self, owner_id: str, payload: GroupCreate) -> GroupOut: ...

    @abstractmethod
    def list_groups(self, user_id: str) -> list[GroupOut]: ...

    @abstractmethod
    def invite_group_member(self, actor_id: str, group_id: str, payload: GroupInviteIn) -> GroupMemberOut: ...

    @abstractmethod
    def accept_group_invite(self, user_id: str, group_id: str) -> GroupMemberOut: ...

    @abstractmethod
    def group_debts(self, user_id: str, group_id: str) -> list[DebtOut]: ...

    @abstractmethod
    def create_settlement(self, payer_id: str, group_id: str, payload: SettlementCreate) -> SettlementOut: ...

    # ── AI / analytics ────────────────────────────────────────────────

    @abstractmethod
    def merchant_facts(self, user_id: str) -> dict[str, object]: ...

    # ── Payment intents ───────────────────────────────────────────────

    @abstractmethod
    def create_payment_intent(
        self,
        debt_id: str,
        provider: str,
        amount: Decimal,
        fee: Decimal,
        checkout_url: str,
        provider_ref: str | None,
        expires_at: datetime,
    ) -> PaymentIntentOut: ...

    @abstractmethod
    def create_payment_intent_and_transition(
        self,
        user_id: str,
        debt_id: str,
        checkout_url: str,
        provider_ref: str | None,
        provider: str,
        amount: Decimal,
        fee: Decimal,
        expires_at: datetime,
    ) -> PayOnlineOut:
        """Debtor-only. Validates state, blocks on pending intent, creates intent record,
        transitions active/overdue → payment_pending_confirmation, writes debt_events row.
        Provider calls (create_checkout, calculate_fee) happen at the handler layer."""

    @abstractmethod
    def get_active_payment_intent(self, debt_id: str) -> PaymentIntentOut | None:
        """Returns the non-expired pending intent for a debt; lazily marks expired ones."""

    @abstractmethod
    def get_payment_intent_by_ref(self, provider_ref: str) -> PaymentIntentOut | None: ...

    @abstractmethod
    def update_payment_intent_status(
        self, intent_id: str, status: str, completed_at: datetime | None = None
    ) -> None: ...

    @abstractmethod
    def confirm_payment_gateway(self, provider_ref: str) -> DebtOut:
        """Idempotent. Transitions payment_pending_confirmation → paid, writes
        debt_events and commitment score identical to confirm_payment(). No-ops if
        debt already paid."""

    @abstractmethod
    def record_payment_failure(self, provider_ref: str) -> None:
        """Marks the payment intent failed and writes a payment_failed debt event.
        Does NOT change the debt state — debtor may retry (FR-013)."""
