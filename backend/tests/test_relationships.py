import json
import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException
from backend.intelligence.models import EntityRef
from backend.intelligence.evidence import EvidenceSet, resolve_evidence
from backend.intelligence.knowledge import Knowledge
from backend.intelligence.repository import Snapshot
from backend.knowledge.generate import generate
from backend.services.responsibility import resolve, find_employees
from backend.tests.intelligence_fixtures import fixture


class RelationshipTests(unittest.TestCase):
    def setUp(self):
        self.data = fixture()

    def resolve(self, kind, identifier):
        return resolve(self.data, EntityRef(entity_type=kind, entity_id=identifier))

    def test_employee_task_project_issue_meeting_schedule(self):
        result = self.resolve('employee', 'e1')
        self.assertEqual(result.department['name'], 'Engineering')
        self.assertEqual(result.manager['id'], 'e2')
        for table in ('tasks', 'projects', 'issues', 'meetings', 'employee_schedule_blocks'):
            self.assertTrue(result.related[table])
        self.assertEqual(find_employees(self.data, 'Avery')[0]['id'], 'e1')

    def test_project_and_contract_owner(self):
        self.assertEqual(self.resolve('project', 'p2').owner['id'], 'e2')
        self.assertEqual(self.resolve('contract', 'con1').owner['id'], 'e3')

    def test_blocker_chain_and_missing_owner(self):
        result = self.resolve('task', 't1')
        self.assertEqual(result.blocker_chain[0]['blocking_task']['id'], 't2')
        self.assertEqual(result.blocker_chain[0]['owner']['id'], 'e2')
        unknown = self.resolve('task', 't3')
        self.assertIsNone(unknown.owner)
        self.assertFalse(unknown.proposed_contacts)
        self.assertTrue(unknown.limitations)

    def test_cycle_does_not_invent_escalation(self):
        self.data.get('tasks', 't2')['blocker_task_id'] = 't1'
        result = self.resolve('task', 't1')
        self.assertEqual(len(result.blocker_chain), 1)
        self.assertIn('Cycle', result.limitations[0])

    def test_missing_blocker(self):
        self.data.get('tasks', 't1')['blocker_task_id'] = 'missing'
        result = self.resolve('task', 't1')
        self.assertFalse(result.blocker_chain)
        self.assertTrue(result.limitations)

    def test_stable_evidence_and_resolution(self):
        one, two = EvidenceSet(self.data), EvidenceSet(fixture())
        key = one.database('tasks', self.data.get('tasks', 't1'), 'status')
        self.assertEqual(key, two.database('tasks', self.data.get('tasks', 't1'), 'status'))
        self.assertEqual(resolve_evidence(key, self.data, Knowledge())['value'], 'Blocked')
        with self.assertRaises(HTTPException):
            resolve_evidence('db:employee_access:e1:auth_user_id', self.data, Knowledge())
        with self.assertRaises(HTTPException):
            self.resolve('employee', 'missing')

    def test_private_fields_never_enter_snapshot(self):
        text = json.dumps(self.data.tables)
        for excluded in ('never-export', 'excluded@example.test', 'annual_value', 'metadata'):
            self.assertNotIn(excluded, text)

    def test_repeatable_generator_90_briefs(self):
        data = Snapshot({'employees': [{'id': f'e{i}', 'full_name': f'Fixture employee {i}'} for i in range(54)], 'clients': [{'id': f'c{i}', 'name': f'Fixture client {i}'} for i in range(14)], 'projects': [{'id': f'p{i}', 'name': f'Fixture project {i}'} for i in range(22)]}, retrieved_at=self.data.retrieved_at)
        with tempfile.TemporaryDirectory() as temporary:
            first = generate(data, temporary)
            contents = {p.name: p.read_bytes() for p in Path(temporary).glob('*.md')}
            self.assertEqual(len(first), 90)
            self.assertEqual(first, generate(data, temporary))
            self.assertEqual(contents, {p.name: p.read_bytes() for p in Path(temporary).glob('*.md')})
