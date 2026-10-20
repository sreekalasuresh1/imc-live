from alembic import context
from app.config import settings
from app.db import Base, engine
from app import models
from app import live_models
from app import homework_models
from app import correction_models
from app import test_models
from app import parent_models
from app import batch_models
from app import security_models

if context.is_offline_mode():
    context.configure(url=settings.database_url, target_metadata=Base.metadata, literal_binds=True, dialect_opts={'paramstyle': 'named'})
    with context.begin_transaction():
        context.run_migrations()
else:
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
