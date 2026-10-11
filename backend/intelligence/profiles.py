"""Conservative, deterministic selection of read-only database table profiles.

A profile is an optimization hint, never an authorization mechanism.
Unsupported, compound, and follow-up requests always retain full access to
whatever the employee's existing RLS policies allow.
"""
import re
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Explicit matching terms are chosen by the backend, not the frontend.
INTENT_HINTS = (
    ('ownership', r'\b(who|owner|owns|responsible|contact|blocking)\b'),
    ('executive', r'\b(executive|leadership|board|company summary)\b'),
    ('workload', r'\b(workload|capacity|team|department|schedule|timetable|calendar)\b'),
    ('incidents', r'\b(incident|incidents|support|urgent|severity|triage)\b'),
    ('usage', r'\b(usage|adoption|engagement|active users)\b'),
    ('meeting', r'\b(meeting|meetings|brief me|client call|prepare for)\b'),
    ('projects', r'\b(project|projects|delivery|delayed|behind schedule)\b'),
)
FOLLOWUP_RE = re.compile(r'\b(this client|this project|focus on|switch to|change to|previous period|last \d+ days|compare|instead|move chart)\b')


def _usage_window(q: str, today):
    """Restrict usage rows to the current comparison window only.

    The composer defaults to 14 days and compares against the preceding 14.
    Return None for unsupported date grammar (fallback to full data).
    """
    if re.search(r'\b(tomorrow|today|yesterday|next week|last week|next month|last month|monday|tuesday|wednesday|thursday|friday)\b', q):
        return None
    match = re.search(r'\blast (\d+) days\b', q)
    if match:
        days = int(match[1])
        if not 1 <= days <= 90:
            return None
        end = today
        start = today - timedelta(days=days - 1)
    elif re.search(r'\b(last|next|on|from|since|between|before|after)\b', q):
        return None
    else:
        end = today
        start = today - timedelta(days=13)
    width = (end - start).days + 1
    return start - timedelta(days=width), end


def profile_for_request(request, *, today=None):
    """Return (profile, optional usage date window); None means full snapshot."""
    if os.getenv('KAIROS_INTELLIGENCE_FULL_SNAPSHOT', '').strip().lower() in {'1', 'true', 'yes'}:
        return None, None
    q = re.sub(r'\s+', ' ', request.input.lower()).strip()
    if request.selection or (request.context_token and FOLLOWUP_RE.search(q)):
        return None, None
    # Both generic ownership and a specific workflow in the same request may
    # require a broader join graph. Unknown and complex requests stay full.
    matched = [name for name, pattern in INTENT_HINTS if re.search(pattern, q)]
    if not matched:
        return None, None
    if len(matched) > 1 and re.search(r'\b(and|also|plus|together with)\b', q):
        return None, None
    profile = matched[0]
    # A pure timetable request needs a narrow, date-aware retrieval path.
    # The intent enum stays team_workload_planning; other workload prompts
    # retain their original profile and all existing v2 datasets.
    if profile == 'workload' and re.search(r'\b(schedule|timetable|calendar|appointments?|bookings?)\b', q):
        return 'calendar', None
    if profile == 'usage':
        window = _usage_window(q, today or datetime.now(ZoneInfo('Asia/Kolkata')).date())
        if window is None:
            return None, None
        return profile, window
    return profile, None
