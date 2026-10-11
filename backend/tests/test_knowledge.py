import unittest
from fastapi import HTTPException
from pydantic import ValidationError
from backend.intelligence.knowledge import Knowledge, Metadata


class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.knowledge = Knowledge()

    def test_load_and_metadata(self):
        self.assertEqual(len(self.knowledge.documents), 24)
        for doc in self.knowledge.documents.values():
            Metadata.model_validate(doc['metadata'])
            self.assertTrue(doc['sections'])

    def test_metadata_rejects_unapproved_status(self):
        doc = self.knowledge.get('playbook-support-triage')['metadata']
        with self.assertRaises(ValidationError):
            Metadata.model_validate({**doc, 'status': 'approved'})

    def test_rank_and_filter(self):
        results = self.knowledge.search('Soryu Guard', category='products')
        self.assertEqual(results['items'][0]['document_id'], 'product-guard')
        self.assertEqual(self.knowledge.search('workload', tag='workload')['items'][0]['document_id'], 'playbook-team-workload')

    def test_stable_sections_and_pagination(self):
        results = self.knowledge.search('owner', limit=2, offset=1)
        self.assertLessEqual(len(results['items']), 2)
        for item in results['items']:
            self.assertIn(item['section'], [s['id'] for s in self.knowledge.get(item['document_id'])['sections']])

    def test_missing_or_traversal(self):
        for key in ['absent', '../.env', 'generated/employee-private']:
            with self.assertRaises(HTTPException) as error:
                self.knowledge.get(key)
            self.assertEqual(error.exception.status_code, 404)


if __name__ == '__main__':
    unittest.main()
