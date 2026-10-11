"""Schedule-specific planner guardrails; synthetic fixtures and no external calls."""
import unittest
from datetime import date

from backend.intelligence.intent import resolve_intent
from backend.intelligence.knowledge import Knowledge
from backend.intelligence.models import IntentRequest, Workspace
from backend.intelligence.repository import Snapshot
from backend.intelligence.workspace import compose_workspace
from backend.tests.intelligence_fixtures import TODAY, USER, fixture


class TimetablePass5Tests(unittest.TestCase):
    def setUp(self):
        self.data = fixture()
        self.knowledge = Knowledge()

    def plan(self, prompt, snapshot=None):
        source = snapshot or self.data
        intent = resolve_intent(IntentRequest(input=prompt), source, USER, today=TODAY)
        result = compose_workspace(source, self.knowledge, intent, today=TODAY, request_text=prompt)
        Workspace.model_validate(result.model_dump(mode='json'))
        return intent, result

    def test_schedule_query_returns_calendar_not_workload(self):
        intent, result = self.plan('Show Avery Test schedule for next week')
        self.assertEqual(intent.name, 'team_workload_planning')
        self.assertEqual((intent.date_from, intent.date_to), (date(2026, 10, 12), date(2026, 10, 18)))
        self.assertEqual(result.status, 'ready')
        self.assertEqual(result.schemaVersion, 2)
        self.assertEqual([c.type for c in result.components], ['InsightPanel'])
        self.assertEqual(len(result.datasets['schedule_events']), 2)
        self.assertEqual(len(result.datasets['schedule_days']), 7)
        summary = result.datasets['schedule_summary'][0]
        self.assertEqual(summary['timezone'], 'Asia/Kolkata')
        self.assertEqual(summary['recorded_block_count'], 2)
        self.assertEqual(summary['merged_booked_hours'], 3.0)
        self.assertTrue(any('3.00 hours in merged calendar intervals' in c.text for c in result.claims))
        self.assertTrue(any('Meeting' in c.text for c in result.claims))
        self.assertFalse(any('owner for Avery Test' in c.text for c in result.claims))
        self.assertFalse(any('estimated backlog hours' in c.text for c in result.claims))
        self.assertFalse(any('Consult Team workload analysis' in c.text for c in result.claims))
        ids = {e.id for e in result.evidence}
        self.assertTrue(all(set(c.evidence_ids) <= ids for c in result.claims))

    def test_ordinary_workload_still_renders_original_widgets(self):
        _, result = self.plan('Show Engineering workload')
        types = [c.type for c in result.components]
        self.assertIn('TaskList', types)
        self.assertIn('ProjectProgress', types)
        self.assertNotIn('schedule_summary', result.datasets)
        self.assertIn('workload_chart', result.datasets)
        self.assertTrue(any('estimated backlog hours' in c.text for c in result.claims))

    def test_my_schedule_targets_authenticated_employee_not_department(self):
        intent, result = self.plan('Show my schedule next week')
        self.assertEqual([(r.entity_type, r.entity_id) for r in intent.entities], [('employee', 'e1')])
        self.assertEqual(result.datasets['schedule_summary'][0]['employee_ids'], ['e1'])

    def test_missing_employee_asks_clarification(self):
        intent, result = self.plan('Show schedule next week')
        self.assertIsNotNone(intent.clarification)
        self.assertIn('Whose schedule', intent.clarification.question)
        self.assertEqual(result.status, 'clarification')

    def test_utc_boundary_event_is_in_local_monday(self):
        tables = {table: [dict(r) for r in rows] for table, rows in self.data.tables.items()}
        tables['employee_schedule_blocks'].append({
            'id': 's3', 'employee_id': 'e1', 'project_id': 'p1',
            'starts_at': '2026-10-11T23:30:00+00:00',
            'ends_at': '2026-10-12T01:00:00+00:00',
            'block_type': 'Focus', 'description': 'Late engineering focus',
        })
        _, result = self.plan('Show Avery Test timetable next week', Snapshot(tables))
        self.assertEqual(result.datasets['schedule_days'][0]['event_count'], 3)
        self.assertTrue(any('05:00 AM' in c.text for c in result.claims))
        self.assertTrue(any('Late engineering focus' in c.text for c in result.claims))

    def test_no_events_does_not_claim_availability(self):
        tables = {table: [dict(r) for r in rows] for table, rows in self.data.tables.items()}
        tables['employee_schedule_blocks'] = []
        _, result = self.plan('Show Avery Test calendar next week', Snapshot(tables))
        self.assertEqual(result.status, 'not_found')
        self.assertEqual(result.datasets['schedule_events'], [])
        self.assertTrue(any(c.kind == 'uncertainty' and 'does not prove availability' in c.text for c in result.claims))

    def test_api_response_contains_calendar_data_and_stable_v2(self):
        from fastapi.testclient import TestClient
        from backend.auth import current_user
        from backend.main import app
        from backend.routers.intelligence import plan_snapshot
        app.dependency_overrides[current_user] = lambda: USER
        app.dependency_overrides[plan_snapshot] = lambda: self.data
        try:
            response = TestClient(app).post('/api/intelligence/workspace/plan',
                                            json={'input': 'Show Avery Test schedule for next week'})
            self.assertEqual(response.status_code, 200, response.text)
            body = response.json()
            self.assertEqual(body['schemaVersion'], 2)
            self.assertEqual(body['datasets']['schedule_summary'][0]['recorded_block_count'], 2)
            self.assertEqual(body['components'][0]['type'], 'InsightPanel')
            self.assertNotIn('owner for Avery Test', ' '.join(x['text'] for x in body['claims']))
            self.assertIn('snapshot;dur=', response.headers['server-timing'])
        finally:
            app.dependency_overrides.clear()

    def test_department_calendar_is_bounded_to_department(self):
        _, result = self.plan('Show Engineering schedule next week')
        summary = result.datasets['schedule_summary'][0]
        self.assertEqual(set(summary['employee_ids']), {'e1', 'e2'})
        self.assertEqual({e['employee_id'] for e in result.datasets['schedule_events']}, {'e1'})


if __name__ == '__main__':
    unittest.main()
