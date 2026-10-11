"""Isolated fictional records. Not exports of production employee/client data."""
from datetime import date, datetime, timedelta, timezone
from uuid import UUID
from backend.auth import Identity
from backend.intelligence.repository import Snapshot

TODAY = date(2026, 10, 11)
USER = Identity(id=UUID('11111111-1111-4111-8111-111111111111'), employee_id='e1', access_role='employee')
OTHER = Identity(id=UUID('22222222-2222-4222-8222-222222222222'), employee_id='e3', access_role='employee')


def fixture():
    tables = {
        'departments': [{'id': 'eng', 'name': 'Engineering', 'description': 'Engineering'}, {'id': 'cs', 'name': 'Customer Success', 'description': 'Customer outcomes'}],
        'employees': [
            {'id': 'e1', 'full_name': 'Avery Test', 'department_id': 'eng', 'manager_id': 'e2', 'job_title': 'Engineer', 'weekly_capacity_hours': 40, 'availability_status': 'Available', 'email': 'excluded@example.test', 'password': 'never-export'},
            {'id': 'e2', 'full_name': 'Morgan Example', 'department_id': 'eng', 'manager_id': None, 'job_title': 'Manager', 'weekly_capacity_hours': 36, 'availability_status': 'Available'},
            {'id': 'e3', 'full_name': 'Riley Fixture', 'department_id': 'cs', 'manager_id': None, 'job_title': 'Account manager', 'weekly_capacity_hours': 40, 'availability_status': 'Available'},
        ],
        'clients': [{'id': 'orbit', 'name': 'OrbitPay', 'account_manager_id': 'e3', 'primary_product_id': 'guard', 'health': 'At risk'}, {'id': 'atlas', 'name': 'Atlas Media Group', 'account_manager_id': 'e3', 'primary_product_id': 'insight', 'health': 'Needs attention'}],
        'products': [{'id': 'guard', 'name': 'Soryu Guard', 'description': 'Identity administration and enterprise SSO'}, {'id': 'insight', 'name': 'Soryu Insight', 'description': 'Product analytics, adoption and executive insights'}],
        'projects': [{'id': 'p1', 'name': 'Orbit rollout', 'client_id': 'orbit', 'product_id': 'guard', 'owner_employee_id': 'e1', 'status': 'At risk', 'progress': 60, 'expected': 80, 'due_date': '2026-10-15'}, {'id': 'p2', 'name': 'Reporting integration', 'client_id': 'atlas', 'product_id': 'insight', 'owner_employee_id': 'e2', 'status': 'Delayed', 'progress': 40, 'expected': 90, 'due_date': '2026-10-09'}],
        'tasks': [{'id': 't1', 'title': 'Validate SSO callback fix', 'client_id': 'orbit', 'project_id': 'p1', 'owner_employee_id': 'e1', 'blocker_task_id': 't2', 'status': 'Blocked', 'priority': 'High', 'due_date': '2026-10-09', 'estimated_hours': 8}, {'id': 't2', 'title': 'Approve identity settings', 'client_id': 'orbit', 'project_id': 'p1', 'owner_employee_id': 'e2', 'blocker_task_id': None, 'status': 'Open', 'priority': 'High', 'due_date': '2026-10-08', 'estimated_hours': 4}, {'id': 't3', 'title': 'Reporting contract review', 'client_id': 'atlas', 'project_id': 'p2', 'owner_employee_id': None, 'blocker_task_id': None, 'status': 'Open', 'priority': 'Medium', 'due_date': '2026-10-10', 'estimated_hours': None}],
        'issues': [{'id': 'i1', 'title': 'SSO failure', 'client_id': 'orbit', 'project_id': 'p1', 'product_id': 'guard', 'owner_employee_id': 'e1', 'status': 'Investigating', 'severity': 'Critical', 'date': '2026-10-08', 'detail': 'Reproduction recorded; cause unverified.', 'sla_hours': 4}],
        'meetings': [{'id': 'm1', 'title': 'OrbitPay success review', 'client_id': 'orbit', 'product_id': 'guard', 'organizer_employee_id': 'e3', 'date': '2026-10-12', 'summary': 'Review open issues', 'upcoming': True}],
        'meeting_participants': [{'meeting_id': 'm1', 'participant_key': 'e1', 'employee_id': 'e1', 'role': 'Attendee'}],
        'communications': [{'id': 'c1', 'client_id': 'orbit', 'product_id': 'guard', 'employee_id': 'e3', 'related_issue_id': 'i1', 'date': '2026-10-10', 'message': 'Please review the incident.', 'channel': 'Email'}],
        'contracts': [{'id': 'con1', 'client_id': 'orbit', 'product_id': 'guard', 'status': 'Active', 'renewal_date': '2026-11-01', 'contract_owner_id': 'e3', 'annual_value': 999999}],
        'employee_schedule_blocks': [{'id': 's1', 'employee_id': 'e1', 'project_id': 'p1', 'starts_at': '2026-10-12T09:00:00+05:30', 'ends_at': '2026-10-12T11:00:00+05:30', 'block_type': 'Project'}, {'id': 's2', 'employee_id': 'e1', 'project_id': 'p1', 'starts_at': '2026-10-12T10:00:00+05:30', 'ends_at': '2026-10-12T12:00:00+05:30', 'block_type': 'Meeting'}],
        'activity_events': [{'id': 'a1', 'project_id': 'p1', 'task_id': 't1', 'issue_id': 'i1', 'client_id': 'orbit', 'actor_employee_id': 'e1', 'event_time': '2026-10-10T12:00:00Z', 'description': 'Issue reproduced', 'metadata': {'secret': 'excluded'}}],
        'product_usage': [{'id': f'u{i}', 'client_id': 'orbit', 'product_id': 'guard', 'date': (TODAY - timedelta(days=i)).isoformat(), 'active_users': 60 if i < 14 else 120, 'sessions': 180 if i < 14 else 360, 'errors': 12 if i < 14 else 2} for i in range(28)],
    }
    return Snapshot(tables, retrieved_at=datetime(2026, 10, 11, 12, tzinfo=timezone.utc))
