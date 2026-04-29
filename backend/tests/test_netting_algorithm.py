"""Pure unit tests for app.services.netting.

These tests do not use FastAPI.TestClient — they exercise the algorithm
directly. Spec: specs/009-groups-auto-netting/.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.services.netting import ProposedTransfer, SnapshotDebt, compute_transfers


def _d(amount: str, currency: str = "SAR") -> Decimal:
    return Decimal(amount)


def _debt(debtor: str, creditor: str, amount: str, currency: str = "SAR", debt_id: str | None = None) -> SnapshotDebt:
    return SnapshotDebt(
        debt_id=debt_id or f"{debtor}->{creditor}:{amount}",
        debtor_id=debtor,
        creditor_id=creditor,
        amount=Decimal(amount),
        currency=currency,
    )


def test_empty_snapshot_returns_empty_list() -> None:
    assert compute_transfers([]) == []


def test_three_member_equal_circular_nets_to_zero() -> None:
    # A→B 100, B→C 100, C→A 100. All members have net 0.
    snapshot = [
        _debt("A", "B", "100"),
        _debt("B", "C", "100"),
        _debt("C", "A", "100"),
    ]
    transfers = compute_transfers(snapshot)
    assert transfers == []


def test_three_member_asymmetric_circular_one_transfer() -> None:
    # A→B 150, B→C 100, C→A 100.
    # Net: A = -150 + 100 = -50, B = +150 - 100 = +50, C = -100 + 100 = 0.
    snapshot = [
        _debt("A", "B", "150"),
        _debt("B", "C", "100"),
        _debt("C", "A", "100"),
    ]
    transfers = compute_transfers(snapshot)
    assert len(transfers) == 1
    assert transfers[0] == ProposedTransfer("A", "B", Decimal("50"))


def test_four_node_chain_three_transfers() -> None:
    # A→B 100, B→C 100, C→D 100. Net: A=-100, B=0, C=0, D=+100.
    snapshot = [
        _debt("A", "B", "100"),
        _debt("B", "C", "100"),
        _debt("C", "D", "100"),
    ]
    transfers = compute_transfers(snapshot)
    # Net positions: only A (-100) and D (+100) — single transfer A→D 100.
    assert len(transfers) == 1
    assert transfers[0] == ProposedTransfer("A", "D", Decimal("100"))


def test_two_payers_two_receivers_chain() -> None:
    # A owes 30, B owes 70, C is owed 50, D is owed 50.
    # net: A=-30, B=-70, C=+50, D=+50.
    # Greedy: |B|=70 (largest payer) matches D=50 (largest receiver) → B→D 50.
    # Then B has 20 left, matches C=50 → B→C 20. C has 30 left.
    # Then A=30 matches C=30 → A→C 30.
    snapshot = [
        _debt("A", "C", "20"),
        _debt("A", "D", "10"),
        _debt("B", "C", "30"),
        _debt("B", "D", "40"),
    ]
    transfers = compute_transfers(snapshot)
    # Three transfers expected for 4 non-zero participants.
    assert len(transfers) == 3
    # Sum of payer-side equals sum of receiver-side (total flow conservation).
    total_out: dict[str, Decimal] = {}
    total_in: dict[str, Decimal] = {}
    for t in transfers:
        total_out[t.payer_id] = total_out.get(t.payer_id, Decimal("0")) + t.amount
        total_in[t.receiver_id] = total_in.get(t.receiver_id, Decimal("0")) + t.amount
    assert total_out == {"A": Decimal("30"), "B": Decimal("70")}
    assert total_in == {"C": Decimal("50"), "D": Decimal("50")}


def test_mixed_currency_raises() -> None:
    snapshot = [
        _debt("A", "B", "100", currency="SAR"),
        _debt("B", "C", "100", currency="USD"),
    ]
    with pytest.raises(ValueError, match="MixedCurrency"):
        compute_transfers(snapshot)


def test_deterministic_tie_break() -> None:
    # Three payers all owe 30, two receivers each owed 45. Sums match.
    # The tie-break must produce identical output across two invocations.
    snapshot = [
        _debt("A", "X", "30"),
        _debt("B", "X", "30"),
        _debt("C", "Y", "30"),
        _debt("A", "Y", "15"),
        _debt("B", "Y", "0"),  # zero amount no-op
    ] if False else [
        _debt("A", "X", "30"),
        _debt("B", "X", "15"),
        _debt("C", "Y", "30"),
        _debt("A", "Y", "0"),
    ]
    # Intentionally simple:
    snapshot = [
        _debt("alice", "xavier", "30"),
        _debt("bob", "xavier", "30"),
        _debt("carol", "yvonne", "30"),
    ]
    first = compute_transfers(snapshot)
    second = compute_transfers(snapshot)
    assert first == second


def test_partial_member_net_zero_excluded() -> None:
    # B both pays and receives 100 → net zero → not in any transfer.
    snapshot = [
        _debt("A", "B", "100"),
        _debt("B", "C", "100"),
    ]
    # A=-100, B=0, C=+100 → A→C 100.
    transfers = compute_transfers(snapshot)
    assert len(transfers) == 1
    assert transfers[0] == ProposedTransfer("A", "C", Decimal("100"))
    payer_ids = {t.payer_id for t in transfers}
    receiver_ids = {t.receiver_id for t in transfers}
    assert "B" not in payer_ids
    assert "B" not in receiver_ids


def test_member_both_pays_and_receives() -> None:
    # B owes 50, B is owed 30 → net B=-20. B is in a payer transfer only.
    # A=-30 (owes 30 to B), B=-20 (owes 50 to C minus 30 received from A),
    # C=+50.
    snapshot = [
        _debt("A", "B", "30"),
        _debt("B", "C", "50"),
    ]
    transfers = compute_transfers(snapshot)
    # Net: A=-30, B=-20, C=+50. Two payers, one receiver → 2 transfers.
    assert len(transfers) == 2
    flows: dict[tuple[str, str], Decimal] = {(t.payer_id, t.receiver_id): t.amount for t in transfers}
    # Greedy: max payer A (-30) → C (+50) → A→C 30; then B (-20) → C (+20) → B→C 20.
    assert flows == {("A", "C"): Decimal("30"), ("B", "C"): Decimal("20")}
