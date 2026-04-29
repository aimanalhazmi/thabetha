from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def utcnow() -> datetime:
    return datetime.now(UTC)


class AccountType(StrEnum):
    creditor = "creditor"
    debtor = "debtor"
    both = "both"
    business = "business"


class DebtStatus(StrEnum):
    """Canonical debt lifecycle states.

    See `docs/debt-lifecycle.md` for the full transition table.
    """

    pending_confirmation = "pending_confirmation"
    active = "active"
    edit_requested = "edit_requested"
    overdue = "overdue"
    payment_pending_confirmation = "payment_pending_confirmation"
    paid = "paid"
    cancelled = "cancelled"


class AttachmentType(StrEnum):
    invoice = "invoice"
    voice_note = "voice_note"
    other = "other"


class AttachmentRetentionState(StrEnum):
    available = "available"
    archived = "archived"
    retention_expired = "retention_expired"


class NotificationType(StrEnum):
    debt_created = "debt_created"
    debt_confirmed = "debt_confirmed"
    debt_edit_requested = "debt_edit_requested"
    debt_edit_approved = "debt_edit_approved"
    debt_edit_rejected = "debt_edit_rejected"
    debt_cancelled = "debt_cancelled"
    due_soon = "due_soon"
    overdue = "overdue"
    payment_requested = "payment_requested"
    payment_confirmed = "payment_confirmed"
    payment_failed = "payment_failed"
    group_invite = "group_invite"
    group_invite_accepted = "group_invite_accepted"
    group_ownership_transferred = "group_ownership_transferred"
    settlement_proposed = "settlement_proposed"
    settlement_reminder = "settlement_reminder"
    settlement_confirmed = "settlement_confirmed"
    settlement_rejected = "settlement_rejected"
    settlement_settled = "settlement_settled"
    settlement_failed = "settlement_failed"
    settlement_expired = "settlement_expired"


class PaymentIntentStatus(StrEnum):
    pending = "pending"
    succeeded = "succeeded"
    failed = "failed"
    expired = "expired"


class GroupMemberStatus(StrEnum):
    pending = "pending"
    accepted = "accepted"
    declined = "declined"
    left = "left"


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    phone: str | None = Field(default=None, min_length=5)
    email: str | None = None
    account_type: AccountType | None = None
    tax_id: str | None = None
    commercial_registration: str | None = None
    shop_name: str | None = None
    activity_type: str | None = None
    shop_location: str | None = None
    shop_description: str | None = None
    whatsapp_enabled: bool | None = None
    ai_enabled: bool | None = None
    groups_enabled: bool | None = None
    preferred_language: str | None = Field(default=None, pattern=r"^(ar|en)$")


class ProfileOut(BaseModel):
    id: str
    name: str
    phone: str
    email: str | None = None
    account_type: AccountType = AccountType.debtor
    tax_id: str | None = None
    commercial_registration: str | None = None
    shop_name: str | None = None
    activity_type: str | None = None
    shop_location: str | None = None
    shop_description: str | None = None
    whatsapp_enabled: bool = True
    ai_enabled: bool = False
    groups_enabled: bool = True
    commitment_score: int = Field(default=50, ge=0, le=100)
    preferred_language: str = "ar"
    created_at: datetime | None = None
    updated_at: datetime | None = None


class BusinessProfileIn(BaseModel):
    shop_name: str = Field(min_length=1)
    activity_type: str = Field(min_length=1)
    location: str = Field(min_length=1)
    description: str = Field(min_length=1)


class BusinessProfileOut(BusinessProfileIn):
    id: str
    owner_id: str
    created_at: datetime
    updated_at: datetime


class QRTokenOut(BaseModel):
    token: str
    user_id: str
    expires_at: datetime
    created_at: datetime


class DebtCreate(BaseModel):
    debtor_name: str = Field(min_length=1)
    debtor_id: str | None = None
    amount: Decimal = Field(gt=Decimal("0"))
    currency: str = Field(min_length=3, max_length=3)
    description: str = Field(min_length=1)
    due_date: date
    reminder_dates: list[date] = Field(default_factory=list)
    invoice_url: str | None = None
    notes: str | None = None
    group_id: str | None = None

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class DebtEditRequest(BaseModel):
    """Debtor-initiated request for the creditor to amend a pending debt."""

    message: str = Field(min_length=1)
    requested_amount: Decimal | None = Field(default=None, gt=Decimal("0"))
    requested_due_date: date | None = None
    requested_description: str | None = Field(default=None, min_length=1)


# Back-compat alias — old import name still resolves.
DebtChangeRequest = DebtEditRequest


class DebtEditApproval(BaseModel):
    """Creditor decision on a debtor's edit request — may override the debtor's proposal."""

    message: str = Field(min_length=1)
    amount: Decimal | None = Field(default=None, gt=Decimal("0"))
    due_date: date | None = None
    description: str | None = Field(default=None, min_length=1)


class ActionMessageIn(BaseModel):
    message: str | None = None


class DebtGroupTagUpdate(BaseModel):
    group_id: str | None = None


class DebtOut(BaseModel):
    id: str
    creditor_id: str
    debtor_id: str | None
    debtor_name: str
    amount: Decimal
    currency: str
    description: str
    due_date: date
    reminder_dates: list[date] = Field(default_factory=list)
    status: DebtStatus
    invoice_url: str | None = None
    notes: str | None = None
    group_id: str | None = None
    created_at: datetime
    updated_at: datetime
    confirmed_at: datetime | None = None
    paid_at: datetime | None = None


class DebtEventOut(BaseModel):
    id: str
    debt_id: str
    actor_id: str
    event_type: str
    message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class PaymentRequest(BaseModel):
    note: str | None = None


class PaymentConfirmationOut(BaseModel):
    id: str
    debt_id: str
    debtor_id: str
    creditor_id: str
    status: str
    note: str | None = None
    requested_at: datetime
    confirmed_at: datetime | None = None


class AttachmentOut(BaseModel):
    id: str
    debt_id: str
    uploader_id: str
    attachment_type: AttachmentType
    file_name: str
    content_type: str | None = None
    url: str
    url_expires_at: datetime | None = None
    retention_state: AttachmentRetentionState = AttachmentRetentionState.available
    retention_expires_at: datetime | None = None
    created_at: datetime


class WhatsAppDeliveryStatus(StrEnum):
    not_attempted = "not_attempted"
    attempted_unknown = "attempted_unknown"
    delivered = "delivered"
    failed = "failed"


def derive_whatsapp_status(
    *,
    whatsapp_attempted: bool,
    whatsapp_delivered: bool | None,
    whatsapp_failed_reason: str | None,
) -> WhatsAppDeliveryStatus:
    if not whatsapp_attempted:
        return WhatsAppDeliveryStatus.not_attempted
    if whatsapp_delivered is True:
        return WhatsAppDeliveryStatus.delivered
    if whatsapp_delivered is False or whatsapp_failed_reason is not None:
        return WhatsAppDeliveryStatus.failed
    return WhatsAppDeliveryStatus.attempted_unknown


class NotificationOut(BaseModel):
    """Debtor-facing (recipient) notification shape — no delivery columns (Q1)."""

    id: str
    user_id: str
    notification_type: NotificationType
    title: str
    body: str
    debt_id: str | None = None
    read_at: datetime | None = None
    whatsapp_attempted: bool = False
    created_at: datetime


class NotificationOutCreditor(NotificationOut):
    """Sender-facing notification shape — exposes WhatsApp delivery columns."""

    whatsapp_delivered: bool | None = None
    whatsapp_failed_reason: str | None = None
    whatsapp_status: WhatsAppDeliveryStatus = WhatsAppDeliveryStatus.not_attempted
    whatsapp_status_received_at: datetime | None = None


class WebhookReceiptOut(BaseModel):
    received: bool
    applied: int


class PaymentIntentOut(BaseModel):
    id: str
    debt_id: str
    provider: str
    provider_ref: str | None = None
    checkout_url: str | None = None
    status: PaymentIntentStatus
    amount: Decimal
    fee: Decimal
    net_amount: Decimal
    created_at: datetime
    expires_at: datetime
    completed_at: datetime | None = None


class PayOnlineOut(BaseModel):
    payment_intent_id: str
    checkout_url: str
    amount: Decimal
    fee: Decimal
    net_amount: Decimal
    currency: str
    expires_at: datetime


class NotificationPreferenceIn(BaseModel):
    merchant_id: str
    whatsapp_enabled: bool


class NotificationPreferenceOut(NotificationPreferenceIn):
    user_id: str
    updated_at: datetime


class CommitmentScoreEventOut(BaseModel):
    id: str
    user_id: str
    delta: int
    score_after: int
    reason: str
    debt_id: str | None = None
    reminder_date: date | None = None
    proposal_id: str | None = None
    created_at: datetime


# Back-compat alias.
TrustScoreEventOut = CommitmentScoreEventOut


class DebtorDashboardOut(BaseModel):
    total_current_debt: Decimal
    due_soon_count: int
    overdue_count: int
    creditors: list[str]
    commitment_score: int
    debts: list[DebtOut]


class CreditorDashboardOut(BaseModel):
    total_receivable: Decimal
    debtor_count: int
    active_count: int
    overdue_count: int
    paid_count: int
    best_customers: list[ProfileOut]
    alerts: list[str]
    debts: list[DebtOut]


class GroupCreate(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None


class GroupOut(BaseModel):
    id: str
    name: str
    description: str | None = None
    owner_id: str
    member_count: int = 1
    member_status: GroupMemberStatus | None = None  # the caller's membership status, when known (e.g. list endpoint).
    created_at: datetime
    updated_at: datetime | None = None


class GroupMemberOut(BaseModel):
    id: str
    group_id: str
    user_id: str
    status: GroupMemberStatus
    created_at: datetime
    accepted_at: datetime | None = None
    name: str | None = None
    commitment_score: int | None = None


class GroupDetailOut(GroupOut):
    members: list[GroupMemberOut] = Field(default_factory=list)
    pending_invites: list[GroupMemberOut] | None = None


class GroupInviteIn(BaseModel):
    user_id: str | None = None
    email: str | None = None
    phone: str | None = None

    @field_validator("user_id", "email", "phone", mode="before")
    @classmethod
    def _empty_to_none(cls, value: str | None) -> str | None:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def _exactly_one_identifier(self) -> "GroupInviteIn":
        present = sum(x is not None for x in (self.user_id, self.email, self.phone))
        if present != 1:
            raise ValueError("Provide exactly one of user_id, email, phone.")
        return self


class GroupRenameIn(BaseModel):
    name: str = Field(min_length=1)


class GroupOwnershipTransferIn(BaseModel):
    new_owner_user_id: str = Field(min_length=1)


class SettlementCreate(BaseModel):
    debtor_id: str = Field(min_length=1)
    amount: Decimal = Field(gt=Decimal("0"))
    currency: str = Field(min_length=3, max_length=3)
    note: str | None = None

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class SettlementOut(BaseModel):
    id: str
    group_id: str
    payer_id: str
    debtor_id: str
    amount: Decimal
    currency: str
    note: str | None = None
    created_at: datetime


# ── Group auto-netting (Phase 9 / UC9 part 2) ──────────────────────────────


class SettlementProposalStatus(StrEnum):
    open = "open"
    rejected = "rejected"
    expired = "expired"
    settlement_failed = "settlement_failed"
    settled = "settled"


class SettlementConfirmationStatus(StrEnum):
    pending = "pending"
    confirmed = "confirmed"
    rejected = "rejected"


class ProposedTransferOut(BaseModel):
    payer_id: str
    receiver_id: str
    amount: Decimal


class SnapshotDebtOut(BaseModel):
    debt_id: str
    debtor_id: str
    creditor_id: str
    amount: Decimal


class SettlementConfirmationOut(BaseModel):
    user_id: str
    status: SettlementConfirmationStatus
    responded_at: datetime | None = None


class SettlementProposalCreate(BaseModel):
    """Empty body — group_id is in the path. Server snapshots and computes."""

    model_config = ConfigDict(extra="forbid")


class SettlementConfirmationIn(BaseModel):
    """Empty body — action is in the URL verb (`/confirm` or `/reject`)."""

    model_config = ConfigDict(extra="forbid")


class SettlementProposalOut(BaseModel):
    id: str
    group_id: str
    proposed_by: str
    currency: str
    transfers: list[ProposedTransferOut]
    snapshot: list[SnapshotDebtOut] | None = None
    confirmations: list[SettlementConfirmationOut]
    status: SettlementProposalStatus
    failure_reason: str | None = None
    created_at: datetime
    expires_at: datetime
    resolved_at: datetime | None = None


class VoiceDebtDraftRequest(BaseModel):
    transcript: str = Field(min_length=1)
    default_currency: str = Field(default="SAR", min_length=3, max_length=3)


class VoiceDebtDraftOut(BaseModel):
    debtor_name: str | None = None
    amount: Decimal | None = None
    currency: str
    description: str | None = None
    due_date: date | None = None
    confidence: float = Field(ge=0, le=1)
    raw_transcript: str


class MerchantChatRequest(BaseModel):
    message: str = Field(min_length=1)


class MerchantChatOut(BaseModel):
    answer: str
    facts: dict[str, Any]


class SignUpRequest(BaseModel):
    name: str = Field(min_length=1)
    phone: str = Field(min_length=5)
    email: str = Field(min_length=5)
    password: str = Field(min_length=6)
    account_type: AccountType = AccountType.debtor
    tax_id: str | None = None
    commercial_registration: str | None = None


class SignInRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class MessageOut(BaseModel):
    message: str


class HealthOut(BaseModel):
    status: str
    service: str
    environment: str
    supabase_connected: bool

    model_config = ConfigDict(extra="forbid")
