import json
from contextlib import contextmanager
from uuid import UUID
from functools import lru_cache
from time import perf_counter

from fastapi import HTTPException
from psycopg import Error
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool, PoolTimeout

from .auth import Identity
from .config import settings


@lru_cache
def get_pool() -> ConnectionPool:
    if not settings.database_url:
        raise HTTPException(503, 'PostgreSQL is not configured')
    options = conninfo_to_dict(settings.database_url)
    # SSL may be verify-full with sslrootcert supplied via the URL.
    if options.get('sslmode', 'require') not in ('require', 'verify-ca', 'verify-full'):
        raise HTTPException(503, 'PostgreSQL must use SSL')
    options.setdefault('sslmode', 'require')
    return ConnectionPool(settings.database_url, min_size=0, max_size=5, timeout=8,
                          kwargs={**options, 'connect_timeout': 5, 'prepare_threshold': None, 'row_factory': dict_row})


@contextmanager
def user_connection(user: Identity, *, read_only: bool = False, timings: dict | None = None):
    """Execute authorized queries with transaction-local RLS claims.

    Optional timing metrics contain durations only; never credentials, token
    contents, SQL, identifiers, or user details. No authorization caching.
    """
    try:
        acquire_started = perf_counter()
        pool = get_pool()
        with pool.connection() as connection:
            if timings is not None:
                timings['db_pool_ms'] = round((perf_counter() - acquire_started) * 1000, 2)
            with connection.transaction():
                setup_started = perf_counter()
                if read_only:
                    connection.execute('SET TRANSACTION READ ONLY')
                # Preserve the exact existing authenticated role and RLS claims.
                connection.execute('SET LOCAL ROLE authenticated')
                claims_json = json.dumps({'sub': str(user.id), 'role': 'authenticated'})
                if read_only:
                    # One parameterized statement instead of three remote
                    # round trips; same transaction-local claims and timeout.
                    # SET LOCAL ROLE above is intentionally preserved.
                    connection.execute(
                        "SELECT set_config('request.jwt.claim.sub', %s, true), "
                        "set_config('request.jwt.claims', %s, true), "
                        "set_config('statement_timeout', '8000ms', true)",
                        (str(user.id), claims_json),
                    )
                else:
                    # Preserve original semantics for every write workflow.
                    connection.execute("SELECT set_config('request.jwt.claim.sub', %s, true)", (str(user.id),))
                    connection.execute("SELECT set_config('request.jwt.claims', %s, true)", (claims_json,))
                    connection.execute("SET LOCAL statement_timeout = '8000ms'")
                if timings is not None:
                    timings['db_setup_ms'] = round((perf_counter() - setup_started) * 1000, 2)
                yield connection
    except (Error, PoolTimeout, ValueError):
        raise HTTPException(503, 'PostgreSQL operation unavailable') from None


def lookup_active_employee(auth_user_id: UUID) -> dict[str, str] | None:
    """Trusted membership lookup; None means missing or disabled employee access.

    Must run before SET ROLE authenticated: employee_access has no SELECT grant
    to the authenticated role. Uses only backend DATABASE_URL credentials.
    """
    try:
        with get_pool().connection() as connection, connection.transaction():
            connection.execute("SET LOCAL statement_timeout = '5000ms'")
            row = connection.execute(
                "SELECT employee_id, access_role FROM public.employee_access "
                "WHERE auth_user_id = %s AND account_enabled IS TRUE LIMIT 1",
                (auth_user_id,),
            ).fetchone()
            return None if row is None else {
                'employee_id': row['employee_id'], 'access_role': row['access_role']
            }
    except (Error, PoolTimeout, ValueError):
        # Fail closed on transient DB failure; never expose database details.
        raise HTTPException(503, 'Employee authorization service unavailable') from None
