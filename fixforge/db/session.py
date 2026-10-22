from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from core.config import settings
from db.models import Base

is_postgres = "postgresql" in settings.DATABASE_URL
engine_kwargs = {
    "echo": False,
    "future": True,
}

if is_postgres:
    engine_kwargs["pool_size"] = 5
    engine_kwargs["max_overflow"] = 10
    engine_kwargs["pool_pre_ping"] = True

engine = create_async_engine(
    settings.DATABASE_URL,
    **engine_kwargs
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
)

def _migrate_schema(sync_conn):
    Base.metadata.create_all(sync_conn)
    from sqlalchemy import text
    try:
        res = sync_conn.execute(text("PRAGMA table_info(review_sessions)")).fetchall()
        col_names = [r[1] for r in res]
        if col_names:
            if "llm_mode" not in col_names:
                sync_conn.execute(text("ALTER TABLE review_sessions ADD COLUMN llm_mode VARCHAR(20) DEFAULT 'fallback'"))
            if "docker_mode" not in col_names:
                sync_conn.execute(text("ALTER TABLE review_sessions ADD COLUMN docker_mode VARCHAR(20) DEFAULT 'unavailable'"))
    except Exception:
        pass

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(_migrate_schema)

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
