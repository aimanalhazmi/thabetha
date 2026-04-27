from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import quote
from uuid import uuid4

from app.core.config import get_settings
from app.schemas.domain import utcnow


@dataclass(frozen=True)
class LocalReceipt:
    content: bytes
    content_type: str
    filename: str


@dataclass(frozen=True)
class LocalReceiptAccess:
    storage_path: str
    expires_at: datetime


_receipts: dict[str, LocalReceipt] = {}
_access_tokens: dict[str, LocalReceiptAccess] = {}


def save_local_receipt(storage_path: str, content: bytes, content_type: str | None, filename: str) -> str:
    _receipts[storage_path] = LocalReceipt(
        content=content,
        content_type=content_type or "application/octet-stream",
        filename=filename,
    )
    return create_local_receipt_url(storage_path)


def create_local_receipt_url(storage_path: str) -> str:
    token = str(uuid4())
    expires_at = _aware(utcnow()) + timedelta(seconds=get_settings().receipt_signed_url_ttl_seconds)
    _access_tokens[token] = LocalReceiptAccess(storage_path=storage_path, expires_at=expires_at)
    filename = _receipts.get(storage_path).filename if storage_path in _receipts else "receipt"
    return f"{get_settings().api_prefix}/receipt-files/{token}/{quote(filename)}"


def get_local_receipt(token: str) -> LocalReceipt | None:
    access = _access_tokens.get(token)
    if access is None:
        return None
    if _aware(utcnow()) > access.expires_at:
        _access_tokens.pop(token, None)
        return None
    return _receipts.get(access.storage_path)


def has_local_receipt(storage_path: str) -> bool:
    return storage_path in _receipts


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
