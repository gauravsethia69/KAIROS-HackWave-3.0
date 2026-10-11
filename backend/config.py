import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name('.env'))


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv('DATABASE_URL', '')
    supabase_url: str = os.getenv('SUPABASE_URL', '').rstrip('/')
    supabase_key: str = os.getenv('SUPABASE_PUBLISHABLE_KEY', '')
    ai_key: str = os.getenv('AI_API_KEY', '')
    ai_base_url: str = os.getenv('AI_BASE_URL', '').rstrip('/')
    ai_model: str = os.getenv('AI_MODEL', '')
    frontend_origin: str = os.getenv('FRONTEND_ORIGIN', 'http://localhost:5173,http://127.0.0.1:5173')

    @property
    def origins(self) -> list[str]:
        origins = [o.strip().rstrip('/') for o in self.frontend_origin.split(',') if o.strip()]
        for origin in origins:
            parsed = urlparse(origin)
            if parsed.scheme not in ('https', 'http') or not parsed.netloc or parsed.path or '*' in origin:
                raise ValueError('FRONTEND_ORIGIN must contain exact HTTP(S) origins')
        return origins


settings = Settings()
