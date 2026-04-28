"""Postgres-backed repository using psycopg connection pool."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.core.config import get_settings
from app.core.security import AuthenticatedUser
from app.db.supabase import get_supabase_client, unwrap_response
from app.repositories.attachment_retention import apply_attachment_access_metadata, retention_for_debt
from app.repositories.base import Repository
from app.repositories.local_receipt_store import create_local_receipt_url, has_local_receipt, save_local_receipt
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
    utcnow,
)
from app.services.whatsapp.provider import SendOutcome, SendResult, StatusUpdate


def _profile_from_row(row: dict) -> ProfileOut:
    return ProfileOut(
        id=str(row["id"]),
        name=row["name"],
        phone=row["phone"],
        email=row.get("email"),
        account_type=row["account_type"],
        tax_id=row.get("tax_id"),
        commercial_registration=row.get("commercial_registration"),
        shop_name=row.get("shop_name"),
        activity_type=row.get("activity_type"),
        shop_location=row.get("shop_location"),
        shop_description=row.get("shop_description"),
        whatsapp_enabled=row["whatsapp_enabled"],
        ai_enabled=row["ai_enabled"],
        commitment_score=row["commitment_score"],
        preferred_language=row.get("preferred_language", "ar"),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
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
        reminder_dates=list(row.get("reminder_dates") or []),
        status=row["status"],
        invoice_url=row.get("invoice_url"),
        notes=row.get("notes"),
        group_id=str(row["group_id"]) if row.get("group_id") else None,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        confirmed_at=row.get("confirmed_at"),
        paid_at=row.get("paid_at"),
    )


def _late_penalty(missed_count: int) -> int:
    """Late-payment / missed-reminder commitment-indicator penalty.

    Base penalty is -2, doubled per already-missed reminder: -2, -4, -8, -16, ...
    """
    return -2 * (2 ** missed_count)


_PROFILE_SELECT = """
SELECT p.*, bp.shop_name, bp.activity_type,
       bp.location AS shop_location, bp.description AS shop_description
FROM profiles p
LEFT JOIN business_profiles bp ON bp.owner_id = p.id
"""


class PostgresRepository(Repository):
    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool
        self._reminder_dates_supported: bool | None = None

    def _has_reminder_dates(self, conn) -> bool:
        """Cache whether migration 006 (reminder_dates column) has been applied."""
        if self._reminder_dates_supported is None:
            row = conn.execute(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'debts' AND column_name = 'reminder_dates'
                """,
            ).fetchone()
            self._reminder_dates_supported = row is not None
        return self._reminder_dates_supported

    # ── helpers ────────────────────────────────────────────────────────

    def _refresh_overdue(self, conn) -> None:
        """Move active debts past due_date to overdue, then apply missed-reminder penalties."""
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
                self._change_commitment_score_raw(conn, debtor_id, -5, "debt_overdue", debt_id)
                self._notify_raw(conn, debtor_id, "overdue", "Debt overdue", f"{amount} {currency} is overdue", debt_id, merchant_id=creditor_id)
        if self._has_reminder_dates(conn):
            self._apply_missed_reminders(conn)

    def _apply_missed_reminders(self, conn) -> None:
        """For every unpaid debt, fire a one-time penalty for each reminder date that has passed."""
        unpaid = ("active", "overdue", "payment_pending_confirmation")
        rows = conn.execute(
            """
            SELECT id, debtor_id, creditor_id, amount, currency, reminder_dates
            FROM debts
            WHERE status = ANY(%s) AND debtor_id IS NOT NULL AND array_length(reminder_dates, 1) > 0
            """,
            (list(unpaid),),
        ).fetchall()
        for row in rows:
            debt_id = str(row["id"])
            debtor_id = str(row["debtor_id"])
            creditor_id = str(row["creditor_id"])
            amount = row["amount"]
            currency = row["currency"].strip()
            reminders = sorted(row["reminder_dates"] or [])
            applied_rows = conn.execute(
                """
                SELECT reminder_date FROM commitment_score_events
                WHERE debt_id = %s AND reason = 'missed_reminder' AND reminder_date IS NOT NULL
                """,
                (debt_id,),
            ).fetchall()
            already = {r["reminder_date"] for r in applied_rows}
            for reminder in reminders:
                if reminder >= date.today() or reminder in already:
                    continue
                prior = conn.execute(
                    "SELECT COUNT(*) AS n FROM commitment_score_events WHERE debt_id = %s AND reason = 'missed_reminder'",
                    (debt_id,),
                ).fetchone()
                prior_n = int(prior["n"]) if prior else 0
                self._change_commitment_score_raw(
                    conn, debtor_id, _late_penalty(prior_n), "missed_reminder", debt_id, reminder_date=reminder,
                )
                self._notify_raw(
                    conn, debtor_id, "overdue", "Reminder missed",
                    f"Reminder for {amount} {currency} on {reminder.isoformat()} passed unpaid",
                    debt_id, merchant_id=creditor_id,
                )
                already.add(reminder)

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

    def _notify_raw(
        self, conn, user_id: str, notification_type: str, title: str, body: str, debt_id: str | None, merchant_id: str | None = None
    ) -> str:
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

    def _change_commitment_score_raw(
        self, conn, user_id: str, delta: int, reason: str, debt_id: str | None = None, reminder_date=None,
    ) -> None:
        row = conn.execute("SELECT commitment_score FROM profiles WHERE id = %s", (user_id,)).fetchone()
        if not row:
            return
        # row may be a dict or tuple depending on cursor row_factory of the caller
        old_score = row[0] if not isinstance(row, dict) else row["commitment_score"]
        new_score = min(100, max(0, old_score + delta))
        conn.execute("UPDATE profiles SET commitment_score = %s, updated_at = now() WHERE id = %s", (new_score, user_id))
        conn.execute(
            """
            INSERT INTO commitment_score_events (id, user_id, delta, score_after, reason, debt_id, reminder_date, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, now())
            """,
            (str(uuid4()), user_id, delta, new_score, reason, debt_id, reminder_date),
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
            row = conn.execute(_PROFILE_SELECT + " WHERE p.id = %s", (user.id,)).fetchone()
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
            row = conn.execute(_PROFILE_SELECT + " WHERE p.id = %s", (user.id,)).fetchone()
            return _profile_from_row(row)

    def get_profile(self, user_id: str) -> ProfileOut:
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            row = conn.execute(_PROFILE_SELECT + " WHERE p.id = %s", (user_id,)).fetchone()
            if not row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
            return _profile_from_row(row)

    # Map ProfileUpdate's shop_* field names to business_profiles column names.
    _BUSINESS_FIELD_MAP = {
        "shop_name": "shop_name",
        "activity_type": "activity_type",
        "shop_location": "location",
        "shop_description": "description",
    }

    def _upsert_business_profile_fields(self, conn, owner_id: str, fields: dict) -> None:
        """Partial upsert into business_profiles. `fields` keys are business_profiles column names."""
        if not fields:
            return
        existing = conn.execute("SELECT 1 FROM business_profiles WHERE owner_id = %s", (owner_id,)).fetchone()
        if existing:
            set_clauses = ", ".join(f"{k} = %s" for k in fields)
            values = list(fields.values()) + [owner_id]
            conn.execute(f"UPDATE business_profiles SET {set_clauses}, updated_at = now() WHERE owner_id = %s", values)  # noqa: S608
        else:
            cols = ["id", "owner_id", *fields.keys(), "created_at", "updated_at"]
            placeholders = ", ".join(["%s"] * (len(fields) + 2) + ["now()", "now()"])
            values = [str(uuid4()), owner_id, *fields.values()]
            conn.execute(f"INSERT INTO business_profiles ({', '.join(cols)}) VALUES ({placeholders})", values)  # noqa: S608
        conn.execute("UPDATE profiles SET account_type = 'business', updated_at = now() WHERE id = %s AND account_type = 'debtor'", (owner_id,))

    def update_profile(self, user: AuthenticatedUser, payload: ProfileUpdate) -> ProfileOut:
        data = payload.model_dump(exclude_unset=True)
        if not data:
            return self.ensure_profile(user)
        self.ensure_profile(user)
        business_fields = {self._BUSINESS_FIELD_MAP[k]: data.pop(k) for k in list(data) if k in self._BUSINESS_FIELD_MAP}
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            if data:
                set_clauses = ", ".join(f"{k} = %s" for k in data)
                values = list(data.values()) + [user.id]
                conn.execute(f"UPDATE profiles SET {set_clauses}, updated_at = now() WHERE id = %s", values)  # noqa: S608
            self._upsert_business_profile_fields(conn, user.id, business_fields)
            conn.commit()
            row = conn.execute(_PROFILE_SELECT + " WHERE p.id = %s", (user.id,)).fetchone()
            return _profile_from_row(row)

    def upsert_business_profile(self, owner_id: str, payload: BusinessProfileIn) -> BusinessProfileOut:
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            self._upsert_business_profile_fields(
                conn,
                owner_id,
                {
                    "shop_name": payload.shop_name,
                    "activity_type": payload.activity_type,
                    "location": payload.location,
                    "description": payload.description,
                },
            )
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
            if self._has_reminder_dates(conn):
                conn.execute(
                    """
                    INSERT INTO debts (id, creditor_id, debtor_id, debtor_name, amount, currency, description, due_date,
                                       reminder_dates, status, invoice_url, notes, group_id, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending_confirmation', %s, %s, %s, now(), now())
                    """,
                    (
                        debt_id,
                        creditor_id,
                        payload.debtor_id,
                        payload.debtor_name,
                        payload.amount,
                        payload.currency,
                        payload.description,
                        payload.due_date,
                        sorted(set(payload.reminder_dates)),
                        payload.invoice_url,
                        payload.notes,
                        payload.group_id,
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO debts (id, creditor_id, debtor_id, debtor_name, amount, currency, description, due_date,
                                       status, invoice_url, notes, group_id, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending_confirmation', %s, %s, %s, now(), now())
                    """,
                    (
                        debt_id,
                        creditor_id,
                        payload.debtor_id,
                        payload.debtor_name,
                        payload.amount,
                        payload.currency,
                        payload.description,
                        payload.due_date,
                        payload.invoice_url,
                        payload.notes,
                        payload.group_id,
                    ),
                )
            self._add_event_raw(conn, debt_id, creditor_id, "debt_created", "Debt created and awaiting debtor confirmation")
            if payload.debtor_id:
                self._notify_raw(
                    conn,
                    payload.debtor_id,
                    "debt_created",
                    "New debt requires confirmation",
                    f"{payload.debtor_name}, confirm {payload.amount} {payload.currency}: {payload.description}",
                    debt_id,
                    merchant_id=creditor_id,
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
            if row["status"] != "pending_confirmation":
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Debt cannot be accepted from its current state")
            conn.execute("UPDATE debts SET status = 'active', confirmed_at = now(), updated_at = now() WHERE id = %s", (debt_id,))
            self._add_event_raw(conn, debt_id, user_id, "debt_confirmed", "Debtor accepted the debt")
            self._notify_raw(
                conn,
                str(row["creditor_id"]),
                "debt_confirmed",
                "Debt accepted",
                f"{row['debtor_name']} accepted {row['amount']} {row['currency'].strip()}",
                debt_id,
            )
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
            conn.execute("UPDATE debts SET status = 'edit_requested', updated_at = now() WHERE id = %s", (debt_id,))
            self._add_event_raw(conn, debt_id, user_id, "debt_edit_requested", payload.message, payload.model_dump(exclude_none=True, mode="json"))
            self._notify_raw(conn, str(row["creditor_id"]), "debt_edit_requested", "Debt edit requested", payload.message, debt_id)
            conn.commit()
            updated = conn.execute("SELECT * FROM debts WHERE id = %s", (debt_id,)).fetchone()
            return _debt_from_row(updated)

    def approve_edit_request(self, user_id: str, debt_id: str, payload: DebtEditApproval) -> DebtOut:
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            row = self._can_view_debt(conn, user_id, debt_id)
            if not row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Debt not found")
            if str(row["creditor_id"]) != user_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the creditor can decide on an edit request")
            if row["status"] != "edit_requested":
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No edit request awaits a decision")
            # Pull the latest edit-request payload (debtor's proposal) for audit + fallback values.
            ev = conn.execute(
                """
                SELECT metadata FROM debt_events
                WHERE debt_id = %s AND event_type = 'debt_edit_requested'
                ORDER BY created_at DESC LIMIT 1
                """,
                (debt_id,),
            ).fetchone()
            requested = (ev["metadata"] if ev else {}) or {}

            # Resolve final values: creditor override > debtor proposal > existing.
            final_amount: Decimal | None = None
            if payload.amount is not None:
                final_amount = payload.amount
            elif requested.get("requested_amount") is not None:
                final_amount = Decimal(str(requested["requested_amount"]))

            final_due_date: date | None = None
            if payload.due_date is not None:
                final_due_date = payload.due_date
            elif requested.get("requested_due_date") is not None:
                final_due_date = date.fromisoformat(str(requested["requested_due_date"]))

            final_description: str | None = None
            if payload.description is not None:
                final_description = payload.description
            elif isinstance(requested.get("requested_description"), str):
                final_description = requested["requested_description"]

            sets = ["status = 'pending_confirmation'", "updated_at = now()"]
            params: list[object] = []
            if final_amount is not None:
                sets.append("amount = %s")
                params.append(final_amount)
            if final_due_date is not None:
                sets.append("due_date = %s")
                params.append(final_due_date)
            if final_description is not None:
                sets.append("description = %s")
                params.append(final_description)
            params.append(debt_id)
            conn.execute(f"UPDATE debts SET {', '.join(sets)} WHERE id = %s", params)  # noqa: S608

            applied = {
                "requested": requested,
                "applied_amount": str(final_amount) if final_amount is not None else None,
                "applied_due_date": final_due_date.isoformat() if final_due_date else None,
                "applied_description": final_description,
            }
            self._add_event_raw(conn, debt_id, user_id, "debt_edit_approved", payload.message, applied)
            debtor_id = str(row["debtor_id"]) if row.get("debtor_id") else None
            if debtor_id:
                self._notify_raw(
                    conn, debtor_id, "debt_edit_approved", "Edit approved",
                    payload.message,
                    debt_id, merchant_id=str(row["creditor_id"]),
                )
            conn.commit()
            updated = conn.execute("SELECT * FROM debts WHERE id = %s", (debt_id,)).fetchone()
            return _debt_from_row(updated)

    def reject_edit_request(self, user_id: str, debt_id: str, message: str | None = None) -> DebtOut:
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            row = self._can_view_debt(conn, user_id, debt_id)
            if not row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Debt not found")
            if str(row["creditor_id"]) != user_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the creditor can decide on an edit request")
            if row["status"] != "edit_requested":
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No edit request awaits a decision")
            conn.execute("UPDATE debts SET status = 'pending_confirmation', updated_at = now() WHERE id = %s", (debt_id,))
            self._add_event_raw(conn, debt_id, user_id, "debt_edit_rejected", message)
            debtor_id = str(row["debtor_id"]) if row.get("debtor_id") else None
            if debtor_id:
                self._notify_raw(
                    conn, debtor_id, "debt_edit_rejected", "Edit rejected",
                    message or "Creditor declined your edit; original terms stand",
                    debt_id, merchant_id=str(row["creditor_id"]),
                )
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
            conn.execute(
                "UPDATE debts SET status = 'payment_pending_confirmation', updated_at = now() WHERE id = %s",
                (debt_id,),
            )
            confirmation_id = str(uuid4())
            conn.execute(
                """
                INSERT INTO payment_confirmations (id, debt_id, debtor_id, creditor_id, status, note, requested_at)
                VALUES (%s, %s, %s, %s, 'pending_creditor_confirmation', %s, now())
                """,
                (confirmation_id, debt_id, user_id, str(row["creditor_id"]), payload.note),
            )
            self._add_event_raw(conn, debt_id, user_id, "payment_requested", payload.note)
            self._notify_raw(
                conn,
                str(row["creditor_id"]),
                "payment_requested",
                "Payment confirmation requested",
                f"{row['debtor_name']} marked the debt as paid",
                debt_id,
            )
            conn.commit()
            pc = conn.execute("SELECT * FROM payment_confirmations WHERE id = %s", (confirmation_id,)).fetchone()
            return PaymentConfirmationOut(
                id=str(pc["id"]),
                debt_id=str(pc["debt_id"]),
                debtor_id=str(pc["debtor_id"]),
                creditor_id=str(pc["creditor_id"]),
                status=pc["status"],
                note=pc.get("note"),
                requested_at=pc["requested_at"],
                confirmed_at=pc.get("confirmed_at"),
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
                today = utcnow().date()
                if today < row["due_date"]:
                    self._change_commitment_score_raw(conn, debtor_id, 3, "paid_early", debt_id)
                elif today == row["due_date"]:
                    self._change_commitment_score_raw(conn, debtor_id, 1, "paid_on_time", debt_id)
                else:
                    missed_row = conn.execute(
                        "SELECT COUNT(*) AS n FROM commitment_score_events WHERE debt_id = %s AND reason = 'missed_reminder'",
                        (debt_id,),
                    ).fetchone()
                    missed = int(missed_row["n"]) if missed_row else 0
                    self._change_commitment_score_raw(conn, debtor_id, _late_penalty(missed), "paid_late", debt_id)
                self._notify_raw(
                    conn,
                    debtor_id,
                    "payment_confirmed",
                    "Payment confirmed",
                    f"{row['amount']} {row['currency'].strip()} was confirmed as paid",
                    debt_id,
                )
            conn.commit()
            updated = conn.execute("SELECT * FROM debts WHERE id = %s", (debt_id,)).fetchone()
            return _debt_from_row(updated)

    def cancel_debt(self, user_id: str, debt_id: str, message: str | None = None) -> DebtOut:
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            row = self._can_view_debt(conn, user_id, debt_id)
            if not row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Debt not found")
            if str(row["creditor_id"]) != user_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the creditor can cancel this debt")
            if row["status"] not in ("pending_confirmation", "edit_requested"):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Active or paid debts cannot be cancelled")
            conn.execute("UPDATE debts SET status = 'cancelled', updated_at = now() WHERE id = %s", (debt_id,))
            self._add_event_raw(conn, debt_id, user_id, "debt_cancelled", message)
            debtor_id = str(row["debtor_id"]) if row.get("debtor_id") else None
            if debtor_id:
                self._notify_raw(
                    conn,
                    debtor_id,
                    "debt_cancelled",
                    "Debt cancelled",
                    message or f"{row['amount']} {row['currency'].strip()} cancelled by creditor",
                    debt_id,
                )
            conn.commit()
            updated = conn.execute("SELECT * FROM debts WHERE id = %s", (debt_id,)).fetchone()
            return _debt_from_row(updated)

    # ── Events & attachments ──────────────────────────────────────────

    def list_events(self, user_id: str, debt_id: str) -> list[DebtEventOut]:
        self.get_authorized_debt(user_id, debt_id)
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            rows = conn.execute("SELECT * FROM debt_events WHERE debt_id = %s ORDER BY created_at", (debt_id,)).fetchall()
            return [
                DebtEventOut(
                    id=str(r["id"]),
                    debt_id=str(r["debt_id"]),
                    actor_id=str(r["actor_id"]) if r.get("actor_id") else None,
                    event_type=r["event_type"],
                    message=r.get("message"),
                    metadata=r.get("metadata") or {},
                    created_at=r["created_at"],
                )
                for r in rows
            ]

    async def add_attachment(self, user_id: str, debt_id: str, attachment_type: AttachmentType, file: UploadFile) -> AttachmentOut:
        debt = self.get_authorized_debt(user_id, debt_id)
        att_id = str(uuid4())
        file_name = file.filename or "attachment"
        safe_file_name = file_name.replace("/", "_").replace("\\", "_")
        storage_path = f"{debt_id}/{att_id}-{safe_file_name}"
        signed_url = await self._store_receipt_and_sign(storage_path, file)
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            conn.execute(
                """
                INSERT INTO attachments (id, debt_id, uploader_id, attachment_type, file_name, content_type, storage_path, public_url, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now())
                """,
                (att_id, debt_id, user_id, attachment_type.value, file_name, file.content_type, storage_path, signed_url),
            )
            self._add_event_raw(
                conn,
                debt_id,
                user_id,
                "attachment_uploaded",
                "Receipt attachment uploaded",
                {
                    "attachment_id": att_id,
                    "attachment_type": attachment_type.value,
                    "file_name": file_name,
                    "content_type": file.content_type,
                    "storage_path": storage_path,
                },
            )
            conn.commit()
        attachment = AttachmentOut(
            id=att_id,
            debt_id=debt_id,
            uploader_id=user_id,
            attachment_type=attachment_type,
            file_name=file_name,
            content_type=file.content_type,
            url=signed_url,
            created_at=utcnow(),
        )
        return apply_attachment_access_metadata(attachment, debt, signed_url)

    def list_attachments(self, user_id: str, debt_id: str) -> list[AttachmentOut]:
        debt = self.get_authorized_debt(user_id, debt_id)
        retention_state, _ = retention_for_debt(debt)
        if retention_state.value == "retention_expired":
            return []
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            rows = conn.execute("SELECT * FROM attachments WHERE debt_id = %s ORDER BY created_at", (debt_id,)).fetchall()
            return [
                apply_attachment_access_metadata(self._attachment_from_row(r), debt, self._signed_receipt_url(r["storage_path"]))
                for r in rows
            ]

    async def _store_receipt_and_sign(self, storage_path: str, file: UploadFile) -> str:
        settings = get_settings()
        bucket_name = settings.supabase_storage_bucket
        client = get_supabase_client()
        content = await file.read()
        await file.close()
        if client is None:
            return save_local_receipt(storage_path, content, file.content_type, file.filename or "attachment")

        bucket = client.storage.from_(bucket_name)
        bucket.upload(
            storage_path,
            content,
            {"content-type": file.content_type or "application/octet-stream", "upsert": "false"},
        )
        return self._signed_receipt_url(storage_path)

    def _signed_receipt_url(self, storage_path: str) -> str:
        settings = get_settings()
        client = get_supabase_client()
        if client is None:
            if has_local_receipt(storage_path):
                return create_local_receipt_url(storage_path)
            return f"{settings.api_prefix}/receipt-files/missing/receipt"
        response = client.storage.from_(settings.supabase_storage_bucket).create_signed_url(
            storage_path,
            settings.receipt_signed_url_ttl_seconds,
        )
        data = unwrap_response(response)
        if isinstance(data, dict):
            return data.get("signedURL") or data.get("signedUrl") or data.get("signed_url") or data.get("url") or f"mock://{settings.supabase_storage_bucket}/{storage_path}"
        return str(data)

    def _attachment_from_row(self, row: dict) -> AttachmentOut:
        return AttachmentOut(
            id=str(row["id"]),
            debt_id=str(row["debt_id"]),
            uploader_id=str(row["uploader_id"]),
            attachment_type=row["attachment_type"],
            file_name=row["file_name"],
            content_type=row.get("content_type"),
            url=row.get("public_url") or row["storage_path"],
            created_at=row["created_at"],
        )

    # ── Dashboards ────────────────────────────────────────────────────

    def debtor_dashboard(self, user_id: str) -> DebtorDashboardOut:
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            self._refresh_overdue(conn)
            conn.commit()

            profile = conn.execute("SELECT commitment_score FROM profiles WHERE id = %s", (user_id,)).fetchone()
            commitment_score = profile["commitment_score"] if profile else 50

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
                commitment_score=commitment_score,
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
                    f"{_PROFILE_SELECT} WHERE p.id IN ({placeholders}) ORDER BY p.commitment_score DESC LIMIT 5",  # noqa: S608
                    list(debtor_ids),
                ).fetchall()
                best_customers = [_profile_from_row(r) for r in rows]

            delayed = [d for d in debts if d["status"] == "overdue"]
            alerts = [f"{d['debtor_name']} is delayed on {d['amount']} {d['currency'].strip()}" for d in delayed]

            return CreditorDashboardOut(
                total_receivable=total,
                debtor_count=len(debtor_ids),
                active_count=len([d for d in debts if d["status"] == "active"]),
                overdue_count=len(delayed),
                paid_count=len([d for d in debts if d["status"] == "paid"]),
                best_customers=best_customers,
                alerts=alerts,
                debts=[_debt_from_row(d) for d in debts],
            )

    # ── Notifications ─────────────────────────────────────────────────

    def list_notifications(self, user_id: str) -> list[NotificationOut]:
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            rows = conn.execute("SELECT * FROM notifications WHERE user_id = %s ORDER BY created_at DESC", (user_id,)).fetchall()
            return [
                NotificationOut(
                    id=str(r["id"]),
                    user_id=str(r["user_id"]),
                    notification_type=r["notification_type"],
                    title=r["title"],
                    body=r["body"],
                    debt_id=str(r["debt_id"]) if r.get("debt_id") else None,
                    read_at=r.get("read_at"),
                    whatsapp_attempted=r["whatsapp_attempted"],
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
                id=str(row["id"]),
                user_id=str(row["user_id"]),
                notification_type=row["notification_type"],
                title=row["title"],
                body=row["body"],
                debt_id=str(row["debt_id"]) if row.get("debt_id") else None,
                read_at=row.get("read_at"),
                whatsapp_attempted=row["whatsapp_attempted"],
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
        return NotificationPreferenceOut(
            user_id=user_id, merchant_id=payload.merchant_id, whatsapp_enabled=payload.whatsapp_enabled, updated_at=utcnow()
        )

    def list_commitment_score_events(self, user_id: str) -> list[CommitmentScoreEventOut]:
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            rows = conn.execute("SELECT * FROM commitment_score_events WHERE user_id = %s ORDER BY created_at DESC", (user_id,)).fetchall()
            return [
                CommitmentScoreEventOut(
                    id=str(r["id"]),
                    user_id=str(r["user_id"]),
                    delta=r["delta"],
                    score_after=r["score_after"],
                    reason=r["reason"],
                    debt_id=str(r["debt_id"]) if r.get("debt_id") else None,
                    reminder_date=r.get("reminder_date"),
                    created_at=r["created_at"],
                )
                for r in rows
            ]

    # ── WhatsApp delivery state ───────────────────────────────────────

    def mark_whatsapp_attempted(self, notification_id: str, result: SendResult) -> None:
        if result.outcome == SendOutcome.sent:
            sql = """
                UPDATE notifications
                   SET whatsapp_attempted = true,
                       whatsapp_provider_ref = %s
                 WHERE id = %s
            """
            params = (result.provider_ref, notification_id)
        else:
            sql = """
                UPDATE notifications
                   SET whatsapp_attempted = true,
                       whatsapp_delivered = false,
                       whatsapp_failed_reason = %s
                 WHERE id = %s
            """
            params = (result.failed_reason, notification_id)
        with self._pool.connection() as conn:
            conn.execute(sql, params)
            conn.commit()

    def apply_whatsapp_status(self, update: StatusUpdate) -> bool:
        sql = """
            UPDATE notifications
               SET whatsapp_delivered = CASE
                       WHEN %(status)s = 'delivered' THEN true
                       WHEN %(status)s = 'failed' AND COALESCE(whatsapp_delivered, false) = false THEN false
                       ELSE whatsapp_delivered
                   END,
                   whatsapp_failed_reason = CASE
                       WHEN %(status)s = 'failed' AND whatsapp_failed_reason IS NULL THEN %(failed_reason)s
                       ELSE whatsapp_failed_reason
                   END,
                   whatsapp_status_received_at = COALESCE(whatsapp_status_received_at, %(occurred_at)s)
             WHERE whatsapp_provider_ref = %(provider_ref)s
        """
        with self._pool.connection() as conn:
            cur = conn.execute(
                sql,
                {
                    "status": update.status,
                    "failed_reason": update.failed_reason,
                    "occurred_at": update.occurred_at,
                    "provider_ref": update.provider_ref,
                },
            )
            conn.commit()
            return (cur.rowcount or 0) > 0

    def get_whatsapp_state(self, notification_id: str) -> dict[str, object] | None:
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            row = conn.execute(
                """
                SELECT whatsapp_attempted AS attempted,
                       whatsapp_delivered AS delivered,
                       whatsapp_provider_ref AS provider_ref,
                       whatsapp_failed_reason AS failed_reason,
                       whatsapp_status_received_at AS status_received_at
                  FROM notifications WHERE id = %s
                """,
                (notification_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_merchant_notification_preference(
        self, creditor_id: str, debtor_id: str
    ) -> NotificationPreferenceOut | None:
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            row = conn.execute(
                """
                SELECT user_id, merchant_id, whatsapp_enabled, updated_at
                  FROM merchant_notification_preferences
                 WHERE user_id = %s AND merchant_id = %s
                """,
                (debtor_id, creditor_id),
            ).fetchone()
            if not row:
                return None
            return NotificationPreferenceOut(
                user_id=str(row["user_id"]),
                merchant_id=str(row["merchant_id"]),
                whatsapp_enabled=row["whatsapp_enabled"],
                updated_at=row["updated_at"],
            )

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
            return GroupOut(
                id=str(row["id"]), owner_id=str(row["owner_id"]), name=row["name"], description=row.get("description"), created_at=row["created_at"]
            )

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
            existing = conn.execute("SELECT * FROM group_members WHERE group_id = %s AND user_id = %s", (group_id, payload.user_id)).fetchone()
            if existing:
                return GroupMemberOut(
                    id=str(existing["id"]),
                    group_id=str(existing["group_id"]),
                    user_id=str(existing["user_id"]),
                    status=existing["status"],
                    created_at=existing["created_at"],
                    accepted_at=existing.get("accepted_at"),
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
                id=str(row["id"]),
                group_id=str(row["group_id"]),
                user_id=str(row["user_id"]),
                status=row["status"],
                created_at=row["created_at"],
                accepted_at=row.get("accepted_at"),
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
                id=str(row["id"]),
                group_id=str(row["group_id"]),
                user_id=str(row["user_id"]),
                status=row["status"],
                created_at=row["created_at"],
                accepted_at=row.get("accepted_at"),
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
            self._notify_raw(
                conn,
                payload.debtor_id,
                "payment_confirmed",
                "Group settlement recorded",
                f"{payer_id} paid {payload.amount} {payload.currency} for you",
                None,
            )
            conn.commit()
            return SettlementOut(
                id=settlement_id,
                group_id=group_id,
                payer_id=payer_id,
                debtor_id=payload.debtor_id,
                amount=payload.amount,
                currency=payload.currency,
                note=payload.note,
                created_at=utcnow(),
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

    # ── Payment intents ───────────────────────────────────────────────

    def _intent_from_row(self, row: dict) -> PaymentIntentOut:
        amount = Decimal(str(row["amount"]))
        fee = Decimal(str(row["fee"]))
        return PaymentIntentOut(
            id=str(row["id"]),
            debt_id=str(row["debt_id"]),
            provider=row["provider"],
            provider_ref=row.get("provider_ref"),
            checkout_url=row.get("checkout_url"),
            status=row["status"],
            amount=amount,
            fee=fee,
            net_amount=amount - fee,
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            completed_at=row.get("completed_at"),
        )

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
        intent_id = str(uuid4())
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            conn.execute(
                """
                INSERT INTO payment_intents
                  (id, debt_id, provider, provider_ref, checkout_url, status, amount, fee, expires_at)
                VALUES (%s, %s, %s, %s, %s, 'pending', %s, %s, %s)
                """,
                (intent_id, debt_id, provider, provider_ref, checkout_url, amount, fee, expires_at),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM payment_intents WHERE id = %s", (intent_id,)).fetchone()
            return self._intent_from_row(row)

    def get_active_payment_intent(self, debt_id: str) -> PaymentIntentOut | None:
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            conn.execute(
                """
                UPDATE payment_intents
                   SET status = 'expired', completed_at = now()
                 WHERE debt_id = %s AND status = 'pending' AND expires_at <= now()
                """,
                (debt_id,),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM payment_intents WHERE debt_id = %s AND status = 'pending' LIMIT 1",
                (debt_id,),
            ).fetchone()
            return self._intent_from_row(row) if row else None

    def get_payment_intent_by_ref(self, provider_ref: str) -> PaymentIntentOut | None:
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            row = conn.execute(
                "SELECT * FROM payment_intents WHERE provider_ref = %s LIMIT 1",
                (provider_ref,),
            ).fetchone()
            return self._intent_from_row(row) if row else None

    def update_payment_intent_status(
        self, intent_id: str, status: str, completed_at: datetime | None = None
    ) -> None:
        with self._pool.connection() as conn:
            if completed_at is not None:
                conn.execute(
                    "UPDATE payment_intents SET status = %s, completed_at = %s WHERE id = %s",
                    (status, completed_at, intent_id),
                )
            else:
                conn.execute(
                    "UPDATE payment_intents SET status = %s WHERE id = %s",
                    (status, intent_id),
                )
            conn.commit()

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
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            row = self._can_view_debt(conn, user_id, debt_id)
            if not row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Debt not found")
            if str(row["creditor_id"]) == user_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the debtor can initiate online payment")
            if row["status"] not in ("active", "overdue"):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Debt must be active or overdue to pay online")
            # Lazy-expire and check pending intents
            conn.execute(
                "UPDATE payment_intents SET status = 'expired', completed_at = now() WHERE debt_id = %s AND status = 'pending' AND expires_at <= now()",
                (debt_id,),
            )
            existing = conn.execute(
                "SELECT id FROM payment_intents WHERE debt_id = %s AND status = 'pending' LIMIT 1",
                (debt_id,),
            ).fetchone()
            if existing:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="payment_in_progress")
            # Create intent and transition debt atomically
            intent_id = str(uuid4())
            conn.execute(
                """
                INSERT INTO payment_intents
                  (id, debt_id, provider, provider_ref, checkout_url, status, amount, fee, expires_at)
                VALUES (%s, %s, %s, %s, %s, 'pending', %s, %s, %s)
                """,
                (intent_id, debt_id, provider, provider_ref, checkout_url, amount, fee, expires_at),
            )
            conn.execute(
                "UPDATE debts SET status = 'payment_pending_confirmation', updated_at = now() WHERE id = %s",
                (debt_id,),
            )
            self._add_event_raw(conn, debt_id, user_id, "payment_initiated", None, {
                "intent_id": intent_id, "provider": provider, "amount": str(amount), "fee": str(fee)
            })
            conn.commit()
            return PayOnlineOut(
                payment_intent_id=intent_id,
                checkout_url=checkout_url,
                amount=amount,
                fee=fee,
                net_amount=amount - fee,
                currency=row["currency"].strip(),
                expires_at=expires_at,
            )

    def confirm_payment_gateway(self, provider_ref: str) -> DebtOut:
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            intent_row = conn.execute(
                "SELECT * FROM payment_intents WHERE provider_ref = %s LIMIT 1",
                (provider_ref,),
            ).fetchone()
            if not intent_row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment intent not found")
            # Idempotency: already succeeded
            if intent_row["status"] == "succeeded":
                debt_row = conn.execute("SELECT * FROM debts WHERE id = %s", (intent_row["debt_id"],)).fetchone()
                if not debt_row:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Debt not found")
                return _debt_from_row(debt_row)
            intent_id = str(intent_row["id"])
            debt_id = str(intent_row["debt_id"])
            conn.execute(
                "UPDATE payment_intents SET status = 'succeeded', completed_at = now() WHERE id = %s",
                (intent_id,),
            )
            debt_row = conn.execute("SELECT * FROM debts WHERE id = %s", (debt_id,)).fetchone()
            if not debt_row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Debt not found")
            if debt_row["status"] == "paid":
                conn.commit()
                return _debt_from_row(debt_row)
            if debt_row["status"] != "payment_pending_confirmation":
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Debt is not awaiting payment confirmation")
            conn.execute("UPDATE debts SET status = 'paid', paid_at = now(), updated_at = now() WHERE id = %s", (debt_id,))
            self._add_event_raw(conn, debt_id, "system", "payment_confirmed", None, {
                "intent_id": intent_id, "provider_ref": provider_ref, "gateway": True
            })
            debtor_id = str(debt_row["debtor_id"]) if debt_row.get("debtor_id") else None
            if debtor_id:
                today = utcnow().date()
                if today < debt_row["due_date"]:
                    self._change_commitment_score_raw(conn, debtor_id, 3, "paid_early", debt_id)
                elif today == debt_row["due_date"]:
                    self._change_commitment_score_raw(conn, debtor_id, 1, "paid_on_time", debt_id)
                else:
                    missed_row = conn.execute(
                        "SELECT COUNT(*) AS n FROM commitment_score_events WHERE debt_id = %s AND reason = 'missed_reminder'",
                        (debt_id,),
                    ).fetchone()
                    missed = int(missed_row["n"]) if missed_row else 0
                    self._change_commitment_score_raw(conn, debtor_id, _late_penalty(missed), "paid_late", debt_id)
                self._notify_raw(conn, debtor_id, "payment_confirmed", "Payment confirmed",
                                 f"{debt_row['amount']} {debt_row['currency'].strip()} was confirmed as paid", debt_id)
            self._notify_raw(conn, str(debt_row["creditor_id"]), "payment_confirmed", "Payment confirmed",
                             f"{debt_row['debtor_name']} paid {debt_row['amount']} {debt_row['currency'].strip()} online", debt_id)
            conn.commit()
            updated = conn.execute("SELECT * FROM debts WHERE id = %s", (debt_id,)).fetchone()
            return _debt_from_row(updated)

    def record_payment_failure(self, provider_ref: str) -> None:
        with self._pool.connection() as conn:
            conn.row_factory = dict_row
            intent_row = conn.execute(
                "SELECT * FROM payment_intents WHERE provider_ref = %s AND status = 'pending' LIMIT 1",
                (provider_ref,),
            ).fetchone()
            if not intent_row:
                return
            intent_id = str(intent_row["id"])
            debt_id = str(intent_row["debt_id"])
            conn.execute(
                "UPDATE payment_intents SET status = 'failed', completed_at = now() WHERE id = %s",
                (intent_id,),
            )
            self._add_event_raw(conn, debt_id, "system", "payment_failed", None, {"provider_ref": provider_ref})
            debt_row = conn.execute("SELECT * FROM debts WHERE id = %s", (debt_id,)).fetchone()
            debtor_id = str(debt_row["debtor_id"]) if debt_row and debt_row.get("debtor_id") else None
            if debtor_id:
                self._notify_raw(conn, debtor_id, "payment_failed", "Payment failed",
                                 f"Payment of {debt_row['amount']} {debt_row['currency'].strip()} failed — you can try again", debt_id)
            conn.commit()
