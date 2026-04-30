#!/usr/bin/env python3
"""Seed dummy data for local Thabetha development.

Creates a set of fake debtor users plus debts in every lifecycle state so
the dashboard has realistic content. Idempotent: re-running cleans up the
previous run's dummy rows first.

Usage:
    python scripts/seed_dummy_data.py [creditor_email]

If creditor_email is omitted, the script uses CREDITOR_EMAIL from the env
or falls back to the first existing profile in the database.

Required env (loaded from backend/.env if present):
    SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, DATABASE_URL
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

DUMMY_TAG = "thabetha"  # marker stored in debts.notes / profile name suffix
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
DEBTORS: list[dict[str, str]] = [
    {"name": "أحمد العامري", "phone": "+966500000001"},
    {"name": "فاطمة الزهراني", "phone": "+966500000002"},
    {"name": "خالد الهمداني", "phone": "+966500000003"},
    {"name": "ليلى الحربي", "phone": "+966500000004"},
    {"name": "عمر الحزمي", "phone": "+966500000005"},
    {"name": "نورة القحطاني", "phone": "+966500000006"},
    {"name": "يوسف الدوسري", "phone": "+966500000007"},
    {"name": "ريم المطيري", "phone": "+966500000008"},
    {"name": "عبدالله الحكيمي", "phone": "+966599999991"},
    {"name": "محمد الصالح", "phone": "+966599999993"},
]

PURCHASE_DATA = [
    # Supermarket (بقالة)
    {"desc": "أغراض بقالة منوعة", "amount": 120.00},
    {"desc": "أرز محمود 5 كيلو ودجاج ساديا حلال", "amount": 59.00},
    {"desc": "لحم غنم طازج حلال 2 كيلو", "amount": 130.00},
    # Barber (حلاق)
    {"desc": "حلاقة شعر ودقن", "amount": 35.00},
    {"desc": "حلاقة أطفال (شخصين)", "amount": 40.00},
    {"desc": "باقة عريس (عناية كاملة)", "amount": 250.00},
    # Plumber (سباك)
    {"desc": "إصلاح تسريب مياه في الحمام", "amount": 150.00},
    {"desc": "تركيب وصيانة سخان مياه", "amount": 120.00},
    {"desc": "تأسيس سباكة مطبخ", "amount": 450.00},
    # Freelancer (عمل حر)
    {"desc": "تصميم شعار وهوية بصرية", "amount": 800.00},
    {"desc": "تطوير واجهة مستخدم للتطبيق", "amount": 1500.00},
    {"desc": "إدارة حسابات التواصل الاجتماعي (شهر)", "amount": 1200.00},
    {"desc": "ترجمة مستندات وتقارير", "amount": 300.00},
]


# ── Supabase admin helpers ────────────────────────────────────────────────────
def admin_headers(service_key: str) -> dict[str, str]:
    return {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }


def create_auth_user(supabase_url: str, service_key: str, email: str, name: str) -> str:
    """Create a confirmed Supabase auth user; return the user id (uuid)."""
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


def delete_auth_user(supabase_url: str, service_key: str, user_id: str) -> None:
    httpx.delete(
        f"{supabase_url}/auth/v1/admin/users/{user_id}",
        headers=admin_headers(service_key),
        timeout=15.0,
    )


# ── Seeding ───────────────────────────────────────────────────────────────────
def cleanup_previous(conn: psycopg.Connection, supabase_url: str, service_key: str) -> None:
    """Remove debts and auth users from previous seed runs.

    auth.users has ON DELETE CASCADE to public.profiles, so deleting auth.users
    cleans up profiles, and FK CASCADE on debts handles those too. We still
    explicitly nuke seeded debts first in case any reference real users.
    """
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
DEFAULT_CREDITOR_PASSWORD = "123456"
DEFAULT_CREDITOR_NAME = "Demo Creditor"


def resolve_creditor(
    conn: psycopg.Connection, email: str | None, supabase_url: str, service_key: str
) -> tuple[uuid.UUID, str, str]:
    with conn.cursor() as cur:
        if email:
            cur.execute("SELECT id, name, email FROM public.profiles WHERE email = %s", (email,))
            row = cur.fetchone()
            if not row:
                sys.exit(f"no profile with email {email}; sign up first via the frontend")
            return row[0], row[1], row[2]
        cur.execute(
            "SELECT id, name, email FROM public.profiles "
            "WHERE email NOT LIKE %s ORDER BY created_at LIMIT 1",
            (f"%@{DUMMY_EMAIL_DOMAIN}",),
        )
        row = cur.fetchone()
        if row:
            print(f"  using existing user {row[2]} ({row[1]}) as creditor")
            return row[0], row[1], row[2]

    # No real users — create a default creditor account.
    print(f"  no users found; creating default creditor {DEFAULT_CREDITOR_EMAIL}")
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
                SET name = %s, phone = %s, account_type = 'debtor',
                    commitment_score = %s
                WHERE id = %s
                """,
                (persona["name"], persona["phone"], random.randint(35, 90), uid),
            )
        debtors.append({"id": uid, "name": persona["name"], "phone": persona["phone"]})
    conn.commit()
    return debtors


def make_debt_rows(creditor_id: uuid.UUID, debtors: list[dict]) -> list[dict]:
    """Build debt dicts covering all 7 lifecycle states + variety on dates / amounts."""
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

    # Find our specific test users from the created list
    user_single = next((d for d in debtors if d["name"] == "عبدالله الحكيمي"), None)
    user_triple = next((d for d in debtors if d["name"] == "محمد الصالح"), None)

    # 1. Create exactly 1 overdue debt for "User Single Overdue"
    if user_single:
        r = base(user_single, days_due=-10, amount=150.0, desc="بناء منصة ثبتها")
        r["status"] = "overdue"
        r["confirmed_at"] = now - timedelta(days=15)
        rows.append(r)

    # 2. Create exactly 3 overdue debts for "User Triple Overdue"
    if user_triple:
        for i in range(3):
            r = base(user_triple, days_due=-(7 + i * 5), amount=200.0 + (i * 50), desc="تأجير سرفر لمنصة ثبتها")
            r["status"] = "overdue"
            r["confirmed_at"] = now - timedelta(days=20)
            rows.append(r)

    # 5 pending_confirmation (newly created, not yet accepted)
    for i in range(5):
        d = debtors[i % len(debtors)]
        item = PURCHASE_DATA[i % len(PURCHASE_DATA)]
        rows.append(base(d, days_due=14 + i, amount=item["amount"], desc=item["desc"]))

    # 6 active (debtor accepted, future due)
    for i in range(6):
        d = debtors[i % len(debtors)]
        item = PURCHASE_DATA[(i + 2) % len(PURCHASE_DATA)]
        r = base(d, days_due=7 + i * 3, amount=item["amount"], desc=item["desc"])
        r["status"] = "active"
        r["confirmed_at"] = now - timedelta(days=2)
        rows.append(r)

    # 4 overdue (active but past due_date)
    for i in range(4):
        d = debtors[i % len(debtors)]
        item = PURCHASE_DATA[(i + 4) % len(PURCHASE_DATA)]
        r = base(d, days_due=-(5 + i * 4), amount=item["amount"], desc=item["desc"])
        r["status"] = "overdue"
        r["confirmed_at"] = now - timedelta(days=10 + i)
        rows.append(r)

    # 3 edit_requested (debtor pushed back on terms)
    for i in range(3):
        d = debtors[i % len(debtors)]
        item = PURCHASE_DATA[(i + 6) % len(PURCHASE_DATA)]
        r = base(d, days_due=10 + i, amount=item["amount"], desc=item["desc"])
        r["status"] = "edit_requested"
        rows.append(r)

    # 3 payment_pending_confirmation (debtor said paid, awaiting creditor)
    for i in range(3):
        d = debtors[i % len(debtors)]
        item = PURCHASE_DATA[(i + 1) % len(PURCHASE_DATA)]
        r = base(d, days_due=-2 + i, amount=item["amount"], desc=item["desc"])
        r["status"] = "payment_pending_confirmation"
        r["confirmed_at"] = now - timedelta(days=8)
        rows.append(r)

    # 4 paid (settled)
    for i in range(4):
        d = debtors[i % len(debtors)]
        item = PURCHASE_DATA[(i + 3) % len(PURCHASE_DATA)]
        r = base(d, days_due=-(10 + i * 2), amount=item["amount"], desc=item["desc"])
        r["status"] = "paid"
        r["confirmed_at"] = now - timedelta(days=20 + i)
        r["paid_at"] = now - timedelta(days=8 + i)
        rows.append(r)

    # 2 cancelled
    for i in range(2):
        d = debtors[i % len(debtors)]
        item = PURCHASE_DATA[(i + 5) % len(PURCHASE_DATA)]
        r = base(d, days_due=5 + i, amount=item["amount"], desc=item["desc"])
        r["status"] = "cancelled"
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
                VALUES
                  (%(id)s, %(creditor_id)s, %(debtor_id)s, %(debtor_name)s, %(amount)s,
                   %(currency)s, %(description)s, %(due_date)s, %(status)s, %(notes)s,
                   %(reminder_dates)s, %(created_at)s, %(updated_at)s, %(confirmed_at)s, %(paid_at)s)
                """,
                r,
            )
    conn.commit()


def insert_reverse_debts(conn: psycopg.Connection, debtor_creditor: uuid.UUID, debtors: list[dict]) -> None:
    """Add a few debts where the target user is the DEBTOR, so dashboard 'I owe' tab shows data."""
    today = date.today()
    now = datetime.now(timezone.utc)
    rows = []
    for i, d in enumerate(debtors[:4]):
        item = PURCHASE_DATA[i % len(PURCHASE_DATA)]
        rows.append({
            "id": uuid.uuid4(),
            "creditor_id": d["id"],
            "debtor_id": debtor_creditor,
            "debtor_name": "You",
            "amount": item["amount"],
            "currency": "SAR",
            "description": item["desc"],
            "due_date": today + timedelta(days=(i - 1) * 7),
            "status": ["pending_confirmation", "active", "overdue", "paid"][i],
            "notes": f"[{DUMMY_TAG}] reverse",
            "reminder_dates": [],
            "created_at": now - timedelta(days=10),
            "updated_at": now,
            "confirmed_at": now - timedelta(days=5) if i > 0 else None,
            "paid_at": now - timedelta(days=2) if i == 3 else None,
        })
    insert_debts(conn, rows)


def main() -> None:
    load_env()
    supabase_url = require_env("SUPABASE_URL")
    service_key = require_env("SUPABASE_SERVICE_ROLE_KEY")
    database_url = require_env("DATABASE_URL")

    creditor_email = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("CREDITOR_EMAIL")

    random.seed(42)
    print("→ connecting to database...")
    with psycopg.connect(database_url) as conn:
        print("→ cleaning previous seed...")
        cleanup_previous(conn, supabase_url, service_key)

        print("→ resolving creditor...")
        creditor_id, creditor_name, creditor_email_resolved = resolve_creditor(
            conn, creditor_email, supabase_url, service_key
        )
        print(f"  creditor: {creditor_name} <{creditor_email_resolved}> ({creditor_id})")

        print("→ creating debtors...")
        debtors = create_debtors(conn, supabase_url, service_key)

        print("→ creating debts (all lifecycle states)...")
        rows = make_debt_rows(creditor_id, debtors)
        insert_debts(conn, rows)
        print(f"  inserted {len(rows)} debts where {creditor_name} is creditor")

        #print("→ creating reverse debts (target user as debtor)...")
        #insert_reverse_debts(conn, creditor_id, debtors)
        #print("  inserted 4 debts where target user owes someone")

    print("\n✓ done. Refresh the dashboard.")


if __name__ == "__main__":
    main()