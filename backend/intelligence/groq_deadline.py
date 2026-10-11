"""Fail-open latency guard for optional Pass 12B Groq ranking.

Existing, auth-scoped database work completes before this function runs.
Work always proceeds from a deep copy so that an abandoned Groq operation
cannot mutate the response that FastAPI is about to serialize.
"""
from concurrent.futures import ThreadPoolExecutor, TimeoutError as DeadlineExceeded
from threading import BoundedSemaphore
import os

from .groq_focus import groq_enrich
from .models import Workspace

# Bounded background execution: at most two provider attempts, no queue.
_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='kairos-groq')
_slots = BoundedSemaphore(value=2)


def _wait_seconds() -> float:
    try:
        seconds = float(os.getenv('KAIROS_GROQ_MAX_WAIT_SECONDS', '4.0'))
        if not 0.25 <= seconds <= 6.0:
            return 4.0
        return seconds
    except (ValueError, OverflowError):
        return 4.0


def groq_enrich_with_deadline(question: str, workspace: Workspace) -> Workspace:
    """Return ranked result only if ready promptly; else verified original.

    A timed-out worker may finish later but cannot write to DB, change the
    current response, or produce a late UI update. It still counts toward
    the existing local Groq usage ceilings.
    """
    if os.getenv('KAIROS_GROQ_ENABLED', '').strip().lower() not in {'1', 'true', 'yes'}:
        return workspace
    if not os.getenv('GROQ_API_KEY', '').strip():
        return workspace
    if workspace.status not in ('ready', 'partial') or not workspace.components:
        return workspace
    if not _slots.acquire(blocking=False):
        workspace.intelligence.status = 'fallback'
        return workspace
    try:
        # NEVER send the same object FastAPI will return to a background worker.
        verified_copy = workspace.model_copy(deep=True)
        future = _pool.submit(groq_enrich, question, verified_copy)
    except Exception:
        _slots.release()
        workspace.intelligence.status = 'fallback'
        return workspace
    # Releases the slot only when the network attempt truly ends.
    future.add_done_callback(lambda _f: _slots.release())
    try:
        return future.result(timeout=_wait_seconds())
    except (DeadlineExceeded, Exception):
        workspace.intelligence.status = 'fallback'
        return workspace
