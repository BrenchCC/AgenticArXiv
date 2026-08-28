"""Thread-safe lifecycle management for cancellable chat runs."""

import threading
from typing import Dict


class ChatRunManager:
    """Register active chat runs and expose cooperative cancellation state."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cancelled: Dict[str, bool] = {}

    def register(self, run_id: str) -> None:
        """Register an active run by its client-provided identifier.

        Args:
            run_id: Unique identifier for one chat request.
        """
        with self._lock:
            self._cancelled.setdefault(run_id, False)

    def cancel(self, run_id: str) -> bool:
        """Request cooperative cancellation for an active run.

        Args:
            run_id: Unique identifier for one chat request.

        Returns:
            True after the cancellation request has been recorded.
        """
        with self._lock:
            self._cancelled[run_id] = True
            return True

    def is_cancelled(self, run_id: str) -> bool:
        """Return whether cancellation has been requested for a run.

        Args:
            run_id: Unique identifier for one chat request.
        """
        with self._lock:
            return self._cancelled.get(run_id, False)

    def finish(self, run_id: str) -> None:
        """Remove a completed run from active tracking.

        Args:
            run_id: Unique identifier for one chat request.
        """
        with self._lock:
            self._cancelled.pop(run_id, None)


chat_run_manager = ChatRunManager()
