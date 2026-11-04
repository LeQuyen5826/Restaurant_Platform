from alembic import context
from sqlalchemy import create_engine

from app.config import settings

def run() -> None:
    engine = create_engine(settings.database_url)
    with engine.connect() as conn:
        context.configure(connection=conn, target_metadata=None)
        with context.begin_transaction():
            context.run_migrations()
        conn.commit()

run()
