import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

# Supabase PostgreSQL connection string (set in .env)
# Format: postgresql+asyncpg://<user>:<password>@<host>:5432/<db>
DATABASE_URL = os.environ["DATABASE_URL"]

# 1. Pooled engine for FastAPI HTTP endpoints (High concurrency, short queries)
# Supabase supports standard connection pooling via its built-in PgBouncer on port 6543,
# but for asyncpg we connect directly on port 5432.
engine = create_async_engine(DATABASE_URL, pool_size=10, max_overflow=20, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


# 2. Isolated NullPool engine for asynchronous vector search and background tasks
# NullPool prevents asyncpg "InterfaceError: another operation is in progress" across asyncio event loops.
def get_isolated_engine(readonly: bool = False):
    url = DATABASE_URL
    if readonly:
        primary_user = os.environ.get("POSTGRES_USER", "postgres")
        readonly_user = os.environ.get("POSTGRES_READONLY_USER")
        if readonly_user:
            url = url.replace(f"://{primary_user}", f"://{readonly_user}")
    return create_async_engine(url, poolclass=NullPool)
