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
        # agent_attempts
        res_a = sync_conn.execute(text("PRAGMA table_info(agent_attempts)")).fetchall()
        cols_a = [r[1] for r in res_a]
        if cols_a:
            for col, ddl in [
                ("source", "ALTER TABLE agent_attempts ADD COLUMN source VARCHAR(20) DEFAULT 'llm'"),
                ("model_name", "ALTER TABLE agent_attempts ADD COLUMN model_name VARCHAR(100)"),
                ("tokens_used", "ALTER TABLE agent_attempts ADD COLUMN tokens_used INTEGER DEFAULT 0"),
                ("latency_sec", "ALTER TABLE agent_attempts ADD COLUMN latency_sec FLOAT DEFAULT 0.0"),
            ]:
                if col not in cols_a:
                    sync_conn.execute(text(ddl))

        # diagnosis_records
        res_d = sync_conn.execute(text("PRAGMA table_info(diagnosis_records)")).fetchall()
        cols_d = [r[1] for r in res_d]
        if cols_d:
            for col, ddl in [
                ("source", "ALTER TABLE diagnosis_records ADD COLUMN source VARCHAR(20) DEFAULT 'llm'"),
                ("model_name", "ALTER TABLE diagnosis_records ADD COLUMN model_name VARCHAR(100)"),
                ("tokens_used", "ALTER TABLE diagnosis_records ADD COLUMN tokens_used INTEGER DEFAULT 0"),
                ("latency_sec", "ALTER TABLE diagnosis_records ADD COLUMN latency_sec FLOAT DEFAULT 0.0"),
            ]:
                if col not in cols_d:
                    sync_conn.execute(text(ddl))
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
