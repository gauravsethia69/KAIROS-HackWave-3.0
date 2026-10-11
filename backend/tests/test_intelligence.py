import unittest
from pydantic import ValidationError
from fastapi import HTTPException
from backend.intelligence.context import ContextStore
from backend.intelligence.intent import resolve_intent
from backend.intelligence.knowledge import Knowledge
from backend.intelligence.models import IntentRequest, EntityRef, ComponentPlan, Workspace
from backend.intelligence.workspace import compose_workspace
from backend.intelligence.retrieval import search
from backend.intelligence.repository import Snapshot
from backend.tests.intelligence_fixtures import fixture, USER, OTHER, TODAY


class IntelligenceTests(unittest.TestCase):
    def setUp(self):
        self.data, self.knowledge = fixture(), Knowledge()

    def intent(self, text, previous=None, **kwargs):
        return resolve_intent(IntentRequest(input=text, **kwargs), self.data, USER, previous, TODAY)

    def plan(self, text):
        return compose_workspace(self.data, self.knowledge, self.intent(text), TODAY)

    def test_six_scenarios(self):
        cases = [('Prepare for tomorrow\'s OrbitPay client meeting', 'client_meeting_prep', 'MeetingBrief'), ('Investigate declining product usage', 'product_usage_investigation', 'UsageChart'), ("Why is Atlas Media Group's reporting project delayed?", 'project_delivery_review', 'ProjectProgress'), ('Summarize urgent support incidents', 'support_incident_command', 'IssuePanel'), ('Show Engineering workload', 'team_workload_planning', 'TaskList'), ('Prepare a leadership briefing', 'executive_briefing', 'ProjectProgress')]
        layouts = []
        for text, intent, component in cases:
            with self.subTest(text=text):
                plan = self.plan(text)
                self.assertEqual(plan.intent.name, intent)
                self.assertIsNone(plan.intent.clarification, plan.intent)
                self.assertEqual(plan.components[0].type, component)
                self.assertTrue(plan.evidence)
                layouts.append([(c.type, c.props.selector) for c in plan.components])
                Workspace.model_validate(plan.model_dump())
        self.assertEqual(len({str(layout) for layout in layouts}), 6)

    def test_ownership_and_my_scope(self):
        plan = self.plan('Who owns the blocked SSO task?')
        self.assertEqual(plan.intent.name, 'ownership_lookup')
        self.assertTrue(any('Avery Test' in c.text for c in plan.claims))
        my = self.plan('Review my overdue tasks')
        self.assertEqual({t['owner_employee_id'] for t in my.datasets['tasks']}, {'e1'})

    def test_explicit_sso_task_priority_over_similar_project(self):
        # Regression: the live-style SSO project must not steal an explicit
        # task lookup merely because its title contains the word "SSO".
        self.data.tables['clients'].append({'id': 'northstar', 'name': 'Northstar Retail'})
        self.data.tables['projects'].append({
            'id': 'p8', 'name': 'SSO readiness validation — Northstar Retail',
            'client_id': 'northstar', 'product_id': 'insight',
            'owner_employee_id': 'e2', 'status': 'On track',
            'progress': 78, 'expected': 75, 'due_date': '2026-10-17',
        })
        # In production, the blocked SSO task has no blocker_task_id; a
        # recorded "Blocked" status alone must still allow finding the task.
        self.data.tables['tasks'][0]['blocker_task_id'] = None
        self.data = Snapshot(self.data.tables)

        for question in ('Who owns task t1?', 'Who owns the blocked SSO task?'):
            with self.subTest(question=question):
                intent = self.intent(question)
                self.assertEqual(intent.name, 'ownership_lookup')
                self.assertIsNone(intent.clarification)
                self.assertEqual([(x.entity_type, x.entity_id) for x in intent.entities], [('task', 't1')])
                plan = compose_workspace(self.data, self.knowledge, intent, TODAY)
                self.assertEqual([task['id'] for task in plan.datasets['tasks']], ['t1'])
                self.assertTrue(any('Avery Test' in c.text for c in plan.claims if c.kind == 'observation'))
                self.assertFalse(any('SSO readiness validation' in c.text for c in plan.claims))

        project_intent = self.intent('Who owns the Northstar SSO readiness project?')
        self.assertIsNone(project_intent.clarification)
        self.assertEqual([(x.entity_type, x.entity_id) for x in project_intent.entities if x.entity_type in ('task', 'project')], [('project', 'p8')])
        project_plan = compose_workspace(self.data, self.knowledge, project_intent, TODAY)
        self.assertEqual([project['id'] for project in project_plan.datasets['projects']], ['p8'])
        self.assertTrue(any('Morgan Example' in c.text for c in project_plan.claims if c.kind == 'observation'))

        missing = self.intent('Who owns the blocked Northstar SSO task?')
        self.assertIsNotNone(missing.clarification)
        self.assertIn('task', missing.clarification.question)
        missing_plan = compose_workspace(self.data, self.knowledge, missing, TODAY)
        self.assertEqual(missing_plan.status, 'clarification')
        self.assertFalse(missing_plan.claims)

    def test_new_ownership_question_resets_stale_client_context(self):
        # React sends the previous context_token with EVERY fresh Compose.
        # The user must be able to leave Northstar and ask for a task in Orbit.
        self.data.tables['clients'].append({'id': 'northstar', 'name': 'Northstar Retail'})
        self.data.tables['projects'].append({
            'id': 'p8', 'name': 'SSO readiness validation — Northstar Retail',
            'client_id': 'northstar', 'owner_employee_id': 'e2', 'status': 'On track',
        })
        self.data.tables['projects'].append({
            'id': 'p22', 'name': 'Renewal readiness initiative — Northstar Retail',
            'client_id': 'northstar', 'owner_employee_id': 'e3', 'status': 'Delayed',
        })
        self.data = Snapshot(self.data.tables)
        project = self.intent('Who owns the Northstar SSO readiness project?')
        self.assertIsNone(project.clarification)
        self.assertIn(('project', 'p8'), [(e.entity_type, e.entity_id) for e in project.entities])
        self.assertNotIn(('project', 'p22'), [(e.entity_type, e.entity_id) for e in project.entities])

        # An independent request must not inherit Northstar, project p8 or its
        # filters, even when both prompts share ownership_lookup intent.
        task = self.intent('Who owns task t1?', project)
        self.assertIsNone(task.clarification)
        self.assertEqual([(e.entity_type, e.entity_id) for e in task.entities], [('task', 't1')])
        self.assertFalse(task.blocked_only)
        result = compose_workspace(self.data, self.knowledge, task, TODAY)
        self.assertEqual([r['id'] for r in result.datasets['tasks']], ['t1'])
        self.assertTrue(any('Avery Test' in claim.text for claim in result.claims))

        blocked = self.intent('Who owns the blocked SSO task?', project)
        self.assertIsNone(blocked.clarification)
        self.assertEqual([(e.entity_type, e.entity_id) for e in blocked.entities], [('task', 't1')])
        self.assertTrue(blocked.blocked_only)

        again = self.intent('Who owns the Northstar SSO readiness project?', task)
        self.assertIsNone(again.clarification)
        self.assertEqual([(e.entity_type, e.entity_id) for e in again.entities if e.entity_type in ('task', 'project')], [('project', 'p8')])

    def test_partial_project_name_remains_ambiguous_when_not_distinctive(self):
        self.data.tables['clients'].append({'id': 'northstar', 'name': 'Northstar Retail'})
        for identifier, name in [
            ('p8', 'SSO readiness validation — Northstar Retail'),
            ('p22', 'Renewal readiness initiative — Northstar Retail'),
        ]:
            self.data.tables['projects'].append({
                'id': identifier, 'name': name, 'client_id': 'northstar', 'owner_employee_id': 'e2',
            })
        self.data = Snapshot(self.data.tables)
        general = self.intent('Who owns the Northstar readiness project?')
        self.assertIsNotNone(general.clarification)
        self.assertEqual({c.entity.entity_id for c in general.clarification.candidates}, {'p8', 'p22'})
        distinct = self.intent('Who owns the Northstar SSO readiness project?')
        self.assertIsNone(distinct.clarification)
        self.assertEqual([x.entity_id for x in distinct.entities if x.entity_type == 'project'], ['p8'])

    def test_multiple_blocked_sso_tasks_are_not_guessed(self):
        self.data.tables['projects'].append({
            'id': 'p8', 'name': 'SSO readiness validation — Northstar Retail',
            'client_id': 'orbit', 'owner_employee_id': 'e2', 'status': 'On track',
        })
        self.data.tables['tasks'].append({
            'id': 't4', 'title': 'Investigate SSO claim handling',
            'client_id': 'orbit', 'project_id': 'p8',
            'owner_employee_id': 'e2', 'blocker_task_id': None,
            'status': 'Blocked', 'priority': 'Medium',
        })
        self.data = Snapshot(self.data.tables)
        result = self.intent('Who owns the blocked SSO task?')
        self.assertIsNotNone(result.clarification)
        self.assertEqual({item.entity.entity_id for item in result.clarification.candidates}, {'t1', 't4'})
        self.assertTrue(all(item.entity.entity_type == 'task' for item in result.clarification.candidates))
        self.assertEqual(compose_workspace(self.data, self.knowledge, result, TODAY).status, 'clarification')

    def test_ambiguous_partial_and_misspelled_names(self):
        typo = self.intent('Prepare for an OrbtPay meeting')
        self.assertIn('orbit', [e.entity_id for e in typo.entities])
        self.data.tables['clients'].append({'id': 'atlas-two', 'name': 'Atlas Media Labs'})
        self.data = Snapshot(self.data.tables)
        ambiguous = self.intent('Prepare for Atlas Media meeting')
        self.assertIsNotNone(ambiguous.clarification)
        self.assertEqual({c.entity.entity_id for c in ambiguous.clarification.candidates}, {'atlas', 'atlas-two'})
        exact = self.intent('Prepare for Atlas Media Group meeting')
        self.assertIsNone(exact.clarification)
        self.assertIn('atlas', [e.entity_id for e in exact.entities])
        selected = self.intent('Prepare for Atlas Media meeting', selection=EntityRef(entity_type='client', entity_id='atlas-two'))
        self.assertIsNone(selected.clarification)
        self.assertIn('atlas-two', [e.entity_id for e in selected.entities])

    def test_unsupported_and_invalid_selection(self):
        self.assertEqual(self.plan('Write a poem about the moon').status, 'unsupported')
        with self.assertRaises(HTTPException):
            self.intent('Show a client', selection=EntityRef(entity_type='client', entity_id='missing'))

    def test_goal_and_client_context_changes(self):
        meeting = self.intent('Prepare for OrbitPay meeting')
        usage = self.intent('Investigate usage for this client', meeting)
        self.assertEqual(usage.name, 'product_usage_investigation')
        self.assertIn('orbit', [e.entity_id for e in usage.entities])
        plan = compose_workspace(self.data, self.knowledge, usage, TODAY)
        self.assertNotIn('MeetingBrief', [c.type for c in plan.components])
        projects = self.intent('Review Atlas Media reporting project')
        changed = self.intent('Switch to OrbitPay', projects)
        self.assertNotIn('p2', [e.entity_id for e in changed.entities])
        team = self.intent('Show my team workload', meeting)
        self.assertEqual([e.entity_id for e in team.entities], ['eng'])

    def test_layout_date_and_blocked_transformations(self):
        usage = self.intent('Investigate OrbitPay usage')
        fourteen = self.intent('Show only the last 14 days', usage)
        self.assertEqual((fourteen.date_to - fourteen.date_from).days, 13)
        table = compose_workspace(self.data, self.knowledge, self.intent('Show this as a table instead', fourteen), TODAY)
        self.assertEqual(table.components[0].type, 'DataTable')
        task = self.intent('Review my tasks')
        blocked = self.intent('Focus on blocked work', task)
        self.assertTrue(blocked.blocked_only)
        self.assertEqual(blocked.name, task.name)
        unresolved = self.intent('Focus on unresolved issues', usage)
        self.assertTrue(unresolved.unresolved_only)
        self.assertEqual(unresolved.name, usage.name)

    def test_no_unsupported_components_props_or_references(self):
        plan = self.plan('Show Engineering workload')
        component = plan.components[0].model_dump()
        for change in [{'type': 'CapacitySuperWidget'}, {'props': {'selector': 'auth.users', 'record_ids': []}}, {'props': {'selector': 'tasks', 'record_ids': [], 'code': 'evil'}}]:
            with self.assertRaises(ValidationError):
                ComponentPlan.model_validate({**component, **change})
        raw = plan.model_dump()
        raw['components'][0]['props']['record_ids'] = ['imaginary']
        with self.assertRaises(ValidationError):
            Workspace.model_validate(raw)

    def test_usage_facts_do_not_infer_causes(self):
        plan = self.plan('Investigate OrbitPay usage')
        self.assertEqual(plan.datasets['usage_metrics'][0]['change_percent'], -50)
        self.assertTrue(any(c.kind == 'uncertainty' and 'causation' in c.text for c in plan.claims))
        for claim in plan.claims:
            if claim.kind in ('observation', 'calculation'):
                self.assertTrue(claim.evidence_ids)

    def test_merged_schedule_and_missing_data(self):
        plan = self.plan('Show Engineering workload')
        avery = next(r for r in plan.datasets['capacity'] if r['id'] == 'e1')
        self.assertEqual(avery['scheduled_interval_hours'], 3)
        self.data.tables['product_usage'] = []
        missing = self.plan('Investigate usage')
        self.assertNotIn('UsageChart', [c.type for c in missing.components])
        self.assertTrue(missing.limitations)

    def test_context_expires_and_never_crosses_users(self):
        now = [0]
        store = ContextStore(ttl=10, clock=lambda: now[0])
        token = store.put(self.intent('Review my tasks'), USER)
        self.assertEqual(store.get(token, USER).entities[0].entity_id, 'e1')
        with self.assertRaises(HTTPException):
            store.get(token, OTHER)
        now[0] = 11
        with self.assertRaises(HTTPException):
            store.get(token, USER)

    def test_retrieval_filters_and_stable_evidence(self):
        result = search(self.data, self.knowledge, 'SSO', department_id='eng', limit=5)
        self.assertTrue(result.items)
        for hit in result.items:
            self.assertIn(hit.evidence_id, {e.id for e in result.evidence})
