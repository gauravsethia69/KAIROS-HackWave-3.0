"""Run with: python -m unittest backend.tests.test_atlas_retrieval -v"""
import tempfile
import unittest
from pathlib import Path

from backend.intelligence.atlas_retrieval import Atlas, atlas, groq_reference_context


class AtlasIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.atlas = atlas()

    def test_exact_24_pages_and_citations(self):
        self.assertEqual(self.atlas.index['total_pages'], 24)
        self.assertEqual(len(set(c['page'] for c in self.atlas.chunks)), 24)
        self.assertEqual(len(self.atlas.chunks), 103)
        self.assertEqual(len({c['source_id'] for c in self.atlas.chunks}), 24)
        self.assertTrue(all(c['status'] in ('proposed', 'reference') for c in self.atlas.chunks))

    def test_product_title(self):
        hits = self.atlas.search('Soryu Guard identity SSO', limit=4)
        self.assertEqual(hits[0]['source_id'], 'product-guard')
        self.assertEqual(hits[0]['page'], 16)

    def test_meeting_playbook_not_approved(self):
        hits = self.atlas.search('Prepare for next OrbitPay client meeting', limit=5)
        self.assertTrue(any(h['page'] == 17 and h['status'] == 'proposed' for h in hits))

    def test_workload(self):
        hits = self.atlas.search('Engineering workload capacity hours tasks and schedule', limit=7)
        self.assertTrue(any(h['page'] == 21 for h in hits))

    def test_usage_investigation(self):
        hits = self.atlas.search('product usage decline compare periods missing measurements', limit=5)
        self.assertTrue(any(h['page'] == 18 for h in hits))

    def test_category_filter(self):
        hits = self.atlas.search('Soryu Insight', category='products')
        self.assertTrue(hits)
        self.assertTrue(all(h['category'] == 'products' for h in hits))

    def test_bounded_context_and_cited_reference(self):
        result = groq_reference_context('who owns blocked task', max_chars=2300)
        self.assertLessEqual(len(result['text']), 2300)
        self.assertIn('PostgreSQL remains authoritative', result['text'])
        self.assertTrue(result['citations'])
        self.assertIn('SORYU Atlas p.', result['text'])
        self.assertTrue(all(1 <= c['page'] <= 24 for c in result['citations']))

    def test_isolation_from_database_and_production_retrieval(self):
        # This standalone class takes only JSON. It has no DB credentials,
        # SQL queries, pgvector migrations or external network requirements.
        module = Path(__import__('backend.intelligence.atlas_retrieval', fromlist=['x']).__file__).read_text(encoding='utf-8')
        self.assertNotIn('psycopg', module)
        self.assertNotIn('load_read_snapshot', module)
        self.assertNotIn('SupabaseClient', module)

    def test_unrelated_query_no_fabricated_context(self):
        self.assertEqual(self.atlas.search('zzzzzzzzzz foobarxyz987'), [])
        self.assertEqual(self.atlas.groq_context('zzzzzzzzzz foobarxyz987')['citations'], [])


if __name__ == '__main__':
    unittest.main()

class AtlasRouteTests(unittest.TestCase):
    def test_route_requires_existing_auth_and_never_uses_public_access(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from backend.routers.atlas import router
        app = FastAPI()
        app.include_router(router)
        with TestClient(app) as client:
            response = client.get('/api/intelligence/atlas/search?q=engineering%20workload')
        self.assertEqual(response.status_code, 401)

    def test_authenticated_route_and_input_limits(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from backend.auth import current_user
        from backend.routers.atlas import router
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[current_user] = lambda: object()  # mock the auth gate; no live credentials
        with TestClient(app) as client:
            result = client.get('/api/intelligence/atlas/search?q=engineering%20workload')
            bad = client.get('/api/intelligence/atlas/search?q=a&limit=999')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.headers.get('cache-control'), 'private, no-store')
        self.assertEqual(result.json()['items'][0]['page'], 21)
        self.assertEqual(bad.status_code, 422)
