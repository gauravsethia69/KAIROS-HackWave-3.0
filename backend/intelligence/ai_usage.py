"""Pass 12D. Minimal process-local AI accounting and per-identity TTL cache.

Never stores secrets, prompts, SQL, model raw outputs, or database snapshots in
telemetry. This is NOT a provider billing quota; server restarts reset counters.
"""
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from threading import RLock
from time import monotonic

_lock = RLock()
_totals = defaultdict(lambda: {'attempts': 0, 'responses': 0, 'input_tokens': 0, 'output_tokens': 0, 'unknown_usage': 0})
_cache = {}  # (feature, verified-user-scope, digest) -> (expiration, success response)
_CACHE_MAX = 120


def _safe_count(value):
    return min(max(value, 0), 5_000_000) if type(value) is int else 0


def record_attempt(feature: str, viewer: str = ''):
    if feature not in ('company_guide', 'workspace_explanation', 'legacy_ranking', 'general_advice'):
        return
    with _lock:
        _totals[(feature, viewer)]['attempts'] += 1


def record_completion(feature: str, provider_usage: object, viewer: str = ''):
    if feature not in ('company_guide', 'workspace_explanation', 'legacy_ranking', 'general_advice'):
        return
    usage = provider_usage if isinstance(provider_usage, dict) else {}
    # Groq uses prompt_tokens + completion_tokens; cached input is already
    # included in prompt_tokens and must NOT be double-counted.
    prompt = _safe_count(usage.get('prompt_tokens'))
    completion = _safe_count(usage.get('completion_tokens'))
    with _lock:
        row = _totals[(feature, viewer)]
        row['responses'] += 1
        row['input_tokens'] += prompt
        row['output_tokens'] += completion
        row['unknown_usage'] += int(not bool(usage))


def usage_snapshot(viewer: str = ''):
    """Report only this authenticated viewer's counters; no cross-user data."""
    with _lock:
        by_feature = {}
        for (feature, owner), stats in _totals.items():
            if owner == viewer:
                by_feature[feature] = deepcopy(stats)
        return {
            'scope': 'this_backend_process_only',
            'billing_authority': 'Groq Console usage; these metrics reset on restart',
            'by_feature': by_feature,
            'recorded_at': datetime.now(timezone.utc).isoformat(),
        }


def cache_lookup(feature: str, viewer: str, digest: str):
    if not viewer or not digest:
        return None
    key = (feature, viewer, digest)
    with _lock:
        row = _cache.get(key)
        if not row:
            return None
        if row[0] < monotonic():
            del _cache[key]
            return None
        return deepcopy(row[1])


def cache_success(feature: str, viewer: str, digest: str, result: dict, ttl: int = 600):
    if not viewer or not digest or result.get('status') != 'enriched':
        return
    key = (feature, viewer, digest)
    with _lock:
        if len(_cache) >= _CACHE_MAX:
            # Bound private in-memory storage and expire older entries first.
            now = monotonic()
            for k, v in list(_cache.items()):
                if v[0] < now:
                    del _cache[k]
            if len(_cache) >= _CACHE_MAX:
                _cache.pop(next(iter(_cache)))
        _cache[key] = (monotonic() + max(1, min(ttl, 1200)), deepcopy(result))
