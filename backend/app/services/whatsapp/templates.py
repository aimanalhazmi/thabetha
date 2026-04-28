"""WhatsApp template registry — NotificationType × locale -> Meta template binding.

Templates referenced here MUST be registered & approved in Meta Business Manager
before `WHATSAPP_PROVIDER=cloud_api` will succeed. The Arabic and English variants
share the same positional parameter layout so the dispatcher can build params once.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.schemas.domain import NotificationType
from app.services.whatsapp.provider import Locale

ParamLayout = list[Literal["creditor_name", "amount", "currency", "debt_link", "due_date", "debtor_name"]]


@dataclass(frozen=True, slots=True)
class TemplateBinding:
    template_id: str
    params_layout: ParamLayout


_DEFAULT_PARAMS: ParamLayout = ["creditor_name", "amount", "currency", "debt_link"]
_PAID_PARAMS: ParamLayout = ["debtor_name", "amount", "currency", "debt_link"]


def _bilingual(name_ar: str, name_en: str, layout: ParamLayout) -> dict[Locale, TemplateBinding]:
    return {
        "ar": TemplateBinding(template_id=name_ar, params_layout=layout),
        "en": TemplateBinding(template_id=name_en, params_layout=layout),
    }


TEMPLATE_REGISTRY: dict[NotificationType, dict[Locale, TemplateBinding]] = {
    NotificationType.debt_created: _bilingual("debt_created_ar", "debt_created_en", _DEFAULT_PARAMS),
    NotificationType.debt_confirmed: _bilingual("debt_confirmed_ar", "debt_confirmed_en", _DEFAULT_PARAMS),
    NotificationType.debt_edit_requested: _bilingual("debt_edit_requested_ar", "debt_edit_requested_en", _DEFAULT_PARAMS),
    NotificationType.debt_edit_approved: _bilingual("debt_edit_approved_ar", "debt_edit_approved_en", _DEFAULT_PARAMS),
    NotificationType.debt_edit_rejected: _bilingual("debt_edit_rejected_ar", "debt_edit_rejected_en", _DEFAULT_PARAMS),
    NotificationType.debt_cancelled: _bilingual("debt_cancelled_ar", "debt_cancelled_en", _DEFAULT_PARAMS),
    NotificationType.due_soon: _bilingual("due_soon_ar", "due_soon_en", ["creditor_name", "amount", "currency", "due_date"]),
    NotificationType.overdue: _bilingual("overdue_ar", "overdue_en", ["creditor_name", "amount", "currency", "due_date"]),
    NotificationType.payment_requested: _bilingual("payment_requested_ar", "payment_requested_en", _PAID_PARAMS),
    NotificationType.payment_confirmed: _bilingual("payment_confirmed_ar", "payment_confirmed_en", _PAID_PARAMS),
}


def pick_template(
    notification_type: NotificationType, preferred_locale: str
) -> tuple[str, Locale, ParamLayout] | None:
    """Return (template_id, locale, params_layout) for the given type+locale.

    Falls back to the other locale when the preferred one is missing. Returns
    `None` when neither locale is registered (caller marks ``no_template``).
    """
    bindings = TEMPLATE_REGISTRY.get(notification_type)
    if not bindings:
        return None
    primary: Locale = "ar" if preferred_locale == "ar" else "en"
    fallback: Locale = "en" if primary == "ar" else "ar"
    for locale in (primary, fallback):
        binding = bindings.get(locale)
        if binding is not None:
            return binding.template_id, locale, binding.params_layout
    return None
