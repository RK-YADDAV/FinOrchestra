import asyncio
from sqlalchemy import text
from db.session import get_isolated_engine

async def check():
    engine = get_isolated_engine()
    try:
        async with engine.connect() as conn:
            res = await conn.execute(text("SELECT COUNT(*) FROM annual_report_chunks;"))
            count = res.scalar()
            print(f"\n=======================")
            print(f"DATABASE CHECK:")
            print(f"There are currently {count} rows in the vector database.")
            print(f"=======================\n")
            
            if count > 0:
                res2 = await conn.execute(text("SELECT company, ticker, doc_type, chunk_type FROM annual_report_chunks LIMIT 5;"))
                print("First 5 rows:")
                for r in res2.mappings().all():
                    print(dict(r))
    except Exception as e:
        print(f"Database Error: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check())
