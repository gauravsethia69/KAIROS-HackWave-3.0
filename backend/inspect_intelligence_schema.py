"""Read-only schema inspection; never emits credentials or employee records."""
import json
import logging
import sys
import psycopg
from .config import settings

TABLES = ['employees', 'employee_access', 'departments', 'clients', 'products', 'projects', 'tasks', 'issues', 'meetings', 'meeting_participants', 'communications', 'product_usage', 'contracts', 'client_products', 'employee_schedule_blocks', 'activity_events']

def inspect():
    logging.getLogger('psycopg').setLevel(logging.CRITICAL)
    try:
        with psycopg.connect(settings.database_url, connect_timeout=8) as connection:
            connection.execute('SET TRANSACTION READ ONLY')
            connection.execute("SET LOCAL statement_timeout = '8000ms'")
            rows = connection.execute('SELECT table_name,column_name,data_type FROM information_schema.columns WHERE table_schema = %s AND table_name = ANY(%s) ORDER BY table_name,ordinal_position', ('public', TABLES)).fetchall()
            fks = connection.execute("SELECT conrelid::regclass::text, pg_get_constraintdef(oid) FROM pg_constraint WHERE contype = 'f' AND connamespace = 'public'::regnamespace ORDER BY conrelid::regclass::text").fetchall()
            if '--catalog' in sys.argv:
                products = connection.execute('SELECT id,name,category,description,lifecycle FROM public.products ORDER BY id').fetchall()
                grants = connection.execute("SELECT c.relname,has_table_privilege('authenticated',c.oid,'SELECT'),c.relrowsecurity FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relname=ANY(%s) ORDER BY c.relname", (TABLES,)).fetchall()
                print(json.dumps({'products': products, 'authenticated_select_and_rls': grants}, indent=2))
            else:
                print(json.dumps({'columns': rows, 'foreign_keys': fks}, indent=2))
    except Exception:
        print('Schema inspection unavailable; no connection details emitted.')
        raise SystemExit(1) from None

if __name__ == '__main__':
    inspect()
