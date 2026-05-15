from __future__ import annotations

import json
import sys
from typing import Any

from .errors import CaldavCalendarError


def emit(payload: dict[str, Any], exit_code: int = 0) -> int:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return exit_code


def emit_error(exc: CaldavCalendarError) -> int:
    return emit(
        {
            "ok": False,
            "error": {
                "code": exc.code,
                "message": exc.message,
            },
        },
        exc.exit_code,
    )


def fail_unexpected(exc: Exception) -> int:
    print(
        json.dumps(
            {
                "ok": False,
                "error": {
                    "code": "GENERAL_ERROR",
                    "message": str(exc),
                },
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        file=sys.stdout,
    )
    return 1
