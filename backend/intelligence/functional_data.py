"""Evidence-grounded, additive v2 functional-workspace datasets and actions.

No schema/RLS modifications. Call only with a caller-authorized read-only snapshot.
"""
from datetime import datetime
from zoneinfo import ZoneInfo
from .catalog import title
from .models import Claim


def graph_data(snapshot, selected_tasks, sources, limit=80):
    """Return actual task -> blocking task relationships; never infer a blocker."""
    seen, nodes, edges = set(), [], []
    def add_node(task):
        if not task or task['id'] in seen or len(nodes) >= limit * 2:
            return
        seen.add(task['id'])
        owner = snapshot.get('employees', task.get('owner_employee_id'))
        nodes.append({
            'id': task['id'], 'title': title(task), 'status': task.get('status'),
            'priority': task.get('priority'), 'project_id': task.get('project_id'),
            'owner_employee_id': task.get('owner_employee_id'),
            'owner_name': owner.get('full_name') if owner else None,
            'evidence_ids': [sources.database('tasks', task)],
        })
    for task in selected_tasks[:limit]:
        add_node(task)
        blocker_id = task.get('blocker_task_id')
        if blocker_id:
            blocker = snapshot.get('tasks', blocker_id)
            if blocker:
                add_node(blocker)
                edges.append({
                    'id': f'{task["id"]}-{blocker["id"]}',
                    'dependent_task_id': task['id'], 'blocker_task_id': blocker['id'],
                    'evidence_ids': [sources.database('tasks', task, 'blocker_task_id'), sources.database('tasks', blocker)],
                })
    return nodes, edges


def schedule_directory(snapshot):
    """Only records already visible to the employee under database RLS."""
    return [dict(id=e['id'], employee_id=e['id'], employee_name=e.get('full_name'),
                 department_id=e.get('department_id'))
            for e in snapshot.rows('employees') if e.get('full_name')][:100]


def scheduled_meetings(snapshot, employee_ids, start, end, sources, limit=80):
    """Organizer/participant-linked meetings with verified start/end instants."""
    attending = {(p.get('meeting_id'), p.get('employee_id'))
                 for p in snapshot.rows('meeting_participants')}
    events = []
    for meeting in snapshot.rows('meetings'):
        if len(events) >= limit:
            break
        raw_start, raw_end = meeting.get('starts_at'), meeting.get('ends_at')
        if not raw_start or not raw_end:
            continue
        try:
            starts_at, ends_at = datetime.fromisoformat(raw_start), datetime.fromisoformat(raw_end)
        except (ValueError, TypeError):
            continue
        if starts_at.tzinfo is None or ends_at.tzinfo is None or ends_at <= starts_at:
            continue
        local_start = starts_at.astimezone(ZoneInfo('Asia/Kolkata')).date()
        local_end = ends_at.astimezone(ZoneInfo('Asia/Kolkata')).date()
        if local_end < start or local_start > end:
            continue
        participants = sorted(id for id in employee_ids if id == meeting.get('organizer_employee_id') or (meeting['id'], id) in attending)
        if not participants:
            continue
        events.append({
            'id': f'meeting-{meeting["id"]}', 'meeting_id': meeting['id'],
            'title': title(meeting), 'client_id': meeting.get('client_id'),
            'starts_at': raw_start, 'ends_at': raw_end, 'employee_ids': participants,
            'source': 'recorded_meeting',
            'evidence_ids': [sources.database('meetings', meeting)],
        })
    return sorted(events, key=lambda e: (e['starts_at'], e['id']))


def specific_action(intent_name, snapshot, rows, sources, *, schedule_focus=False):
    """Offer a bounded, verifiable next step, never assert approval or mutate data."""
    if schedule_focus:
        return None
    projects = rows.get('projects', [])
    issues = rows.get('issues', [])
    if intent_name == 'client_meeting_prep':
        client = rows.get('clients', [None])[0] if rows.get('clients') else None
        if client:
            owner = snapshot.get('employees', client.get('account_manager_id'))
            owner_label = owner.get('full_name') if owner else 'the recorded account manager'
            ids = [sources.database('clients', client)]
            if owner: ids.append(sources.database('employees', owner))
            return Claim(kind='proposed_action', text=(
                f'Confirm the meeting date and agenda with {owner_label}; review recorded client issues and the latest meeting before proposing commitments. '
                'Do not treat proposed topics as an approved agenda.'), evidence_ids=ids)
    if intent_name == 'project_delivery_review' and projects:
        item = sorted(projects, key=lambda p: (str(p.get('status', '')).lower() != 'delayed',
                                               (p.get('progress') or 0) - (p.get('expected') or 0)))[0]
        owner = snapshot.get('employees', item.get('owner_employee_id'))
        ids = [sources.database('projects', item)] + ([sources.database('employees', owner)] if owner else [])
        return Claim(kind='proposed_action', text=(
            f'Review the critical path and recorded task dependencies for {title(item)} with '
            f'{owner["full_name"] if owner else "the project owner"} before proposing a new delivery commitment.'), evidence_ids=ids)
    if intent_name == 'support_incident_command' and issues:
        item = issues[0]
        owner = snapshot.get('employees', item.get('owner_employee_id'))
        ids = [sources.database('issues', item)] + ([sources.database('employees', owner)] if owner else [])
        return Claim(kind='proposed_action', text=(
            f'Prioritize investigation of {title(item)} ({item.get("severity")}, {item.get("status")}); '
            f'confirm next update and SLA timing with {owner["full_name"] if owner else "the recorded incident owner"}. '
            'No SLA breach is inferred from the recorded duration.'), evidence_ids=ids)
    if intent_name == 'executive_briefing' and projects:
        problem = next((p for p in projects if str(p.get('status')).lower() == 'delayed'), None)
        if problem:
            owner = snapshot.get('employees', problem.get('owner_employee_id'))
            ids = [sources.database('projects', problem)] + ([sources.database('employees', owner)] if owner else [])
            return Claim(kind='proposed_action', text=(
                f'Request a delivery risk update for {title(problem)} from '
                f'{owner["full_name"] if owner else "the project owner"}; review other delayed projects and renewal-due contracts separately.'), evidence_ids=ids)
    if intent_name == 'team_workload_planning':
        employees = rows.get('tasks', [])
        if employees:
            task = employees[0]
            owner = snapshot.get('employees', task.get('owner_employee_id'))
            ids = [sources.database('tasks', task)] + ([sources.database('employees', owner)] if owner else [])
            return Claim(kind='proposed_action', text=(
                f'Confirm due dates and actual booked availability with '
                f'{owner["full_name"] if owner else "the task owner"} before redistributing estimated task backlog. '
                'Unscheduled hours are not confirmed capacity.'), evidence_ids=ids)
    if intent_name == 'product_usage_investigation':
        usage = rows.get('product_usage', [])
        if usage:
            item = usage[-1]
            return Claim(kind='proposed_action', text=(
                'Compare measured active-user trends against the preceding period and inspect related incidents. '
                'Confirm missing measurements and product scope before attributing a cause.'),
                evidence_ids=[sources.database('product_usage', item)])
    return None
