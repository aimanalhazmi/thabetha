"""Postgres-backed repository using psycopg connection pool."""

from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.core.security import AuthenticatedUser
from app.repositories.base import Repository
from app.schemas.domain import (
    AttachmentOut,
    AttachmentType,
    BusinessProfileIn,
    BusinessProfileOut,
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
    TrustScoreEventOut,
    utcnow,
)


def _profile_from_row(row: dict) -> ProfileOut:
    return ProfileOut(
        id=str(row["id"]),
        name=row["name"],
        phone=row["phone"],
        email=row.get("email"),
        account_type=row["account_type"],
        tax_id=row.get("tax_id"),
        commercial_registration=row.get("commercial_registration"),
        whatsapp_enabled=row["whatsapp_enabled"],
        ai_enabled=row["ai_enabled"],
        trust_score=row["trust_score"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _debt_from_row(row: dict) -> DebtOut:
    return DebtOut(
        id=str(row["id"]),
        creditor_id=str(row["creditor_id"]),
        debtor_id=str(row["debtor_id"]) if row.get("debtor_id") else None,
        debtor_name=row["debtor_name"],
        amount=row["amount"],
        currency=row["currency"].strip(),
        description=row["description"],
        due_date=row["due_date"],
        status=row["status"],
        invoice_url=row.get("invoice_url"),
        notes=row.get("notes"),
        group_id=str(row["group_id"]) if row.get("group_id") else None,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        confirmed_at=row.get("confirmed_at"),
        paid_at=row.get("paid_at"),
    )


class PostgresRepository(Repository):
    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool

    # ── helpers ────────────────────────────────────────────────────────

    def _refresh_overdue(self, conn) -> None:
        """Move active debts past due_date to overdue status."""
        cur = conn.execute(
            """
            UPDATE debts SET status = 'overdue', updated_at = now()
            WHERE status = 'active' AND due_date < CURRENT_DATE
            RETURNING id, debtor_id, amount, currency, creditor_id
            """,
        )
        for row in cur.fetchall():
            debt_id = str(row[0])
            debtor_id = str(row[1]) if row[1] else None
            amount, currency, creditor_id = row[2], row[3].strip(), str(row[4])
            self._add_event_raw(conn, debt_id, "system", "debt_overdue", "Debt moved to overdue")
            if debtor_id:
                self._change_trust_score_raw(conn, debtor_id, -5, "debt_overdue", debt_id)
                self._notify_raw(conn, debtor_id, "overdue", "Debt overdue", f"{amount} {currency} is overdue", debt_id, merchant_id=creditor_id)

    def _add_event_raw(self, conn, debt_id: str, actor_id: str, event_type: str, message: str | None = None, metadata: dict | None = None) -> str:
        event_id = str(uuid4())
        conn.execute(
            """
            INSERT INTO debt_events (id, debt_id, actor_id, event_type, message, metadata, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, now())
            """,
            (event_id, debt_id, actor_id if actor_id != "system" else None, event_type, message, json.dumps(metadata or {})),
        )
        return event_id

    def _notify_raw(self, conn, user_id: str, notification_type: str, title: str, body: str, debt_id: str | None, merchant_id: str | None = None) -> str:
        # Check WhatsApp preference
        whatsapp_attempted = True
        if merchant_id:
            row = conn.execute(
                "SELECT whatsapp_enabled FROM merchant_notification_preferences WHERE user_id = %s AND merchant_id = %s",
                (user_id, merchant_id),
            ).fetchone()
            if row:
                whatsapp_attempted = bool(row[0])
        nid = str(uuid4())
        conn.execute(
            """
            INSERT INTO notifications (id, user_id, notification_type, title, body, debt_id, whatsapp_attempted, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, now())
            """,
            (nid, user_id, notification_type, title, body, debt_id, whatsapp_attempted),
        )
        return nid

    def _change_trust_score_raw(self, conn, user_id: str, delta: int, reason: str, debt_id: str | None = None) -> None:
        row = conn.execute("SELECT trust_score FROM profiles WHERE id = %s", (user_id,)).fetchone()
        if not row:
            return
        old_score = row[0]
        new_score = min(100, max(0, old_score + delta))
        conn.execute("UPDATE profiles SET trust_score = %s, updated_at = now() WHERE id = %s", (new_score, user_id))
        conn.execute(
            """
            INSERT INTO trust_score_events (id, user_id, delta, score_after, reason, debt_id, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, now())
            """,
            (str(uuid4()), user_id, delta, new_score, reason, debt_id),
        )

    def _can_view_debt(self, conn, user_id: str, debt_id: str) -> dict | None:
        """Return debt row if user can view it, else None."""
        row = conn.execute(
            """
            SELECT d.* FROM debts d
            WHERE d.id = %s AND (
                d.creditor_id = %s
                OR d.debtor_id = %s
                OR EXISTS (
                    SELECT 1 FROM group_members gm
                    WHERE gm.group_id = d.group_id AND gm.user_id = %s AND gm.status = 'accepted'
                )
            )
            """,
            (debt_id, user_id, user_id, user_id),
        ).fetchone()
        return dict(row) if row else None

    # ── Profiles ──────────────────────────────────────────────────────

    def ensure_profile(self, user: AuthenticatedUser) -> ProfileOut:
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            row = conn.execute("SELECT * FROM profiles WHERE id = %s", (user.id,)).fetchone()
            if row:
                return _profile_from_row(row)
            conn.execute(
                """
                INSERT INTO profiles (id, name, phone, email, created_at, updated_at)
                VALUES (%s, %s, %s, %s, now(), now())
                """,
                (user.id, user.name or user.email or user.phone or f"User {user.id[:6]}", user.phone or "+000000000", user.email),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM profiles WHERE id = %s", (user.id,)).fetchone()
            return _profile_from_row(row)

    def get_profile(self, user_id: str) -> ProfileOut:
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            row = conn.execute("SELECT * FROM profiles WHERE id = %s", (user_id,)).fetchone()
            if not row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
            return _profile_from_row(row)

    def update_profile(self, user: AuthenticatedUser, payload: ProfileUpdate) -> ProfileOut:
        data = payload.model_dump(exclude_unset=True)
        if not data:
            return self.ensure_profile(user)
        self.ensure_profile(user)
        set_clauses = ", ".join(f"{k} = %s" for k in data)
        values = list(data.values()) + [user.id]
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            conn.execute(f"UPDATE profiles SET {set_clauses}, updated_at = now() WHERE id = %s", values)  # noqa: S608
            conn.commit()
            row = conn.execute("SELECT * FROM profiles WHERE id = %s", (user.id,)).fetchone()
            return _profile_from_row(row)

    def upsert_business_profile(self, owner_id: str, payload: BusinessProfileIn) -> BusinessProfileOut:
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            existing = conn.execute("SELECT * FROM business_profiles WHERE owner_id = %s", (owner_id,)).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE business_profiles SET shop_name = %s, activity_type = %s, location = %s, description = %s, updated_at = now()
                    WHERE owner_id = %s
                    """,
                    (payload.shop_name, payload.activity_type, payload.location, payload.description, owner_id),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO business_profiles (id, owner_id, shop_name, activity_type, location, description, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, now(), now())
                    """,
                    (str(uuid4()), owner_id, payload.shop_name, payload.activity_type, payload.location, payload.description),
                )
            conn.execute("UPDATE profiles SET account_type = 'business', updated_at = now() WHERE id = %s", (owner_id,))
            conn.commit()
            row = conn.execute("SELECT * FROM business_profiles WHERE owner_id = %s", (owner_id,)).fetchone()
            return BusinessProfileOut(
                id=str(row["id"]),
                owner_id=str(row["owner_id"]),
                shop_name=row["shop_name"],
                activity_type=row["activity_type"],
                location=row["location"],
                description=row["description"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

    def current_business_profile(self, owner_id: str) -> BusinessProfileOut | None:
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            row = conn.execute("SELECT * FROM business_profiles WHERE owner_id = %s", (owner_id,)).fetchone()
            if not row:
                return None
            return BusinessProfileOut(
                id=str(row["id"]),
                owner_id=str(row["owner_id"]),
                shop_name=row["shop_name"],
                activity_type=row["activity_type"],
                location=row["location"],
                description=row["description"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

    # ── QR tokens ─────────────────────────────────────────────────────

    def rotate_qr_token(self, user_id: str, ttl_minutes: int = 10) -> dict[str, object]:
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            token = str(uuid4())
            now = utcnow()
            expires_at = now + timedelta(minutes=ttl_minutes)
            conn.execute(
                "INSERT INTO qr_tokens (token, user_id, expires_at, created_at) VALUES (%s, %s, %s, %s)",
                (token, user_id, expires_at, now),
            )
            conn.commit()
            return {"token": token, "user_id": user_id, "expires_at": expires_at, "created_at": now}

    def current_qr_token(self, user_id: str) -> dict[str, object]:
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            row = conn.execute(
                "SELECT * FROM qr_tokens WHERE user_id = %s AND expires_at > now() ORDER BY created_at DESC LIMIT 1",
                (user_id,),
            ).fetchone()
            if row:
                return {"token": str(row["token"]), "user_id": str(row["user_id"]), "expires_at": row["expires_at"], "created_at": row["created_at"]}
        return self.rotate_qr_token(user_id)

    def resolve_qr_token(self, token: str) -> ProfileOut:
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            row = conn.execute("SELECT user_id FROM qr_tokens WHERE token = %s AND expires_at > now()", (token,)).fetchone()
            if not row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="QR token is invalid or expired")
        return self.get_profile(str(row["user_id"]))

    # ── Debts ─────────────────────────────────────────────────────────

    def create_debt(self, creditor_id: str, payload: DebtCreate) -> DebtOut:
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            self._refresh_overdue(conn)
            debt_id = str(uuid4())
            conn.execute(
                """
                INSERT INTO debts (id, creditor_id, debtor_id, debtor_name, amount, currency, description, due_date,
                                   status, invoice_url, notes, group_id, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending_confirmation', %s, %s, %s, now(), now())
                """,
                (debt_id, creditor_id, payload.debtor_id, payload.debtor_name, payload.amount, payload.currency,
                 payload.description, payload.due_date, payload.invoice_url, payload.notes, payload.group_id),
            )
            self._add_event_raw(conn, debt_id, creditor_id, "debt_created", "Debt created and awaiting debtor confirmation")
            if payload.debtor_id:
                self._notify_raw(
                    conn, payload.debtor_id, "debt_created", "New debt requires confirmation",
                    f"{payload.debtor_name}, confirm {payload.amount} {payload.currency}: {payload.description}",
                    debt_id, merchant_id=creditor_id,
                )
            conn.commit()
            row = conn.execute("SELECT * FROM debts WHERE id = %s", (debt_id,)).fetchone()
            return _debt_from_row(row)

    def list_debts_for_user(self, user_id: str) -> list[DebtOut]:
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            self._refresh_overdue(conn)
            conn.commit()
            rows = conn.execute(
                """
                SELECT d.* FROM debts d
                WHERE d.creditor_id = %s
                   OR d.debtor_id = %s
                   OR EXISTS (
                       SELECT 1 FROM group_members gm
                       WHERE gm.group_id = d.group_id AND gm.user_id = %s AND gm.status = 'accepted'
                   )
                ORDER BY d.created_at DESC
                """,
                (user_id, user_id, user_id),
            ).fetchall()
            return [_debt_from_row(r) for r in rows]

    def get_authorized_debt(self, user_id: str, debt_id: str) -> DebtOut:
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            self._refresh_overdue(conn)
            conn.commit()
            row = self._can_view_debt(conn, user_id, debt_id)
            if not row:
                # Check if debt exists at all
                exists = conn.execute("SELECT 1 FROM debts WHERE id = %s", (debt_id,)).fetchone()
                if not exists:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Debt not found")
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot access this debt")
            return _debt_from_row(row)

    def accept_debt(self, user_id: str, debt_id: str) -> DebtOut:
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            row = self._can_view_debt(conn, user_id, debt_id)
            if not row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Debt not found")
            if str(row["debtor_id"]) != user_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the debtor can accept this debt")
            if row["status"] not in ("pending_confirmation", "change_requested"):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Debt cannot be accepted from its current state")
            conn.execute("UPDATE debts SET status = 'active', confirmed_at = now(), updated_at = now() WHERE id = %s", (debt_id,))
            self._add_event_raw(conn, debt_id, user_id, "debt_confirmed", "Debtor accepted the debt")
            self._notify_raw(conn, str(row["creditor_id"]), "debt_confirmed", "Debt accepted",
                             f"{row['debtor_name']} accepted {row['amount']} {row['currency'].strip()}", debt_id)
            conn.commit()
            updated = conn.execute("SELECT * FROM debts WHERE id = %s", (debt_id,)).fetchone()
            return _debt_from_row(updated)

    def reject_debt(self, user_id: str, debt_id: str, message: str | None = None) -> DebtOut:
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            row = self._can_view_debt(conn, user_id, debt_id)
            if not row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Debt not found")
            if str(row["debtor_id"]) != user_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the debtor can reject this debt")
            if row["status"] != "pending_confirmation":
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Debt cannot be rejected from its current state")
            conn.execute("UPDATE debts SET status = 'rejected', updated_at = now() WHERE id = %s", (debt_id,))
            self._add_event_raw(conn, debt_id, user_id, "debt_rejected", message)
            self._notify_raw(conn, str(row["creditor_id"]), "debt_rejected", "Debt rejected",
                             message or f"{row['debtor_name']} rejected the debt", debt_id)
            conn.commit()
            updated = conn.execute("SELECT * FROM debts WHERE id = %s", (debt_id,)).fetchone()
            return _debt_from_row(updated)

    def request_debt_change(self, user_id: str, debt_id: str, payload: DebtChangeRequest) -> DebtOut:
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            row = self._can_view_debt(conn, user_id, debt_id)
            if not row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Debt not found")
            if str(row["debtor_id"]) != user_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the debtor can request changes")
            if row["status"] != "pending_confirmation":
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only pending debts can be changed")
            conn.execute("UPDATE debts SET status = 'change_requested', updated_at = now() WHERE id = %s", (debt_id,))
            self._add_event_raw(conn, debt_id, user_id, "debt_change_requested", payload.message, payload.model_dump(exclude_none=True))
            self._notify_raw(conn, str(row["creditor_id"]), "debt_change_requested", "Debt change requested", payload.message, debt_id)
            conn.commit()
            updated = conn.execute("SELECT * FROM debts WHERE id = %s", (debt_id,)).fetchone()
            return _debt_from_row(updated)

    def mark_paid(self, user_id: str, debt_id: str, payload: PaymentRequest) -> PaymentConfirmationOut:
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            row = self._can_view_debt(conn, user_id, debt_id)
            if not row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Debt not found")
            if str(row["debtor_id"]) != user_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the debtor can mark the debt paid")
            if row["status"] not in ("active", "overdue"):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Debt must be active or overdue")
            conn.execute("UPDATE debts SET status = 'payment_pending_confirmation', updated_at = now() WHERE id = %s", (debt_id,))
            confirmation_id = str(uuid4())
            conn.execute(
                """
                INSERT INTO payment_confirmations (id, debt_id, debtor_id, creditor_id, status, note, requested_at)
                VALUES (%s, %s, %s, %s, 'pending_creditor_confirmation', %s, now())
                """,
                (confirmation_id, debt_id, user_id, str(row["creditor_id"]), payload.note),
            )
            self._add_event_raw(conn, debt_id, user_id, "payment_requested", payload.note)
            self._notify_raw(conn, str(row["creditor_id"]), "payment_requested", "Payment confirmation requested",
                             f"{row['debtor_name']} marked the debt as paid", debt_id)
            conn.commit()
            pc = conn.execute("SELECT * FROM payment_confirmations WHERE id = %s", (confirmation_id,)).fetchone()
            return PaymentConfirmationOut(
                id=str(pc["id"]), debt_id=str(pc["debt_id"]), debtor_id=str(pc["debtor_id"]),
                creditor_id=str(pc["creditor_id"]), status=pc["status"], note=pc.get("note"),
                requested_at=pc["requested_at"], confirmed_at=pc.get("confirmed_at"),
            )

    def confirm_payment(self, user_id: str, debt_id: str) -> DebtOut:
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            row = self._can_view_debt(conn, user_id, debt_id)
            if not row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Debt not found")
            if str(row["creditor_id"]) != user_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the creditor can confirm payment")
            if row["status"] != "payment_pending_confirmation":
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Payment is not awaiting confirmation")
            conn.execute("UPDATE debts SET status = 'paid', paid_at = now(), updated_at = now() WHERE id = %s", (debt_id,))
            conn.execute("UPDATE payment_confirmations SET status = 'confirmed', confirmed_at = now() WHERE debt_id = %s", (debt_id,))
            self._add_event_raw(conn, debt_id, user_id, "payment_confirmed", "Creditor confirmed receiving payment")
            debtor_id = str(row["debtor_id"]) if row.get("debtor_id") else None
            if debtor_id:
                now = utcnow()
                delta = 5 if now.date() <= row["due_date"] else -2
                self._change_trust_score_raw(conn, debtor_id, delta, "payment_confirmed", debt_id)
                self._notify_raw(conn, debtor_id, "payment_confirmed", "Payment confirmed",
                                 f"{row['amount']} {row['currency'].strip()} was confirmed as paid", debt_id)
            conn.commit()
            updated = conn.execute("SELECT * FROM debts WHERE id = %s", (debt_id,)).fetchone()
            return _debt_from_row(updated)

    # ── Events & attachments ──────────────────────────────────────────

    def list_events(self, user_id: str, debt_id: str) -> list[DebtEventOut]:
        self.get_authorized_debt(user_id, debt_id)
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            rows = conn.execute(
                "SELECT * FROM debt_events WHERE debt_id = %s ORDER BY created_at", (debt_id,)
            ).fetchall()
            return [
                DebtEventOut(
                    id=str(r["id"]), debt_id=str(r["debt_id"]),
                    actor_id=str(r["actor_id"]) if r.get("actor_id") else None,
                    event_type=r["event_type"], message=r.get("message"),
                    metadata=r.get("metadata") or {},
                    created_at=r["created_at"],
                )
                for r in rows
            ]

    async def add_attachment(self, user_id: str, debt_id: str, attachment_type: AttachmentType, file: UploadFile) -> AttachmentOut:
        self.get_authorized_debt(user_id, debt_id)
        att_id = str(uuid4())
        file_name = file.filename or "attachment"
        storage_path = f"attachments/{debt_id}/{att_id}-{file_name}"
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            conn.execute(
                """
                INSERT INTO attachments (id, debt_id, uploader_id, attachment_type, file_name, content_type, storage_path, public_url, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now())
                """,
                (att_id, debt_id, user_id, attachment_type.value, file_name, file.content_type, storage_path, f"mock://{storage_path}"),
            )
            conn.commit()
        await file.close()
        return AttachmentOut(
            id=att_id, debt_id=debt_id, uploader_id=user_id,
            attachment_type=attachment_type, file_name=file_name,
            content_type=file.content_type, url=f"mock://{storage_path}",
            created_at=utcnow(),
        )

    def list_attachments(self, user_id: str, debt_id: str) -> list[AttachmentOut]:
        self.get_authorized_debt(user_id, debt_id)
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            rows = conn.execute("SELECT * FROM attachments WHERE debt_id = %s ORDER BY created_at", (debt_id,)).fetchall()
            return [
                AttachmentOut(
                    id=str(r["id"]), debt_id=str(r["debt_id"]), uploader_id=str(r["uploader_id"]),
                    attachment_type=r["attachment_type"], file_name=r["file_name"],
                    content_type=r.get("content_type"), url=r.get("public_url") or r["storage_path"],
                    created_at=r["created_at"],
                )
                for r in rows
            ]

    # ── Dashboards ────────────────────────────────────────────────────

    def debtor_dashboard(self, user_id: str) -> DebtorDashboardOut:
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            self._refresh_overdue(conn)
            conn.commit()

            profile = conn.execute("SELECT trust_score FROM profiles WHERE id = %s", (user_id,)).fetchone()
            trust_score = profile["trust_score"] if profile else 50

            debts = conn.execute(
                """
                SELECT * FROM debts WHERE debtor_id = %s ORDER BY created_at DESC
                """,
                (user_id,),
            ).fetchall()

            current_statuses = {"active", "overdue", "payment_pending_confirmation"}
            current = [d for d in debts if d["status"] in current_statuses]
            total = sum((d["amount"] for d in current), Decimal("0"))
            today = date.today()
            due_soon = [d for d in current if today <= d["due_date"] <= today + timedelta(days=3)]
            overdue = [d for d in current if d["status"] == "overdue"]
            creditors = sorted({str(d["creditor_id"]) for d in current})

            return DebtorDashboardOut(
                total_current_debt=total,
                due_soon_count=len(due_soon),
                overdue_count=len(overdue),
                creditors=creditors,
                trust_score=trust_score,
                debts=[_debt_from_row(d) for d in debts],
            )

    def creditor_dashboard(self, user_id: str) -> CreditorDashboardOut:
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            self._refresh_overdue(conn)
            conn.commit()

            debts = conn.execute(
                "SELECT * FROM debts WHERE creditor_id = %s ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()

            receivable_statuses = {"active", "overdue", "payment_pending_confirmation"}
            receivable = [d for d in debts if d["status"] in receivable_statuses]
            total = sum((d["amount"] for d in receivable), Decimal("0"))
            debtor_ids = {str(d["debtor_id"]) for d in debts if d.get("debtor_id")}

            best_customers: list[ProfileOut] = []
            if debtor_ids:
                placeholders = ", ".join(["%s"] * len(debtor_ids))
                rows = conn.execute(
                    f"SELECT * FROM profiles WHERE id IN ({placeholders}) ORDER BY trust_score DESC LIMIT 5",  # noqa: S608
                    list(debtor_ids),
                ).fetchall()
                best_customers = [_profile_from_row(r) for r in rows]

            overdue = [d for d in debts if d["status"] == "overdue"]
            alerts = [f"{d['debtor_name']} is overdue on {d['amount']} {d['currency'].strip()}" for d in overdue]

            return CreditorDashboardOut(
                total_receivable=total,
                debtor_count=len(debtor_ids),
                active_count=len([d for d in debts if d["status"] == "active"]),
                overdue_count=len(overdue),
                paid_count=len([d for d in debts if d["status"] == "paid"]),
                best_customers=best_customers,
                alerts=alerts,
                debts=[_debt_from_row(d) for d in debts],
            )

    # ── Notifications ─────────────────────────────────────────────────

    def list_notifications(self, user_id: str) -> list[NotificationOut]:
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            rows = conn.execute(
                "SELECT * FROM notifications WHERE user_id = %s ORDER BY created_at DESC", (user_id,)
            ).fetchall()
            return [
                NotificationOut(
                    id=str(r["id"]), user_id=str(r["user_id"]),
                    notification_type=r["notification_type"], title=r["title"], body=r["body"],
                    debt_id=str(r["debt_id"]) if r.get("debt_id") else None,
                    read_at=r.get("read_at"), whatsapp_attempted=r["whatsapp_attempted"],
                    created_at=r["created_at"],
                )
                for r in rows
            ]

    def read_notification(self, user_id: str, notification_id: str) -> NotificationOut:
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            conn.execute(
                "UPDATE notifications SET read_at = now() WHERE id = %s AND user_id = %s AND read_at IS NULL",
                (notification_id, user_id),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM notifications WHERE id = %s AND user_id = %s", (notification_id, user_id)).fetchone()
            if not row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
            return NotificationOut(
                id=str(row["id"]), user_id=str(row["user_id"]),
                notification_type=row["notification_type"], title=row["title"], body=row["body"],
                debt_id=str(row["debt_id"]) if row.get("debt_id") else None,
                read_at=row.get("read_at"), whatsapp_attempted=row["whatsapp_attempted"],
                created_at=row["created_at"],
            )

    def set_notification_preference(self, user_id: str, payload: NotificationPreferenceIn) -> NotificationPreferenceOut:
        with self._pool.connection() as conn:
            conn.execute(
                """
                INSERT INTO merchant_notification_preferences (user_id, merchant_id, whatsapp_enabled, updated_at)
                VALUES (%s, %s, %s, now())
                ON CONFLICT (user_id, merchant_id)
                DO UPDATE SET whatsapp_enabled = EXCLUDED.whatsapp_enabled, updated_at = now()
                """,
                (user_id, payload.merchant_id, payload.whatsapp_enabled),
            )
            conn.commit()
        return NotificationPreferenceOut(user_id=user_id, merchant_id=payload.merchant_id, whatsapp_enabled=payload.whatsapp_enabled, updated_at=utcnow())

    def list_trust_score_events(self, user_id: str) -> list[TrustScoreEventOut]:
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            rows = conn.execute(
                "SELECT * FROM trust_score_events WHERE user_id = %s ORDER BY created_at DESC", (user_id,)
            ).fetchall()
            return [
                TrustScoreEventOut(
                    id=str(r["id"]), user_id=str(r["user_id"]),
                    delta=r["delta"], score_after=r["score_after"],
                    reason=r["reason"],
                    debt_id=str(r["debt_id"]) if r.get("debt_id") else None,
                    created_at=r["created_at"],
                )
                for r in rows
            ]

    # ── Groups ────────────────────────────────────────────────────────

    def create_group(self, owner_id: str, payload: GroupCreate) -> GroupOut:
        group_id = str(uuid4())
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            conn.execute(
                "INSERT INTO groups (id, owner_id, name, description, created_at) VALUES (%s, %s, %s, %s, now())",
                (group_id, owner_id, payload.name, payload.description),
            )
            conn.execute(
                "INSERT INTO group_members (id, group_id, user_id, status, created_at, accepted_at) VALUES (%s, %s, %s, 'accepted', now(), now())",
                (str(uuid4()), group_id, owner_id),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM groups WHERE id = %s", (group_id,)).fetchone()
            return GroupOut(id=str(row["id"]), owner_id=str(row["owner_id"]), name=row["name"], description=row.get("description"), created_at=row["created_at"])

    def list_groups(self, user_id: str) -> list[GroupOut]:
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            rows = conn.execute(
                """
                SELECT g.* FROM groups g
                JOIN group_members gm ON gm.group_id = g.id
                WHERE gm.user_id = %s AND gm.status = 'accepted'
                ORDER BY g.created_at DESC
                """,
                (user_id,),
            ).fetchall()
            return [
                GroupOut(id=str(r["id"]), owner_id=str(r["owner_id"]), name=r["name"], description=r.get("description"), created_at=r["created_at"])
                for r in rows
            ]

    def invite_group_member(self, actor_id: str, group_id: str, payload: GroupInviteIn) -> GroupMemberOut:
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            group = conn.execute("SELECT * FROM groups WHERE id = %s", (group_id,)).fetchone()
            if not group:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
            if str(group["owner_id"]) != actor_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the group owner can invite members")
            existing = conn.execute(
                "SELECT * FROM group_members WHERE group_id = %s AND user_id = %s", (group_id, payload.user_id)
            ).fetchone()
            if existing:
                return GroupMemberOut(
                    id=str(existing["id"]), group_id=str(existing["group_id"]), user_id=str(existing["user_id"]),
                    status=existing["status"], created_at=existing["created_at"], accepted_at=existing.get("accepted_at"),
                )
            member_id = str(uuid4())
            conn.execute(
                "INSERT INTO group_members (id, group_id, user_id, status, created_at) VALUES (%s, %s, %s, 'pending', now())",
                (member_id, group_id, payload.user_id),
            )
            self._notify_raw(conn, payload.user_id, "debt_created", "Group invitation", f"You were invited to {group['name']}", None)
            conn.commit()
            row = conn.execute("SELECT * FROM group_members WHERE id = %s", (member_id,)).fetchone()
            return GroupMemberOut(
                id=str(row["id"]), group_id=str(row["group_id"]), user_id=str(row["user_id"]),
                status=row["status"], created_at=row["created_at"], accepted_at=row.get("accepted_at"),
            )

    def accept_group_invite(self, user_id: str, group_id: str) -> GroupMemberOut:
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            conn.execute(
                "UPDATE group_members SET status = 'accepted', accepted_at = now() WHERE group_id = %s AND user_id = %s AND status = 'pending'",
                (group_id, user_id),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM group_members WHERE group_id = %s AND user_id = %s", (group_id, user_id)).fetchone()
            if not row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group invitation not found")
            return GroupMemberOut(
                id=str(row["id"]), group_id=str(row["group_id"]), user_id=str(row["user_id"]),
                status=row["status"], created_at=row["created_at"], accepted_at=row.get("accepted_at"),
            )

    def group_debts(self, user_id: str, group_id: str) -> list[DebtOut]:
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            member = conn.execute(
                "SELECT 1 FROM group_members WHERE group_id = %s AND user_id = %s AND status = 'accepted'",
                (group_id, user_id),
            ).fetchone()
            if not member:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not an accepted group member")
            rows = conn.execute(
                """
                SELECT d.* FROM debts d
                WHERE d.group_id = %s
                   OR d.creditor_id IN (SELECT gm.user_id FROM group_members gm WHERE gm.group_id = %s AND gm.status = 'accepted')
                   OR d.debtor_id IN (SELECT gm.user_id FROM group_members gm WHERE gm.group_id = %s AND gm.status = 'accepted')
                ORDER BY d.created_at DESC
                """,
                (group_id, group_id, group_id),
            ).fetchall()
            return [_debt_from_row(r) for r in rows]

    def create_settlement(self, payer_id: str, group_id: str, payload: SettlementCreate) -> SettlementOut:
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            member = conn.execute(
                "SELECT 1 FROM group_members WHERE group_id = %s AND user_id = %s AND status = 'accepted'",
                (group_id, payer_id),
            ).fetchone()
            if not member:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not an accepted group member")
            debtor_member = conn.execute(
                "SELECT 1 FROM group_members WHERE group_id = %s AND user_id = %s AND status = 'accepted'",
                (group_id, payload.debtor_id),
            ).fetchone()
            if not debtor_member:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Debtor must be an accepted group member")
            settlement_id = str(uuid4())
            conn.execute(
                """
                INSERT INTO group_settlements (id, group_id, payer_id, debtor_id, amount, currency, note, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, now())
                """,
                (settlement_id, group_id, payer_id, payload.debtor_id, payload.amount, payload.currency, payload.note),
            )
            self._notify_raw(conn, payload.debtor_id, "payment_confirmed", "Group settlement recorded",
                             f"{payer_id} paid {payload.amount} {payload.currency} for you", None)
            conn.commit()
            return SettlementOut(
                id=settlement_id, group_id=group_id, payer_id=payer_id,
                debtor_id=payload.debtor_id, amount=payload.amount, currency=payload.currency,
                note=payload.note, created_at=utcnow(),
            )

    # ── AI / analytics ────────────────────────────────────────────────

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
