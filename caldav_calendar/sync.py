from __future__ import annotations

import subprocess

from .errors import SyncFailureError


def run_sync() -> dict:
    completed = subprocess.run(
        ["vdirsyncer", "sync"],
        check=False,
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise SyncFailureError(completed.stderr.strip() or completed.stdout.strip() or "vdirsyncer sync failed")
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
