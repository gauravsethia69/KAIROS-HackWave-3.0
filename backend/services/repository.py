from fastapi import HTTPException
from psycopg import sql
from psycopg.types.json import Jsonb

from ..auth import Identity
from ..database import user_connection
from ..schemas import WorkspacePlan

TABLES = {'clients', 'meetings', 'communications', 'product_usage', 'projects', 'tasks', 'issues'}


def records(table: str, user: Identity, client_id: str | None = None):
    if table not in TABLES:
        raise ValueError('Unsupported table')
    # These tables intentionally contain shared fictional records, as in the existing RLS policy.
    query = sql.SQL('SELECT * FROM public.{}').format(sql.Identifier(table))
    params = ()
    if client_id is not None:
        column = 'id' if table == 'clients' else 'client_id'
        query += sql.SQL(' WHERE {} = %s').format(sql.Identifier(column))
        params = (client_id,)
    query += sql.SQL(' ORDER BY id')
    with user_connection(user) as connection:
        return connection.execute(query, params).fetchall()


def client(client_id: str, user: Identity):
    rows = records('clients', user, client_id)
    if not rows:
        raise HTTPException(404, 'Client not found')
    return rows[0]


def sessions(user: Identity):
    with user_connection(user) as connection:
        # Explicit ownership remains in place even if deployment accidentally weakens RLS.
        return connection.execute('SELECT id,title,plan,created_at FROM public.workspace_sessions WHERE user_id = %s ORDER BY created_at DESC LIMIT 10', (user.id,)).fetchall()


def save(plan: WorkspacePlan, user: Identity):
    with user_connection(user) as connection:
        return connection.execute('INSERT INTO public.workspace_sessions (user_id,title,plan) VALUES (%s,%s,%s) RETURNING id,title,plan,created_at', (user.id, plan.title, Jsonb(plan.model_dump(exclude_none=True)))).fetchone()


def claim_ai_request(user: Identity):
    with user_connection(user) as connection:
        return connection.execute('SELECT public.claim_ai_request() AS allowed').fetchone()['allowed']
