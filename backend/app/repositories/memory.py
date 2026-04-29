from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from threading import RLock
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status

from app.core.security import AuthenticatedUser
from app.repositories.attachment_retention import apply_attachment_access_metadata, retention_for_debt
from app.repositories.base import Repository
from app.repositories.local_receipt_store import save_local_receipt
from app.schemas.domain import (
    AccountType,
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
    DebtStatus,
    GroupCreate,
    GroupDetailOut,
    GroupInviteIn,
    GroupMemberOut,
    GroupMemberStatus,
    GroupOut,
    GroupOwnershipTransferIn,
    GroupRenameIn,
    NotificationOut,
    NotificationPreferenceIn,
    NotificationPreferenceOut,
    NotificationType,
    PaymentConfirmationOut,
    PaymentIntentOut,
    PaymentIntentStatus,
    PaymentRequest,
    PayOnlineOut,
    ProfileOut,
    ProfileUpdate,
    ProposedTransferOut,
    SettlementConfirmationOut,
    SettlementConfirmationStatus,
    SettlementCreate,
    SettlementOut,
    SettlementProposalOut,
    SettlementProposalStatus,
    SnapshotDebtOut,
    utcnow,
)
from app.services.netting import SnapshotDebt as _NetSnapshotDebt
from app.services.netting import compute_transfers as _compute_transfers
from app.services.whatsapp.provider import SendOutcome, SendResult, StatusUpdate


def _late_penalty(missed_count: int) -> int:
    """Late-payment / missed-reminder commitment-indicator penalty.

    Base penalty is -2, doubled per already-missed reminder: -2, -4, -8, -16, ...
    """
    return -2 * (2 ** missed_count)


class InMemoryRepository(Repository):
    """A local repository for demo/test use.

    Supabase is the production persistence target. This repository keeps the API
    runnable for development, CI, and hackathon demos before credentials exist.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self.profiles: dict[str, ProfileOut] = {}
            self.business_profiles: dict[str, BusinessProfileOut] = {}
            self.qr_tokens: dict[str, dict[str, object]] = {}
            self.debts: dict[str, DebtOut] = {}
            self.debt_events: list[DebtEventOut] = []
            self.payment_confirmations: dict[str, PaymentConfirmationOut] = {}
            self.attachments: list[AttachmentOut] = []
            self.notifications: list[NotificationOut] = []
            # WhatsApp delivery state per notification id (T007–T008).
            # Keys: attempted (bool), delivered (bool|None), provider_ref (str|None),
            #       failed_reason (str|None), status_received_at (datetime|None).
            self._whatsapp_state: dict[str, dict[str, object]] = {}
            self.notification_preferences: dict[tuple[str, str], NotificationPreferenceOut] = {}
            self.commitment_score_events: list[CommitmentScoreEventOut] = []
            self.groups: dict[str, GroupOut] = {}
            self.group_members: list[GroupMemberOut] = []
            self.settlements: list[SettlementOut] = []
            # Group settlement proposals (UC9 part 2). Each proposal stores its
            # own snapshot, transfer list, status, expiry, and confirmation
            # roster. Confirmations are keyed (proposal_id, user_id).
            self.settlement_proposals: dict[str, dict[str, object]] = {}
            self.settlement_confirmations: dict[tuple[str, str], dict[str, object]] = {}
            self._overdue_penalties: set[str] = set()
            self._edit_request_payloads: dict[str, dict[str, object]] = {}
            self._original_terms: dict[str, dict[str, object]] = {}
            self.payment_intents: dict[str, PaymentIntentOut] = {}

    def ensure_profile(self, user: AuthenticatedUser) -> ProfileOut:
        with self._lock:
            existing = self.profiles.get(user.id)
            if existing:
                return existing
            now = utcnow()
            profile = ProfileOut(
                id=user.id,
                name=user.name or user.email or user.phone or f"User {user.id[:6]}",
                phone=user.phone or "+000000000",
                email=user.email,
                account_type=AccountType.debtor,
                created_at=now,
                updated_at=now,
            )
            self.profiles[user.id] = profile
            return profile

    def get_profile(self, user_id: str) -> ProfileOut:
        profile = self.profiles.get(user_id)
        if profile is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
        return profile

    def update_profile(self, user: AuthenticatedUser, payload: ProfileUpdate) -> ProfileOut:
        with self._lock:
            profile = self.ensure_profile(user)
            data = payload.model_dump(exclude_unset=True)
            if not data:
                return profile
            now = utcnow()
            shop_keys = {"shop_name", "activity_type", "shop_location", "shop_description"}
            shop_data = {k: data[k] for k in shop_keys if k in data}
            if shop_data:
                existing = self.business_profiles.get(user.id)
                merged = {
                    "shop_name": shop_data.get("shop_name", existing.shop_name if existing else ""),
                    "activity_type": shop_data.get("activity_type", existing.activity_type if existing else ""),
                    "location": shop_data.get("shop_location", existing.location if existing else ""),
                    "description": shop_data.get("shop_description", existing.description if existing else ""),
                }
                # BusinessProfileIn requires min_length=1 on all four fields. Only mirror to
                # business_profiles once all four are populated; partial state stays on the profile.
                if all(v for v in merged.values()):
                    self.business_profiles[user.id] = BusinessProfileOut(
                        id=existing.id if existing else str(uuid4()),
                        owner_id=user.id,
                        **merged,
                        created_at=existing.created_at if existing else now,
                        updated_at=now,
                    )
            profile = profile.model_copy(update={**data, "updated_at": now})
            self.profiles[user.id] = profile
            return profile

    def upsert_business_profile(self, owner_id: str, payload: BusinessProfileIn) -> BusinessProfileOut:
        with self._lock:
            now = utcnow()
            existing = self.business_profiles.get(owner_id)
            business = BusinessProfileOut(
                id=existing.id if existing else str(uuid4()),
                owner_id=owner_id,
                **payload.model_dump(),
                created_at=existing.created_at if existing else now,
                updated_at=now,
            )
            self.business_profiles[owner_id] = business
            current = self.get_profile(owner_id)
            if current.account_type == AccountType.debtor:
                current = current.model_copy(update={"account_type": AccountType.creditor})
            self.profiles[owner_id] = current.model_copy(update={"updated_at": now})
            return business

    def current_business_profile(self, owner_id: str) -> BusinessProfileOut | None:
        return self.business_profiles.get(owner_id)

    def rotate_qr_token(self, user_id: str, ttl_minutes: int = 10) -> dict[str, object]:
        with self._lock:
            token = str(uuid4())
            now = utcnow()
            record: dict[str, object] = {
                "token": token,
                "user_id": user_id,
                "expires_at": now + timedelta(minutes=ttl_minutes),
                "created_at": now,
            }
            self.qr_tokens[token] = record
            return record

    def current_qr_token(self, user_id: str) -> dict[str, object]:
        with self._lock:
            now = utcnow()
            tokens = [record for record in self.qr_tokens.values() if record["user_id"] == user_id and record["expires_at"] > now]
            if tokens:
                return max(tokens, key=lambda record: record["created_at"])
            return self.rotate_qr_token(user_id)

    def resolve_qr_token(self, token: str) -> ProfileOut:
        record = self.qr_tokens.get(token)
        if not record or record["expires_at"] <= utcnow():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="QR token is invalid or expired")
        return self.get_profile(str(record["user_id"]))

    def create_debt(self, creditor_id: str, payload: DebtCreate) -> DebtOut:
        with self._lock:
            self._refresh_overdue()
            if payload.group_id:
                if not payload.debtor_id:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "DebtorRequired", "message": "Group tag requires a registered debtor."})
                shared = {g.id for g in self.shared_accepted_groups(creditor_id, payload.debtor_id)}
                if payload.group_id not in shared:
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "NotInSharedGroup", "message": "Both parties must be accepted members of the group."})
            now = utcnow()
            debt = DebtOut(
                id=str(uuid4()),
                creditor_id=creditor_id,
                debtor_id=payload.debtor_id,
                debtor_name=payload.debtor_name,
                amount=payload.amount,
                currency=payload.currency,
                description=payload.description,
                due_date=payload.due_date,
                reminder_dates=sorted(set(payload.reminder_dates)),
                status=DebtStatus.pending_confirmation,
                invoice_url=payload.invoice_url,
                notes=payload.notes,
                group_id=payload.group_id,
                created_at=now,
                updated_at=now,
            )
            self.debts[debt.id] = debt
            self._add_event(debt.id, creditor_id, "debt_created", "Debt created and awaiting debtor confirmation")
            if payload.debtor_id:
                self._notify(
                    payload.debtor_id,
                    NotificationType.debt_created,
                    "New debt requires confirmation",
                    f"{payload.debtor_name}, confirm {payload.amount} {payload.currency}: {payload.description}",
                    debt.id,
                    merchant_id=creditor_id,
                )
            return debt

    def list_debts_for_user(self, user_id: str) -> list[DebtOut]:
        self._refresh_overdue()
        group_ids = self._accepted_group_ids(user_id)
        member_ids = self._accepted_group_member_ids(group_ids)
        return [
            debt
            for debt in self.debts.values()
            if debt.creditor_id == user_id
            or debt.debtor_id == user_id
            or (debt.group_id in group_ids and (debt.creditor_id in member_ids or debt.debtor_id in member_ids))
        ]

    def get_authorized_debt(self, user_id: str, debt_id: str) -> DebtOut:
        self._refresh_overdue()
        debt = self.debts.get(debt_id)
        if not debt:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Debt not found")
        if self._can_view_debt(user_id, debt):
            return debt
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot access this debt")

    def accept_debt(self, user_id: str, debt_id: str) -> DebtOut:
        with self._lock:
            debt = self.get_authorized_debt(user_id, debt_id)
            if debt.debtor_id != user_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the debtor can accept this debt")
            if debt.status not in {DebtStatus.pending_confirmation, DebtStatus.edit_requested}:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Debt cannot be accepted from its current state")
            debt = debt.model_copy(update={"status": DebtStatus.active, "confirmed_at": utcnow(), "updated_at": utcnow()})
            self.debts[debt_id] = debt
            self._add_event(debt.id, user_id, "debt_confirmed", "Debtor accepted the debt")
            self._notify(debt.creditor_id, NotificationType.debt_confirmed, "Debt accepted", f"{debt.debtor_name} accepted {debt.amount} {debt.currency}", debt.id)
            return debt

    def request_debt_change(self, user_id: str, debt_id: str, payload: DebtChangeRequest) -> DebtOut:
        with self._lock:
            debt = self.get_authorized_debt(user_id, debt_id)
            if debt.debtor_id != user_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the debtor can request changes")
            if debt.status != DebtStatus.pending_confirmation:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only pending debts can be changed")
            debt = debt.model_copy(update={"status": DebtStatus.edit_requested, "updated_at": utcnow()})
            self.debts[debt_id] = debt
            self._edit_request_payloads[debt_id] = payload.model_dump(exclude_none=True)
            self._add_event(debt.id, user_id, "debt_edit_requested", payload.message, payload.model_dump(exclude_none=True))
            self._notify(debt.creditor_id, NotificationType.debt_edit_requested, "Debt change requested", payload.message, debt.id)
            return debt

    def approve_edit_request(self, user_id: str, debt_id: str, payload: DebtEditApproval) -> DebtOut:
        with self._lock:
            debt = self.get_authorized_debt(user_id, debt_id)
            if debt.creditor_id != user_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the creditor can decide on an edit request")
            if debt.status != DebtStatus.edit_requested:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No edit request awaits a decision")
            requested = self._edit_request_payloads.pop(debt_id, {})

            update: dict[str, object] = {"status": DebtStatus.pending_confirmation, "updated_at": utcnow()}
            if payload.amount is not None:
                update["amount"] = payload.amount
            elif requested.get("requested_amount") is not None:
                update["amount"] = Decimal(str(requested["requested_amount"]))
            if payload.due_date is not None:
                update["due_date"] = payload.due_date
            elif requested.get("requested_due_date") is not None:
                value = requested["requested_due_date"]
                update["due_date"] = value if isinstance(value, date) else date.fromisoformat(str(value))
            if payload.description is not None:
                update["description"] = payload.description
            elif isinstance(requested.get("requested_description"), str):
                update["description"] = requested["requested_description"]

            debt = debt.model_copy(update=update)
            self.debts[debt_id] = debt
            self._add_event(debt.id, user_id, "debt_edit_approved", payload.message, {"requested": requested})
            if debt.debtor_id:
                self._notify(
                    debt.debtor_id,
                    NotificationType.debt_edit_approved,
                    "Edit approved",
                    payload.message,
                    debt.id,
                    merchant_id=debt.creditor_id,
                )
            return debt

    def reject_edit_request(self, user_id: str, debt_id: str, message: str | None = None) -> DebtOut:
        with self._lock:
            debt = self.get_authorized_debt(user_id, debt_id)
            if debt.creditor_id != user_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the creditor can decide on an edit request")
            if debt.status != DebtStatus.edit_requested:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No edit request awaits a decision")
            self._edit_request_payloads.pop(debt_id, None)
            debt = debt.model_copy(update={"status": DebtStatus.pending_confirmation, "updated_at": utcnow()})
            self.debts[debt_id] = debt
            self._add_event(debt.id, user_id, "debt_edit_rejected", message)
            if debt.debtor_id:
                self._notify(
                    debt.debtor_id,
                    NotificationType.debt_edit_rejected,
                    "Edit rejected",
                    message or "Creditor declined your edit; original terms stand",
                    debt.id,
                    merchant_id=debt.creditor_id,
                )
            return debt

    def mark_paid(self, user_id: str, debt_id: str, payload: PaymentRequest) -> PaymentConfirmationOut:
        with self._lock:
            debt = self.get_authorized_debt(user_id, debt_id)
            if debt.debtor_id != user_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the debtor can mark the debt paid")
            if debt.status not in {DebtStatus.active, DebtStatus.overdue}:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Debt must be active or overdue")
            now = utcnow()
            debt = debt.model_copy(update={"status": DebtStatus.payment_pending_confirmation, "updated_at": now})
            self.debts[debt_id] = debt
            confirmation = PaymentConfirmationOut(
                id=str(uuid4()),
                debt_id=debt.id,
                debtor_id=user_id,
                creditor_id=debt.creditor_id,
                status="pending_creditor_confirmation",
                note=payload.note,
                requested_at=now,
            )
            self.payment_confirmations[debt.id] = confirmation
            self._add_event(debt.id, user_id, "payment_requested", payload.note)
            self._notify(debt.creditor_id, NotificationType.payment_requested, "Payment confirmation requested", f"{debt.debtor_name} marked the debt as paid", debt.id)
            return confirmation

    def confirm_payment(self, user_id: str, debt_id: str) -> DebtOut:
        with self._lock:
            debt = self.get_authorized_debt(user_id, debt_id)
            if debt.creditor_id != user_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the creditor can confirm payment")
            if debt.status != DebtStatus.payment_pending_confirmation:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Payment is not awaiting confirmation")
            now = utcnow()
            debt = debt.model_copy(update={"status": DebtStatus.paid, "paid_at": now, "updated_at": now})
            self.debts[debt_id] = debt
            confirmation = self.payment_confirmations.get(debt.id)
            if confirmation:
                self.payment_confirmations[debt.id] = confirmation.model_copy(update={"status": "confirmed", "confirmed_at": now})
            self._add_event(debt.id, user_id, "payment_confirmed", "Creditor confirmed receiving payment")
            if debt.debtor_id:
                today = now.date()
                if today < debt.due_date:
                    self._change_commitment_score(debt.debtor_id, 3, "paid_early", debt.id)
                elif today == debt.due_date:
                    self._change_commitment_score(debt.debtor_id, 1, "paid_on_time", debt.id)
                else:
                    missed = sum(
                        1 for ev in self.commitment_score_events
                        if ev.debt_id == debt.id and ev.reason == "missed_reminder"
                    )
                    self._change_commitment_score(debt.debtor_id, _late_penalty(missed), "paid_late", debt.id)
                self._notify(debt.debtor_id, NotificationType.payment_confirmed, "Payment confirmed", f"{debt.amount} {debt.currency} was confirmed as paid", debt.id)
            return debt

    def cancel_debt(self, user_id: str, debt_id: str, message: str | None = None) -> DebtOut:
        with self._lock:
            debt = self.get_authorized_debt(user_id, debt_id)
            if debt.creditor_id != user_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the creditor can cancel this debt")
            cancellable = {DebtStatus.pending_confirmation, DebtStatus.edit_requested}
            if debt.status not in cancellable:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Active or paid debts cannot be cancelled")
            debt = debt.model_copy(update={"status": DebtStatus.cancelled, "updated_at": utcnow()})
            self.debts[debt_id] = debt
            self._add_event(debt.id, user_id, "debt_cancelled", message)
            if debt.debtor_id:
                self._notify(debt.debtor_id, NotificationType.debt_cancelled, "Debt cancelled", message or f"{debt.amount} {debt.currency} cancelled by creditor", debt.id)
            return debt

    def list_events(self, user_id: str, debt_id: str) -> list[DebtEventOut]:
        self.get_authorized_debt(user_id, debt_id)
        return [event for event in self.debt_events if event.debt_id == debt_id]

    async def add_attachment(self, user_id: str, debt_id: str, attachment_type: AttachmentType, file: UploadFile) -> AttachmentOut:
        with self._lock:
            debt = self.get_authorized_debt(user_id, debt_id)
            file_name = file.filename or "attachment"
            storage_id = uuid4()
            content = await file.read()
            storage_path = f"{debt_id}/{storage_id}-{file_name}"
            attachment = AttachmentOut(
                id=str(uuid4()),
                debt_id=debt_id,
                uploader_id=user_id,
                attachment_type=attachment_type,
                file_name=file_name,
                content_type=file.content_type,
                url=save_local_receipt(storage_path, content, file.content_type, file_name),
                created_at=utcnow(),
            )
            attachment = apply_attachment_access_metadata(attachment, debt)
            self.attachments.append(attachment)
            self._add_event(
                debt_id,
                user_id,
                "attachment_uploaded",
                "Receipt attachment uploaded",
                {
                    "attachment_id": attachment.id,
                    "attachment_type": attachment_type.value,
                    "file_name": file_name,
                    "content_type": file.content_type,
                },
            )
            await file.close()
            return attachment

    def list_attachments(self, user_id: str, debt_id: str) -> list[AttachmentOut]:
        debt = self.get_authorized_debt(user_id, debt_id)
        retention_state, _ = retention_for_debt(debt)
        if retention_state.value == "retention_expired":
            return []
        return [
            apply_attachment_access_metadata(attachment, debt)
            for attachment in self.attachments
            if attachment.debt_id == debt_id
        ]

    def debtor_dashboard(self, user_id: str) -> DebtorDashboardOut:
        self._refresh_overdue()
        profile = self.get_profile(user_id)
        debts = [debt for debt in self.list_debts_for_user(user_id) if debt.debtor_id == user_id]
        current = [debt for debt in debts if debt.status in {DebtStatus.active, DebtStatus.overdue, DebtStatus.payment_pending_confirmation}]
        total = sum((debt.amount for debt in current), Decimal("0"))
        today = date.today()
        due_soon = [debt for debt in current if today <= debt.due_date <= today + timedelta(days=3)]
        creditors = sorted({debt.creditor_id for debt in current})
        return DebtorDashboardOut(
            total_current_debt=total,
            due_soon_count=len(due_soon),
            overdue_count=len([debt for debt in current if debt.status == DebtStatus.overdue]),
            creditors=creditors,
            commitment_score=profile.commitment_score,
            debts=debts,
        )

    def creditor_dashboard(self, user_id: str) -> CreditorDashboardOut:
        self._refresh_overdue()
        debts = [debt for debt in self.list_debts_for_user(user_id) if debt.creditor_id == user_id]
        receivable = [debt for debt in debts if debt.status in {DebtStatus.active, DebtStatus.overdue, DebtStatus.payment_pending_confirmation}]
        total = sum((debt.amount for debt in receivable), Decimal("0"))
        debtor_ids = {debt.debtor_id for debt in debts if debt.debtor_id}
        best_customers = sorted(
            [self.profiles[debtor_id] for debtor_id in debtor_ids if debtor_id in self.profiles],
            key=lambda profile: profile.commitment_score,
            reverse=True,
        )[:5]
        overdue = [debt for debt in debts if debt.status == DebtStatus.overdue]
        alerts = [f"{debt.debtor_name} is overdue on {debt.amount} {debt.currency}" for debt in overdue]
        return CreditorDashboardOut(
            total_receivable=total,
            debtor_count=len(debtor_ids),
            active_count=len([debt for debt in debts if debt.status == DebtStatus.active]),
            overdue_count=len(overdue),
            paid_count=len([debt for debt in debts if debt.status == DebtStatus.paid]),
            best_customers=best_customers,
            alerts=alerts,
            debts=debts,
        )

    def list_notifications(self, user_id: str) -> list[NotificationOut]:
        return [notification for notification in self.notifications if notification.user_id == user_id]

    def read_notification(self, user_id: str, notification_id: str) -> NotificationOut:
        with self._lock:
            for index, notification in enumerate(self.notifications):
                if notification.id == notification_id and notification.user_id == user_id:
                    updated = notification.model_copy(update={"read_at": utcnow()})
                    self.notifications[index] = updated
                    return updated
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    def set_notification_preference(self, user_id: str, payload: NotificationPreferenceIn) -> NotificationPreferenceOut:
        preference = NotificationPreferenceOut(user_id=user_id, **payload.model_dump(), updated_at=utcnow())
        self.notification_preferences[(user_id, payload.merchant_id)] = preference
        return preference

    def list_commitment_score_events(self, user_id: str) -> list[CommitmentScoreEventOut]:
        return [event for event in self.commitment_score_events if event.user_id == user_id]

    # ── WhatsApp delivery state ───────────────────────────────────────

    def _ensure_whatsapp_state(self, notification_id: str) -> dict[str, object]:
        state = self._whatsapp_state.get(notification_id)
        if state is None:
            state = {
                "attempted": False,
                "delivered": None,
                "provider_ref": None,
                "failed_reason": None,
                "status_received_at": None,
            }
            self._whatsapp_state[notification_id] = state
        return state

    def mark_whatsapp_attempted(self, notification_id: str, result: SendResult) -> None:
        with self._lock:
            state = self._ensure_whatsapp_state(notification_id)
            state["attempted"] = True
            if result.outcome == SendOutcome.sent:
                state["provider_ref"] = result.provider_ref
                # delivered stays None (attempted_unknown) until a webhook arrives.
            else:
                # blocked or error -> failed; record the reason.
                state["delivered"] = False
                state["failed_reason"] = result.failed_reason
            for index, notification in enumerate(self.notifications):
                if notification.id == notification_id:
                    self.notifications[index] = notification.model_copy(update={"whatsapp_attempted": True})
                    break

    def apply_whatsapp_status(self, update: StatusUpdate) -> bool:
        with self._lock:
            for _notification_id, state in self._whatsapp_state.items():
                if state.get("provider_ref") != update.provider_ref:
                    continue
                # Forward-only: delivered is sticky; failed after delivered is no-op.
                already_delivered = state.get("delivered") is True
                if update.status == "delivered" and not already_delivered:
                    state["delivered"] = True
                elif update.status == "failed" and not already_delivered:
                    if state.get("delivered") is None:
                        state["delivered"] = False
                    if state.get("failed_reason") is None:
                        state["failed_reason"] = update.failed_reason
                if state.get("status_received_at") is None:
                    state["status_received_at"] = update.occurred_at
                return True
            return False

    def get_whatsapp_state(self, notification_id: str) -> dict[str, object] | None:
        state = self._whatsapp_state.get(notification_id)
        return dict(state) if state is not None else None

    def get_merchant_notification_preference(
        self, creditor_id: str, debtor_id: str
    ) -> NotificationPreferenceOut | None:
        # Stored keyed on (debtor_id, creditor_id) — debtor sets a preference
        # against a particular creditor (merchant).
        return self.notification_preferences.get((debtor_id, creditor_id))

    GROUP_MEMBER_CAP = 20

    def _enrich_member(self, member: GroupMemberOut) -> GroupMemberOut:
        profile = self.profiles.get(member.user_id)
        if profile is None:
            return member
        return member.model_copy(update={"name": profile.name, "commitment_score": profile.commitment_score})

    def _group_member_count(self, group_id: str, *, statuses: tuple[GroupMemberStatus, ...] = (GroupMemberStatus.accepted,)) -> int:
        return sum(1 for m in self.group_members if m.group_id == group_id and m.status in statuses)

    def _group_with_count(self, group: GroupOut) -> GroupOut:
        return group.model_copy(update={"member_count": self._group_member_count(group.id)})

    def find_profile_by_email_or_phone(self, *, email: str | None = None, phone: str | None = None) -> ProfileOut | None:
        if email:
            email_l = email.strip().lower()
            for p in self.profiles.values():
                if p.email and p.email.lower() == email_l:
                    return p
        if phone:
            phone_n = phone.strip()
            for p in self.profiles.values():
                if p.phone and p.phone == phone_n:
                    return p
        return None

    def _resolve_invite_target(self, payload: GroupInviteIn) -> str:
        if payload.user_id is not None:
            if payload.user_id not in self.profiles:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "NotPlatformUser", "message": "Recipient is not a platform user."})
            return payload.user_id
        profile = self.find_profile_by_email_or_phone(email=payload.email, phone=payload.phone)
        if profile is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "NotPlatformUser", "message": "Recipient is not a platform user."})
        return profile.id

    def create_group(self, owner_id: str, payload: GroupCreate) -> GroupOut:
        with self._lock:
            now = utcnow()
            group = GroupOut(id=str(uuid4()), owner_id=owner_id, name=payload.name, description=payload.description, created_at=now, updated_at=now, member_count=1)
            self.groups[group.id] = group
            self.group_members.append(
                GroupMemberOut(id=str(uuid4()), group_id=group.id, user_id=owner_id, status=GroupMemberStatus.accepted, created_at=now, accepted_at=now)
            )
            return self._group_with_count(group)

    def list_groups(self, user_id: str) -> list[GroupOut]:
        live = {GroupMemberStatus.pending, GroupMemberStatus.accepted}
        my_groups: list[tuple[GroupMemberStatus, GroupOut]] = []
        seen: set[str] = set()
        for member in self.group_members:
            if member.user_id != user_id or member.status not in live or member.group_id in seen:
                continue
            group = self.groups.get(member.group_id)
            if group is None:
                continue
            seen.add(member.group_id)
            enriched = self._group_with_count(group).model_copy(update={"member_status": member.status})
            my_groups.append((member.status, enriched))
        my_groups.sort(key=lambda pair: (0 if pair[0] == GroupMemberStatus.accepted else 1, -(pair[1].updated_at or pair[1].created_at).timestamp()))
        return [g for _, g in my_groups]

    def invite_group_member(self, actor_id: str, group_id: str, payload: GroupInviteIn) -> GroupMemberOut:
        with self._lock:
            group = self._require_group_owner(actor_id, group_id)
            target_id = self._resolve_invite_target(payload)
            if target_id == actor_id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "InviteToSelf", "message": "Cannot invite yourself."})
            for member in self.group_members:
                if member.group_id == group.id and member.user_id == target_id and member.status in (GroupMemberStatus.pending, GroupMemberStatus.accepted):
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "AlreadyMember", "message": "Recipient is already a member or has a pending invite.", "status": member.status.value})
            member = GroupMemberOut(id=str(uuid4()), group_id=group.id, user_id=target_id, status=GroupMemberStatus.pending, created_at=utcnow())
            self.group_members.append(member)
            self._notify(target_id, NotificationType.group_invite, "Group invitation", f"You were invited to {group.name}", None)
            return self._enrich_member(member)

    def accept_group_invite(self, user_id: str, group_id: str) -> GroupMemberOut:
        with self._lock:
            group = self.groups.get(group_id)
            if group is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "NoPendingInvite", "message": "No pending invite for this group."})
            target_index: int | None = None
            for index, member in enumerate(self.group_members):
                if member.group_id == group_id and member.user_id == user_id and member.status == GroupMemberStatus.pending:
                    target_index = index
                    break
            if target_index is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "NoPendingInvite", "message": "No pending invite for this group."})
            if self._group_member_count(group_id) >= self.GROUP_MEMBER_CAP:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "GroupFull", "message": f"Group is full (max {self.GROUP_MEMBER_CAP} members)."})
            updated = self.group_members[target_index].model_copy(update={"status": GroupMemberStatus.accepted, "accepted_at": utcnow()})
            self.group_members[target_index] = updated
            self._notify(group.owner_id, NotificationType.group_invite_accepted, "Invitation accepted", f"{user_id} joined {group.name}", None)
            return self._enrich_member(updated)

    def decline_group_invite(self, user_id: str, group_id: str) -> GroupMemberOut:
        with self._lock:
            for index, member in enumerate(self.group_members):
                if member.group_id == group_id and member.user_id == user_id and member.status == GroupMemberStatus.pending:
                    updated = member.model_copy(update={"status": GroupMemberStatus.declined})
                    self.group_members[index] = updated
                    return self._enrich_member(updated)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "NoPendingInvite", "message": "No pending invite for this group."})

    def leave_group(self, user_id: str, group_id: str) -> GroupMemberOut:
        with self._lock:
            group = self.groups.get(group_id)
            if group is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "NotAGroupMember", "message": "Group not found."})
            if group.owner_id == user_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "OwnerCannotLeave", "message": "Owner must transfer ownership before leaving."})
            # FR-013: cannot leave while in any open proposal's transfers.
            for proposal in self.settlement_proposals.values():
                if proposal["group_id"] != group_id or proposal["status"] != SettlementProposalStatus.open:
                    continue
                transfers = proposal["transfers"]
                if any(t["payer_id"] == user_id or t["receiver_id"] == user_id for t in transfers):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail={"code": "LeaveBlockedByOpenProposal", "message": "You cannot leave while an open settlement proposal includes you."},
                    )
            for index, member in enumerate(self.group_members):
                if member.group_id == group_id and member.user_id == user_id and member.status == GroupMemberStatus.accepted:
                    updated = member.model_copy(update={"status": GroupMemberStatus.left})
                    self.group_members[index] = updated
                    return self._enrich_member(updated)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "NotAGroupMember", "message": "You are not an accepted member."})

    def rename_group(self, owner_id: str, group_id: str, payload: GroupRenameIn) -> GroupOut:
        with self._lock:
            group = self._require_group_owner(owner_id, group_id)
            updated = group.model_copy(update={"name": payload.name, "updated_at": utcnow()})
            self.groups[group_id] = updated
            return self._group_with_count(updated)

    def transfer_group_ownership(self, owner_id: str, group_id: str, payload: GroupOwnershipTransferIn) -> GroupOut:
        with self._lock:
            group = self._require_group_owner(owner_id, group_id)
            target = payload.new_owner_user_id
            if target == owner_id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "SameOwner", "message": "Target is already the owner."})
            target_member = next((m for m in self.group_members if m.group_id == group_id and m.user_id == target and m.status == GroupMemberStatus.accepted), None)
            if target_member is None:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "NotAGroupMember", "message": "Target must be an accepted member."})
            updated = group.model_copy(update={"owner_id": target, "updated_at": utcnow()})
            self.groups[group_id] = updated
            self._notify(target, NotificationType.group_ownership_transferred, "You're now the owner", f"You are now the owner of {group.name}", None)
            return self._group_with_count(updated)

    def delete_group(self, owner_id: str, group_id: str) -> None:
        with self._lock:
            self._require_group_owner(owner_id, group_id)
            attached = sum(1 for d in self.debts.values() if d.group_id == group_id)
            if attached > 0:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "GroupHasDebts", "message": "Group has attached debts. Settle or detach them first.", "count": attached})
            self.group_members = [m for m in self.group_members if m.group_id != group_id]
            self.settlements = [s for s in self.settlements if s.group_id != group_id]
            self.groups.pop(group_id, None)

    def revoke_group_invite(self, owner_id: str, group_id: str, target_user_id: str) -> None:
        with self._lock:
            self._require_group_owner(owner_id, group_id)
            for index, member in enumerate(self.group_members):
                if member.group_id == group_id and member.user_id == target_user_id and member.status == GroupMemberStatus.pending:
                    self.group_members.pop(index)
                    return
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "NoPendingInvite", "message": "No pending invite for this user."})

    def list_pending_group_invites(self, owner_id: str, group_id: str) -> list[GroupMemberOut]:
        self._require_group_owner(owner_id, group_id)
        return [self._enrich_member(m) for m in self.group_members if m.group_id == group_id and m.status == GroupMemberStatus.pending]

    def list_group_members(self, viewer_id: str, group_id: str) -> list[GroupMemberOut]:
        group = self.groups.get(group_id)
        if group is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "NotAGroupMember", "message": "Group not found."})
        is_member = any(m.group_id == group_id and m.user_id == viewer_id and m.status == GroupMemberStatus.accepted for m in self.group_members)
        if not is_member:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "NotAGroupMember", "message": "You are not an accepted member."})
        accepted = [self._enrich_member(m) for m in self.group_members if m.group_id == group_id and m.status == GroupMemberStatus.accepted]
        if group.owner_id == viewer_id:
            accepted.extend(self._enrich_member(m) for m in self.group_members if m.group_id == group_id and m.status == GroupMemberStatus.pending)
        return accepted

    def get_group_detail(self, viewer_id: str, group_id: str) -> GroupDetailOut:
        group = self.groups.get(group_id)
        if group is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "NotAGroupMember", "message": "Group not found."})
        is_member = any(m.group_id == group_id and m.user_id == viewer_id and m.status == GroupMemberStatus.accepted for m in self.group_members)
        if not is_member:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "NotAGroupMember", "message": "You are not an accepted member."})
        members = [self._enrich_member(m) for m in self.group_members if m.group_id == group_id and m.status == GroupMemberStatus.accepted]
        pending = None
        if group.owner_id == viewer_id:
            pending = [self._enrich_member(m) for m in self.group_members if m.group_id == group_id and m.status == GroupMemberStatus.pending]
        enriched = self._group_with_count(group)
        return GroupDetailOut(**enriched.model_dump(), members=members, pending_invites=pending)

    def shared_accepted_groups(self, user_a: str, user_b: str) -> list[GroupOut]:
        a_groups = {m.group_id for m in self.group_members if m.user_id == user_a and m.status == GroupMemberStatus.accepted}
        b_groups = {m.group_id for m in self.group_members if m.user_id == user_b and m.status == GroupMemberStatus.accepted}
        shared = a_groups & b_groups
        return [self._group_with_count(self.groups[g]) for g in shared if g in self.groups]

    def update_debt_group_tag(self, creditor_id: str, debt_id: str, group_id: str | None) -> DebtOut:
        with self._lock:
            debt = self.debts.get(debt_id)
            if debt is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "DebtNotFound", "message": "Debt not found."})
            if debt.creditor_id != creditor_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "NotDebtCreditor", "message": "Only the creditor can change the group tag."})
            if debt.status not in (DebtStatus.pending_confirmation, DebtStatus.edit_requested):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "GroupTagLocked", "message": "Group tag is locked once the debt is binding."})
            if group_id is not None:
                if debt.debtor_id is None:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "DebtorRequired", "message": "Group tag requires a registered debtor."})
                shared = {g.id for g in self.shared_accepted_groups(creditor_id, debt.debtor_id)}
                if group_id not in shared:
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "NotInSharedGroup", "message": "Both parties must be accepted members of the group."})
            updated = debt.model_copy(update={"group_id": group_id, "updated_at": utcnow()})
            self.debts[debt_id] = updated
            return updated

    def group_debts(self, user_id: str, group_id: str) -> list[DebtOut]:
        group = self.groups.get(group_id)
        if group is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "NotAGroupMember", "message": "Group not found."})
        is_member = any(m.group_id == group_id and m.user_id == user_id and m.status == GroupMemberStatus.accepted for m in self.group_members)
        if not is_member:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "NotAGroupMember", "message": "You are not an accepted group member"})
        return [debt for debt in self.debts.values() if debt.group_id == group_id]

    def create_settlement(self, payer_id: str, group_id: str, payload: SettlementCreate) -> SettlementOut:
        with self._lock:
            if group_id not in self._accepted_group_ids(payer_id):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not an accepted group member")
            if payload.debtor_id not in self._accepted_group_member_ids({group_id}):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Debtor must be an accepted group member")
            settlement = SettlementOut(id=str(uuid4()), group_id=group_id, payer_id=payer_id, **payload.model_dump(), created_at=utcnow())
            self.settlements.append(settlement)
            self._notify(payload.debtor_id, NotificationType.payment_confirmed, "Group settlement recorded", f"{payer_id} paid {payload.amount} {payload.currency} for you", None)
            return settlement

    # ── Group settlement proposals (UC9 part 2) ──────────────────────

    def create_settlement_proposal(self, user_id: str, group_id: str) -> SettlementProposalOut:
        with self._lock:
            self._require_accepted_member(user_id, group_id)
            self.sweep_settlement_proposals(group_id)
            # One open proposal per group.
            for proposal in self.settlement_proposals.values():
                if proposal["group_id"] == group_id and proposal["status"] == SettlementProposalStatus.open:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail={"code": "OpenProposalExists", "message": "An open proposal already exists for this group.", "existing_proposal_id": proposal["id"]},
                    )
            # Snapshot active|overdue debts in this group.
            settle_states = {DebtStatus.active, DebtStatus.overdue}
            snapshot_debts = sorted(
                [d for d in self.debts.values() if d.group_id == group_id and d.status in settle_states and d.debtor_id is not None],
                key=lambda d: d.id,
            )
            if not snapshot_debts:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "NothingToSettle", "message": "Nothing to settle in this group."})
            currencies = {d.currency for d in snapshot_debts}
            if len(currencies) > 1:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "MixedCurrency", "message": "Cannot auto-net mixed currencies."})
            currency = next(iter(currencies))
            net_inputs = [
                _NetSnapshotDebt(debt_id=d.id, debtor_id=d.debtor_id, creditor_id=d.creditor_id, amount=d.amount, currency=d.currency)
                for d in snapshot_debts
            ]
            transfers = _compute_transfers(net_inputs)
            now = utcnow()
            pid = str(uuid4())
            transfers_list = [
                {"payer_id": t.payer_id, "receiver_id": t.receiver_id, "amount": t.amount}
                for t in transfers
            ]
            snapshot_list = [
                {"debt_id": d.id, "debtor_id": d.debtor_id, "creditor_id": d.creditor_id, "amount": d.amount}
                for d in snapshot_debts
            ]
            required_users: set[str] = set()
            for t in transfers_list:
                required_users.add(t["payer_id"])
                required_users.add(t["receiver_id"])
            self.settlement_proposals[pid] = {
                "id": pid,
                "group_id": group_id,
                "proposed_by": user_id,
                "currency": currency,
                "snapshot": snapshot_list,
                "transfers": transfers_list,
                "status": SettlementProposalStatus.open,
                "failure_reason": None,
                "created_at": now,
                "expires_at": now + timedelta(days=7),
                "resolved_at": None,
                "reminder_sent_at": None,
            }
            for uid in sorted(required_users):
                self.settlement_confirmations[(pid, uid)] = {
                    "proposal_id": pid,
                    "user_id": uid,
                    "status": SettlementConfirmationStatus.pending,
                    "responded_at": None,
                }
            self._record_group_event(group_id, user_id, "settlement_proposed", {"proposal_id": pid, "transfer_count": len(transfers_list)})
            # Notify each required confirmer; if none required, proposal is
            # immediately settle-able with zero transfers — auto-settle.
            for uid in required_users:
                their_amount = sum(
                    (t["amount"] for t in transfers_list if t["payer_id"] == uid),
                    Decimal("0"),
                ) or sum(
                    (t["amount"] for t in transfers_list if t["receiver_id"] == uid),
                    Decimal("0"),
                )
                self._notify(uid, NotificationType.settlement_proposed, "Settlement proposal", f"{their_amount} {currency} settlement proposed in your group", None)
            if not required_users:
                # Net-zero group with non-empty snapshot (e.g. perfect cycle)
                # → settle immediately, no confirmations needed.
                self._apply_settlement(pid)
            return self._serialise_proposal(pid, viewer_id=user_id)

    def get_settlement_proposal(self, user_id: str, group_id: str, proposal_id: str) -> SettlementProposalOut:
        self._require_accepted_member(user_id, group_id)
        self.sweep_settlement_proposals(group_id)
        proposal = self.settlement_proposals.get(proposal_id)
        if proposal is None or proposal["group_id"] != group_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "ProposalNotFound", "message": "Proposal not found."})
        return self._serialise_proposal(proposal_id, viewer_id=user_id)

    def list_settlement_proposals(
        self, user_id: str, group_id: str, status_filter: str | None = None
    ) -> list[SettlementProposalOut]:
        self._require_accepted_member(user_id, group_id)
        self.sweep_settlement_proposals(group_id)
        items = [p for p in self.settlement_proposals.values() if p["group_id"] == group_id]
        if status_filter and status_filter != "all":
            items = [p for p in items if p["status"] == status_filter]
        items.sort(key=lambda p: p["created_at"], reverse=True)
        return [self._serialise_proposal(p["id"], viewer_id=user_id) for p in items]

    def confirm_settlement_proposal(self, user_id: str, group_id: str, proposal_id: str) -> SettlementProposalOut:
        with self._lock:
            self._require_accepted_member(user_id, group_id)
            self.sweep_settlement_proposals(group_id)
            proposal = self.settlement_proposals.get(proposal_id)
            if proposal is None or proposal["group_id"] != group_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "ProposalNotFound", "message": "Proposal not found."})
            if proposal["status"] != SettlementProposalStatus.open:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "ProposalNotOpen", "message": "Proposal is not open."})
            confirmation = self.settlement_confirmations.get((proposal_id, user_id))
            if confirmation is None:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "NotARequiredParty", "message": "You are not a required party for this proposal."})
            if confirmation["status"] == SettlementConfirmationStatus.confirmed:
                # Idempotent.
                return self._serialise_proposal(proposal_id, viewer_id=user_id)
            if confirmation["status"] == SettlementConfirmationStatus.rejected:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "AlreadyResponded", "message": "You have already rejected this proposal."})
            confirmation["status"] = SettlementConfirmationStatus.confirmed
            confirmation["responded_at"] = utcnow()
            self._record_group_event(group_id, user_id, "settlement_confirmed", {"proposal_id": proposal_id})
            # If everyone has confirmed, atomically settle.
            roster = [c for c in self.settlement_confirmations.values() if c["proposal_id"] == proposal_id]
            if all(c["status"] == SettlementConfirmationStatus.confirmed for c in roster):
                try:
                    self._apply_settlement(proposal_id)
                except Exception as exc:  # noqa: BLE001 — guard for mocked/unexpected raises
                    p = self.settlement_proposals[proposal_id]
                    p["status"] = SettlementProposalStatus.settlement_failed
                    p["failure_reason"] = type(exc).__name__
                    p["resolved_at"] = utcnow()
            return self._serialise_proposal(proposal_id, viewer_id=user_id)

    def reject_settlement_proposal(self, user_id: str, group_id: str, proposal_id: str) -> SettlementProposalOut:
        with self._lock:
            self._require_accepted_member(user_id, group_id)
            self.sweep_settlement_proposals(group_id)
            proposal = self.settlement_proposals.get(proposal_id)
            if proposal is None or proposal["group_id"] != group_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "ProposalNotFound", "message": "Proposal not found."})
            if proposal["status"] != SettlementProposalStatus.open:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "ProposalNotOpen", "message": "Proposal is not open."})
            confirmation = self.settlement_confirmations.get((proposal_id, user_id))
            if confirmation is None:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "NotARequiredParty", "message": "You are not a required party for this proposal."})
            if confirmation["status"] != SettlementConfirmationStatus.pending:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "AlreadyResponded", "message": "You have already responded."})
            now = utcnow()
            confirmation["status"] = SettlementConfirmationStatus.rejected
            confirmation["responded_at"] = now
            proposal["status"] = SettlementProposalStatus.rejected
            proposal["resolved_at"] = now
            self._record_group_event(group_id, user_id, "settlement_rejected", {"proposal_id": proposal_id})
            for c in self.settlement_confirmations.values():
                if c["proposal_id"] == proposal_id:
                    self._notify(c["user_id"], NotificationType.settlement_rejected, "Settlement rejected", "A required party rejected the settlement.", None)
            return self._serialise_proposal(proposal_id, viewer_id=user_id)

    def sweep_settlement_proposals(self, group_id: str) -> None:
        with self._lock:
            now = utcnow()
            for proposal in list(self.settlement_proposals.values()):
                if proposal["group_id"] != group_id or proposal["status"] != SettlementProposalStatus.open:
                    continue
                if proposal["expires_at"] <= now:
                    proposal["status"] = SettlementProposalStatus.expired
                    proposal["resolved_at"] = now
                    self._record_group_event(group_id, proposal["proposed_by"], "settlement_expired", {"proposal_id": proposal["id"]})
                    for c in self.settlement_confirmations.values():
                        if c["proposal_id"] == proposal["id"]:
                            self._notify(c["user_id"], NotificationType.settlement_expired, "Settlement expired", "A settlement proposal has expired.", None)
                    continue
                # Near-expiry reminder (within 24h, idempotent).
                if proposal["reminder_sent_at"] is None and proposal["expires_at"] - now <= timedelta(hours=24):
                    proposal["reminder_sent_at"] = now
                    for c in self.settlement_confirmations.values():
                        if c["proposal_id"] == proposal["id"] and c["status"] == SettlementConfirmationStatus.pending:
                            self._notify(c["user_id"], NotificationType.settlement_reminder, "Settlement expiring soon", "A settlement proposal is awaiting your response.", None)

    def _apply_settlement(self, proposal_id: str) -> None:
        """Atomically settle every snapshotted debt. On any error, restore prior
        state, mark proposal settlement_failed, notify, and swallow the exception.
        """
        proposal = self.settlement_proposals[proposal_id]
        # Snapshot prior state so we can roll back on failure.
        debts_snapshot = {d.id: d.model_copy() for d in self.debts.values()}
        debt_events_len = len(self.debt_events)
        commitment_events_len = len(self.commitment_score_events)
        profiles_snapshot = {uid: p.model_copy() for uid, p in self.profiles.items()}
        try:
            now = utcnow()
            for debt_ref in proposal["snapshot"]:
                debt = self.debts.get(debt_ref["debt_id"])
                if debt is None or debt.status not in (DebtStatus.active, DebtStatus.overdue):
                    raise RuntimeError("StaleSnapshot")
                # Step 1: active|overdue → payment_pending_confirmation.
                self.debts[debt.id] = debt.model_copy(update={"status": DebtStatus.payment_pending_confirmation, "updated_at": now})
                self._add_event(debt.id, debt.debtor_id or proposal["proposed_by"], "marked_paid", "Group settlement", {"source": "group_settlement", "proposal_id": proposal_id})
                # Step 2: payment_pending_confirmation → paid.
                self.debts[debt.id] = self.debts[debt.id].model_copy(update={"status": DebtStatus.paid, "paid_at": now, "updated_at": now})
                self._add_event(debt.id, debt.creditor_id, "payment_confirmed", "Group settlement", {"source": "group_settlement", "proposal_id": proposal_id})
                # Step 3: neutral commitment event (delta 0), idempotent on (debt_id, proposal_id).
                if debt.debtor_id:
                    profile = self.profiles.get(debt.debtor_id)
                    score_after = profile.commitment_score if profile else 50
                    event = CommitmentScoreEventOut(
                        id=str(uuid4()),
                        user_id=debt.debtor_id,
                        delta=0,
                        score_after=score_after,
                        reason="settlement_neutral",
                        debt_id=debt.id,
                        proposal_id=proposal_id,
                        created_at=now,
                    )
                    self.commitment_score_events.append(event)
            proposal["status"] = SettlementProposalStatus.settled
            proposal["resolved_at"] = now
            self._record_group_event(proposal["group_id"], proposal["proposed_by"], "settlement_settled", {"proposal_id": proposal_id})
            for c in self.settlement_confirmations.values():
                if c["proposal_id"] == proposal_id:
                    self._notify(c["user_id"], NotificationType.settlement_settled, "Settlement complete", "All debts in the proposal are now paid.", None)
        except Exception as exc:  # noqa: BLE001 — defensive rollback
            # Roll back all in-memory changes.
            self.debts.clear()
            self.debts.update(debts_snapshot)
            del self.debt_events[debt_events_len:]
            del self.commitment_score_events[commitment_events_len:]
            self.profiles.clear()
            self.profiles.update(profiles_snapshot)
            proposal["status"] = SettlementProposalStatus.settlement_failed
            proposal["failure_reason"] = type(exc).__name__
            proposal["resolved_at"] = utcnow()
            self._record_group_event(proposal["group_id"], proposal["proposed_by"], "settlement_failed", {"proposal_id": proposal_id, "reason": type(exc).__name__})
            for c in self.settlement_confirmations.values():
                if c["proposal_id"] == proposal_id:
                    self._notify(c["user_id"], NotificationType.settlement_failed, "Settlement failed", "The settlement could not be applied. All debts are unchanged.", None)

    def _record_group_event(self, group_id: str, actor_id: str, event_type: str, metadata: dict[str, object] | None = None) -> None:
        # Phase 8 stored group events in-memory via a list helper if present.
        # The in-memory repo has historically been event-light for groups;
        # we accept that and rely on debt_events for per-debt audit. This
        # method exists for parity with the postgres path.
        return

    def _require_accepted_member(self, user_id: str, group_id: str) -> None:
        group = self.groups.get(group_id)
        if group is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "NotAGroupMember", "message": "Group not found."})
        is_member = any(
            m.group_id == group_id and m.user_id == user_id and m.status == GroupMemberStatus.accepted
            for m in self.group_members
        )
        if not is_member:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "NotAGroupMember", "message": "You are not an accepted member."})

    def _serialise_proposal(self, proposal_id: str, viewer_id: str) -> SettlementProposalOut:
        proposal = self.settlement_proposals[proposal_id]
        is_required = (proposal_id, viewer_id) in self.settlement_confirmations
        # FR-007: only required parties see the snapshot; observers see None.
        snapshot: list[SnapshotDebtOut] | None = None
        if is_required:
            snapshot = [
                SnapshotDebtOut(
                    debt_id=row["debt_id"],
                    debtor_id=row["debtor_id"],
                    creditor_id=row["creditor_id"],
                    amount=row["amount"],
                )
                for row in proposal["snapshot"]
            ]
        transfers = [
            ProposedTransferOut(payer_id=t["payer_id"], receiver_id=t["receiver_id"], amount=t["amount"])
            for t in proposal["transfers"]
        ]
        confirmations = [
            SettlementConfirmationOut(
                user_id=c["user_id"],
                status=c["status"],
                responded_at=c["responded_at"],
            )
            for c in self.settlement_confirmations.values()
            if c["proposal_id"] == proposal_id
        ]
        confirmations.sort(key=lambda c: c.user_id)
        return SettlementProposalOut(
            id=proposal["id"],
            group_id=proposal["group_id"],
            proposed_by=proposal["proposed_by"],
            currency=proposal["currency"],
            transfers=transfers,
            snapshot=snapshot,
            confirmations=confirmations,
            status=proposal["status"],
            failure_reason=proposal["failure_reason"],
            created_at=proposal["created_at"],
            expires_at=proposal["expires_at"],
            resolved_at=proposal["resolved_at"],
        )

    def merchant_facts(self, user_id: str) -> dict[str, object]:
        dashboard = self.creditor_dashboard(user_id)
        return {
            "total_receivable": str(dashboard.total_receivable),
            "debtor_count": dashboard.debtor_count,
            "active_count": dashboard.active_count,
            "overdue_count": dashboard.overdue_count,
            "paid_count": dashboard.paid_count,
            "alerts": dashboard.alerts,
        }

    # ── Payment intents ───────────────────────────────────────────────

    def create_payment_intent(
        self,
        debt_id: str,
        provider: str,
        amount: Decimal,
        fee: Decimal,
        checkout_url: str,
        provider_ref: str | None,
        expires_at: datetime,
    ) -> PaymentIntentOut:
        intent = PaymentIntentOut(
            id=str(uuid4()),
            debt_id=debt_id,
            provider=provider,
            provider_ref=provider_ref,
            checkout_url=checkout_url,
            status=PaymentIntentStatus.pending,
            amount=amount,
            fee=fee,
            net_amount=amount - fee,
            created_at=utcnow(),
            expires_at=expires_at,
        )
        self.payment_intents[intent.id] = intent
        return intent

    def get_active_payment_intent(self, debt_id: str) -> PaymentIntentOut | None:
        now = utcnow()
        for intent in list(self.payment_intents.values()):
            if intent.debt_id != debt_id or intent.status != PaymentIntentStatus.pending:
                continue
            if intent.expires_at <= now:
                self.payment_intents[intent.id] = intent.model_copy(
                    update={"status": PaymentIntentStatus.expired, "completed_at": now}
                )
                return None
            return intent
        return None

    def get_payment_intent_by_ref(self, provider_ref: str) -> PaymentIntentOut | None:
        for intent in self.payment_intents.values():
            if intent.provider_ref == provider_ref:
                return intent
        return None

    def update_payment_intent_status(
        self, intent_id: str, status: str, completed_at: datetime | None = None
    ) -> None:
        intent = self.payment_intents.get(intent_id)
        if intent:
            update: dict[str, object] = {"status": status}
            if completed_at is not None:
                update["completed_at"] = completed_at
            self.payment_intents[intent_id] = intent.model_copy(update=update)

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
        with self._lock:
            debt = self.get_authorized_debt(user_id, debt_id)
            if debt.creditor_id == user_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the debtor can initiate online payment")
            if debt.status not in {DebtStatus.active, DebtStatus.overdue}:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Debt must be active or overdue to pay online")
            existing = self.get_active_payment_intent(debt_id)
            if existing:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="payment_in_progress")
            intent = self.create_payment_intent(debt_id, provider, amount, fee, checkout_url, provider_ref, expires_at)
            now = utcnow()
            debt = debt.model_copy(update={"status": DebtStatus.payment_pending_confirmation, "updated_at": now})
            self.debts[debt_id] = debt
            self._add_event(debt_id, user_id, "payment_initiated", None, {
                "intent_id": intent.id, "provider": provider, "amount": str(amount), "fee": str(fee)
            })
            return PayOnlineOut(
                payment_intent_id=intent.id,
                checkout_url=checkout_url,
                amount=amount,
                fee=fee,
                net_amount=amount - fee,
                currency=debt.currency,
                expires_at=expires_at,
            )

    def confirm_payment_gateway(self, provider_ref: str) -> DebtOut:
        with self._lock:
            intent = self.get_payment_intent_by_ref(provider_ref)
            if not intent:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment intent not found")
            if intent.status == PaymentIntentStatus.succeeded:
                debt = self.debts.get(intent.debt_id)
                if not debt:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Debt not found")
                return debt
            now = utcnow()
            self.update_payment_intent_status(intent.id, PaymentIntentStatus.succeeded, now)
            debt = self.debts.get(intent.debt_id)
            if not debt:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Debt not found")
            if debt.status == DebtStatus.paid:
                return debt
            if debt.status != DebtStatus.payment_pending_confirmation:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Debt is not awaiting payment confirmation")
            debt = debt.model_copy(update={"status": DebtStatus.paid, "paid_at": now, "updated_at": now})
            self.debts[intent.debt_id] = debt
            self._add_event(intent.debt_id, "system", "payment_confirmed", None, {
                "intent_id": intent.id, "provider_ref": provider_ref, "gateway": True
            })
            if debt.debtor_id:
                today = now.date()
                if today < debt.due_date:
                    self._change_commitment_score(debt.debtor_id, 3, "paid_early", debt.id)
                elif today == debt.due_date:
                    self._change_commitment_score(debt.debtor_id, 1, "paid_on_time", debt.id)
                else:
                    missed = sum(
                        1 for ev in self.commitment_score_events
                        if ev.debt_id == debt.id and ev.reason == "missed_reminder"
                    )
                    self._change_commitment_score(debt.debtor_id, _late_penalty(missed), "paid_late", debt.id)
                self._notify(debt.debtor_id, NotificationType.payment_confirmed, "Payment confirmed",
                             f"{debt.amount} {debt.currency} was confirmed as paid", debt.id)
            self._notify(debt.creditor_id, NotificationType.payment_confirmed, "Payment confirmed",
                         f"{debt.debtor_name} paid {debt.amount} {debt.currency} online", debt.id)
            return debt

    def record_payment_failure(self, provider_ref: str) -> None:
        with self._lock:
            intent = self.get_payment_intent_by_ref(provider_ref)
            if not intent:
                return
            if intent.status != PaymentIntentStatus.pending:
                return
            now = utcnow()
            self.update_payment_intent_status(intent.id, PaymentIntentStatus.failed, now)
            self._add_event(intent.debt_id, "system", "payment_failed", None, {"provider_ref": provider_ref})
            debt = self.debts.get(intent.debt_id)
            if debt and debt.debtor_id:
                self._notify(debt.debtor_id, NotificationType.payment_failed, "Payment failed",
                             f"Payment of {debt.amount} {debt.currency} failed — you can try again", debt.id)

    def _add_event(self, debt_id: str, actor_id: str, event_type: str, message: str | None = None, metadata: dict[str, object] | None = None) -> DebtEventOut:
        event = DebtEventOut(
            id=str(uuid4()),
            debt_id=debt_id,
            actor_id=actor_id,
            event_type=event_type,
            message=message,
            metadata=metadata or {},
            created_at=utcnow(),
        )
        self.debt_events.append(event)
        return event

    def _notify(
        self,
        user_id: str,
        notification_type: NotificationType,
        title: str,
        body: str,
        debt_id: str | None,
        merchant_id: str | None = None,
    ) -> NotificationOut:
        notification = NotificationOut(
            id=str(uuid4()),
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            body=body,
            debt_id=debt_id,
            whatsapp_attempted=False,
            created_at=utcnow(),
        )
        self.notifications.append(notification)
        self._dispatch_whatsapp(notification, merchant_id=merchant_id, debt_id=debt_id)
        return notification

    def _dispatch_whatsapp(
        self,
        notification: NotificationOut,
        *,
        merchant_id: str | None,
        debt_id: str | None,
    ) -> None:
        # Lazy imports to avoid circulars at module load time.
        from app.services.whatsapp import get_provider
        from app.services.whatsapp.dispatch import (
            DispatchContext,
            build_default_template_params,
            dispatch_notification,
        )

        recipient = self.profiles.get(notification.user_id)
        if recipient is None:
            return

        creditor_id: str | None = None
        debtor_id: str | None = None
        creditor_name = ""
        debtor_name = ""
        amount = ""
        currency = ""
        due_date = ""
        if debt_id and debt_id in self.debts:
            debt = self.debts[debt_id]
            creditor_id = debt.creditor_id
            debtor_id = debt.debtor_id
            creditor_profile = self.profiles.get(debt.creditor_id)
            creditor_name = creditor_profile.name if creditor_profile else ""
            debtor_name = debt.debtor_name
            amount = str(debt.amount)
            currency = debt.currency
            due_date = debt.due_date.isoformat()
        elif merchant_id:
            creditor_id = merchant_id
            debtor_id = notification.user_id

        ctx = DispatchContext(
            recipient=recipient,
            sender_id=creditor_id,
            creditor_id=creditor_id,
            debtor_id=debtor_id,
            template_params=build_default_template_params(
                creditor_name=creditor_name,
                debtor_name=debtor_name,
                amount=amount,
                currency=currency,
                debt_link=f"/debts/{debt_id}" if debt_id else "",
                due_date=due_date,
            ),
        )
        dispatch_notification(notification, ctx, self, get_provider())

    def _change_commitment_score(
        self,
        user_id: str,
        delta: int,
        reason: str,
        debt_id: str | None = None,
        reminder_date: date | None = None,
    ) -> CommitmentScoreEventOut:
        profile = self.profiles.get(user_id)
        if not profile:
            return CommitmentScoreEventOut(id=str(uuid4()), user_id=user_id, delta=0, score_after=50, reason="profile_missing", debt_id=debt_id, created_at=utcnow())
        score_after = min(100, max(0, profile.commitment_score + delta))
        event = CommitmentScoreEventOut(
            id=str(uuid4()), user_id=user_id, delta=delta, score_after=score_after,
            reason=reason, debt_id=debt_id, reminder_date=reminder_date, created_at=utcnow(),
        )
        self.commitment_score_events.append(event)
        self.profiles[user_id] = profile.model_copy(update={"commitment_score": score_after, "updated_at": utcnow()})
        return event

    def _refresh_overdue(self) -> None:
        today = date.today()
        unpaid_states = {DebtStatus.active, DebtStatus.overdue, DebtStatus.payment_pending_confirmation}
        for debt in list(self.debts.values()):
            if debt.status == DebtStatus.active and debt.due_date < today:
                updated = debt.model_copy(update={"status": DebtStatus.overdue, "updated_at": utcnow()})
                self.debts[debt.id] = updated
                self._add_event(debt.id, "system", "debt_overdue", "Debt moved to overdue")
                if debt.debtor_id and debt.id not in self._overdue_penalties:
                    self._change_commitment_score(debt.debtor_id, -5, "debt_overdue", debt.id)
                    self._overdue_penalties.add(debt.id)
                    self._notify(debt.debtor_id, NotificationType.overdue, "Debt overdue", f"{debt.amount} {debt.currency} is overdue", debt.id, merchant_id=debt.creditor_id)
        # Apply missed-reminder penalties for any unpaid debt whose reminder dates have passed.
        for debt in list(self.debts.values()):
            if debt.status not in unpaid_states or not debt.debtor_id:
                continue
            self._apply_missed_reminder_penalties(debt, today)

    def _apply_missed_reminder_penalties(self, debt: DebtOut, today: date) -> None:
        already = {
            ev.reminder_date for ev in self.commitment_score_events
            if ev.debt_id == debt.id and ev.reason == "missed_reminder" and ev.reminder_date is not None
        }
        for reminder in sorted(debt.reminder_dates):
            if reminder >= today or reminder in already:
                continue
            prior = sum(
                1 for ev in self.commitment_score_events
                if ev.debt_id == debt.id and ev.reason == "missed_reminder"
            )
            self._change_commitment_score(debt.debtor_id, _late_penalty(prior), "missed_reminder", debt.id, reminder_date=reminder)
            self._notify(
                debt.debtor_id,
                NotificationType.overdue,
                "Reminder missed",
                f"Reminder for {debt.amount} {debt.currency} on {reminder.isoformat()} passed unpaid",
                debt.id,
                merchant_id=debt.creditor_id,
            )
            already.add(reminder)

    def _can_view_debt(self, user_id: str, debt: DebtOut) -> bool:
        if debt.creditor_id == user_id or debt.debtor_id == user_id:
            return True
        if not debt.group_id:
            return False
        return debt.group_id in self._accepted_group_ids(user_id)

    def _accepted_group_ids(self, user_id: str) -> set[str]:
        return {member.group_id for member in self.group_members if member.user_id == user_id and member.status == GroupMemberStatus.accepted}

    def _accepted_group_member_ids(self, group_ids: set[str]) -> set[str]:
        return {member.user_id for member in self.group_members if member.group_id in group_ids and member.status == GroupMemberStatus.accepted}

    def _require_group_owner(self, actor_id: str, group_id: str) -> GroupOut:
        group = self.groups.get(group_id)
        if not group:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
        if group.owner_id != actor_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the group owner can invite members")
        return group


repository = InMemoryRepository()


def get_repository() -> InMemoryRepository:
    return repository
