"""Answer relevance and additive v2 contract tests; synthetic records only."""
from datetime import date
import unittest

from backend.intelligence.intent import resolve_intent
from backend.intelligence.knowledge import Knowledge
from backend.intelligence.models import IntentRequest, Workspace
from backend.intelligence.repository import Snapshot
from backend.intelligence.workspace import compose_workspace
from backend.tests.intelligence_fixtures import TODAY, USER, fixture


class AnswerQualityContractTests(unittest.TestCase):
    def setUp(self):
        self.knowledge = Knowledge()
        self.data = fixture()

    def query(self, text, data=None):
        data = data or self.data
        resolved = resolve_intent(IntentRequest(input=text), data, USER, today=TODAY)
        result = compose_workspace(data, self.knowledge, resolved, today=TODAY)
        Workspace.model_validate(result.model_dump(mode='json'))
        self.assertEqual(result.schemaVersion, 2)
        self.assertEqual(result.source, 'deterministic-enterprise')
        self.assertTrue(all(p.props.binding == 'response.datasets' for p in result.components))
        return result

    def test_scheduled_meeting_brief_has_organizer_and_real_topic_evidence(self):
        plan = self.query("Prepare for tomorrow's OrbitPay client meeting")
        brief = plan.datasets['meeting_brief'][0]
        self.assertTrue(brief['scheduled_meeting_found'])
        self.assertEqual(brief['scheduled_meeting_ids'], ['m1'])
        self.assertEqual(brief['requested_date_from'], '2026-10-12')
        self.assertEqual(brief['account_manager_name'], 'Riley Fixture')
        self.assertTrue(any('Recorded organizer: Riley Fixture' in c.text for c in plan.claims))
        self.assertFalse(any('No OrbitPay meeting was found' in c.text for c in plan.claims))
        self.assertTrue(brief['suggested_topics'])
        self.assertEqual(brief['suggested_topics'][0]['entity_id'], 'i1')
        self.assertIn('MeetingBrief', [p.type for p in plan.components])
        self.assertTrue(all(c.evidence_ids for c in plan.claims if c.kind in ('observation', 'calculation')))

    def test_missing_meeting_date_never_implicitly_invents_appointment(self):
        all_tables = {t: [dict(row) for row in rows] for t, rows in self.data.tables.items()}
        all_tables['meetings'][0]['date'] = '2026-10-05'
        all_tables['meetings'][0]['title'] = 'Previous OrbitPay review'
        source = Snapshot(all_tables)
        plan = self.query("Prepare for tomorrow's OrbitPay client meeting", source)
        brief = plan.datasets['meeting_brief'][0]
        self.assertFalse(brief['scheduled_meeting_found'])
        self.assertEqual(brief['scheduled_meeting_ids'], [])
        self.assertEqual(brief['latest_past_meeting_date'], '2026-10-05')
        self.assertIn('no orbitpay meeting', ' '.join(c.text for c in plan.claims).lower())
        self.assertTrue(any('Latest recorded past meeting: Previous OrbitPay review' in c.text for c in plan.claims))
        self.assertFalse(any(c.type == 'MeetingBrief' for c in plan.components))
        self.assertEqual(plan.datasets['meetings'], [])
        self.assertEqual([c.kind for c in plan.claims].count('observation'), 2)

    def test_delayed_project_primary_owner_precedes_client_manager(self):
        plan = self.query('Review delayed projects for Atlas Media Group')
        first = next(c.text for c in plan.claims if c.kind == 'observation')
        self.assertIn('Morgan Example', first)
        self.assertIn('delivery owner', first)
        self.assertTrue(any('Riley Fixture' in c.text and 'account manager' in c.text for c in plan.claims))
        self.assertTrue(any('progress 40%, expected 90%' in c.text for c in plan.claims))
        self.assertFalse(any('Riley Fixture' in c.text and 'delivery owner' in c.text for c in plan.claims))

    def test_executive_portfolio_counts_are_based_on_records(self):
        plan = self.query('Prepare an executive briefing on company risks')
        metrics = plan.datasets['portfolio_summary'][0]
        self.assertEqual((metrics['total_projects'], metrics['delayed_projects'], metrics['at_risk_projects']), (2, 1, 1))
        self.assertEqual(metrics['total_contracts'], 1)
        self.assertEqual(metrics['contracts_renewal_due'], 0)
        self.assertIn('1 delayed, 1 at-risk', plan.claims[0].text)
        self.assertEqual(len(plan.datasets['contracts']), 1)
        self.assertTrue(set(metrics['evidence_ids']) <= {e.id for e in plan.evidence})
        self.assertEqual(len([c for c in plan.components if c.type == 'ProjectProgress']), 1)

    def test_employee_workload_includes_schedule_events_and_chart_data(self):
        plan = self.query('Show Engineering workload')
        events = plan.datasets['schedule_events']
        self.assertEqual({b['id'] for b in events}, {'s1', 's2'})
        self.assertTrue(all(b['employee_id'] == 'e1' for b in events))
        self.assertTrue(all(b['starts_at'].startswith('2026-10-12') for b in events))
        self.assertEqual(len(plan.datasets['workload_chart']), 2)
        av = next(row for row in plan.datasets['capacity'] if row['employee_id']=='e1')
        self.assertEqual(av['scheduled_interval_hours'], 3)
        self.assertEqual(av['estimated_backlog_hours'], 8)
        self.assertTrue(all(set(b['evidence_ids']) <= {e.id for e in plan.evidence} for b in events))
        self.assertFalse(any(c.type == 'EmployeeTimetable' for c in plan.components))

    def test_employee_timetable_query_resolves_and_filters_next_calendar_week(self):
        from backend.intelligence.profiles import profile_for_request
        request = IntentRequest(input='Show Avery Test schedule for next week')
        from backend.intelligence.intent import resolve_intent
        result = resolve_intent(request, self.data, USER, today=TODAY)
        self.assertEqual(result.name, 'team_workload_planning')
        self.assertEqual((result.date_from, result.date_to), (date(2026, 10, 12), date(2026, 10, 18)))
        self.assertEqual([(e.entity_type, e.entity_id) for e in result.entities], [('employee','e1')])
        self.assertEqual(profile_for_request(request, today=TODAY)[0], 'calendar')
        plan = compose_workspace(self.data, self.knowledge, result, today=TODAY)
        self.assertEqual({r['employee_id'] for r in plan.datasets['schedule_events']}, {'e1'})
        self.assertEqual(len(plan.datasets['schedule_events']), 2)

    def test_timetable_interprets_utc_boundary_in_local_week(self):
        tables = {t: [dict(r) for r in items] for t, items in self.data.tables.items()}
        tables['employee_schedule_blocks'].append({
            'id': 's3', 'employee_id': 'e1', 'project_id': 'p1',
            'starts_at': '2026-10-11T23:30:00+00:00',
            'ends_at': '2026-10-12T01:00:00+00:00',
            'block_type': 'Project',
        })
        snapshot = Snapshot(tables)
        resolved = resolve_intent(IntentRequest(input='Show Avery Test timetable next week'), snapshot, USER, today=TODAY)
        plan = compose_workspace(snapshot, self.knowledge, resolved, today=TODAY)
        self.assertIn('s3', {event['id'] for event in plan.datasets['schedule_events']})
        self.assertEqual(resolved.date_from, date(2026,10,12))

    def test_support_incidents_rank_critical_before_high(self):
        tables={t:[dict(r) for r in v] for t, v in self.data.tables.items()}
        tables['issues'].append({'id':'i2','title':'Example high incident','client_id':'orbit','project_id':'p1',
                                'product_id':'guard','owner_employee_id':'e1','status':'Open',
                                'severity':'High','date':'2026-10-10','sla_hours':8})
        plan = self.query('Summarize urgent support incidents', Snapshot(tables))
        self.assertEqual([i['id'] for i in plan.datasets['issues']], ['i1', 'i2'])
        self.assertIn('exact breach time is unverified', plan.claims[0].text)

    def test_response_shape_unchanged_for_six_flows(self):
        inputs=[
            "Prepare for tomorrow's OrbitPay client meeting",
            'Investigate product usage for OrbitPay',
            'Review delayed projects for Atlas Media Group',
            'Summarize urgent support incidents',
            'Show Engineering workload',
            'Prepare an executive briefing on company risks',
        ]
        baseline_fields = set(Workspace.model_fields)
        for prompt in inputs:
            with self.subTest(prompt=prompt):
                plan = self.query(prompt)
                self.assertEqual(set(plan.model_dump()), baseline_fields)
                for component in plan.components:
                    self.assertIn(component.props.selector, plan.datasets)
                    self.assertEqual(component.props.binding,'response.datasets')
                for claim in plan.claims:
                    self.assertTrue(set(claim.evidence_ids) <= {e.id for e in plan.evidence})


if __name__=='__main__':
    unittest.main()
