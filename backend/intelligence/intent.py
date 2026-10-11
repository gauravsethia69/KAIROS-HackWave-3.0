import re
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from zoneinfo import ZoneInfo

from .catalog import ENTITY_TABLE, title
from .knowledge import normalize
from .models import Candidate, Clarification, EntityRef, ResolvedIntent

PRIMARY = [
    ('ownership_lookup', r'\b(who|owner|owns|responsible|contact|blocking)\b'),
    ('executive_briefing', r'\b(executive|leadership|board|company summary)\b'),
    ('team_workload_planning', r'\b(workload|capacity|team|department|schedule|timetable|calendar)\b'),
    ('support_incident_command', r'\b(incident|incidents|support|urgent|severity|triage)\b'),
    ('product_usage_investigation', r'\b(usage|adoption|engagement|active users)\b'),
    ('client_meeting_prep', r'\b(meeting|meetings|brief me|client call|prepare for)\b'),
    ('project_delivery_review', r'\b(project|projects|delivery|delayed|behind schedule)\b'),
    ('entity_lookup', r'\b(task|tasks|assigned|employee|client|product|issue|contract|find|lookup)\b'),
]
STOP = set('who owns owner responsible is for the a an my me this that these those show review why what which to with at of please prepare investigate declining decline delayed project projects task tasks blocked blocking fix client meeting tomorrow today last days only reporting? everything assigned team workload focus change switch instead usage adoption product support urgent incidents summarize information table compare previous period move chart top'.split())


def requested_work_types(query):
    """Work item nouns are type constraints, not generic search terms.

    In particular, ``blocked SSO task`` must not become an SSO-named
    *project* ownership lookup just because a project is also a fuzzy match.
    Plural nouns request collections and do not require one unique entity.
    """
    work_words = {
        'task': r'\btask\b',
        'project': r'\bproject\b',
        'issue': r'\b(?:issue|incident)\b',
        'contract': r'\bcontract\b',
        'meeting': r'\bmeeting\b',
    }
    return {kind for kind, pattern in work_words.items() if re.search(pattern, query)}


def entity_matches(snapshot, text, entity_type, removed=()):
    q = normalize(text)
    tokens = set(q.split()) - STOP - set(removed)
    candidates = []
    for row in snapshot.rows(ENTITY_TABLE[entity_type]):
        name, identifier = normalize(title(row)), normalize(row['id'])
        aliases = {name}
        if entity_type == 'client':
            aliases.add(' '.join(w for w in name.split() if w not in {'corp', 'corporation', 'group', 'inc', 'ltd', 'studio'}))
        if entity_type == 'product':
            aliases.add(name.removeprefix('soryu '))
        score = 0.0
        # A human-readable ID such as "atlas" must not outrank two names
        # beginning "Atlas Media". Explicit ID syntax remains authoritative.
        id_mentioned = re.search(r'(?<!\w)' + re.escape(identifier) + r'(?!\w)', q)
        explicit_id = re.search(r'\b(?:' + entity_type + r'|id)\s+' + re.escape(identifier) + r'(?!\w)', q)
        if id_mentioned and (q == identifier or explicit_id or any(c.isdigit() for c in identifier)):
            score = 1.0
        for alias in aliases:
            if alias and f' {alias} ' in f' {q} ':
                score = max(score, .99 if alias == name else (.93 if entity_type == 'client' else .95))
        name_tokens = set(name.split()) - STOP
        meaningful = tokens & name_tokens
        if meaningful:
            # Count distinctive matching words and how much of the user's
            # entity description they cover. The old .86 + .01/word ranking
            # tied 'Northstar SSO readiness' with 'Northstar renewal readiness'.
            coverage = len(meaningful) / max(1, len(tokens))
            specificity = len(meaningful) / max(1, len(name_tokens))
            relevance = min(.975, .72 + .055 * len(meaningful) + .065 * coverage + .025 * specificity)
            score = max(score, relevance)
        # Fuzzy only meaningful words of at least four characters; no arbitrary nearest match.
        similarity = max((SequenceMatcher(None, a, b).ratio() for a in tokens if len(a) >= 4 for b in name.split() if len(b) >= 4), default=0)
        # Fuzzy similarity helps with misspellings, but must never turn one
        # shared word (e.g. 'readiness') into a near-tie with a record that
        # matches both distinctive words ('SSO readiness').
        if similarity >= .83 and not meaningful:
            score = max(score, round(similarity * .90, 3))
        if score >= .74:
            candidates.append(Candidate(entity=EntityRef(entity_type=entity_type, entity_id=row['id']), label=title(row), score=score))
    return sorted(candidates, key=lambda c: (-c.score, c.entity.entity_id))


def resolve_intent(request, snapshot, user, previous=None, today=None):
    today = today or datetime.now(ZoneInfo('Asia/Kolkata')).date()
    q = normalize(request.input)
    name = next((name for name, pattern in PRIMARY if re.search(pattern, q)), None)
    followup = bool(re.search(r'\b(last \d+ days|compare|previous period|move|table|focus|switch|change|this client|blocked work)\b', q))
    if not name:
        name = previous.name if previous and followup else 'unsupported'
    if previous and q in ('focus on blocked work', 'focus on unresolved issues'):
        name = previous.name
    resolved = ResolvedIntent(name=name, confidence=.82 if name != 'unsupported' else .1)
    # Client context is useful for genuine follow-ups ('this client',
    # 'focus on blocked work'), but must not leak into a NEW self-contained
    # question. The React app sends a context token for successive requests.
    # Formerly we reused entities whenever the intent name happened to match,
    # silently filtering 'task t1' through an unrelated prior client/project.
    reuse_context = previous is not None and (followup or request.selection is not None)
    if reuse_context:
        resolved.entities = [ref.model_copy() for ref in previous.entities if ref.entity_type in ('client', 'product') or name == previous.name]
        if name in ('executive_briefing', 'team_workload_planning') and name != previous.name:
            resolved.entities = []
        for field in ('date_from', 'date_to', 'blocked_only', 'unresolved_only', 'overdue_only', 'compare', 'presentation', 'chart_first'):
            setattr(resolved, field, getattr(previous, field))
        resolved.changes.append(f'Goal changed from {previous.name} to {name}.' if previous.name != name else 'Goal retained; relevant context reused.')
    elif previous:
        resolved.changes.append('New independent request; previous entity filters cleared.')
    if request.selection:
        snapshot.entity(request.selection)
        resolved.entities = [e for e in resolved.entities if e.entity_type != request.selection.entity_type] + [request.selection]
    # User-selected calendar navigation: bounded ISO date windows. Parse the
    # original text, because normalize() removes punctuation from date tokens.
    explicit_window = (re.search(r'\bfrom\s+(\d{4}-\d{2}-\d{2})\s+to\s+(\d{4}-\d{2}-\d{2})\b', request.input, re.I)
                       if name == 'team_workload_planning' and re.search(r'\b(schedule|timetable|calendar)\b', q) else None)
    if explicit_window:
        try:
            from datetime import date as date_type
            start, end = date_type.fromisoformat(explicit_window[1]), date_type.fromisoformat(explicit_window[2])
            if end < start or (end - start).days > 30:
                raise ValueError('Unsupported schedule date span')
            resolved.date_from, resolved.date_to = start, end
        except ValueError:
            resolved.clarification = Clarification(question='Choose a valid calendar range of 1–31 days, in YYYY-MM-DD format.')
            return resolved
    elif 'tomorrow' in q:
        resolved.date_from = resolved.date_to = today + timedelta(days=1)
    elif 'today' in q:
        resolved.date_from = resolved.date_to = today
    elif re.search(r'\b(next|last) week\b', q):
        start = today + timedelta(days=7-today.weekday()) if 'next week' in q else today - timedelta(days=7+today.weekday())
        resolved.date_from, resolved.date_to = start, start + timedelta(days=6)
    elif match := re.search(r'last (\d+) days', q):
        days = int(match[1])
        if not 1 <= days <= 90:
            resolved.clarification = Clarification(question='Choose a date window between 1 and 90 days.', suggestions=['Show only the last 14 days', 'Show only the last 30 days'])
            return resolved
        resolved.date_from, resolved.date_to = today - timedelta(days=days - 1), today
    elif re.search(r'\b(yesterday|next month|last month|monday|tuesday|wednesday|thursday|friday)\b', q):
        resolved.clarification = Clarification(question='That date expression is not supported by this rules engine. Use today, tomorrow, next week, last week or last N days.')
        return resolved
    resolved.blocked_only = resolved.blocked_only or bool(re.search(r'\b(blocked|blocking|blocker)\b', q))
    resolved.overdue_only = resolved.overdue_only or 'overdue' in q
    resolved.unresolved_only = resolved.unresolved_only or 'unresolved' in q
    resolved.compare = resolved.compare or 'compare' in q or 'previous period' in q
    if 'table' in q:
        resolved.presentation = 'table'
    if 'chart' in q and ('top' in q or 'first' in q):
        resolved.chart_first = True
    removed = set()
    kinds = ['client', 'product', 'department', 'employee']
    requested = requested_work_types(q) if name in ('ownership_lookup', 'entity_lookup') else set()
    # For an explicit work item, search that table rather than also searching
    # every vaguely related project/task. Contextual project/client records
    # can still be derived safely from the matched item's foreign keys.
    allow_general_work = not requested
    if 'project' in requested or (allow_general_work and (name in ('project_delivery_review', 'ownership_lookup') or re.search(r'\bprojects?\b', q))):
        kinds.append('project')
    if 'task' in requested or (allow_general_work and (name in ('ownership_lookup', 'entity_lookup') or re.search(r'\b(task|fix|blocker|blocking)\b', q))):
        kinds.append('task')
    if 'issue' in requested or (allow_general_work and name == 'ownership_lookup' and re.search(r'\b(incident|issue)\b', q)):
        kinds.append('issue')
    if 'contract' in requested or (allow_general_work and re.search(r'\bcontract\b', q)):
        kinds.append('contract')
    if 'meeting' in requested or (allow_general_work and name == 'ownership_lookup' and re.search(r'\bmeeting\b', q)):
        kinds.append('meeting')
    explicit = set()
    for kind in kinds:
        if request.selection and request.selection.entity_type == kind:
            explicit.add(kind)
            continue
        matches = entity_matches(snapshot, request.input, kind, removed)
        client = next((r for r in resolved.entities if r.entity_type == 'client'), None)
        if client and kind in ('project', 'task', 'issue'):
            matches = [c for c in matches if snapshot.entity(c.entity).get('client_id') == client.entity_id]
        if resolved.blocked_only and kind == 'task':
            matches = [c for c in matches if snapshot.entity(c.entity).get('blocker_task_id') or str(snapshot.entity(c.entity).get('status')).lower() == 'blocked']
        if not matches:
            continue
        # Exact references outrank weaker aliases; competing partials are never guessed.
        best = matches[0].score
        contenders = [c for c in matches if c.score >= best - .025]
        if len(contenders) > 1:
            resolved.clarification = Clarification(question=f'Which {kind} do you mean?', candidates=contenders[:10])
            resolved.confidence = .45
            return resolved
        match = matches[0]
        resolved.entities = [e for e in resolved.entities if e.entity_type != kind] + [match.entity]
        explicit.add(kind)
        removed.update(normalize(match.label).split())
        resolved.confidence = min(resolved.confidence, match.score)
    # Changing the selected client invalidates stale project/task context.
    if 'client' in explicit:
        client_id = next(e.entity_id for e in resolved.entities if e.entity_type == 'client')
        resolved.entities = [e for e in resolved.entities if e.entity_type not in ('project', 'task', 'issue') or snapshot.entity(e).get('client_id') == client_id]
    if re.search(r'\b(my|me)\b', q):
        employee = snapshot.get('employees', user.employee_id)
        if not employee:
            resolved.clarification = Clarification(question='Your authorized employee record is not visible. Ask the data administrator to review access.')
            return resolved
        is_schedule = name == 'team_workload_planning' and re.search(r'\b(schedule|timetable|calendar|appointments?|bookings?)\b', q)
        kind, identifier = ('department', employee.get('department_id')) if name == 'team_workload_planning' and not is_schedule else ('employee', user.employee_id)
        if identifier:
            resolved.entities = [e for e in resolved.entities if e.entity_type not in ('employee', 'department')] + [EntityRef(entity_type=kind, entity_id=identifier)]
    # An explicit singular work-item request must never silently fall back to
    # a client, employee or similarly named work-item type.
    if name == 'ownership_lookup' and requested:
        found = {ref.entity_type for ref in resolved.entities}
        missing = requested - found
        if missing:
            item = sorted(missing)[0]
            resolved.clarification = Clarification(
                question=f'I could not identify the {item} you asked about. Please provide its ID or a more specific title.',
            )
            resolved.confidence = min(resolved.confidence, .45)
            return resolved
    # A personal timetable needs a target; never silently display everyone.
    if name == 'team_workload_planning' and re.search(r'\b(schedule|timetable|calendar|appointments?|bookings?)\b', q):
        if not any(e.entity_type in ('employee', 'department') for e in resolved.entities):
            resolved.clarification = Clarification(
                question='Whose schedule should I show? Specify an employee or department.',
                suggestions=['Show my schedule next week', 'Show Engineering schedule next week'])
            return resolved
    if name == 'unsupported' and resolved.entities:
        resolved.name, resolved.confidence = 'entity_lookup', .7
    if name == 'client_meeting_prep' and not any(e.entity_type == 'client' for e in resolved.entities):
        resolved.clarification = Clarification(question='Which client meeting should I prepare?', candidates=[Candidate(entity=EntityRef(entity_type='client', entity_id=r['id']), label=title(r), score=1) for r in snapshot.rows('clients')[:10]])
    if 'this client' in q and not any(e.entity_type == 'client' for e in resolved.entities):
        resolved.clarification = Clarification(question='No client is selected. Choose a visible client.', candidates=[Candidate(entity=EntityRef(entity_type='client', entity_id=r['id']), label=title(r), score=1) for r in snapshot.rows('clients')[:10]])
    if resolved.name == 'ownership_lookup' and not any(e.entity_type in ('project', 'task', 'issue', 'contract', 'meeting', 'client') for e in resolved.entities):
        resolved.clarification = Clarification(question='No unique recorded work item matched. Provide its exact ID or more of its title.', suggestions=['Who owns project p1?', 'Show everything assigned to me'])
    return resolved
