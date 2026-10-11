"""Explicit field/relationship allowlists verified against public schema 2026-10-11.

No employee email, employee_access, activity metadata, or financial values are
included in intelligence snapshots or document generation.
"""
FIELDS = {
    'employees': 'id department_id full_name job_title manager_id weekly_capacity_hours availability_status',
    'departments': 'id name description',
    'clients': 'id name sector contact owner plan seats health account_manager_id primary_product_id lifecycle',
    'products': 'id name category description lifecycle',
    'projects': 'id client_id name progress expected due_date status product_id owner_employee_id started_on',
    'tasks': 'id client_id project_id title due_date status priority owner_employee_id estimated_hours blocker_task_id',
    'issues': 'id client_id project_id title date status severity detail product_id owner_employee_id sla_hours',
    'meetings': 'id client_id title date summary upcoming product_id organizer_employee_id starts_at ends_at',
    'meeting_participants': 'meeting_id participant_key employee_id role',
    'communications': 'id client_id date channel message product_id employee_id related_issue_id direction',
    'product_usage': 'id client_id date active_users sessions errors product_id',
    'contracts': 'id client_id product_id start_date end_date renewal_date currency status contract_owner_id',
    'client_products': 'client_id product_id seats activated_on subscription_status',
    'employee_schedule_blocks': 'id employee_id project_id starts_at ends_at block_type description',
    'activity_events': 'id client_id product_id project_id task_id issue_id meeting_id actor_employee_id event_type severity event_time description',
}
FIELDS = {table: tuple(fields.split()) for table, fields in FIELDS.items()}
ENTITY_TABLE = {'employee': 'employees', 'department': 'departments', 'client': 'clients', 'product': 'products', 'project': 'projects', 'task': 'tasks', 'issue': 'issues', 'meeting': 'meetings', 'contract': 'contracts', 'communication': 'communications', 'usage': 'product_usage', 'schedule': 'employee_schedule_blocks', 'activity': 'activity_events'}
TABLE_ENTITY = {table: entity for entity, table in ENTITY_TABLE.items()}
OWNER_FIELDS = {'projects': 'owner_employee_id', 'tasks': 'owner_employee_id', 'issues': 'owner_employee_id', 'contracts': 'contract_owner_id', 'meetings': 'organizer_employee_id', 'clients': 'account_manager_id'}
RELATIONS = {'department_id': 'departments', 'manager_id': 'employees', 'client_id': 'clients', 'product_id': 'products', 'primary_product_id': 'products', 'project_id': 'projects', 'blocker_task_id': 'tasks', 'task_id': 'tasks', 'issue_id': 'issues', 'related_issue_id': 'issues', 'meeting_id': 'meetings', 'employee_id': 'employees', 'actor_employee_id': 'employees', **{value: 'employees' for value in OWNER_FIELDS.values()}}


def title(row):
    return str(row.get('name') or row.get('full_name') or row.get('title') or row.get('id') or 'Recorded relationship')
