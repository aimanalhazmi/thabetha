"""T013 — template registry locale selection + fallback."""
from __future__ import annotations

import pytest

from app.schemas.domain import NotificationType
from app.services.whatsapp import templates as t


@pytest.fixture(autouse=True)
def restore_registry() -> None:
    snapshot = {k: dict(v) for k, v in t.TEMPLATE_REGISTRY.items()}
    yield
    t.TEMPLATE_REGISTRY.clear()
    t.TEMPLATE_REGISTRY.update(snapshot)


def test_pick_template_prefers_requested_locale() -> None:
    chosen = t.pick_template(NotificationType.debt_created, "ar")
    assert chosen is not None
    assert chosen[0] == "debt_created_ar"
    assert chosen[1] == "ar"


def test_pick_template_falls_back_to_other_locale() -> None:
    # Drop the AR variant and confirm EN is selected for an "ar" caller.
    bindings = t.TEMPLATE_REGISTRY[NotificationType.debt_created]
    bindings.pop("ar")
    chosen = t.pick_template(NotificationType.debt_created, "ar")
    assert chosen is not None
    assert chosen[1] == "en"
    assert chosen[0] == "debt_created_en"


def test_pick_template_returns_none_when_both_missing() -> None:
    t.TEMPLATE_REGISTRY[NotificationType.debt_created] = {}
    assert t.pick_template(NotificationType.debt_created, "ar") is None
