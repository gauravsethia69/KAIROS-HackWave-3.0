from pydantic import BaseModel, Field
from ..intelligence.catalog import ENTITY_TABLE, TABLE_ENTITY, OWNER_FIELDS, RELATIONS, title
from ..intelligence.models import EntityRef, Evidence
from ..intelligence.evidence import EvidenceSet
from ..intelligence.knowledge import normalize


class Responsibility(BaseModel):
    entity: EntityRef
    record: dict
    owner: dict | None = None
    department: dict | None = None
    manager: dict | None = None
    related: dict[str, list[dict]] = Field(default_factory=dict)
    blocker_chain: list[dict] = Field(default_factory=list)
    proposed_contacts: list[dict] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


def find_employees(snapshot, query, limit=10):
    q = normalize(query)
    return sorted([r for r in snapshot.rows('employees') if q == normalize(r['id']) or q in normalize(r['full_name'])], key=lambda r: r['id'])[:limit]


def resolve(snapshot, ref: EntityRef, *, max_depth=8):
    row = snapshot.entity(ref)
    table = ENTITY_TABLE[ref.entity_type]
    sources = EvidenceSet(snapshot)
    sources.database(table, row)
    result = Responsibility(entity=ref, record=row)
    owner_field = OWNER_FIELDS.get(table)
    owner = row if table == 'employees' else snapshot.get('employees', row.get(owner_field)) if owner_field else None
    if owner_field:
        sources.database(table, row, owner_field)
    if owner:
        result.owner = owner
        sources.database('employees', owner)
        result.department = snapshot.get('departments', owner.get('department_id'))
        result.manager = snapshot.get('employees', owner.get('manager_id'))
        for relation, target in [(result.department, 'departments'), (result.manager, 'employees')]:
            if relation:
                sources.database(target, relation)
        result.proposed_contacts.append({'employee_id': owner['id'], 'full_name': owner['full_name'], 'basis': 'Recorded owner; contacting them is a proposed action.'})
        if result.manager:
            result.proposed_contacts.append({'employee_id': result.manager['id'], 'full_name': result.manager['full_name'], 'basis': 'Recorded manager; escalation authority is not established.'})
    elif owner_field:
        result.limitations.append('No visible recorded owner. No owner or escalation target has been inferred from textual names.')
    for field, target in RELATIONS.items():
        parent = snapshot.get(target, row.get(field))
        if parent:
            result.related.setdefault(target, []).append(parent)
            sources.database(target, parent)
    if table == 'employees':
        employee_id = row['id']
        related = {
            'tasks': [r for r in snapshot.rows('tasks') if r.get('owner_employee_id') == employee_id],
            'projects': [r for r in snapshot.rows('projects') if r.get('owner_employee_id') == employee_id],
            'issues': [r for r in snapshot.rows('issues') if r.get('owner_employee_id') == employee_id],
            'employee_schedule_blocks': [r for r in snapshot.rows('employee_schedule_blocks') if r.get('employee_id') == employee_id],
        }
        participant_meetings = {r['meeting_id'] for r in snapshot.rows('meeting_participants') if r.get('employee_id') == employee_id}
        related['meetings'] = [r for r in snapshot.rows('meetings') if r.get('organizer_employee_id') == employee_id or r['id'] in participant_meetings]
        for related_table, records in related.items():
            result.related[related_table] = records[:100]
            for record in records[:100]:
                sources.database(related_table, record)
    if table == 'tasks':
        current, seen = row, {row['id']}
        for _ in range(max_depth):
            blocker_id = current.get('blocker_task_id')
            if not blocker_id:
                break
            sources.database('tasks', current, 'blocker_task_id')
            if blocker_id in seen:
                result.limitations.append('Cycle detected in recorded blockers; traversal stopped.')
                break
            seen.add(blocker_id)
            blocker = snapshot.get('tasks', blocker_id)
            if not blocker:
                result.limitations.append('A recorded blocking task is missing or not visible; no further escalation inferred.')
                break
            blocker_owner = snapshot.get('employees', blocker.get('owner_employee_id'))
            manager = snapshot.get('employees', blocker_owner.get('manager_id')) if blocker_owner else None
            sources.database('tasks', blocker)
            for employee in (blocker_owner, manager):
                if employee:
                    sources.database('employees', employee)
            result.blocker_chain.append({'blocked_task_id': current['id'], 'blocking_task': blocker, 'owner': blocker_owner, 'manager': manager, 'project': snapshot.get('projects', blocker.get('project_id')), 'interpretation': 'Recorded dependency; not proof of personal fault or root cause.'})
            current = blocker
        else:
            if current.get('blocker_task_id'):
                result.limitations.append(f'Blocker traversal stopped at {max_depth} levels.')
    fk = {'projects': 'project_id', 'tasks': 'task_id', 'issues': 'issue_id', 'meetings': 'meeting_id', 'clients': 'client_id', 'employees': 'actor_employee_id', 'products': 'product_id'}.get(table)
    if fk and table != 'employees':
        for child_table in ('projects', 'tasks', 'issues', 'meetings', 'communications', 'contracts', 'product_usage'):
            children = [r for r in snapshot.rows(child_table) if r.get(fk) == row['id']]
            if children:
                result.related[child_table] = children[:100]
                for child in children[:100]:
                    sources.database(child_table, child)
                if len(children) > 100:
                    result.limitations.append(f'{child_table} relationships limited to 100 visible records.')
    if fk:
        activity = sorted((r for r in snapshot.rows('activity_events') if r.get(fk) == row['id']), key=lambda r: (str(r.get('event_time')), r['id']), reverse=True)[:20]
        result.related['activity_events'] = activity
        for item in activity:
            sources.database('activity_events', item)
    if owner and owner.get('manager_id') and not result.manager:
        result.limitations.append('Recorded manager is not visible; no substitute escalation contact inferred.')
    result.evidence = list(sources.items.values())
    return result
