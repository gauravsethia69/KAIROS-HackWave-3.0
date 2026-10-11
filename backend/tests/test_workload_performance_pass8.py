"""Pass 8: workload read scoping and caveat status; no live DB changes."""
import unittest
from contextlib import contextmanager
from datetime import date
from unittest.mock import MagicMock, patch

from backend.intelligence.catalog import FIELDS
from backend.intelligence.repository import Snapshot, WORKFLOW_PROFILES, _read_scope, load_snapshot
from backend.intelligence.profiles import profile_for_request
from backend.intelligence.models import IntentRequest, Workspace
from backend.intelligence.intent import resolve_intent
from backend.intelligence.workspace import compose_workspace
from backend.intelligence.knowledge import Knowledge
from backend.tests.intelligence_fixtures import fixture, USER, TODAY


class WorkloadPerformancePass8Tests(unittest.TestCase):
    def capture(self, prompt):
        connection = MagicMock()
        connection.execute.return_value.fetchall.return_value=[]
        @contextmanager
        def fake_read(_user, *, timings=None):
            yield connection
        with patch('backend.intelligence.repository.read_connection', fake_read):
            result=load_snapshot(USER,profile='workload',request_text=prompt)
        query,values=connection.execute.call_args.args
        return result, query.as_string(),values

    def test_workload_profile_removes_unused_streams(self):
        self.assertEqual(len(WORKFLOW_PROFILES['workload']),8)
        self.assertTrue({'employees','departments','clients','products','projects','tasks','issues','employee_schedule_blocks'} == WORKFLOW_PROFILES['workload'])
        self.assertEqual(profile_for_request(IntentRequest(input='Show Engineering team workload'), today=TODAY)[0], 'workload')
        self.assertEqual(profile_for_request(IntentRequest(input='Show Engineering schedule next week'), today=TODAY)[0], 'calendar')

    def test_named_team_workload_is_scoped_and_date_bounded(self):
        _, query, params=self.capture('Show Engineering team workload from 2026-10-12 to 2026-10-18')
        self.assertIn('WITH matched_employees AS',query)
        self.assertIn('matched_departments',query)
        self.assertIn('target_employees',query)
        self.assertIn('owner_employee_id IN (SELECT id FROM target_employees)',query)
        self.assertIn('employee_id IN (SELECT id FROM target_employees)',query)
        self.assertIn('starts_at < (SELECT end_utc FROM calendar_bounds)',query)
        self.assertIn('ends_at > (SELECT start_utc FROM calendar_bounds)',query)
        for unneeded in ('meetings','meeting_participants','activity_events','communications','contracts','product_usage'):
            self.assertNotIn('public."'+unneeded+'"',query)
        self.assertEqual(params[0],'Show Engineering team workload from 2026-10-12 to 2026-10-18')
        self.assertEqual(params[1],params[0])
        self.assertEqual(params[2].isoformat(),'2026-10-11T18:30:00+00:00')
        self.assertEqual(params[3].isoformat(),'2026-10-18T18:30:00+00:00')
        self.assertEqual(len(params),4+8)
        self.assertNotIn("'Engineering'",query)

    def test_unmatched_or_ambiguous_team_defaults_to_full_workload_dataset(self):
        _,q,_=self.capture('Show unrecognized department workload')
        self.assertIn('NOT EXISTS (SELECT 1 FROM target_employees)',q)
        # The planner still sees all employee and department identities.
        self.assertIn('public."employees"',q)
        self.assertIn('public."departments"',q)
        self.assertIn('public."clients"',q)
        self.assertIn('public."products"',q)
        self.assertIn('public."tasks"',q)

    def test_self_workload_scopes_to_verified_department(self):
        _,q,params=self.capture('Show my workload')
        self.assertIn('WHERE e.department_id = (SELECT department_id FROM public.employees WHERE id = %s)',q)
        self.assertEqual(params[0],USER.employee_id)
        self.assertEqual(_read_scope('workload','Show my workload'),('workload_self',None))
        self.assertNotIn("'e1'",q)

    def test_department_comparison_retains_existing_v2_workload_chart_and_evidence(self):
        full=fixture()
        engineer_ids={e['id'] for e in full.rows('employees') if e.get('department_id')=='eng'}
        slim={table:list(full.rows(table)) for table in WORKFLOW_PROFILES['workload']}
        slim['tasks']=[r for r in slim['tasks'] if r.get('owner_employee_id') in engineer_ids]
        slim['employee_schedule_blocks']=[r for r in slim['employee_schedule_blocks'] if r.get('employee_id') in engineer_ids]
        scoped=Snapshot(slim)
        prompt='Show Engineering team workload'
        full_intent=resolve_intent(IntentRequest(input=prompt),full,USER,today=TODAY)
        slim_intent=resolve_intent(IntentRequest(input=prompt),scoped,USER,today=TODAY)
        self.assertEqual(full_intent.model_dump(mode='json'),slim_intent.model_dump(mode='json'))
        knowledge=Knowledge()
        original=compose_workspace(full,knowledge,full_intent,today=TODAY,request_text=prompt)
        optimized=compose_workspace(scoped,knowledge,slim_intent,today=TODAY,request_text=prompt)
        self.assertEqual(original.schemaVersion,2)
        self.assertEqual(original.status,optimized.status)
        for key in ('workload_chart','capacity','schedule_events','tasks','projects'):
            self.assertEqual(original.datasets.get(key),optimized.datasets.get(key),key)
        self.assertEqual([c.text for c in original.claims],[c.text for c in optimized.claims])
        Workspace.model_validate(optimized.model_dump(mode='json'))
        ids={e.id for e in optimized.evidence}
        self.assertTrue(all(set(c.evidence_ids) <= ids for c in optimized.claims))

    def test_ordinary_workload_caveat_not_mislabeled_partial(self):
        full=fixture()
        prompt='Show Engineering team workload'
        intent=resolve_intent(IntentRequest(input=prompt),full,USER,today=TODAY)
        plan=compose_workspace(full,Knowledge(),intent,today=TODAY,request_text=prompt)
        self.assertEqual(plan.status,'ready')
        self.assertTrue(any('not guaranteed availability' in l for l in plan.limitations))
        self.assertEqual(len(plan.datasets['workload_chart']),2)

    def test_real_missing_widget_still_marks_partial(self):
        data=fixture()
        tables={key:list(vals) for key, vals in data.tables.items()}
        tables['projects']=[]
        snapshot=Snapshot(tables)
        prompt='Show Engineering team workload'
        intent=resolve_intent(IntentRequest(input=prompt),snapshot,USER,today=TODAY)
        result=compose_workspace(snapshot,Knowledge(),intent,today=TODAY,request_text=prompt)
        self.assertEqual(result.status,'partial')
        self.assertTrue(any('No matching projects' in l for l in result.limitations))

    def test_compound_and_followups_are_not_force_scoped(self):
        request=IntentRequest(input='Show workload and urgent incidents')
        self.assertEqual(profile_for_request(request,today=TODAY),(None,None))
        followup=IntentRequest(input='Compare with previous period',context_token='v2-token')
        self.assertEqual(profile_for_request(followup,today=TODAY),(None,None))
        self.assertIsNone(_read_scope(None,'Show Engineering team workload')[0])

if __name__=='__main__': unittest.main()
