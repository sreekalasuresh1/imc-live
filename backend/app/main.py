import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy import text
from .config import settings
from .db import engine
from .routes import auth, classrooms, documents, join, live, homework, corrections, parents, batches
from .body_limit import BodyLimit
from .http_security import SecurityBoundary

app = FastAPI(title=settings.app_name, version='0.1.0', docs_url='/api/docs' if settings.environment != 'production' else None, redoc_url=None, openapi_url='/api/openapi.json' if settings.environment != 'production' else None)
app.add_middleware(CORSMiddleware, allow_origins=settings.origins, allow_credentials=True, allow_methods=['GET', 'POST', 'PUT', 'OPTIONS'], allow_headers=['Content-Type', 'X-CSRF-Token'])
app.add_middleware(BodyLimit)
app.add_middleware(SecurityBoundary)


@app.exception_handler(RequestValidationError)
async def invalid_request(request:Request,error:RequestValidationError):
    # Pydantic's default errors include submitted values, including passwords/codes.
    return JSONResponse({'detail':'Invalid request. Check the supplied fields and try again.'},status_code=422)


@app.get('/api/health')
def health():
    try:
        with engine.connect() as connection:
            connection.execute(text('SELECT 1'))
    except Exception:
        logging.getLogger(__name__).exception('Database health check failed')
        return JSONResponse({'status': 'unavailable'}, status_code=503)
    return {'status': 'ok'}


@app.get('/api/config')
def config():
    return {'app_name': settings.app_name, 'phase': 17}


app.include_router(auth.router, prefix='/api')
app.include_router(classrooms.router, prefix='/api')
app.include_router(documents.router, prefix='/api')
app.include_router(join.router, prefix='/api')
app.include_router(live.router, prefix='/api')
app.include_router(homework.router, prefix='/api')
app.include_router(corrections.router, prefix='/api')
app.include_router(parents.router, prefix='/api')
app.include_router(batches.router, prefix='/api')


@app.get("/create-first-teacher")
def create_first_teacher():
    from .db import SessionLocal
    from sqlalchemy import text
    import traceback
    try:
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        hashed = pwd_context.hash("Teacher@123")
        db = SessionLocal()
        db.execute(text("DELETE FROM users WHERE username='teacher'"))
        db.commit()
        db.execute(text("INSERT INTO users (id, username, name, password_hash, role, active, created_at, updated_at) VALUES (gen_random_uuid(), 'teacher', 'teacher', :h, 'TEACHER', true, now(), now())"), {"h": hashed})
        db.commit()
        db.close()
        return {"success": True, "message": "Created teacher / Teacher@123 - you can login now"}
    except Exception as e:
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}
