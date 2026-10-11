"""KAIROS Reflex v1: conservative, read-only meeting counterfactuals.

Uses the *existing* authorized meeting preview as the source of truth for
conflicts and no database write paths. Candidate slots are hypothetical;
creation ALWAYS goes back through /scheduling/preview and /scheduling/confirm.
"""
from datetime import timedelta

from .meeting_scheduler import MeetingProposal, _validate, _participants, preview_meeting
from ..auth import Identity
from ..database import user_connection

# One baseline + two bounded alternatives. Avoid user-visible delays on Render Free.
_OFFSETS = (("Requested slot", timedelta()), ("One hour later", timedelta(hours=1)),
            ("Next day, same time", timedelta(days=1)))
_CLOSED = frozenset({'done', 'completed', 'resolved', 'closed', 'cancelled'})


def _overlap_hours(conflicts: list[dict], start, end) -> float:
    """Union of overlaps per employee; duplicate meeting/calendar records count once."""
    from datetime import datetime
    intervals: dict[str, list[tuple]] = {}
    for row in conflicts:
        a, b = datetime.fromisoformat(row['starts_at']), datetime.fromisoformat(row['ends_at'])
        a, b = max(a, start), min(b, end)
        if a < b:
            intervals.setdefault(row['employee_id'], []).append((a, b))
    minutes = 0.0
    for spans in intervals.values():
        current = None
        for a, b in sorted(spans):
            if current and a <= current[1]:
                current = (current[0], max(current[1], b))
            else:
                if current:
                    minutes += (current[1] - current[0]).total_seconds() / 60
                current = (a, b)
        if current:
            minutes += (current[1] - current[0]).total_seconds() / 60
    return round(minutes / 60, 2)


def _task_context(user: Identity, ids: list[str]) -> dict:
    """Aggregate ONLY visible, assigned tasks; estimates are backlog, not bookings."""
    with user_connection(user, read_only=True) as connection:
        rows = connection.execute("""
            SELECT owner_employee_id, status, estimated_hours
            FROM public.tasks WHERE owner_employee_id = ANY(%s::text[])
            ORDER BY id LIMIT 201
        """, (ids,)).fetchall()
    truncated = len(rows) > 200
    visible = rows[:200]
    active = [r for r in visible if str(r.get('status', '')).lower() not in _CLOSED]
    hours = sum(float(r['estimated_hours']) for r in active if r['estimated_hours'] is not None)
    return {'visible_open_tasks': len(active), 'estimated_backlog_hours': round(hours, 2),
            'tasks_without_estimates': sum(r['estimated_hours'] is None for r in active),
            'truncated': truncated,
            'notice': ('Task results were capped, so workload totals are incomplete.' if truncated else
                       'Task estimates describe visible unfinished backlog, not calendar bookings or a weekly commitment.')}


def compare_meeting(proposal: MeetingProposal, user: Identity) -> dict:
    """Read-only, three hypothetical slots, ranking by recorded conflicts only.

    This endpoint has no write capability; using a ranked slot updates the
    editable meeting form, which must be re-previewed and explicitly confirmed.
    """
    _validate(proposal)
    ids = _participants(proposal, user)
    candidates = []
    for label, offset in _OFFSETS:
        attempt = proposal.model_copy(update={'starts_at': proposal.starts_at + offset,
                                              'ends_at': proposal.ends_at + offset})
        try:
            _validate(attempt)
        except Exception:
            # Out-of-range next-day candidates are omitted, never invented.
            continue
        preview = preview_meeting(attempt, user)
        affected = sorted(set(c['employee_id'] for c in preview['conflicts']))
        start = attempt.starts_at
        end = attempt.ends_at
        candidates.append({
            'label': label, 'starts_at': preview['starts_at'], 'ends_at': preview['ends_at'],
            'recorded_clear': bool(preview['can_create']), 'truncated': bool(preview['truncated']),
            'affected_employee_count': len(affected), 'recorded_overlap_count': len(preview['conflicts']),
            'overlap_participant_hours': _overlap_hours(preview['conflicts'], start, end),
            'conflicts': preview['conflicts'][:20],
            'more_conflicts': len(preview['conflicts']) > 20,
            'notice': preview['notice'],
        })
    # The actual booking preview provides conflict authority; scores here are
    # comparative only, not availability probabilities or workload forecasts.
    ranked = sorted(range(len(candidates)), key=lambda i: (
        not candidates[i]['recorded_clear'], candidates[i]['truncated'],
        candidates[i]['affected_employee_count'],
        candidates[i]['overlap_participant_hours'], i))
    for rank, i in enumerate(ranked, 1):
        candidates[i]['rank'] = rank
    context = _task_context(user, ids)
    return {
        'status': 'compared', 'source': 'authorized-scheduling-preview', 'read_only': True,
        'time_zone': 'Asia/Kolkata', 'participants_count': len(ids),
        'candidates': candidates, 'task_context': context,
        'warning': ('These are hypothetical alternatives, not reservations. Only recorded overlaps can be evaluated. '
                    'No overlap does not guarantee availability. Recheck the selected slot in Review meeting '
                    'and require explicit confirmation to create anything.'),
    }
