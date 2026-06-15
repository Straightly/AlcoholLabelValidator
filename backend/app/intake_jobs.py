from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from threading import Lock, Thread
from typing import Callable


@dataclass
class IntakeJobStatus:
    started: bool = False
    state: str = "idle"
    message: str = (
        "No sample intake job is running. (Note: Preprocessing batch labels on this VM "
        "takes up to 30 minutes due to CPU/RAM limits. In production, this runs in seconds on GPU hardware.)"
    )
    started_at: str | None = None
    finished_at: str | None = None
    packages_found: int = 0
    packages_imported: int = 0
    packages_skipped: int = 0
    applications_preprocessed: int = 0
    applications_needing_manual_review: int = 0


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class IntakeJobRunner:
    def __init__(self, work: Callable[[], dict[str, int]]) -> None:
        self._work = work
        self._lock = Lock()
        self._status = IntakeJobStatus()

    def status(self) -> dict[str, object]:
        with self._lock:
            return asdict(self._status)

    def start(self) -> tuple[bool, dict[str, object]]:
        with self._lock:
            if self._status.state == "running":
                return False, asdict(self._status)
            self._status = IntakeJobStatus(
                started=True,
                state="running",
                message=(
                    "Background preprocessing started. Due to VM hardware limitations (low memory and no GPU), "
                    "processing all batch labels can take up to 30 minutes. In a production environment with "
                    "appropriate GPU-accelerated hardware, this background job runs asynchronously and finishes in seconds."
                ),
                started_at=utc_now_iso(),
            )
        Thread(target=self._run, daemon=True).start()
        return True, self.status()

    def reset(self) -> None:
        with self._lock:
            self._status = IntakeJobStatus()

    def _run(self) -> None:
        try:
            result = self._work()
        except Exception as exc:
            with self._lock:
                self._status.state = "failed"
                self._status.message = f"Background preprocessing failed: {exc}"
                self._status.finished_at = utc_now_iso()
            return
        with self._lock:
            self._status.state = "completed"
            self._status.message = (
                "Background preprocessing completed. Refresh the queue to review new applications. "
                "This simulates AI image processing of submitted applications. In production, "
                "all submitted applications would be pre-processed before compliance officers "
                "view and process them, so the background work would not slow officers down at all."
            )
            self._status.finished_at = utc_now_iso()
            for key, value in result.items():
                setattr(self._status, key, value)
