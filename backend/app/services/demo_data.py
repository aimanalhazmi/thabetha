from datetime import date, timedelta
from decimal import Decimal

from app.core.security import AuthenticatedUser
from app.repositories.memory import InMemoryRepository
from app.schemas.domain import BusinessProfileIn, DebtCreate, GroupCreate, GroupInviteIn, PaymentRequest, ProfileUpdate


def seed_demo_data(repo: InMemoryRepository) -> None:
    if repo.debts:
        return

    merchant = AuthenticatedUser(id="merchant-1", name="Baqala Al Noor", phone="+966500000001")
    customer = AuthenticatedUser(id="customer-1", name="Ahmed", phone="+966500000002")
    friend = AuthenticatedUser(id="friend-1", name="Sara", phone="+966500000003")

    repo.ensure_profile(merchant)
    repo.ensure_profile(customer)
    repo.ensure_profile(friend)
    repo.update_profile(merchant, ProfileUpdate(account_type="business", ai_enabled=True))
    repo.upsert_business_profile(
        merchant.id,
        BusinessProfileIn(shop_name="Baqala Al Noor", activity_type="Grocery", location="Riyadh", description="Neighborhood grocery and essentials"),
    )

    active_debt = repo.create_debt(
        merchant.id,
        DebtCreate(
            debtor_name="Ahmed",
            debtor_id=customer.id,
            amount=Decimal("25.00"),
            currency="SAR",
            description="Groceries",
            due_date=date.today() + timedelta(days=2),
        ),
    )
    repo.accept_debt(customer.id, active_debt.id)

    paid_debt = repo.create_debt(
        merchant.id,
        DebtCreate(
            debtor_name="Ahmed",
            debtor_id=customer.id,
            amount=Decimal("12.00"),
            currency="SAR",
            description="Coffee and bread",
            due_date=date.today(),
        ),
    )
    repo.accept_debt(customer.id, paid_debt.id)
    repo.mark_paid(customer.id, paid_debt.id, PaymentRequest(note="Paid cash"))
    repo.confirm_payment(merchant.id, paid_debt.id)

    group = repo.create_group(customer.id, GroupCreate(name="Family", description="Family and friend settlements"))
    repo.invite_group_member(customer.id, group.id, GroupInviteIn(user_id=friend.id))
    repo.accept_group_invite(friend.id, group.id)

    # Phase 13 — extra ledger so the merchant-chat demo prompts have grounded answers.
    for debtor_name, amount in (("Alpha", "500.00"), ("Bravo", "1200.00"), ("Charlie", "300.00")):
        debt = repo.create_debt(
            merchant.id,
            DebtCreate(
                debtor_name=debtor_name,
                amount=Decimal(amount),
                currency="SAR",
                description=f"Phase 13 demo — {debtor_name}",
                due_date=date.today() + timedelta(days=14),
            ),
        )
        # Accept some so the assistant can answer "active" questions.
        if debtor_name in {"Alpha", "Bravo"}:
            # Auto-accept by treating debtor_name as a synthetic acceptance — only meaningful
            # when debtor_id is known; here debtors are unlinked so debt stays pending_confirmation.
            _ = debt

