"""Pure greedy min-flow netting algorithm.

Given a snapshot of group debts (debtor_id → creditor_id, amount, currency),
compute the minimum-edge set of transfers (payer → receiver, amount) that
nets all members' positions to zero.

This module is intentionally pure: no I/O, no repository coupling, no
Pydantic. The repository layer (memory + postgres) calls `compute_transfers`
during proposal creation and persists the returned list as JSONB.

Spec ref: specs/009-groups-auto-netting/research.md#R1.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class SnapshotDebt:
    debt_id: str
    debtor_id: str
    creditor_id: str
    amount: Decimal
    currency: str


@dataclass(frozen=True)
class ProposedTransfer:
    payer_id: str
    receiver_id: str
    amount: Decimal


def compute_transfers(snapshot: list[SnapshotDebt]) -> list[ProposedTransfer]:
    """Compute minimum-edge transfers that settle the snapshot.

    Steps:
        1. Validate single currency (raise ValueError("MixedCurrency") on mix).
        2. Compute per-user net = sum(received) - sum(owed).
        3. Drop net-zero users.
        4. Greedy match: max payer (most negative) with max receiver (most
           positive); emit transfer of min(|payer|, |receiver|); update both
           balances; repeat until all are zero.
        5. Tie-break by user_id (lexicographic ascending) for determinism.

    Returns an empty list for an empty snapshot or when all users net to zero.
    Raises ValueError("MixedCurrency") if the snapshot mixes currencies.
    """
    if not snapshot:
        return []

    currencies = {d.currency for d in snapshot}
    if len(currencies) > 1:
        raise ValueError("MixedCurrency")

    net: dict[str, Decimal] = {}
    for d in snapshot:
        net[d.debtor_id] = net.get(d.debtor_id, Decimal("0")) - d.amount
        net[d.creditor_id] = net.get(d.creditor_id, Decimal("0")) + d.amount

    payers: list[tuple[str, Decimal]] = sorted(
        ((uid, amt) for uid, amt in net.items() if amt < 0),
        key=lambda t: (t[1], t[0]),
    )
    receivers: list[tuple[str, Decimal]] = sorted(
        ((uid, amt) for uid, amt in net.items() if amt > 0),
        key=lambda t: (-t[1], t[0]),
    )

    transfers: list[ProposedTransfer] = []
    pi = ri = 0
    while pi < len(payers) and ri < len(receivers):
        payer_id, payer_amt = payers[pi]
        receiver_id, receiver_amt = receivers[ri]
        delta = min(-payer_amt, receiver_amt)
        transfers.append(ProposedTransfer(payer_id, receiver_id, delta))
        new_payer = payer_amt + delta
        new_receiver = receiver_amt - delta
        if new_payer == 0:
            pi += 1
        else:
            payers[pi] = (payer_id, new_payer)
        if new_receiver == 0:
            ri += 1
        else:
            receivers[ri] = (receiver_id, new_receiver)

    return transfers
