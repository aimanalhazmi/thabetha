from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def utcnow() -> datetime:
    return datetime.now(UTC)


class AccountType(StrEnum):
    individual = "individual"
    business = "business"


class DebtStatus(StrEnum):
    pending_confirmation = "pending_confirmation"
    active = "active"
    overdue = "overdue"
    payment_pending_confirmation = "payment_pending_confirmation"
    paid = "paid"
    rejected = "rejected"
    change_requested = "change_requested"


class AttachmentType(StrEnum):
    invoice = "invoice"
    voice_note = "voice_note"
    other = "other"


class NotificationType(StrEnum):
    debt_created = "debt_created"
    debt_confirmed = "debt_confirmed"
    debt_rejected = "debt_rejected"
    debt_change_requested = "debt_change_requested"
    due_soon = "due_soon"
    overdue = "overdue"
    payment_requested = "payment_requested"
    payment_confirmed = "payment_confirmed"


class GroupMemberStatus(StrEnum):
    pending = "pending"
    accepted = "accepted"


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    phone: str | None = Field(default=None, min_length=5)
    email: str | None = None
    account_type: AccountType | None = None
    tax_id: str | None = None
    commercial_registration: str | None = None
    whatsapp_enabled: bool | None = None
    ai_enabled: bool | None = None


class ProfileOut(BaseModel):
    id: str
    name: str
    phone: str
    email: str | None = None
    account_type: AccountType = AccountType.individual
    tax_id: str | None = None
    commercial_registration: str | None = None
    whatsapp_enabled: bool = True
    ai_enabled: bool = False
    trust_score: int = Field(default=50, ge=0, le=100)
    created_at: datetime
    updated_at: datetime


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
    invoice_url: str | None = None
    notes: str | None = None
    group_id: str | None = None

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class DebtChangeRequest(BaseModel):
    message: str = Field(min_length=1)
    requested_amount: Decimal | None = Field(default=None, gt=Decimal("0"))
    requested_due_date: date | None = None


class ActionMessageIn(BaseModel):
    message: str | None = None


class DebtOut(BaseModel):
    id: str
    creditor_id: str
    debtor_id: str | None
    debtor_name: str
    amount: Decimal
    currency: str
    description: str
    due_date: date
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
    created_at: datetime


class NotificationOut(BaseModel):
    id: str
    user_id: str
    notification_type: NotificationType
    title: str
    body: str
    debt_id: str | None = None
    read_at: datetime | None = None
    whatsapp_attempted: bool = False
    created_at: datetime


class NotificationPreferenceIn(BaseModel):
    merchant_id: str
    whatsapp_enabled: bool


class NotificationPreferenceOut(NotificationPreferenceIn):
    user_id: str
    updated_at: datetime


class TrustScoreEventOut(BaseModel):
    id: str
    user_id: str
    delta: int
    score_after: int
    reason: str
    debt_id: str | None = None
    created_at: datetime


class DebtorDashboardOut(BaseModel):
    total_current_debt: Decimal
    due_soon_count: int
    overdue_count: int
    creditors: list[str]
    trust_score: int
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
    created_at: datetime


class GroupMemberOut(BaseModel):
    id: str
    group_id: str
    user_id: str
    status: GroupMemberStatus
    created_at: datetime
    accepted_at: datetime | None = None


class GroupInviteIn(BaseModel):
    user_id: str = Field(min_length=1)


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


class MessageOut(BaseModel):
    message: str


class HealthOut(BaseModel):
    status: str
    service: str
    environment: str

    model_config = ConfigDict(extra="forbid")
