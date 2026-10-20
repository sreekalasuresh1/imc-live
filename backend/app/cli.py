"""Local administration only: no public teacher registration endpoint."""
import argparse
from getpass import getpass
from sqlalchemy import delete, select
from .db import SessionLocal
from .models import AuthSession, TeacherProfile, User
from .schemas import Login
from .security import passwords


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['create-teacher', 'reset-password'])
    parser.add_argument('--username', required=True)
    parser.add_argument('--name')
    args = parser.parse_args()
    username = Login(username=args.username, password='validation').username
    password = getpass('Password (12–128 characters): ')
    if not 12 <= len(password) <= 128 or password != getpass('Confirm password: '):
        raise SystemExit('Passwords must match and contain 12–128 characters')
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == username))
        if args.command == 'create-teacher':
            if user:
                raise SystemExit('Username already exists')
            if not args.name or not 1 <= len(args.name.strip()) <= 120:
                raise SystemExit('--name is required (1–120 characters)')
            user = User(username=username, name=args.name.strip(), password_hash=passwords.hash(password), role='TEACHER')
            db.add(user)
            db.flush()
            db.add(TeacherProfile(user_id=user.id))
        else:
            if not user:
                raise SystemExit('User not found')
            user.password_hash = passwords.hash(password)
            db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
        db.commit()
    print('Account saved.')


if __name__ == '__main__':
    main()
