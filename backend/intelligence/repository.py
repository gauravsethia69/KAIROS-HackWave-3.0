"""Read-only, bounded SORYU snapshot under verified employee RLS.

One SQL statement (UNION ALL of per-table bounded projections) avoids paying
one cloud round-trip for each of the 15 allowlisted company tables. No table
names or columns originate from user input. A per-table cap/limitation is kept.
"""
import json
import logging
import re
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta, date, time
from zoneinfo import ZoneInfo
from decimal import Decimal
from time import perf_counter

from fastapi import HTTPException
from psycopg import sql

from ..auth import Identity
from ..database import user_connection
from .catalog import FIELDS, ENTITY_TABLE

logger = logging.getLogger(__name__)


@contextmanager
def read_connection(user: Identity, *, timings: dict | None = None):
    with user_connection(user, read_only=True, timings=timings) as connection:
        yield connection


def scalar(value):
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


class Snapshot:
    """A bounded per-request view under the caller's database permissions."""
    def __init__(self, tables, retrieved_at=None, limitations=None):
        self.tables = {table: [{field: scalar(row.get(field)) for field in FIELDS[table] if field in row} for row in rows] for table, rows in tables.items() if table in FIELDS}
        self.retrieved_at = retrieved_at or datetime.now(timezone.utc)
        self.limitations = limitations or []
        self.index = {table: {str(r['id']): r for r in rows if 'id' in r} for table, rows in self.tables.items()}
        self.load_ms = 0.0
        self.timings: dict[str, float] = {}

    def rows(self, table):
        return self.tables.get(table, [])

    def get(self, table, entity_id):
        return self.index.get(table, {}).get(str(entity_id))

    def entity(self, ref):
        row = self.get(ENTITY_TABLE[ref.entity_type], ref.entity_id)
        if not row:
            raise HTTPException(404, 'Entity missing or not visible')
        return row


# A selective table read is safe only when all records necessary for entity
# matching and the selected workflow remain available. Unknown/compound
# queries and context-changing requests use the original full-table snapshot.
# Only backend-owned constant table identifiers can be interpolated into SQL.
LOOKUP_TABLES = frozenset({
    'employees', 'departments', 'clients', 'products',
    'projects', 'tasks', 'issues', 'meetings', 'contracts',
})
WORKFLOW_PROFILES = {
    'ownership': LOOKUP_TABLES | {'activity_events', 'employee_schedule_blocks', 'meeting_participants', 'communications'},
    'meeting': {'employees', 'departments', 'clients', 'products', 'projects',
                'tasks', 'issues', 'meetings', 'communications',
                'meeting_participants', 'activity_events'},
    'usage': {'employees', 'departments', 'clients', 'products', 'projects',
              'tasks', 'issues', 'product_usage', 'activity_events', 'communications'},
    'projects': {'employees', 'departments', 'clients', 'products', 'projects',
                 'tasks', 'issues', 'activity_events', 'communications'},
    'incidents': {'employees', 'departments', 'clients', 'products', 'projects',
                  'tasks', 'issues', 'activity_events', 'communications'},
    # Workload math consumes assigned tasks and recorded booking intervals.
    # Meetings, participants and activity streams are not needed by this
    # workflow and had inflated its remote snapshot payload.
    'workload': {'employees', 'departments', 'clients', 'products', 'projects',
                 'tasks', 'issues', 'employee_schedule_blocks'},
    # Timetable-only requests use much less data than workforce analytics.
    # The full authorized employee/department directory is still available
    # for disambiguation and employee switching.
    'calendar': {'employees', 'departments', 'projects', 'tasks',
                 'meetings', 'meeting_participants', 'employee_schedule_blocks'},
    'executive': LOOKUP_TABLES | {'activity_events', 'communications', 'meeting_participants'},
}

# The explicit ID route is intentionally narrow. Compound questions, vague
# names and follow-ups continue through the established resolver and fallback.
DIRECT_TASK_RE = re.compile(r'^\s*who\s+(?:owns|is\s+responsible\s+for)\s+(?:the\s+)?task\s+(t[0-9]+)\s*[?.!]?\s*$', re.IGNORECASE)
DIRECT_TASK_TABLES = frozenset({'employees', 'departments', 'clients', 'products', 'projects', 'tasks'})
CLIENT_SCOPED_PROFILES = frozenset({'meeting', 'usage', 'projects', 'incidents'})


def _read_scope(profile: str | None, request_text: str | None):
    """Backend-selected read scope, never an authorization decision.

    A client scope is applied only when *exactly one* stored client name is a
    substring of the request. Otherwise the SQL itself falls back to the full
    selected profile so ambiguous/fuzzy matches retain the original behavior.
    """
    if not request_text or profile is None:
        return None, None
    if profile == 'calendar':
        if re.search(r'\bmy\s+(?:weekly\s+)?(?:schedule|timetable|calendar)\b', request_text, re.I):
            return 'calendar_self', None
        return 'calendar_named', request_text
    if profile == 'workload':
        # The old planner treats 'my workload' as the authenticated person's
        # department. Restrict through that verified department, not an
        # untrusted employee identifier in the prompt.
        if re.search(r'\bmy\s+(?:(?:team|department)\s+)?(?:workload|capacity)\b', request_text, re.I):
            return 'workload_self', None
        # Try one unique visible person or department. A missing/ambiguous
        # match returns the entire workload profile so clarification and
        # other entity-based workload requests keep working.
        return 'workload_named', request_text
    if profile == 'ownership':
        match = DIRECT_TASK_RE.fullmatch(request_text)
        if match:
            return 'task_id', match.group(1).lower()
    if profile in CLIENT_SCOPED_PROFILES:
        # Comparative / multi-entity language must preserve the broad profile.
        if re.search(r'\b(?:and|also|versus|vs|compare|across|multiple|all clients|both clients)\b', request_text, re.I):
            return None, None
        return 'named_client', request_text
    return None, None


def _profile_tables(profile: str | None):
    if profile is None:
        return tuple(FIELDS)
    if profile not in WORKFLOW_PROFILES:
        raise ValueError('Unknown internal snapshot profile')
    return tuple(table for table in FIELDS if table in WORKFLOW_PROFILES[profile])


def _calendar_window(request_text: str | None, *, today: date | None = None):
    """Mirror recognized timetable date grammar without altering intent rules.

    Unrecognized/invalid temporal language skips DB date pruning so the
    normal resolver can return its clarification safely. SQL values are bound.
    """
    if not request_text:
        return None
    q = request_text.lower()
    today = today or datetime.now(ZoneInfo('Asia/Kolkata')).date()
    explicit = re.search(r'\bfrom\s+(\d{4}-\d{2}-\d{2})\s+to\s+(\d{4}-\d{2}-\d{2})\b', q)
    if explicit:
        try:
            start, end = date.fromisoformat(explicit[1]), date.fromisoformat(explicit[2])
        except ValueError:
            return None
        return (start, end) if start <= end and (end-start).days <= 30 else None
    if re.search(r'\b(yesterday|next month|last month|monday|tuesday|wednesday|thursday|friday)\b', q):
        return None
    if 'next week' in q:
        start = today + timedelta(days=7-today.weekday())
    elif 'last week' in q:
        start = today - timedelta(days=7+today.weekday())
    elif re.search(r'\btomorrow\b', q):
        start = today + timedelta(days=1)
        return start, start
    elif re.search(r'\btoday\b', q):
        return today, today
    elif re.search(r'\blast (\d+) days\b', q):
        days = int(re.search(r'\blast (\d+) days\b', q)[1])
        return (today - timedelta(days=days-1), today) if 1 <= days <= 90 else None
    elif re.search(r'\b(next|last|on|between|before|after)\b', q):
        return None
    else:
        start = today
    return start, start + timedelta(days=6)


def load_snapshot(user: Identity, *, profile: str | None = None,
                  usage_window: tuple[date, date] | None = None,
                  request_text: str | None = None) -> Snapshot:
    """Read only the allowlisted tables a known workflow can consume.

    If a query isn't clearly classifiable, pass profile=None to preserve the
    original full-snapshot behavior. A usage_window is a bound date predicate
    used *only* for usage queries, and must include the comparison period.
    """
    start = perf_counter()
    scope, scope_value = _read_scope(profile, request_text)
    # Both calendar and workload calculations use bounded recorded intervals;
    # the workload default is today plus six days in the workspace timezone.
    calendar_window = _calendar_window(request_text) if profile in ('calendar', 'workload') else None
    calendar_start_utc = calendar_end_utc = None
    if calendar_window:
        zone = ZoneInfo('Asia/Kolkata')
        calendar_start_utc = datetime.combine(calendar_window[0], time.min, zone).astimezone(timezone.utc)
        calendar_end_utc = datetime.combine(calendar_window[1] + timedelta(days=1), time.min, zone).astimezone(timezone.utc)
    selected = (tuple(t for t in FIELDS if t in DIRECT_TASK_TABLES)
                if scope == 'task_id' else _profile_tables(profile))
    if usage_window is not None and profile != 'usage':
        raise ValueError('Usage dates are restricted to the usage profile')
    if usage_window is not None and usage_window[0] > usage_window[1]:
        raise ValueError('Invalid internal usage date window')
    caps = {table: 2000 if table == 'product_usage' else 500 for table in selected}
    # Scoped CTE identifiers are backend constants; all user values are bound
    # parameters. RLS applies equally to CTEs and every underlying table.
    branches, args = [], []
    cte = sql.SQL('')
    if scope == 'task_id':
        cte = sql.SQL(
            'WITH RECURSIVE requested_task AS ('
            'SELECT id, client_id, project_id, blocker_task_id '
            'FROM public.tasks WHERE id = %s), '
            'blocker_chain(id, blocker_task_id, depth) AS ('
            'SELECT id, blocker_task_id, 0 FROM requested_task '
            'UNION ALL SELECT task.id, task.blocker_task_id, chain.depth + 1 '
            'FROM public.tasks task JOIN blocker_chain chain '
            'ON task.id = chain.blocker_task_id WHERE chain.depth < 8) '
        )
        args.append(scope_value)
    elif scope == 'named_client':
        cte = sql.SQL(
            'WITH matched_clients AS ('
            'SELECT id FROM public.clients WHERE POSITION(LOWER(name) IN LOWER(%s)) > 0), '
            'unique_client AS ('
            'SELECT id FROM matched_clients '
            'WHERE (SELECT COUNT(*) FROM matched_clients) = 1) '
        )
        args.append(scope_value)
    elif scope == 'calendar_self':
        # The employee ID originates from verified access, never the prompt.
        cte = sql.SQL('WITH target_employees AS (SELECT id FROM public.employees WHERE id = %s) ')
        args.append(user.employee_id)
    elif scope == 'workload_self':
        # Preserve the pre-existing meaning of 'my workload': my team.
        cte = sql.SQL('WITH target_employees AS ('
                      'SELECT e.id FROM public.employees e '
                      'WHERE e.department_id = (SELECT department_id FROM public.employees WHERE id = %s)) ')
        args.append(user.employee_id)
    elif scope in ('calendar_named', 'workload_named'):
        # Unique full-name match takes precedence; then a unique department.
        # Ambiguous/no matches fall back to a full *calendar* profile for
        # existing clarification, without silently guessing an identity.
        cte = sql.SQL(
            'WITH matched_employees AS ('
            'SELECT id FROM public.employees WHERE POSITION(LOWER(full_name) IN LOWER(%s)) > 0), '
            'matched_departments AS ('
            'SELECT id FROM public.departments WHERE POSITION(LOWER(name) IN LOWER(%s)) > 0), '
            'target_employees AS ('
            'SELECT id FROM matched_employees WHERE (SELECT COUNT(*) FROM matched_employees) = 1 '
            'UNION ALL SELECT e.id FROM public.employees e '
            'WHERE NOT EXISTS (SELECT 1 FROM matched_employees) '
            'AND e.department_id IN (SELECT id FROM matched_departments '
            'WHERE (SELECT COUNT(*) FROM matched_departments) = 1)) '
        )
        args.extend((scope_value, scope_value))
    if scope in ('calendar_self', 'calendar_named', 'workload_self', 'workload_named') and calendar_window:
        # Use typed bind parameters just once for all relevant branches.
        cte = cte + sql.SQL(', calendar_bounds AS ('
            'SELECT %s::timestamptz AS start_utc, %s::timestamptz AS end_utc) ')
        args.extend((calendar_start_utc, calendar_end_utc))
    for table in selected:
        fields = FIELDS[table]
        clauses = []
        if scope == 'task_id':
            if table == 'tasks':
                clauses.append(sql.SQL('id IN (SELECT id FROM blocker_chain)'))
            elif table == 'projects':
                clauses.append(sql.SQL('id IN (SELECT project_id FROM requested_task)'))
            elif table == 'clients':
                clauses.append(sql.SQL('id IN (SELECT client_id FROM requested_task)'))
        elif scope == 'named_client':
            fallback = sql.SQL('NOT EXISTS (SELECT 1 FROM unique_client)')
            if 'client_id' in fields:
                clauses.append(sql.SQL('({} OR {} IN (SELECT id FROM unique_client))').format(
                    fallback, sql.Identifier('client_id')))
            elif table == 'clients':
                clauses.append(sql.SQL('({} OR id IN (SELECT id FROM unique_client))').format(fallback))
            elif table == 'meeting_participants':
                clauses.append(sql.SQL(
                    '({} OR meeting_id IN (SELECT id FROM public.meetings '
                    'WHERE client_id IN (SELECT id FROM unique_client)))'
                ).format(fallback))
        elif scope in ('calendar_self', 'calendar_named', 'workload_self', 'workload_named'):
            # Unique target scope reduces tasks/blocks without excluding the
            # visible people and department directory used by the resolver.
            fallback = sql.SQL('NOT EXISTS (SELECT 1 FROM target_employees)')
            if table == 'tasks':
                clauses.append(sql.SQL('({} OR owner_employee_id IN (SELECT id FROM target_employees))').format(fallback))
            elif table == 'employee_schedule_blocks':
                clauses.append(sql.SQL('({} OR employee_id IN (SELECT id FROM target_employees))').format(fallback))
                if calendar_window:
                    clauses.append(sql.SQL('(starts_at < (SELECT end_utc FROM calendar_bounds) '
                                           'AND ends_at > (SELECT start_utc FROM calendar_bounds))'))
            elif table == 'meeting_participants':
                clauses.append(sql.SQL('({} OR employee_id IN (SELECT id FROM target_employees))').format(fallback))
            elif table == 'meetings':
                clauses.append(sql.SQL('({} OR organizer_employee_id IN (SELECT id FROM target_employees) '
                                       'OR id IN (SELECT meeting_id FROM public.meeting_participants '
                                       'WHERE employee_id IN (SELECT id FROM target_employees)))').format(fallback))
                if calendar_window:
                    clauses.append(sql.SQL('(starts_at < (SELECT end_utc FROM calendar_bounds) '
                                           'AND ends_at > (SELECT start_utc FROM calendar_bounds))'))
        if table == 'product_usage' and usage_window is not None:
            clauses.append(sql.SQL('{} >= %s AND {} <= %s').format(
                sql.Identifier('date'), sql.Identifier('date')))
            args.extend(usage_window)
        predicate = (sql.SQL(' WHERE ') + sql.SQL(' AND ').join(clauses)) if clauses else sql.SQL('')
        branch = sql.SQL("SELECT {} AS table_name, to_jsonb(row_data) AS payload FROM "
                         "(SELECT {} FROM public.{}{} ORDER BY {} LIMIT %s) AS row_data").format(
            sql.Literal(table),
            sql.SQL(',').join(map(sql.Identifier, fields)),
            sql.Identifier(table), predicate,
            sql.Identifier(fields[0]),
        )
        branches.append(branch)
        args.append(caps[table] + 1)
    query = cte + sql.SQL(' UNION ALL ').join(branches)
    timings = {}
    with read_connection(user, timings=timings) as connection:
        sql_started = perf_counter()
        cursor = connection.execute(query, tuple(args))
        timings['db_sql_ms'] = round((perf_counter() - sql_started) * 1000, 2)
        fetch_started = perf_counter()
        combined = cursor.fetchall()
        timings['db_fetch_ms'] = round((perf_counter() - fetch_started) * 1000, 2)
    decode_started = perf_counter()
    tables = {table: [] for table in FIELDS}
    for row in combined:
        table = row['table_name']
        if table not in selected:
            raise ValueError('Database returned an unexpected table identifier')
        payload = row['payload']
        if isinstance(payload, str):
            payload = json.loads(payload)
        if not isinstance(payload, dict):
            raise ValueError('Database returned an unexpected record shape')
        tables[table].append(payload)
    limitations = []
    for table, cap in caps.items():
        if len(tables[table]) > cap:
            limitations.append(f'{table} exceeded the {cap}-record snapshot bound; aggregates describe only loaded records.')
        tables[table] = tables[table][:cap]
    result = Snapshot(tables, limitations=limitations)
    timings['db_decode_ms'] = round((perf_counter() - decode_started) * 1000, 2)
    result.load_ms = round((perf_counter() - start) * 1000, 2)
    result.timings = timings
    logger.info('KAIROS enterprise snapshot: elapsed_ms=%.2f profile=%s scope=%s tables=%d records=%d',
                result.load_ms, profile or 'full', scope or 'unscoped', len(selected), sum(map(len, tables.values())))
    return result
