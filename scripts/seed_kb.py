import asyncio
import os
import uuid
from google import genai
from google.genai import types
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

SEED_INDIAN_DOCUMENTS = [
    # Baseline
    {"company": "Reliance Industries", "ticker": "RELIANCE", "fiscal_year": 2024, "doc_type": "Annual Report", "content": "Reliance Industries consolidated EBITDA for FY24 reached \u20b91,78,677 crore, representing 16.1% YoY growth."},
    {"company": "Tata Consultancy Services", "ticker": "TCS", "fiscal_year": 2024, "doc_type": "Annual Report", "content": "TCS reported FY24 EBIT operating margin of 24.6% with total revenue of \u20b9240,893 crore."},
    {"company": "HDFC Bank", "ticker": "HDFCBANK", "fiscal_year": 2024, "doc_type": "Annual Report", "content": "HDFC Bank post-merger FY24 CASA ratio stood at 38.2% with total balance sheet size exceeding \u20b936 lakh crore."},
    {"company": "Tata Motors", "ticker": "TATAMOTORS", "fiscal_year": 2024, "doc_type": "Annual Report", "content": "Tata Motors reduced net auto debt to \u20b916,000 crore in FY24, with JLR net debt reaching \u00a3700 million."},
    {"company": "ITC Limited", "ticker": "ITC", "fiscal_year": 2024, "doc_type": "Annual Report", "content": "ITC Limited declared a total dividend of \u20b913.75 per share for FY24."},
]

async def seed():
    api_key = os.environ["GOOGLE_API_KEY"]
    client = genai.Client(api_key=api_key)
    from db.session import get_isolated_engine

    engine = get_isolated_engine()
    
    # First, truncate the table to avoid duplication
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE annual_report_chunks;"))

    async with engine.begin() as conn:
        for doc in SEED_INDIAN_DOCUMENTS:
            emb = client.models.embed_content(
                model="gemini-embedding-001",
                contents=doc["content"],
            )
            emb_str = "[" + ",".join(str(x) for x in emb.embeddings[0].values[:768]) + "]"
            await conn.execute(text("""
                INSERT INTO annual_report_chunks (id, company, ticker, fiscal_year, doc_type, content, embedding)
                VALUES (:id, :c, :t, :fy, :dt, :cnt, CAST(:emb AS vector(768)))
            """), {
                "id": str(uuid.uuid4()), "c": doc["company"], "t": doc["ticker"],
                "fy": doc["fiscal_year"], "dt": doc["doc_type"], "cnt": doc["content"], "emb": emb_str
            })
            await asyncio.sleep(0.3)
    
    await engine.dispose()
    print("Indian Knowledge Base Seeding Complete.")

if __name__ == "__main__":
    asyncio.run(seed())
