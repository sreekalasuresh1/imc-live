import hashlib
import secrets
import time
from datetime import timedelta
from fastapi import Depends, HTTPException, Request
from pwdlib import PasswordHash
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
from .db import get_db
from .models import AuthSession, LoginAttempt, User, now
from .security_models import SecurityRate
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as pg_insert

passwords = PasswordHash.recommended()
DUMMY_HASH = passwords.hash(secrets.token_urlsafe(32))
COOKIE = 'classroom_session'


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()

def valid_csrf(value,expected):
    return isinstance(value,str) and value.isascii() and secrets.compare_digest(value,expected)


def verify_password(raw, hashed):
    return passwords.verify(raw, hashed)


def rate_limit(db: Session, key: str, limit: int = 10):
    """Atomic fixed 15-minute buckets shared by all server workers."""
    bucket=int(time.time())//900
    insert=pg_insert if db.bind.dialect.name=='postgresql' else sqlite_insert
    statement=insert(SecurityRate).values(key=digest(str(bucket)+':'+key),bucket=bucket,attempts=1)
    count=db.scalar(statement.on_conflict_do_update(index_elements=['key'],set_={'attempts':SecurityRate.attempts+1}).returning(SecurityRate.attempts))
    db.execute(delete(SecurityRate).where(SecurityRate.bucket<bucket-1))
    db.commit()
    if count>limit:
        raise HTTPException(429, 'Too many attempts. Try again later.',headers={'Retry-After':str(max(1,900-int(time.time())%900))})


def authenticated(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE)
    session = db.scalar(select(AuthSession).where(AuthSession.token_hash == digest(token or ''), AuthSession.expires_at > now()))
    user = db.get(User, session.user_id) if session else None
    if not user or not user.active:
        raise HTTPException(401, 'Please sign in to continue')
    if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
        if not valid_csrf(request.headers.get('X-CSRF-Token', ''), session.csrf_token):
            raise HTTPException(403, 'Invalid security token. Refresh and try again.')
    request.state.session = session
    return user


def teacher(user: User = Depends(authenticated)) -> User:
    if user.role != 'TEACHER':
        raise HTTPException(403, 'Teacher access required')
    return user


def public_user(user: User):
    return {'id': user.id, 'name': user.name, 'username': user.username, 'role': user.role}
