"""Structured stdout logger for RLS shadow-mode violations."""

from __future__ import annotations

import json
import sys
import time
from collections.abc import Mapping
from datetime import UTC, datetime
from threading import Lock
from typing import Any

_WINDOW_SECONDS = 60.0
_lock = Lock()
_seen: dict[tuple[str | None, str | None, str | None], tuple[float, int, dict[str, Any]]] = {}


def log_shadow_violation(event_dict: Mapping[str, Any]) -> None:
    now = time.monotonic()
    event = {
        "event": "rls.shadow_violation",
        "timestamp": datetime.now(UTC).isoformat(),
        "count": 1,
        **dict(event_dict),
    }
    key = (event.get("route"), event.get("table"), event.get("policy"))

    with _lock:
        previous = _seen.get(key)
        if previous and now - previous[0] < _WINDOW_SECONDS:
            _, count, stored = previous
            stored["count"] = count + 1
            _seen[key] = (now, count + 1, stored)
            payload = stored
        else:
            _seen[key] = (now, 1, event)
            payload = event

    print(json.dumps(payload, separators=(",", ":"), sort_keys=True, default=str), file=sys.stdout, flush=True)
