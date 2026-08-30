import asyncio
from dotenv import load_dotenv
load_dotenv()
from core.tools import tool_filings_rag
from db.session import get_isolated_engine

async def main():
    engine = get_isolated_engine()
    print("Testing local RAG retrieval across all companies")
    try:
        # Search for "financial highlights and revenue growth" without restricting by ticker
        result = await tool_filings_rag("financial highlights and revenue growth", None, engine, embed_client=None, limit=5)
        print("Success:", result.success)
        if result.success:
            for i, chunk in enumerate(result.data['chunks']):
                print(f"[{i}] {chunk['company']} ({chunk['ticker']}) - Relevance: {chunk['relevance']:.4f}")
                print(f"    Text: {chunk['text'][:200]}...\n")
        else:
            print("Error:", result.error_code, result.error_message)
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
