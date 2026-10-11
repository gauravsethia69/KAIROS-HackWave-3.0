"""Opaque employee-bound, expiring request context. No DB writes or shared fallback."""
import secrets
import time
from threading import Lock
from fastapi import HTTPException


class ContextStore:
    def __init__(self, ttl=900, maximum=500, clock=time.monotonic):
        self.ttl, self.maximum, self.clock = ttl, maximum, clock
        self.items, self.lock = {}, Lock()

    def _prune(self):
        now = self.clock()
        for token in [key for key, (_, _, deadline, _) in self.items.items() if deadline <= now]:
            del self.items[token]

    def get(self, token, user):
        if not token:
            return None
        with self.lock:
            self._prune()
            item = self.items.get(token)
            if not item or item[:2] != (str(user.id), user.employee_id):
                raise HTTPException(404, 'Workspace context unavailable; start a new request')
            return item[3].model_copy(deep=True)

    def put(self, intent, user):
        with self.lock:
            self._prune()
            if len(self.items) >= self.maximum:
                del self.items[next(iter(self.items))]
            token = secrets.token_urlsafe(24)
            self.items[token] = (str(user.id), user.employee_id, self.clock() + self.ttl, intent.model_copy(deep=True))
            return token


contexts = ContextStore()
