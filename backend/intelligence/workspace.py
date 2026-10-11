import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from .catalog import ENTITY_TABLE, TABLE_ENTITY, title
from .evidence import EvidenceSet
from .functional_data import graph_data, schedule_directory, scheduled_meetings, specific_action
from .models import BoundProps, Claim, ComponentPlan, EntityRef, Workspace
from ..services.responsibility import resolve as responsibility
from ..schemas import BINDINGS

SELECTORS = {'clients': 'clients', 'meetings': 'meetings', 'communications': 'communications', 'product_usage': 'usage', 'projects': 'projects', 'tasks': 'tasks', 'issues': 'issues', 'activity_events': 'activity'}
LAYOUTS = {
    'client_meeting_prep': [('MeetingBrief', 'meetings'), ('ClientProfile', 'clients'), ('ActivityTimeline', 'communications'), ('IssuePanel', 'issues'), ('TaskList', 'tasks'), ('InsightPanel', 'insights')],
    'product_usage_investigation': [('UsageChart', 'usage'), ('MetricCards', 'usage'), ('IssuePanel', 'issues'), ('ActivityTimeline', 'activity'), ('InsightPanel', 'insights')],
    'project_delivery_review': [('ProjectProgress', 'projects'), ('TaskList', 'tasks'), ('IssuePanel', 'issues'), ('ActivityTimeline', 'activity'), ('InsightPanel', 'insights')],
    'support_incident_command': [('IssuePanel', 'issues'), ('ActivityTimeline', 'communications'), ('TaskList', 'tasks'), ('InsightPanel', 'insights')],
    'team_workload_planning': [('TaskList', 'tasks'), ('ProjectProgress', 'projects'), ('InsightPanel', 'insights')],
    'executive_briefing': [('ProjectProgress', 'projects'), ('ClientProfile', 'clients'), ('IssuePanel', 'issues'), ('MeetingBrief', 'meetings'), ('InsightPanel', 'insights')],
    'ownership_lookup': [('TaskList', 'tasks'), ('ProjectProgress', 'projects'), ('IssuePanel', 'issues'), ('InsightPanel', 'insights')],
    'entity_lookup': [('DataTable', 'tasks'), ('ProjectProgress', 'projects'), ('ClientProfile', 'clients'), ('MeetingBrief', 'meetings'), ('IssuePanel', 'issues'), ('InsightPanel', 'insights')],
}
PLAYBOOK = {'client_meeting_prep': 'playbook-client-meeting-prep', 'product_usage_investigation': 'playbook-usage-decline', 'project_delivery_review': 'playbook-delayed-project', 'support_incident_command': 'playbook-support-triage', 'team_workload_planning': 'playbook-team-workload', 'executive_briefing': 'playbook-executive-briefing', 'ownership_lookup': 'playbook-blocker-escalation', 'entity_lookup': 'ownership-conventions'}
LABELS = {'client_meeting_prep': 'Client meeting preparation', 'product_usage_investigation': 'Product usage investigation', 'project_delivery_review': 'Project delivery review', 'support_incident_command': 'Support incident command', 'team_workload_planning': 'Team workload planning', 'executive_briefing': 'Executive briefing', 'ownership_lookup': 'Recorded ownership', 'entity_lookup': 'Entity workspace', 'unsupported': 'Clarify your goal'}
TITLES = {'clients': 'Client context', 'meetings': 'Meetings and recorded agenda', 'communications': 'Recorded communication', 'usage': 'Product usage', 'projects': 'Delivery progress', 'tasks': 'Assignments and blockers', 'issues': 'Issues and responders', 'activity': 'Related activity', 'insights': 'Evidence and next steps'}



def ownership_focus(intent):
    """Choose one primary answer target, not all related client/product aliases.

    Ownership of a project is not the same as ownership of its client.
    For an explicit task, project, incident, contract or meeting lookup, the
    work item is authoritative; other entities remain supporting context.
    """
    priority = ('task', 'project', 'issue', 'contract', 'meeting', 'client', 'employee')
    for kind in priority:
        for ref in intent.entities:
            if ref.entity_type == kind:
                return ref
    return None


def ownership_layout(intent):
    focus = ownership_focus(intent)
    choice = {
        'task': ('TaskList', 'tasks'),
        'project': ('ProjectProgress', 'projects'),
        'issue': ('IssuePanel', 'issues'),
        'meeting': ('MeetingBrief', 'meetings'),
        'client': ('ClientProfile', 'clients'),
    }.get(focus.entity_type if focus else '')
    # A direct factual answer gets a concise explanation, followed by one
    # relevant detail widget; no unrelated issue/project/meeting panels.
    return [('InsightPanel', 'insights'), choice] if choice else [('InsightPanel', 'insights')]


def open_work(row):
    return str(row.get('status', '')).lower() not in {'done', 'completed', 'resolved', 'closed', 'cancelled'}


def parse_date(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None




def schedule_local_date(value):
    """Interpret timezone-aware schedule timestamps in the workspace timezone.

    A Sunday night UTC block can belong to Monday's employee timetable in
    India, and must not disappear from a 'next week' request.
    """
    if value is None:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return dt.astimezone(ZoneInfo('Asia/Kolkata')).date() if dt.tzinfo else dt.date()
    except (TypeError, ValueError, OverflowError):
        return None


def compose_meeting_brief(snapshot, rows, intent, today, sources, claims, result):
    """A meeting brief grounded in visible client records, even if no event is scheduled.

    Supplemental ``datasets.meeting_brief`` is additive: existing v2 widgets,
    properties and evidence navigation keep their current contracts.
    """
    client_ref = next((ref for ref in intent.entities if ref.entity_type == 'client'), None)
    meeting_ref = next((ref for ref in intent.entities if ref.entity_type == 'meeting'), None)
    meeting_row = snapshot.get('meetings', meeting_ref.entity_id) if meeting_ref else None
    client_id = client_ref.entity_id if client_ref else (meeting_row or {}).get('client_id')
    if not client_id and len(rows['clients']) == 1:
        client_id = rows['clients'][0]['id']
    client = snapshot.get('clients', client_id) if client_id else None
    if not client:
        result['limitations'].append('A client must be identified to prepare a specific meeting brief.')
        return

    all_meetings = [m for m in snapshot.rows('meetings') if m.get('client_id') == client_id]
    all_meetings.sort(key=lambda m: (str(m.get('date') or ''), str(m.get('starts_at') or ''), m['id']), reverse=True)
    planned = list(rows['meetings'])
    if meeting_row and meeting_row not in planned:
        planned = [meeting_row]
    # Only an actual meeting on the requested date can be considered scheduled.
    historical = [m for m in all_meetings if parse_date(m.get('date')) and parse_date(m['date']) < today]
    last_meeting = historical[0] if historical else None
    manager = snapshot.get('employees', client.get('account_manager_id'))
    focus = planned[0] if planned else None
    evidence_ids = [sources.database('clients', client)]
    if manager:
        evidence_ids.append(sources.database('clients', client, 'account_manager_id'))
        evidence_ids.append(sources.database('employees', manager))
        claims.append(Claim(kind='observation',
                            text=f'{manager["full_name"]} is the recorded account manager for {title(client)} (not necessarily the meeting organizer).',
                            evidence_ids=evidence_ids[-2:]))
    if focus:
        event_evidence = [sources.database('meetings', focus, key) for key in ('title', 'date')]
        organizer = snapshot.get('employees', focus.get('organizer_employee_id'))
        sentence = f'Meeting found: {title(focus)} on {focus.get("date")}.'
        if organizer:
            sentence += f' Recorded organizer: {organizer["full_name"]}.'
            event_evidence.extend([sources.database('meetings', focus, 'organizer_employee_id'), sources.database('employees', organizer)])
        claims.insert(0, Claim(kind='observation', text=sentence, evidence_ids=event_evidence))
        evidence_ids.extend(event_evidence)
    else:
        timeframe = (f'on {intent.date_from.isoformat()}' if intent.date_from and intent.date_to == intent.date_from
                     else f'between {intent.date_from.isoformat()} and {intent.date_to.isoformat()}' if intent.date_from and intent.date_to
                     else 'in the upcoming search window')
        claims.insert(0, Claim(kind='uncertainty',
                        text=f'No {title(client)} meeting was found {timeframe} in the accessible meeting records. Do not assume a meeting is scheduled.'))
        if last_meeting:
            previous_evidence = [sources.database('meetings', last_meeting, 'date'), sources.database('meetings', last_meeting, 'title')]
            claims.append(Claim(kind='observation', text=f'Latest recorded past meeting: {title(last_meeting)} on {last_meeting["date"]}.',
                                evidence_ids=previous_evidence))
            evidence_ids.extend(previous_evidence)

    severity_rank = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
    open_issues = sorted((r for r in snapshot.rows('issues') if r.get('client_id') == client_id and open_work(r)),
                         key=lambda r: (severity_rank.get(str(r.get('severity')).lower(), 4), r['id']))[:4]
    projects = sorted((r for r in snapshot.rows('projects') if r.get('client_id') == client_id),
                      key=lambda r: ({'delayed': 0, 'at risk': 1, 'on track': 2}.get(str(r.get('status')).lower(), 3), r['id']))[:4]
    recent_comms = sorted((r for r in snapshot.rows('communications') if r.get('client_id') == client_id),
                          key=lambda r: (str(r.get('date') or ''), r['id']), reverse=True)[:3]
    topics = []
    for issue in open_issues[:3]:
        ids = [sources.database('issues', issue, 'status'), sources.database('issues', issue, 'severity')]
        topics.append({'type': 'issue', 'entity_id': issue['id'], 'title': title(issue),
                       'reason': f'Recorded {issue.get("severity")} issue; status {issue.get("status")}', 'evidence_ids': ids})
        evidence_ids.extend(ids)
    for project in projects[:2]:
        ids = [sources.database('projects', project, 'status')]
        topics.append({'type': 'project', 'entity_id': project['id'], 'title': title(project),
                       'reason': f'Recorded project status: {project.get("status")}', 'evidence_ids': ids})
        evidence_ids.extend(ids)
    for comm in recent_comms:
        evidence_ids.append(sources.database('communications', comm))
    if topics:
        claims.append(Claim(kind='proposed_action',
                            text=f'Suggested briefing topics for {title(client)}: ' + '; '.join(t['title'] for t in topics[:3]) + '. These are proposals derived from current records, not an approved meeting agenda.',
                            evidence_ids=sorted({key for item in topics[:3] for key in item['evidence_ids']})))
    result['datasets']['meeting_brief'] = [{
        'id': f'brief-{client_id}', 'client_id': client_id, 'client_name': title(client),
        'requested_date_from': intent.date_from.isoformat() if intent.date_from else None,
        'requested_date_to': intent.date_to.isoformat() if intent.date_to else None,
        'scheduled_meeting_found': bool(focus),
        'scheduled_meeting_ids': [m['id'] for m in planned[:5]],
        'latest_past_meeting_id': (last_meeting or {}).get('id'),
        'latest_past_meeting_date': (last_meeting or {}).get('date'),
        'account_manager_id': client.get('account_manager_id'),
        'account_manager_name': (manager or {}).get('full_name'),
        'suggested_topics': topics[:5],
        'recent_communication_ids': [c['id'] for c in recent_comms],
        'evidence_ids': sorted(set(evidence_ids)),
        'status': 'meeting_recorded' if focus else 'no_meeting_found',
    }]
    result['integration_requirements'].append('Optional additive datasets.meeting_brief contains agenda suggestions and date verification. Existing v2 widget bindings are unchanged.')


def compose_executive_summary(snapshot, sources, claims, result):
    """A small chart-ready portfolio summary; no inferred causes or financial totals."""
    projects = list(snapshot.rows('projects'))
    contracts = list(snapshot.rows('contracts'))
    clients = list(snapshot.rows('clients'))
    if not projects:
        return
    state_count = lambda rows, key: {status: sum(str(r.get(key, '')).lower() == status for r in rows)
                                      for status in ('delayed', 'at risk', 'on track')}
    counts = state_count(projects, 'status')
    renewal_due = sum(str(c.get('status', '')).lower() == 'renewal due' for c in contracts)
    at_risk_clients = sum(str(c.get('health', '')).lower() == 'at risk' for c in clients)
    ids = [sources.database('projects', p, 'status') for p in projects]
    claims.insert(0, Claim(kind='calculation',
                           text=(f'Portfolio: {counts["delayed"]} delayed, {counts["at risk"]} at-risk, '
                                 f'{counts["on track"]} on-track projects out of {len(projects)} recorded.'),
                           evidence_ids=ids))
    if contracts:
        claims.insert(1, Claim(kind='calculation', text=f'{renewal_due} of {len(contracts)} contracts are marked Renewal Due; this does not establish renewal loss.',
                               evidence_ids=[sources.database('contracts', c, 'status') for c in contracts]))
    result['datasets']['portfolio_summary'] = [{
        'id': 'portfolio-summary', 'total_projects': len(projects),
        'delayed_projects': counts['delayed'], 'at_risk_projects': counts['at risk'],
        'on_track_projects': counts['on track'], 'contracts_renewal_due': renewal_due,
        'total_contracts': len(contracts), 'clients_at_risk': at_risk_clients,
        'evidence_ids': ids,
    }]
    result['integration_requirements'].append('Optional additive datasets.portfolio_summary supports chart/KPI adapters; the existing v2 registry is unchanged.')

def select_rows(snapshot, intent, today):
    selected = {e.entity_type: e.entity_id for e in intent.entities}
    project = snapshot.get('projects', selected.get('project'))
    task = snapshot.get('tasks', selected.get('task'))
    if task:
        selected.setdefault('project', task.get('project_id'))
        project = snapshot.get('projects', task.get('project_id'))
    if project:
        selected.setdefault('client', project.get('client_id'))
    employee_ids = None
    if selected.get('department'):
        employee_ids = {r['id'] for r in snapshot.rows('employees') if r.get('department_id') == selected['department']}
    if selected.get('employee'):
        employee_ids = {selected['employee']}
    rows = {}
    for table in SELECTORS:
        result = list(snapshot.rows(table))
        for kind, fk in [('client', 'client_id'), ('product', 'product_id'), ('project', 'project_id')]:
            identifier = selected.get(kind)
            if not identifier:
                continue
            if table == ENTITY_TABLE[kind]:
                result = [r for r in result if r['id'] == identifier]
            elif any(fk in r for r in result):
                result = [r for r in result if r.get(fk) == identifier]
        if table in ('tasks', 'issues') and selected.get(TABLE_ENTITY[table]):
            result = [r for r in result if r['id'] == selected[TABLE_ENTITY[table]]]
        if employee_ids is not None:
            if table in ('tasks', 'projects', 'issues'):
                result = [r for r in result if r.get('owner_employee_id') in employee_ids]
            elif table == 'meetings':
                attending = {r['meeting_id'] for r in snapshot.rows('meeting_participants') if r.get('employee_id') in employee_ids}
                result = [r for r in result if r.get('organizer_employee_id') in employee_ids or r['id'] in attending]
            elif table == 'communications':
                result = [r for r in result if r.get('employee_id') in employee_ids]
            elif table == 'activity_events':
                result = [r for r in result if r.get('actor_employee_id') in employee_ids]
            elif table == 'clients':
                result = [r for r in result if r.get('account_manager_id') in employee_ids]
        if intent.name == 'project_delivery_review' and table == 'projects' and not selected.get('project'):
            result = [r for r in result if str(r.get('status')).lower() in ('delayed', 'at risk') or (r.get('progress') is not None and r.get('expected') is not None and r['progress'] < r['expected'])]
        if intent.name == 'support_incident_command' and table == 'issues':
            result = [r for r in result if open_work(r) and str(r.get('severity')).lower() in ('high', 'critical', 'urgent', 'p0', 'p1')]
        if intent.unresolved_only and table == 'issues':
            result = [r for r in result if open_work(r)]
        if table == 'tasks':
            if intent.name not in ('ownership_lookup',):
                result = [r for r in result if open_work(r)]
            if intent.blocked_only:
                result = [r for r in result if r.get('blocker_task_id') or str(r.get('status')).lower() == 'blocked']
            if intent.overdue_only:
                result = [r for r in result if parse_date(r.get('due_date')) and parse_date(r['due_date']) < today and open_work(r)]
        if table == 'meetings':
            start, end = intent.date_from or today, intent.date_to or today + timedelta(days=30)
            result = [r for r in result if parse_date(r.get('date')) and start <= parse_date(r['date']) <= end]
        elif table in ('communications', 'issues', 'activity_events') and intent.date_from and intent.name != 'client_meeting_prep':
            field = 'event_time' if table == 'activity_events' else 'date'
            result = [r for r in result if parse_date(r.get(field)) and intent.date_from <= parse_date(r[field]) <= (intent.date_to or today)]
        rows[table] = result
    if intent.name == 'project_delivery_review':
        projects = {r['id'] for r in rows['projects']}
        for table in ('tasks', 'issues', 'activity_events'):
            rows[table] = [r for r in rows[table] if r.get('project_id') in projects]
    if selected.get('product'):
        projects = {r['id'] for r in rows['projects']}
        rows['tasks'] = [r for r in rows['tasks'] if r.get('project_id') in projects]
    if intent.name == 'support_incident_command':
        severity_order = {'critical': 0, 'high': 1, 'urgent': 2}
        rows['issues'] = sorted(rows['issues'], key=lambda r: (
            severity_order.get(str(r.get('severity')).lower(), 3),
            0 if str(r.get('status', '')).lower() == 'open' else 1, r['id']))
        issues = {r['id'] for r in rows['issues']}
        projects = {r.get('project_id') for r in rows['issues']}
        rows['communications'] = [r for r in rows['communications'] if r.get('related_issue_id') in issues]
        rows['tasks'] = [r for r in rows['tasks'] if r.get('project_id') in projects]
    return rows, employee_ids


def schedule_request(text, intent):
    """Separate timetable presentation from general team workload, with no API enum change."""
    return (intent.name == 'team_workload_planning' and
            bool(re.search(r'\b(schedule|timetable|calendar|appointments?|bookings?)\b', text or '', re.IGNORECASE)))


def local_schedule_time(value):
    """Convert a recorded instant to the team's stated display timezone."""
    try:
        dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return dt.astimezone(ZoneInfo('Asia/Kolkata')) if dt.tzinfo else None
    except (TypeError, ValueError, OverflowError):
        return None


def compose_workspace(snapshot, knowledge, intent, today=None, request_text=None):
    today = today or datetime.now(ZoneInfo('Asia/Kolkata')).date()
    result = dict(title=LABELS[intent.name], intent=intent, components=[], datasets={}, evidence=[], claims=[], explanations=list(intent.changes), limitations=list(snapshot.limitations), integration_requirements=[])
    if intent.clarification or intent.name == 'unsupported':
        return Workspace(status='clarification' if intent.clarification else 'unsupported', **result)
    rows, employee_ids = select_rows(snapshot, intent, today)
    schedule_focus = schedule_request(request_text, intent)
    sources, claims = EvidenceSet(snapshot), []
    relationships = []
    # On a "who owns" question, show the owner of the requested item only.
    # Client managers and product owners can be related but must not be
    # presented as competing answers to the primary ownership question.
    refs = ([ownership_focus(intent)] if ownership_focus(intent) else []) if intent.name == 'ownership_lookup' else intent.entities
    if intent.name == 'project_delivery_review' and any(ref.entity_type == 'project' for ref in refs):
        refs = [ref for ref in refs if ref.entity_type != 'client']
    if intent.name == 'client_meeting_prep':
        refs = [ref for ref in refs if ref.entity_type != 'client']
    if intent.name == 'team_workload_planning':
        # An employee isn't the 'owner' of themselves. Avoid irrelevant claims.
        refs = [ref for ref in refs if ref.entity_type not in ('employee', 'department')]
    for ref in refs:
        if ref.entity_type in ('project', 'task', 'issue', 'employee', 'client', 'meeting', 'contract'):
            relation = responsibility(snapshot, ref)
            relationships.append(relation.model_dump(mode='json'))
            sources.items.update({e.id: e for e in relation.evidence})
            if relation.owner:
                claim_ids = [sources.database(ENTITY_TABLE[ref.entity_type], relation.record)]
                owner_field = {'task': 'owner_employee_id', 'project': 'owner_employee_id',
                               'issue': 'owner_employee_id', 'contract': 'contract_owner_id',
                               'meeting': 'organizer_employee_id', 'client': 'account_manager_id'}.get(ref.entity_type)
                if owner_field:
                    claim_ids.append(sources.database(ENTITY_TABLE[ref.entity_type], relation.record, owner_field))
                claim_ids.append(sources.database('employees', relation.owner))
                if intent.name == 'ownership_lookup':
                    label = 'account manager' if ref.entity_type == 'client' else 'organizer' if ref.entity_type == 'meeting' else 'recorded owner'
                    sentence = f'{relation.owner["full_name"]} is the {label} of {ref.entity_type} {title(relation.record)}.'
                else:
                    role = ('account manager' if ref.entity_type == 'client' else
                            'organizer' if ref.entity_type == 'meeting' else 'owner')
                    sentence = f'{relation.owner["full_name"]} is the recorded {role} for {title(relation.record)}.'
                claims.append(Claim(kind='observation', text=sentence, evidence_ids=claim_ids))
            result['limitations'].extend(relation.limitations)
            if intent.name == 'ownership_lookup' and ref.entity_type == 'task':
                # A Blocked status is a fact; a missing blocking-task FK is
                # not an invitation to invent the actual cause.
                if str(relation.record.get('status', '')).lower() == 'blocked' and not relation.record.get('blocker_task_id'):
                    ids = [sources.database('tasks', relation.record, 'status'), sources.database('tasks', relation.record, 'blocker_task_id')]
                    claims.append(Claim(kind='uncertainty', text='The task is recorded as Blocked, but no specific blocking-task dependency is recorded.', evidence_ids=ids))
    for project in rows['projects'][:6]:
        if intent.name in ('project_delivery_review', 'executive_briefing'):
            claims.append(Claim(kind='observation', text=f'{title(project)} is recorded as {project.get("status", "unknown")}; progress {project.get("progress")}%, expected {project.get("expected")}%. This status does not establish a cause.', evidence_ids=[sources.database('projects', project, field) for field in ('status', 'progress', 'expected')]))
    if intent.name == 'client_meeting_prep':
        compose_meeting_brief(snapshot, rows, intent, today, sources, claims, result)
    if intent.name == 'project_delivery_review':
        represented = {r.entity_id for r in refs if r.entity_type == 'project'}
        for project in rows['projects'][:5]:
            if project['id'] in represented:
                continue
            owner = snapshot.get('employees', project.get('owner_employee_id'))
            if owner:
                claims.insert(0, Claim(kind='observation',
                            text=f'{owner["full_name"]} is the recorded delivery owner of project {title(project)}.',
                            evidence_ids=[sources.database('projects', project, 'owner_employee_id'), sources.database('employees', owner)]))
        for task in rows['tasks'][:12]:
            if task.get('blocker_task_id'):
                relation = responsibility(snapshot, EntityRef(entity_type='task', entity_id=task['id']))
                sources.items.update({e.id: e for e in relation.evidence})
                relationships.append(relation.model_dump(mode='json'))
                if relation.blocker_chain:
                    blocker = relation.blocker_chain[0]['blocking_task']
                    claims.append(Claim(kind='observation', text=f'{title(task)} records a dependency on {title(blocker)} (status: {blocker.get("status")}). A dependency is not proof of the cause of project delay.', evidence_ids=[sources.database('tasks', task, 'blocker_task_id'), sources.database('tasks', blocker, 'status')]))
        claims.append(Claim(kind='uncertainty', text='The records do not establish a verified causal explanation for delay or assign personal blame. Confirm the critical path with the recorded owners.'))
    if intent.name == 'product_usage_investigation':
        end, start = intent.date_to or today, intent.date_from or today - timedelta(days=13)
        days = (end - start).days + 1
        prior_start = start - timedelta(days=days)
        usage = [r for r in rows['product_usage'] if parse_date(r.get('date')) and prior_start <= parse_date(r['date']) <= end]
        rows['product_usage'] = usage
        groups = defaultdict(list)
        for row in usage:
            groups[(row.get('client_id'), row.get('product_id'))].append(row)
        metrics = []
        for (client, product), group in sorted(groups.items(), key=str):
            current = [r for r in group if parse_date(r['date']) >= start]
            previous = [r for r in group if parse_date(r['date']) < start]
            if not current:
                continue
            daily = defaultdict(list)
            baseline = defaultdict(list)
            for r in current:
                daily[r['date']].append(r['active_users'])
            for r in previous:
                baseline[r['date']].append(r['active_users'])
            # Repeated daily rows are averaged, not falsely counted as extra days.
            avg = sum(sum(v) / len(v) for v in daily.values()) / len(daily)
            prior = sum(sum(v) / len(v) for v in baseline.values()) / len(baseline) if baseline else None
            change = round((avg - prior) / prior * 100, 1) if prior else None
            ids = [sources.database('product_usage', r) for r in group]
            metric = {'id': f'{client}-{product}', 'client_id': client, 'product_id': product, 'average_daily_active_users': round(avg, 2), 'previous_average': round(prior, 2) if prior is not None else None, 'change_percent': change, 'measured_days': len(daily), 'previous_measured_days': len(baseline), 'window_days': days, 'date_from': start.isoformat(), 'date_to': end.isoformat(), 'evidence_ids': ids}
            metrics.append(metric)
            claims.append(Claim(kind='calculation', text=f'{client}/{product}: average daily active users {avg:.2f} across {len(daily)} measured days; preceding period change {str(change) + "%" if change is not None else "not available"}. Missing days are not zero.', evidence_ids=ids))
        result['datasets']['usage_metrics'] = metrics
        claims.append(Claim(kind='uncertainty', text='Usage and incident timing can overlap without establishing causation. Missing measurements and cohort differences limit interpretation.'))
    if intent.name == 'support_incident_command':
        for issue in rows['issues'][:8]:
            fields = ['severity', 'status', 'owner_employee_id']
            statement = f'{title(issue)}: recorded severity {issue.get("severity")}, status {issue.get("status")}.'
            if issue.get('sla_hours') is not None:
                fields.append('sla_hours')
                statement += f' Recorded SLA duration: {issue["sla_hours"]} hours; exact breach time is unverified.'
            claims.append(Claim(kind='observation', text=statement, evidence_ids=[sources.database('issues', issue, field) for field in fields]))
    if intent.name == 'team_workload_planning':
        employees = [r for r in snapshot.rows('employees') if employee_ids is None or r['id'] in employee_ids]
        start = intent.date_from or today
        end = intent.date_to or start + timedelta(days=6)
        capacities = []
        for employee in employees:
            tasks = [r for r in rows['tasks'] if r.get('owner_employee_id') == employee['id']]
            blocks = [r for r in snapshot.rows('employee_schedule_blocks') if r.get('employee_id') == employee['id'] and schedule_local_date(r.get('starts_at')) and schedule_local_date(r.get('ends_at')) and schedule_local_date(r['starts_at']) <= end and schedule_local_date(r['ends_at']) >= start]
            estimated = sum(r.get('estimated_hours') or 0 for r in tasks)
            missing = sum(r.get('estimated_hours') is None for r in tasks)
            bounds = (datetime.combine(start, datetime.min.time(), ZoneInfo('Asia/Kolkata')), datetime.combine(end + timedelta(days=1), datetime.min.time(), ZoneInfo('Asia/Kolkata')))
            intervals = []
            for block in blocks:
                a, b = datetime.fromisoformat(block['starts_at']), datetime.fromisoformat(block['ends_at'])
                if a.tzinfo and b.tzinfo and b > a:
                    a, b = max(a, bounds[0]), min(b, bounds[1])
                    if a < b:
                        intervals.append((a, b))
            merged = []
            for a, b in sorted(intervals):
                if merged and a <= merged[-1][1]:
                    merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
                else:
                    merged.append((a, b))
            booked = sum((b - a).total_seconds() / 3600 for a, b in merged)
            ids = [sources.database('employees', employee, 'weekly_capacity_hours')] + [sources.database('tasks', r) for r in tasks] + [sources.database('employee_schedule_blocks', r) for r in blocks]
            capacity = {'id': employee['id'], 'employee_id': employee['id'], 'name': employee['full_name'], 'open_tasks': len(tasks), 'estimated_backlog_hours': estimated, 'tasks_without_estimates': missing, 'recorded_weekly_capacity_hours': employee.get('weekly_capacity_hours'), 'scheduled_interval_hours': round(booked, 2), 'unbooked_capacity_hours': max(0, employee['weekly_capacity_hours'] - booked) if employee.get('weekly_capacity_hours') is not None and (end - start).days == 6 else None, 'evidence_ids': ids}
            capacities.append(capacity)
            if not schedule_focus and len(claims) < 8:
                claims.append(Claim(kind='calculation', text=f'{employee["full_name"]}: {len(tasks)} visible open tasks, {estimated} estimated backlog hours, {missing} tasks without estimates; {booked:.2f} hours in merged schedule blocks. Backlog hours are not a weekly commitment.', evidence_ids=ids))
        result['datasets']['capacity'] = capacities
        # Frontend-ready employee timetable and workload graph datasets.
        # Read-only: preserve actual UTC-offset timestamps and never imply
        # that task backlog hours are already booked into the calendar.
        schedule = []
        for block in sorted(snapshot.rows('employee_schedule_blocks'), key=lambda b: (str(b.get('starts_at', '')), b['id'])):
            if employee_ids is not None and block.get('employee_id') not in employee_ids:
                continue
            block_start, block_end = schedule_local_date(block.get('starts_at')), schedule_local_date(block.get('ends_at'))
            if not block_start or not block_end or block_start > end or block_end < start:
                continue
            employee = snapshot.get('employees', block.get('employee_id'))
            project = snapshot.get('projects', block.get('project_id'))
            schedule.append({
                'id': block['id'], 'employee_id': block.get('employee_id'),
                'employee_name': employee.get('full_name') if employee else None,
                'project_id': block.get('project_id'),
                'project_name': title(project) if project else None,
                'starts_at': block.get('starts_at'), 'ends_at': block.get('ends_at'),
                'block_type': block.get('block_type'),
                'evidence_ids': [sources.database('employee_schedule_blocks', block)],
            })
        result['datasets']['schedule_events'] = schedule[:150]
        if schedule_focus:
            result['datasets']['employee_options'] = schedule_directory(snapshot)
            meeting_people = employee_ids if employee_ids is not None else {e['id'] for e in employees}
            result['datasets']['schedule_meetings'] = scheduled_meetings(snapshot, meeting_people, start, end, sources)
            window_start = start.isoformat()
            window_end = end.isoformat()
            requested_people = [r for r in employees if r['id'] in employee_ids] if employee_ids is not None else employees
            labels = [r['full_name'] for r in requested_people]
            focus_name = labels[0] if len(labels) == 1 else (title(snapshot.get('departments', next(
                (x.entity_id for x in intent.entities if x.entity_type == 'department'), None)))
                if any(e.entity_type == 'department' for e in intent.entities) else 'Selected employees')
            if not focus_name:
                focus_name = 'Selected employees'
            visible = schedule[:150]
            events_evidence = [e for event in visible for e in event['evidence_ids']]
            for event in visible[:7]:
                first, last = local_schedule_time(event['starts_at']), local_schedule_time(event['ends_at'])
                if not first or not last:
                    continue
                begin = first.strftime('%a %d %b %Y, %I:%M %p')
                ending = last.strftime('%I:%M %p')
                label = str(event.get('block_type') or 'Schedule block')
                description = snapshot.get('employee_schedule_blocks', event['id'])
                if description and description.get('description'):
                    label = str(description['description'])
                claims.append(Claim(kind='observation', text=(
                    f'{event["employee_name"]}: {label} on {begin}–{ending} IST.'),
                    evidence_ids=event['evidence_ids']))
            if visible:
                # The event evidence is attached to the summary, including one
                # visible overlap-safe arithmetic figure for the selected people.
                total_booked = sum(float(r['scheduled_interval_hours']) for r in capacities)
                claims.insert(0, Claim(kind='calculation', text=(
                    f'{focus_name}: {len(visible)} recorded schedule block(s) during '
                    f'{window_start} to {window_end}; {total_booked:.2f} hours in merged '
                    'calendar intervals. Task backlog is not a calendar booking.'),
                    evidence_ids=sorted(set(events_evidence))))
            else:
                claims.append(Claim(kind='uncertainty', text=(
                    f'No schedule blocks are recorded for {focus_name} during '
                    f'{window_start} to {window_end} in accessible records. '
                    'An empty calendar does not prove availability.')))
            day_rows = []
            for offset in range((end-start).days+1):
                day = start + timedelta(days=offset)
                overlaps = [event for event in visible if
                            schedule_local_date(event['starts_at']) <= day <= schedule_local_date(event['ends_at'])]
                day_rows.append({'id': day.isoformat(), 'date': day.isoformat(),
                                 'day_name': day.strftime('%A'),
                                 'event_ids': [e['id'] for e in overlaps],
                                 'event_count': len(overlaps)})
            result['datasets']['schedule_summary'] = [{
                'id': f'schedule-{window_start}-{window_end}', 'timezone': 'Asia/Kolkata',
                'focus_label': focus_name,
                'date_from': window_start, 'date_to': window_end,
                'employee_ids': [r['id'] for r in requested_people],
                'employee_names': labels, 'recorded_block_count': len(visible),
                'merged_booked_hours': round(sum(float(r['scheduled_interval_hours']) for r in capacities), 2),
                'truncated': len(schedule) > 150, 'evidence_ids': sorted(set(events_evidence)),
            }]
            result['datasets']['schedule_days'] = day_rows
            result['integration_requirements'].append('Schedule-specific intent: render datasets.schedule_events in a local-time weekly calendar, using schedule_summary and schedule_days. No new v2 component type is required.')
            if len(schedule) > 150:
                result['limitations'].append('Calendar display limited to 150 recorded blocks; totals may be incomplete.')
            result['limitations'].append('Empty time slots are not verified free time; recorded blocks are not proof of all appointments.')
        result['datasets']['workload_chart'] = [{
            'id': row['employee_id'], 'employee_id': row['employee_id'],
            'employee_name': row['name'], 'estimated_backlog_hours': row['estimated_backlog_hours'],
            'scheduled_interval_hours': row['scheduled_interval_hours'],
            'open_tasks': row['open_tasks'], 'evidence_ids': row['evidence_ids'],
        } for row in capacities]
        result['integration_requirements'].append('Optional datasets.schedule_events and datasets.workload_chart support an employee timetable and bar chart. Frontend widget integration remains with Person B.')
        result['integration_requirements'].append('Capacity/schedule data is supplied separately; map it into an approved table/insight adapter. No capacity widget is registered.')
        result['limitations'].append('Unbooked capacity is a seven-day arithmetic estimate, not guaranteed availability; schedule blocks may be incomplete and backlog has no planned start dates.')
    if intent.name == 'executive_briefing':
        compose_executive_summary(snapshot, sources, claims, result)
        selected_client = next((e.entity_id for e in intent.entities if e.entity_type == 'client'), None)
        contracts = [r for r in snapshot.rows('contracts') if not selected_client or r.get('client_id') == selected_client]
        result['datasets']['contracts'] = contracts[:100]
        for contract in contracts[:6]:
            claims.append(Claim(kind='observation', text=f'Contract {contract["id"]}: status {contract.get("status")}; recorded renewal {contract.get("renewal_date")}. No revenue impact inferred.', evidence_ids=[sources.database('contracts', contract)]))
        result['integration_requirements'].append('Contract status/renewal records require a table adapter; no contract-specific component is registered. Financial amounts are excluded.')
    needed = {selector for _, selector in LAYOUTS[intent.name]}
    for table, selector in SELECTORS.items():
        if selector not in needed:
            continue
        data = rows[table]
        if len(data) > 250:
            result['limitations'].append(f'{selector} widget records limited to 250; use the entity viewer for further inspection.')
        result['datasets'][selector] = data[:250]
    # Minimal visible employee directory for owner labels in authorized views.
    if intent.name in ('project_delivery_review', 'support_incident_command', 'executive_briefing'):
        referenced_owners = {r.get('owner_employee_id') for table in ('projects', 'issues', 'tasks')
                             for r in rows.get(table, []) if r.get('owner_employee_id')}
        result['datasets']['employee_directory'] = [
            {'id': e['id'], 'name': e.get('full_name'), 'department_id': e.get('department_id')}
            for e in snapshot.rows('employees') if e['id'] in referenced_owners
        ][:100]
    result['datasets']['responsibilities'] = relationships
    if intent.name in ('project_delivery_review', 'ownership_lookup', 'executive_briefing'):
        nodes, edges = graph_data(snapshot, rows['tasks'], sources)
        result['datasets']['task_nodes'] = nodes
        result['datasets']['task_dependencies'] = edges
    # Lookups need a direct answer, not an unrelated escalation playbook.
    # Keep procedures for real investigations; blockers warrant one focused
    # procedure only if the user explicitly asked about blocked work.
    action = specific_action(intent.name, snapshot, rows, sources, schedule_focus=schedule_focus)
    if action:
        claims.append(action)
    # Playbooks are available through evidence navigation, but do not dilute
    # specific, supported next steps with a generic 'Consult procedure' card.
    elif not schedule_focus and (intent.name != 'ownership_lookup' or intent.blocked_only):
        document = knowledge.get(PLAYBOOK[intent.name])
        doc_evidence = sources.document(document, document['sections'][0]['id'])
        claims.append(Claim(kind='proposed_action', text=(
            f'Consult the proposed {document["metadata"]["title"]} procedure for follow-up steps; '
            'no assignment or deadline changes are authorized.'), evidence_ids=[doc_evidence]))
    result['datasets']['insights'] = [{'id': f'claim-{i}', **claim.model_dump()} for i, claim in enumerate(claims)]
    layout = ([('InsightPanel', 'insights')] if schedule_focus else
              ownership_layout(intent) if intent.name == 'ownership_lookup' else list(LAYOUTS[intent.name]))
    if intent.chart_first and ('UsageChart', 'usage') in layout:
        layout.remove(('UsageChart', 'usage'))
        layout.insert(0, ('UsageChart', 'usage'))
    record_count = 0
    for component_type, selector in layout:
        data = result['datasets'].get(selector, [])
        if not data:
            if intent.name != 'ownership_lookup':
                result['limitations'].append(f'No matching {selector} records were visible; its component was omitted.')
            continue
        if selector != 'insights':
            record_count += len(data)
        evidence_ids = []
        if selector == 'insights':
            evidence_ids = sorted({e for c in claims for e in c.evidence_ids})
        else:
            table = next(t for t, s in SELECTORS.items() if s == selector)
            evidence_ids = [sources.database(table, r) for r in data]
        component_type = 'DataTable' if intent.presentation == 'table' and selector in BINDINGS['DataTable'] and component_type != 'MetricCards' else component_type
        i = len(result['components'])
        reason = f'{TITLES[selector]} supports {LABELS[intent.name].lower()} using {len(data)} visible records.'
        result['components'].append(ComponentPlan(id=f'{component_type}-{selector}', type=component_type, title=TITLES[selector], order=i, priority=max(1, 10 - i), size='wide' if i == 0 or component_type == 'MetricCards' else 'medium', props=BoundProps(selector=selector, record_ids=[r['id'] for r in data]), evidence_ids=evidence_ids, reason=reason))
        result['explanations'].append(reason)
    result['evidence'], result['claims'] = list(sources.items.values()), claims
    result['integration_requirements'].append('Use the v2 response datasets and props binding via a nonvisual adapter; legacy v1 Zod restricts clients to acme/nova and computes demo-date insights locally.')
    # A caveat about incomplete *real-world* availability is important to
    # show, but does not make a fully populated workload chart a partial
    # database response. Preserve the caveat in limitations for inspection.
    advisory_only = (
        intent.name == 'team_workload_planning'
        and not schedule_focus
        and result['limitations']
        and all(message == ('Unbooked capacity is a seven-day arithmetic estimate, '
                            'not guaranteed availability; schedule blocks may be '
                            'incomplete and backlog has no planned start dates.')
                for message in result['limitations'])
    )
    status = ('ready' if result['datasets'].get('schedule_events') else 'not_found') if schedule_focus else (
        'not_found' if not record_count else 'partial' if result['limitations'] and not advisory_only else 'ready')
    return Workspace(status=status, **result)
