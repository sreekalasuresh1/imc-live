import secrets
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from ..config import settings
from ..db import get_db
from ..models import AuthSession, User, now
from ..schemas import Login, PasswordChange
from ..security import COOKIE, DUMMY_HASH, authenticated, digest, passwords, public_user, rate_limit, verify_password

router = APIRouter(prefix='/auth', tags=['Authentication'])


@router.post('/login')
def login(body: Login, request: Request, response: Response, db: Session = Depends(get_db)):
    rate_limit(db, 'ip:' + (request.client.host if request.client else 'unknown'), 50)
    rate_limit(db, 'login:' + body.username)
    user = db.scalar(select(User).where(User.username == body.username))
    valid = verify_password(body.password, user.password_hash if user else DUMMY_HASH)
    if not valid or not user or not user.active:
        raise HTTPException(401, 'Username or password is incorrect')
    old = request.cookies.get(COOKIE)
    if old:
        db.execute(delete(AuthSession).where(AuthSession.token_hash == digest(old)))
    db.execute(delete(AuthSession).where(AuthSession.expires_at <= now()))
    token = secrets.token_urlsafe(48)
    session = AuthSession(user_id=user.id, token_hash=digest(token), csrf_token=secrets.token_hex(32), expires_at=now() + timedelta(hours=settings.session_hours))
    db.add(session)
    user.last_login_at = now()
    db.commit()
    response.set_cookie(COOKIE, token, httponly=True, secure=settings.cookie_secure, samesite='lax', max_age=settings.session_hours * 3600, path='/api')
    return {'user': public_user(user), 'csrf_token': session.csrf_token}


@router.get('/me')
def me(request: Request, user: User = Depends(authenticated)):
    return {'user': public_user(user), 'csrf_token': request.state.session.csrf_token}


@router.post('/logout', status_code=204)
def logout(request: Request, response: Response, user: User = Depends(authenticated), db: Session = Depends(get_db)):
    db.delete(request.state.session)
    db.commit()
    response.delete_cookie(COOKIE, path='/api', secure=settings.cookie_secure, httponly=True, samesite='lax')


@router.post('/password', status_code=204)
def change_password(body: PasswordChange, response: Response, user: User = Depends(authenticated), db: Session = Depends(get_db)):
    rate_limit(db, 'password:' + user.id)
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, 'Current password is incorrect')
    user.password_hash = passwords.hash(body.new_password)
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    db.commit()
    response.delete_cookie(COOKIE, path='/api', secure=settings.cookie_secure, httponly=True, samesite='lax')
