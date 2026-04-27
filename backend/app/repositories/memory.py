from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from threading import RLock
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status

from app.core.security import AuthenticatedUser
from app.repositories.base import Repository
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
    GroupInviteIn,
    GroupMemberOut,
    GroupMemberStatus,
    GroupOut,
    NotificationOut,
    NotificationPreferenceIn,
    NotificationPreferenceOut,
    NotificationType,
    PaymentConfirmationOut,
    PaymentRequest,
    ProfileOut,
    ProfileUpdate,
    SettlementCreate,
    SettlementOut,
    utcnow,
)


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
            self.notification_preferences: dict[tuple[str, str], NotificationPreferenceOut] = {}
            self.commitment_score_events: list[CommitmentScoreEventOut] = []
            self.groups: dict[str, GroupOut] = {}
            self.group_members: list[GroupMemberOut] = []
            self.settlements: list[SettlementOut] = []
            self._overdue_penalties: set[str] = set()
            self._edit_request_payloads: dict[str, dict[str, object]] = {}
            self._original_terms: dict[str, dict[str, object]] = {}

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
            self.get_authorized_debt(user_id, debt_id)
            attachment = AttachmentOut(
                id=str(uuid4()),
                debt_id=debt_id,
                uploader_id=user_id,
                attachment_type=attachment_type,
                file_name=file.filename or "attachment",
                content_type=file.content_type,
                url=f"mock://attachments/{debt_id}/{uuid4()}-{file.filename or 'attachment'}",
                created_at=utcnow(),
            )
            self.attachments.append(attachment)
            await file.close()
            return attachment

    def list_attachments(self, user_id: str, debt_id: str) -> list[AttachmentOut]:
        self.get_authorized_debt(user_id, debt_id)
        return [attachment for attachment in self.attachments if attachment.debt_id == debt_id]

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

    def create_group(self, owner_id: str, payload: GroupCreate) -> GroupOut:
        with self._lock:
            group = GroupOut(id=str(uuid4()), owner_id=owner_id, name=payload.name, description=payload.description, created_at=utcnow())
            self.groups[group.id] = group
            self.group_members.append(
                GroupMemberOut(id=str(uuid4()), group_id=group.id, user_id=owner_id, status=GroupMemberStatus.accepted, created_at=utcnow(), accepted_at=utcnow())
            )
            return group

    def list_groups(self, user_id: str) -> list[GroupOut]:
        group_ids = self._accepted_group_ids(user_id)
        return [group for group in self.groups.values() if group.id in group_ids]

    def invite_group_member(self, actor_id: str, group_id: str, payload: GroupInviteIn) -> GroupMemberOut:
        with self._lock:
            group = self._require_group_owner(actor_id, group_id)
            for member in self.group_members:
                if member.group_id == group.id and member.user_id == payload.user_id:
                    return member
            member = GroupMemberOut(id=str(uuid4()), group_id=group.id, user_id=payload.user_id, status=GroupMemberStatus.pending, created_at=utcnow())
            self.group_members.append(member)
            self._notify(payload.user_id, NotificationType.debt_created, "Group invitation", f"You were invited to {group.name}", None)
            return member

    def accept_group_invite(self, user_id: str, group_id: str) -> GroupMemberOut:
        with self._lock:
            for index, member in enumerate(self.group_members):
                if member.group_id == group_id and member.user_id == user_id:
                    updated = member.model_copy(update={"status": GroupMemberStatus.accepted, "accepted_at": utcnow()})
                    self.group_members[index] = updated
                    return updated
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group invitation not found")

    def group_debts(self, user_id: str, group_id: str) -> list[DebtOut]:
        if group_id not in self._accepted_group_ids(user_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not an accepted group member")
        member_ids = self._accepted_group_member_ids({group_id})
        return [debt for debt in self.debts.values() if debt.group_id == group_id or debt.creditor_id in member_ids or debt.debtor_id in member_ids]

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
        preference = self.notification_preferences.get((user_id, merchant_id or ""))
        whatsapp_attempted = bool(preference.whatsapp_enabled if preference else True)
        notification = NotificationOut(
            id=str(uuid4()),
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            body=body,
            debt_id=debt_id,
            whatsapp_attempted=whatsapp_attempted,
            created_at=utcnow(),
        )
        self.notifications.append(notification)
        return notification

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

