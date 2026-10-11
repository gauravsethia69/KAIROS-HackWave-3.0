from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from .config import settings
from .database import get_pool
from .intelligence.gateway import invalidate_snapshots
from .routers.api import router
from .routers.intelligence import router as intelligence_router
from .routers.scheduling import router as scheduling_router
from .routers.atlas import router as atlas_router
from .routers.company_guide import router as company_guide_router  # Pass 12C
from .routers.general_advice import router as general_advice_router  # Pass 12E


@asynccontextmanager
async def lifespan(_app):
    yield
    invalidate_snapshots()
    if get_pool.cache_info().currsize:
        get_pool().close()
        get_pool.cache_clear()


app = FastAPI(title='KAIROS API', version='0.2.0', lifespan=lifespan)


class BodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['method'] not in ('POST', 'PUT', 'PATCH'):
            return await self.app(scope, receive, send)
        chunks, size = [], 0
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            body = message.get('body', b'')
            size += len(body)
            if size > 24000:
                return await JSONResponse({'detail': 'Request body too large'}, status_code=413)(scope, receive, send)
            chunks.append(body)
            if not message.get('more_body', False):
                break
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {'type': 'http.request', 'body': b''.join(chunks), 'more_body': False}
            return await receive()
        await self.app(scope, replay, send)


app.add_middleware(BodyLimit)
app.add_middleware(CORSMiddleware, allow_origins=settings.origins, allow_methods=['GET', 'POST'], allow_headers=['Authorization', 'Content-Type'], allow_credentials=False)
app.include_router(router)
app.include_router(intelligence_router)
app.include_router(scheduling_router)
app.include_router(atlas_router)
app.include_router(company_guide_router)
app.include_router(general_advice_router)


@app.get('/health')
def health() -> dict[str, str]:
    # Liveness only: deliberately does not claim the database/provider was reached.
    return {'status': 'ok', 'service': 'kairos-api'}
