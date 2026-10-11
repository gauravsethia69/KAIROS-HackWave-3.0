"""Cache-scope security, correctness, concurrency and v2 compatibility tests."""
import os
import threading
import time
import unittest
from datetime import date, datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from backend.main import app
from backend.auth import current_user
from backend.intelligence import gateway
from backend.intelligence.models import Workspace
from backend.tests.intelligence_fixtures import fixture, USER, OTHER


class UniversalReadGatewayTests(unittest.TestCase):
    def setUp(self):
        gateway.invalidate_snapshots()
        self.env = patch.dict(os.environ, {'KAIROS_READ_CACHE_SECONDS': '20'})
        self.env.start()
        self.calls = []

    def tearDown(self):
        self.env.stop()
        gateway.invalidate_snapshots()
        app.dependency_overrides.clear()

    def read(self, user, **kwargs):
        self.calls.append((user.id, kwargs))
        return fixture()

    def test_same_user_same_request_cached_across_calls(self):
        with patch.object(gateway, 'load_snapshot', side_effect=self.read):
            one = gateway.load_read_snapshot(USER, profile='workload', request_text='Show Engineering workload')
            two = gateway.load_read_snapshot(USER, profile='workload', request_text='Show Engineering workload')
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(one.cache_state, 'MISS')
        self.assertEqual(two.cache_state, 'HIT')
        self.assertEqual(two.get('tasks', 't1')['title'], 'Validate SSO callback fix')

    def test_different_verified_id_never_shares_cached_data(self):
        with patch.object(gateway, 'load_snapshot', side_effect=self.read):
            gateway.load_read_snapshot(USER, profile='calendar', request_text='Show next week schedule')
            gateway.load_read_snapshot(OTHER, profile='calendar', request_text='Show next week schedule')
        self.assertEqual(len(self.calls), 2)

    def test_same_uuid_different_role_or_employee_does_not_share(self):
        from backend.auth import Identity
        other_role = Identity(id=USER.id, employee_id=USER.employee_id, access_role='manager')
        other_employee = Identity(id=USER.id, employee_id=OTHER.employee_id, access_role='employee')
        with patch.object(gateway, 'load_snapshot', side_effect=self.read):
            for user in (USER, other_role, other_employee):
                gateway.load_read_snapshot(user, profile='workload', request_text='Show my workload')
        self.assertEqual(len(self.calls), 3)

    def test_profile_and_client_scope_do_not_cross_contaminate(self):
        with patch.object(gateway, 'load_snapshot', side_effect=self.read):
            gateway.load_read_snapshot(USER, profile='meeting', request_text='Prepare OrbitPay client meeting')
            gateway.load_read_snapshot(USER, profile='meeting', request_text='Prepare Atlas Media Group client meeting')
            gateway.load_read_snapshot(USER, profile='projects', request_text='Review Atlas Media Group project')
        self.assertEqual(len(self.calls), 3)

    def test_unscoped_profiles_share_when_query_does_not_change_sql(self):
        with patch.object(gateway, 'load_snapshot', side_effect=self.read):
            gateway.load_read_snapshot(USER, profile=None, request_text='Compare all departments')
            hit = gateway.load_read_snapshot(USER, profile=None, request_text='Company wide assessment')
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(hit.cache_state, 'HIT')

    def test_calendar_date_window_changes_key(self):
        with patch.object(gateway, 'load_snapshot', side_effect=self.read):
            gateway.load_read_snapshot(USER, profile='calendar', request_text='Show Jordan Lee schedule from 2026-10-12 to 2026-10-18')
            gateway.load_read_snapshot(USER, profile='calendar', request_text='Show Jordan Lee schedule from 2026-10-19 to 2026-10-25')
        self.assertEqual(len(self.calls), 2)

    def test_midnight_timezone_rollover_changes_key(self):
        ist = ZoneInfo('Asia/Kolkata')
        a = datetime(2026, 10, 11, 23, 59, tzinfo=ist)
        b = datetime(2026, 10, 12, 0, 1, tzinfo=ist)
        one = gateway._key(USER, profile='calendar', usage_window=None, request_text='Show next week schedule', now=a)
        two = gateway._key(USER, profile='calendar', usage_window=None, request_text='Show next week schedule', now=b)
        self.assertNotEqual(one, two)

    def test_snapshot_mutations_cannot_poison_cache(self):
        with patch.object(gateway, 'load_snapshot', side_effect=self.read):
            first = gateway.load_read_snapshot(USER, profile='workload', request_text='Show Engineering workload')
            first.tables['tasks'][0]['title'] = 'poisoned'
            second = gateway.load_read_snapshot(USER, profile='workload', request_text='Show Engineering workload')
            second.tables['tasks'][0]['title'] = 'another poison'
            third = gateway.load_read_snapshot(USER, profile='workload', request_text='Show Engineering workload')
        self.assertEqual(third.tables['tasks'][0]['title'], 'Validate SSO callback fix')
        self.assertEqual(len(self.calls), 1)

    def test_invalidate_after_write_forces_fresh_read(self):
        with patch.object(gateway, 'load_snapshot', side_effect=self.read):
            gateway.load_read_snapshot(USER, profile='calendar', request_text='Show next week schedule')
            gateway.invalidate_snapshots(USER.id)
            fresh = gateway.load_read_snapshot(USER, profile='calendar', request_text='Show next week schedule')
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(fresh.cache_state, 'MISS')

    def test_off_switch_always_reads_from_db(self):
        with patch.dict(os.environ, {'KAIROS_READ_CACHE_SECONDS': '0'}), patch.object(gateway, 'load_snapshot', side_effect=self.read):
            one = gateway.load_read_snapshot(USER, profile='workload', request_text='Show workload')
            two = gateway.load_read_snapshot(USER, profile='workload', request_text='Show workload')
        self.assertEqual(len(self.calls), 2)
        self.assertEqual((one.cache_state, two.cache_state), ('BYPASS', 'BYPASS'))

    def test_expired_snapshot_forces_reload(self):
        with patch.dict(os.environ, {'KAIROS_READ_CACHE_SECONDS': '0.02'}), patch.object(gateway, 'load_snapshot', side_effect=self.read):
            gateway.load_read_snapshot(USER, profile='workload', request_text='Show workload')
            time.sleep(.035)
            gateway.load_read_snapshot(USER, profile='workload', request_text='Show workload')
        self.assertEqual(len(self.calls), 2)

    def test_fresh_meeting_conflict_check_bypasses_cache(self):
        with patch.object(gateway, 'load_snapshot', side_effect=self.read):
            gateway.load_read_snapshot(USER, profile='meeting', request_text='Meet with OrbitPay')
            result = gateway.load_read_snapshot(USER, profile='meeting', request_text='Meet with OrbitPay', fresh=True)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(result.cache_state, 'BYPASS')

    def test_failed_db_load_is_never_cached(self):
        with patch.object(gateway, 'load_snapshot', side_effect=[RuntimeError('database error'), fixture()]):
            with self.assertRaises(RuntimeError):
                gateway.load_read_snapshot(USER, profile='workload', request_text='Show workload')
            result = gateway.load_read_snapshot(USER, profile='workload', request_text='Show workload')
        self.assertEqual(result.cache_state, 'MISS')

    def test_two_simultaneous_identical_requests_only_one_db_call(self):
        started = threading.Event()
        release = threading.Event()
        output = []
        lock = threading.Lock()
        def blocking_read(user, **kwargs):
            with lock:
                self.calls.append(user.id)
            started.set()
            self.assertTrue(release.wait(timeout=3))
            return fixture()
        def worker():
            output.append(gateway.load_read_snapshot(USER, profile='workload', request_text='Show Engineering workload'))
        with patch.object(gateway, 'load_snapshot', side_effect=blocking_read):
            a = threading.Thread(target=worker)
            b = threading.Thread(target=worker)
            a.start()
            self.assertTrue(started.wait(timeout=2))
            b.start()
            time.sleep(.02)
            release.set()
            a.join(timeout=3)
            b.join(timeout=3)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(len(output), 2)
        self.assertEqual(sorted(x.cache_state for x in output), ['HIT','MISS'])

    def test_targeted_read_uses_existing_authorized_read_only_transaction(self):
        from contextlib import contextmanager
        from unittest.mock import MagicMock
        from psycopg.sql import SQL
        fake = MagicMock()
        fake.execute.return_value.fetchmany.return_value = [{'id': 'e1'}, {'id': 'e2'}]
        flags = []
        @contextmanager
        def connection(user, *, read_only=False, timings=None):
            flags.append((user, read_only))
            yield fake
        with patch('backend.database.user_connection', connection):
            rows, partial, timings = gateway.read_targeted(USER,
                statement=SQL('SELECT id FROM public.employees WHERE department_id = %s'),
                parameters=('eng',), max_rows=1)
        self.assertEqual(rows, [{'id':'e1'}])
        self.assertTrue(partial)
        self.assertEqual(flags, [(USER, True)])
        self.assertEqual(fake.execute.call_args.args[1], ('eng',))
        self.assertEqual(fake.execute.return_value.fetchmany.call_args.args[0], 2)
        self.assertIn('db_sql_ms', timings)

    def test_targeted_read_rejects_non_sql_objects_and_unbounded_rows(self):
        from psycopg.sql import SQL
        with self.assertRaises(TypeError):
            gateway.read_targeted(USER, statement='SELECT * FROM public.employees')
        with self.assertRaises(ValueError):
            gateway.read_targeted(USER, statement=SQL('SELECT 1'), max_rows=9999)

    def test_original_workspaces_remain_v2(self):
        from backend.intelligence.intent import resolve_intent
        from backend.intelligence.knowledge import Knowledge
        from backend.intelligence.workspace import compose_workspace
        from backend.intelligence.models import IntentRequest
        requests = ('Show Engineering team workload', 'Show Jordan Lee schedule next week',
                    'Summarize urgent support incidents', 'Prepare an executive briefing on company risks',
                    'Investigate product usage for OrbitPay', 'Review delayed projects for Atlas Media Group')
        with patch.object(gateway, 'load_snapshot', side_effect=self.read):
            for request_text in requests:
                data = gateway.load_read_snapshot(USER, profile=None, request_text=request_text)
                intent = resolve_intent(IntentRequest(input=request_text), data, USER, today=date(2026,10,11))
                plan = compose_workspace(data, Knowledge(), intent, today=date(2026,10,11), request_text=request_text)
                Workspace.model_validate(plan.model_dump(mode='json'))
                self.assertEqual(plan.schemaVersion, 2)

    def test_real_api_response_exposes_cache_status_not_secrets(self):
        with patch('backend.routers.intelligence.load_read_snapshot', side_effect=self.read):
            app.dependency_overrides[current_user] = lambda: USER
            client = TestClient(app)
            response = client.post('/api/intelligence/workspace/plan', json={'input':'Show Engineering team workload'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['schemaVersion'], 2)
        self.assertEqual(response.headers['Cache-Control'], 'private, no-store')
        self.assertIn('cache;desc=', response.headers['Server-Timing'])
        self.assertNotIn('11111111-1111', response.headers['Server-Timing'])

if __name__=='__main__': unittest.main()
