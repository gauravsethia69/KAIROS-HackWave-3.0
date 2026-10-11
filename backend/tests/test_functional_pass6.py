"""Pass 6: synthetic, RLS-filtered snapshot assertions; no remote database use."""
import unittest
from datetime import date
from backend.intelligence.intent import resolve_intent
from backend.intelligence.models import IntentRequest, Workspace
from backend.intelligence.knowledge import Knowledge
from backend.intelligence.repository import Snapshot
from backend.intelligence.workspace import compose_workspace
from backend.tests.intelligence_fixtures import fixture, TODAY, USER


class FunctionalPass6Tests(unittest.TestCase):
    def setUp(self):
        self.data=fixture()
        self.knowledge=Knowledge()

    def plan(self,q,source=None):
        snapshot=source or self.data
        intent=resolve_intent(IntentRequest(input=q),snapshot,USER,today=TODAY)
        result=compose_workspace(snapshot,self.knowledge,intent,today=TODAY,request_text=q)
        Workspace.model_validate(result.model_dump(mode='json'))
        return intent,result

    def test_calendar_bounded_range_and_directory(self):
        intent,result=self.plan('Show Avery Test schedule from 2026-10-12 to 2026-10-18')
        self.assertEqual((intent.date_from,intent.date_to),(date(2026,10,12),date(2026,10,18)))
        self.assertEqual(result.schemaVersion,2)
        self.assertEqual({row['id'] for row in result.datasets['employee_options']},{'e1','e2','e3'})
        self.assertEqual(result.datasets['schedule_summary'][0]['employee_ids'],['e1'])

    def test_calendar_rejects_excessive_ranges(self):
        intent,result=self.plan('Show Avery Test schedule from 2026-10-12 to 2027-02-01')
        self.assertIsNotNone(intent.clarification)
        self.assertEqual(result.status,'clarification')

    def test_calendar_filters_organizer_attendee_meetings(self):
        tables={table:[dict(row) for row in rows] for table,rows in self.data.tables.items()}
        tables['meetings'][0]['starts_at']='2026-10-12T10:00:00+05:30'
        tables['meetings'][0]['ends_at']='2026-10-12T10:30:00+05:30'
        _,result=self.plan('Show Avery Test schedule next week',Snapshot(tables))
        event=result.datasets['schedule_meetings'][0]
        self.assertEqual(event['meeting_id'],'m1')
        self.assertEqual(event['employee_ids'],['e1'])
        self.assertTrue(set(event['evidence_ids']) <= {e.id for e in result.evidence})
        self.assertEqual(result.datasets['schedule_summary'][0]['recorded_block_count'],2)

    def test_unlinked_meetings_not_on_other_employees_calendar(self):
        tables={table:[dict(row) for row in rows] for table,rows in self.data.tables.items()}
        tables['meetings'][0]['starts_at']='2026-10-12T10:00:00+05:30'
        tables['meetings'][0]['ends_at']='2026-10-12T10:30:00+05:30'
        _,result=self.plan('Show Morgan Example schedule next week',Snapshot(tables))
        self.assertEqual(result.datasets['schedule_meetings'],[])

    def test_blocker_graph_uses_real_task_fk(self):
        _,result=self.plan('Review delayed projects for OrbitPay')
        # The fixture's Orbit project is At risk and explicitly links t1 -> t2.
        edges=result.datasets['task_dependencies']
        self.assertEqual([(e['dependent_task_id'],e['blocker_task_id']) for e in edges],[('t1','t2')])
        self.assertTrue(set(edges[0]['evidence_ids']) <= {e.id for e in result.evidence})

    def test_no_invented_graph_edges(self):
        tables={table:[dict(row) for row in rows] for table,rows in self.data.tables.items()}
        tables['tasks'][0]['blocker_task_id']=None
        _,result=self.plan('Review delayed projects for OrbitPay',Snapshot(tables))
        self.assertEqual(result.datasets['task_dependencies'],[])

    def test_contextual_actions_replace_generic_procedure(self):
        for q in ["Prepare for tomorrow's OrbitPay client meeting",
                  'Review delayed projects for Atlas Media Group',
                  'Summarize urgent support incidents',
                  'Prepare an executive briefing on company risks',
                  'Show Engineering workload',
                  'Investigate product usage for OrbitPay']:
            with self.subTest(q=q):
                _,result=self.plan(q)
                actions=[c for c in result.claims if c.kind=='proposed_action']
                self.assertTrue(actions)
                self.assertTrue(actions[0].evidence_ids)
                self.assertFalse(any(c.text.startswith('Consult ') for c in actions))

    def test_top_level_v2_contract_and_references_remain_valid(self):
        _,result=self.plan('Show Engineering workload')
        self.assertEqual(set(result.model_dump()),set(Workspace.model_fields))
        ids={e.id for e in result.evidence}
        self.assertTrue(all(set(c.evidence_ids)<=ids for c in result.claims))
        self.assertTrue(all(set(c.evidence_ids)<=ids for c in result.components))

if __name__=='__main__':unittest.main()
