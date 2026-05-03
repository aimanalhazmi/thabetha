#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "httpx>=0.28.1",
#   "psycopg[binary]>=3.2.0",
# ]
# ///
"""Seed dummy data for local Thabetha development.

Creates a set of fake debtor users plus debts in every lifecycle state so
the dashboard has realistic content. Idempotent: re-running cleans up the
previous run's dummy rows first.
"""

from __future__ import annotations

import os
import random
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx
import psycopg
from psycopg.types.json import Json

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ENV = REPO_ROOT / "backend" / ".env"
ROOT_ENV = REPO_ROOT / ".env"

DUMMY_TAG = "thabetha"
DUMMY_EMAIL_DOMAIN = "dummy.thabetha.dev"


def load_env() -> None:
    for path in (ROOT_ENV, BACKEND_ENV):
        if not path.exists():
            continue
        for raw in path.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            os.environ.setdefault(key, val)


def require_env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        sys.exit(f"missing env var: {name} (check backend/.env)")
    return val


# ── Debtor personas ───────────────────────────────────────────────────────────
DEBTORS: list[dict[str, str | int]] = [
    {"name": "طارق العوزة", "phone": "+962790000001", "score": 94, "status": "active"},
    {"name": "أحمد عباس", "phone": "+201000000004", "score": 91, "status": "paid"},
    {"name": "محمود النابلسي", "phone": "+970590000004", "score": 88, "status": "active"},
    {"name": "بلال الزعبي", "phone": "+962790000005", "score": 86, "status": "active"},
    {"name": "معتز الشامي", "phone": "+963930000001", "score": 89, "status": "paid"},
    {"name": "حمزة زاغة", "phone": "+970590000002", "score": 14, "status": "overdue"},
    {"name": "أحمد حطاب", "phone": "+962780000003", "score": 18, "status": "overdue"},
    {"name": "أبو فهد العتيبي", "phone": "+966500000003", "score": 11, "status": "overdue"},
    {"name": "صبحي الجزار", "phone": "+201100000002", "score": 22, "status": "overdue"},
    {"name": "سيف الدين مراد", "phone": "+961300000006", "score": 15, "status": "overdue"},
]

TASK_MAP = {
    "طارق العوزة": "إنتاج حلقات بودكاست تقني وتدريب تكنولوجي",
    "حمزة زاغة": "تطوير أنظمة برمجية",
    "أحمد حطاب": "استشارات تقنية ",
    "أحمد عباس": "إدارة منتجات SaaS وحلول تجارة إلكترونية",
    "صبحي الجزار": "توريد بضائع مواد غذائية جملة",
    "محمود النابلسي": "فاتورة مواد استهلاكية ومنظفات",
    "معتز الشامي": "تجهيزات كراسي حلاقة وأدوات تجميل",
    "سيف الدين مراد": "صيانة أدوات حلاقة احترافية",
    "أبو فهد العتيبي": "أدوات سباكة وقطع غيار صيانة",
    "بلال الزعبي": "تمديدات صحية وصيانة شبكة مياه",
}


# ── Supabase admin helpers ────────────────────────────────────────────────────
def admin_headers(service_key: str) -> dict[str, str]:
    return {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }


def create_auth_user(supabase_url: str, service_key: str, email: str, name: str) -> str:
    resp = httpx.post(
        f"{supabase_url}/auth/v1/admin/users",
        headers=admin_headers(service_key),
        json={
            "email": email,
            "password": "123456",
            "email_confirm": True,
            "user_metadata": {"name": name, DUMMY_TAG: True},
        },
        timeout=15.0,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"failed to create auth user {email}: {resp.status_code} {resp.text}")
    return resp.json()["id"]


def cleanup_previous(conn: psycopg.Connection, supabase_url: str, service_key: str) -> None:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM public.debts WHERE notes LIKE %s", (f"%{DUMMY_TAG}%",))
        cur.execute(
            "DELETE FROM auth.users WHERE email LIKE %s RETURNING id",
            (f"%@{DUMMY_EMAIL_DOMAIN}",),
        )
        deleted = cur.rowcount
    conn.commit()
    if deleted:
        print(f"  cleaned {deleted} previous dummy users + their debts")


DEFAULT_CREDITOR_EMAIL = "demo@thabetha.dev"
DEFAULT_CREDITOR_NAME = "Demo Creditor"


def resolve_creditor(
        conn: psycopg.Connection, email: str | None, supabase_url: str, service_key: str
) -> tuple[uuid.UUID, str, str]:
    with conn.cursor() as cur:
        # If user specified an email, strictly check for it.
        if email:
            cur.execute("SELECT id, name, email FROM public.profiles WHERE email = %s", (email,))
            row = cur.fetchone()
            if not row:
                sys.exit(f"no profile with email {email}")
            return row[0], row[1], row[2]

        # If no specific email, check if our default demo already exists.
        cur.execute("SELECT id, name, email FROM public.profiles WHERE email = %s", (DEFAULT_CREDITOR_EMAIL,))
        row = cur.fetchone()
        if row:
            return row[0], row[1], row[2]

    # No specific request and no demo account: Create default creditor (Pass: 123456).
    print(f"  creating default creditor {DEFAULT_CREDITOR_EMAIL}...")
    uid = create_auth_user(supabase_url, service_key, DEFAULT_CREDITOR_EMAIL, DEFAULT_CREDITOR_NAME)
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE public.profiles SET name = %s, account_type = 'creditor', commitment_score = 75 WHERE id = %s",
            (DEFAULT_CREDITOR_NAME, uid),
        )
    conn.commit()
    return uuid.UUID(uid), DEFAULT_CREDITOR_NAME, DEFAULT_CREDITOR_EMAIL


def create_debtors(conn: psycopg.Connection, supabase_url: str, service_key: str) -> list[dict]:
    debtors: list[dict] = []
    print(f"  creating {len(DEBTORS)} dummy debtors...")
    for persona in DEBTORS:
        slug = uuid.uuid4().hex[:8]
        email = f"debtor.{slug}@{DUMMY_EMAIL_DOMAIN}"
        uid = create_auth_user(supabase_url, service_key, email, persona["name"])
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE public.profiles
                SET name             = %s,
                    phone            = %s,
                    account_type     = 'debtor',
                    commitment_score = %s
                WHERE id = %s
                """,
                (persona["name"], persona["phone"], persona["score"], uid),
            )
        debtors.append({"id": uid, "name": persona["name"], "phone": persona["phone"], "status": persona["status"]})
    conn.commit()
    return debtors


def make_debt_rows(creditor_id: uuid.UUID, debtors: list[dict]) -> list[dict]:
    today = date.today()
    now = datetime.now(timezone.utc)
    rows: list[dict] = []

    def base(debtor: dict, *, days_due: int, amount: float, desc: str) -> dict:
        return {
            "id": uuid.uuid4(),
            "creditor_id": creditor_id,
            "debtor_id": debtor["id"],
            "debtor_name": debtor["name"],
            "amount": round(amount, 2),
            "currency": "SAR",
            "description": desc,
            "due_date": today + timedelta(days=days_due),
            "notes": f"[{DUMMY_TAG}] auto-seeded",
            "reminder_dates": [today + timedelta(days=days_due - d) for d in (3, 1) if days_due - d > -30],
            "created_at": now - timedelta(days=max(0, -days_due) + 5),
            "updated_at": now,
            "confirmed_at": None,
            "paid_at": None,
            "status": "pending_confirmation",
        }

    for d in debtors:
        desc = TASK_MAP.get(d["name"], "خدمات عامة")
        # Overdue logic based on persona status
        days = -15 if d["status"] == "overdue" else 14
        r = base(d, days_due=days, amount=float(random.randint(50, 2000)), desc=desc)
        r["status"] = d["status"]

        if d["status"] != "pending_confirmation":
            r["confirmed_at"] = now - timedelta(days=20)
        if d["status"] == "paid":
            r["paid_at"] = now - timedelta(days=2)

        rows.append(r)

    return rows


def insert_debts(conn: psycopg.Connection, rows: list[dict]) -> None:
    with conn.cursor() as cur:
        for r in rows:
            cur.execute(
                """
                INSERT INTO public.debts
                (id, creditor_id, debtor_id, debtor_name, amount, currency, description,
                 due_date, status, notes, reminder_dates,
                 created_at, updated_at, confirmed_at, paid_at)
                VALUES (%(id)s, %(creditor_id)s, %(debtor_id)s, %(debtor_name)s, %(amount)s,
                        %(currency)s, %(description)s, %(due_date)s, %(status)s, %(notes)s,
                        %(reminder_dates)s, %(created_at)s, %(updated_at)s, %(confirmed_at)s, %(paid_at)s)
                """,
                r,
            )
    conn.commit()


def main() -> None:
    load_env()
    supabase_url = require_env("SUPABASE_URL")
    service_key = require_env("SUPABASE_SERVICE_ROLE_KEY")
    database_url = require_env("DATABASE_URL")

    creditor_email = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("CREDITOR_EMAIL")

    random.seed(42)
    with psycopg.connect(database_url) as conn:
        cleanup_previous(conn, supabase_url, service_key)
        creditor_id, creditor_name, creditor_email_resolved = resolve_creditor(
            conn, creditor_email, supabase_url, service_key
        )
        print(f"  creditor: {creditor_name} <{creditor_email_resolved}>")

        debtors = create_debtors(conn, supabase_url, service_key)
        rows = make_debt_rows(creditor_id, debtors)
        insert_debts(conn, rows)
        print(f"  inserted {len(rows)} debts.")

    print("\n✓ done. Refresh the dashboard.")


if __name__ == "__main__":
    main()
