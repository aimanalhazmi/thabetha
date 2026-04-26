"""Abstract repository interface.

All routers depend on this interface, not on a specific implementation.
Currently two implementations exist: InMemoryRepository (tests/demo) and
PostgresRepository (local Supabase / production).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

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
    PaymentRequest,
    ProfileOut,
    ProfileUpdate,
    SettlementCreate,
    SettlementOut,
)


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
    def reject_debt(self, user_id: str, debt_id: str, message: str | None = None) -> DebtOut: ...

    @abstractmethod
    def request_debt_change(self, user_id: str, debt_id: str, payload: DebtChangeRequest) -> DebtOut: ...

    @abstractmethod
    def mark_paid(self, user_id: str, debt_id: str, payload: PaymentRequest) -> PaymentConfirmationOut: ...

    @abstractmethod
    def confirm_payment(self, user_id: str, debt_id: str) -> DebtOut: ...

    @abstractmethod
    def cancel_debt(self, user_id: str, debt_id: str, message: str | None = None) -> DebtOut: ...

    # ── Events & attachments ──────────────────────────────────────────

    @abstractmethod
    def list_events(self, user_id: str, debt_id: str) -> list[DebtEventOut]: ...

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
