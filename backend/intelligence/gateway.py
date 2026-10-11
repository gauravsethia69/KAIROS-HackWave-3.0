"""KAIROS read gateway: bounded, identity-partitioned snapshot reuse.

This is a latency optimization, not an authorization boundary. FastAPI must
verify the Supabase session AND employee_access on EVERY request before calling.
DB access on misses remains inside the existing transaction-local RLS context.

Writes must call invalidate_snapshots(...) after transaction COMMIT. Conflict,
booking and fresh-availability checks MUST bypass this cache and re-check in
one writable transaction before committing.
"""
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
from os import getenv
from threading import Event, RLock
from time import monotonic, perf_counter
from zoneinfo import ZoneInfo

from .repository import Snapshot, _read_scope, _calendar_window, load_snapshot

_ZONE = ZoneInfo('Asia/Kolkata')
_LOCK = RLock()
_ENTRIES = OrderedDict()
_INFLIGHT = {}
_MAX_ENTRIES = 24
_GENERATION = 0


def _ttl():
    """Short-lived and optional: 0 disables caching with no code changes."""
    try:
        return max(0, min(60, float(getenv('KAIROS_READ_CACHE_SECONDS', '20'))))
    except (TypeError, ValueError):
        return 20


def _key(user, *, profile, usage_window, request_text, now=None):
    # Tokens and database credentials are NEVER cache keys or logs.
    # Date bucket prevents stale 'tomorrow'/'next week' across midnight IST.
    local_day = (now or datetime.now(_ZONE)).astimezone(_ZONE).date().isoformat()
    scope, scope_value = _read_scope(profile, request_text)
    if scope in ('calendar_self', 'workload_self'):
        scope_value = user.employee_id
    elif scope_value is not None:
        # Exact-task IDs can be reused across prompt punctuation variations.
        value = scope_value.lower().strip() if scope == 'task_id' else ' '.join(scope_value.lower().split())
        scope_value = sha256(value.encode('utf-8')).hexdigest()
    elif scope is None:
        # When the repository has NO text-derived SQL scope, it reads the same
        # allowlisted profile regardless of the wording of the request.
        scope_value = 'unscoped'
    temporal = None
    if profile in ('calendar', 'workload'):
        window = _calendar_window(request_text, today=datetime.fromisoformat(local_day).date())
        temporal = tuple(d.isoformat() for d in window) if window else None
    usage = tuple(d.isoformat() for d in usage_window) if usage_window else None
    # Employee ID/role are checked afresh by current_user, before key access.
    return (str(user.id), user.employee_id, user.access_role,
            profile, scope, scope_value, temporal, usage, local_day)


def _clone(snapshot, *, cache_state, elapsed_ms):
    # Consumers must never modify the retained cache object: Snapshot wraps
    # plain dictionaries, and some downstream tools create/reshape datasets.
    output = Snapshot(deepcopy(snapshot.tables), retrieved_at=snapshot.retrieved_at,
                      limitations=list(snapshot.limitations))
    output.load_ms = round(elapsed_ms, 2)
    output.timings = {'cache_ms': round(elapsed_ms, 2)}
    output.cache_state = cache_state
    return output


def invalidate_snapshots(user_id=None):
    """Call after an approved write commits; no mutation before commit.

    Per-user invalidation removes only the matching verified UUID's entries.
    In multi-worker deployments, use shared invalidation/versioning or short
    TTL; this in-process function cannot clear other workers' private memory.
    """
    global _GENERATION
    with _LOCK:
        _GENERATION += 1  # discard reads already in flight before the write
        if user_id is None:
            _ENTRIES.clear()
        else:
            uid = str(user_id)
            for key in list(_ENTRIES):
                if key[0] == uid:
                    _ENTRIES.pop(key, None)


def load_read_snapshot(user, *, profile=None, usage_window=None,
                       request_text=None, fresh=False):
    """Authorization-scoped read-through cache + same-key single-flight.

    Safe high-stakes operations (meeting/conflict/approval) must pass fresh=True
    and should generally make targeted SQL queries instead of snapshots.
    """
    started = perf_counter()
    ttl = _ttl()
    if ttl <= 0 or fresh:
        result = load_snapshot(user, profile=profile, usage_window=usage_window,
                               request_text=request_text)
        result.cache_state = 'BYPASS'
        result.timings.setdefault('cache_ms', 0.0)
        return result
    key = _key(user, profile=profile, usage_window=usage_window,
               request_text=request_text)
    while True:
        with _LOCK:
            entry = _ENTRIES.get(key)
            now = monotonic()
            if entry and entry[0] > now:
                _ENTRIES.move_to_end(key)
                return _clone(entry[1], cache_state='HIT', elapsed_ms=(perf_counter()-started)*1000)
            if entry:
                _ENTRIES.pop(key, None)
            waiting = _INFLIGHT.get(key)
            if waiting is None:
                event = Event()
                generation = _GENERATION
                _INFLIGHT[key] = event
                break
        # Wait for same-user/same-scope work instead of issuing another DB read.
        if not waiting.wait(timeout=20):
            # Existing request may be hung. Fall back to own safe RLS-protected
            # read, rather than waiting forever or serving stale data.
            result = load_snapshot(user, profile=profile, usage_window=usage_window,
                                   request_text=request_text)
            result.cache_state = 'WAIT_TIMEOUT'
            return result
    try:
        result = load_snapshot(user, profile=profile, usage_window=usage_window,
                               request_text=request_text)
        # Don't retain truncated snapshots: a follow-up could otherwise treat
        # known-incomplete data as an authoritative cache hit.
        if not any('exceeded' in str(x) for x in result.limitations):
            with _LOCK:
                if generation == _GENERATION:
                    _ENTRIES[key] = (monotonic() + ttl, _clone(result, cache_state='STORED', elapsed_ms=0))
                    _ENTRIES.move_to_end(key)
                    while len(_ENTRIES) > _MAX_ENTRIES:
                        _ENTRIES.popitem(last=False)
        result.cache_state = 'MISS'
        result.timings.setdefault('cache_ms', 0.0)
        return result
    finally:
        with _LOCK:
            _INFLIGHT.pop(key, None)
            event.set()


def read_targeted(user, *, statement, parameters=(), max_rows=250):
    """Reusable narrow read for new features (meeting preview, conflict checks).

    The statement MUST be authored in backend source, with caller-provided
    values passed only as Psycopg bind parameters. This is NOT exposed as an
    arbitrary-SQL HTTP endpoint. Existing `user_connection` provides verified
    RLS claims, read-only transaction, and a database-side statement timeout.

    Always uncached: meeting availability must reflect current bookings.
    Returns (records, truncated, duration_metrics); caller must disclose
    truncation rather than treating the result as comprehensive.
    """
    from ..database import user_connection
    from psycopg.sql import Composable

    if not isinstance(statement, Composable):
        raise TypeError('Only backend-owned Psycopg SQL objects are accepted')
    if not isinstance(max_rows, int) or not (1 <= max_rows <= 1000):
        raise ValueError('Invalid bounded read size')
    durations = {}
    with user_connection(user, read_only=True, timings=durations) as connection:
        started = perf_counter()
        cursor = connection.execute(statement, tuple(parameters))
        durations['db_sql_ms'] = round((perf_counter()-started)*1000, 2)
        started = perf_counter()
        rows = cursor.fetchmany(max_rows + 1)
        durations['db_fetch_ms'] = round((perf_counter()-started)*1000, 2)
    return rows[:max_rows], len(rows) > max_rows, durations
