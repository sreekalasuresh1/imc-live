from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit
from ipaddress import ip_network
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parents[2] / '.env', extra='ignore')
    app_name: str = 'My Classroom'
    environment: Literal['development','testing','production'] = 'development'
    database_url: str = 'postgresql+psycopg://classroom:classroom_local@localhost:5432/classroom'
    allowed_origins: str = 'http://localhost:5173,http://127.0.0.1:5173'
    cookie_secure: bool = False
    session_hours: int = 12
    storage_path: Path = Path('./storage')
    forwarded_allow_ips: str = '127.0.0.1'

    @property
    def origins(self) -> list[str]:
        return [s.strip() for s in self.allowed_origins.split(',') if s.strip()]

    @model_validator(mode='after')
    def production_safety(self):
        for origin in self.origins:
            url=urlsplit(origin)
            if url.scheme not in ['http','https'] or not url.hostname or url.username or url.password or url.path or url.query or url.fragment or '*' in origin or '\\' in origin or not origin.isascii() or any(c.isspace() for c in origin):
                raise ValueError('ALLOWED_ORIGINS must contain exact HTTP(S) origins without paths, credentials or wildcards')
            _=url.port
        if not 1 <= self.session_hours <= 72:
            raise ValueError('SESSION_HOURS must be between 1 and 72')
        if self.environment == 'production':
            if not self.cookie_secure or not self.database_url.startswith('postgresql'):
                raise ValueError('Production requires PostgreSQL and secure cookies')
            if not self.origins or any(not o.startswith('https://') for o in self.origins):
                raise ValueError('Production requires explicit HTTPS origins')
            database=urlsplit(self.database_url)
            if not database.password or database.password in ['classroom_local','password','changeme']:
                raise ValueError('Production requires a non-default database password')
            proxies = [x.strip() for x in self.forwarded_allow_ips.split(',') if x.strip() and x.strip() != '*']
            if not proxies:
                raise ValueError('Production requires explicit trusted proxy IPs or bounded networks')

    
        


settings = Settings()
