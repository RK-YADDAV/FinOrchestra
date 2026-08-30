import asyncio
import os
import uuid
import json
from google import genai
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

async def embed_text(client, txt: str) -> str:
    """Helper to embed text and return pgvector string format."""
    # We use text-embedding-004 as recommended!
    emb = await asyncio.to_thread(
        client.models.embed_content,
        model="text-embedding-004",
        contents=txt,
    )
    return "[" + ",".join(str(x) for x in emb.embeddings[0].values[:768]) + "]"

async def seed():
    api_key = os.environ["GOOGLE_API_KEY"]
    client = genai.Client(api_key=api_key)
    from db.session import get_isolated_engine
    from db.models import Base

    engine = get_isolated_engine()
    
    # Recreate tables to apply the new schema (parent_id, chunk_type, metadata)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        # Create HNSW index for fast vector search
        await conn.execute(text("CREATE INDEX ON annual_report_chunks USING hnsw (embedding vector_cosine_ops);"))

    async with engine.begin() as conn:
        print("Inserting 1: Standard Text Chunk")
        text_id = str(uuid.uuid4())
        emb_text = await embed_text(client, "Tata Motors reported a 20% increase in EV sales for FY24.")
        await conn.execute(text("""
            INSERT INTO annual_report_chunks (id, company, ticker, fiscal_year, doc_type, chunk_type, content, embedding)
            VALUES (:id, 'Tata Motors', 'TATAMOTORS', 2024, 'Annual Report', 'text', :cnt, CAST(:emb AS vector(768)))
        """), {"id": text_id, "cnt": "Tata Motors reported a 20% increase in EV sales for FY24.", "emb": emb_text})

        print("Inserting 2: Parent-Child Table (Balance Sheet)")
        # 1. Create the PARENT Table (Full Markdown)
        parent_id = str(uuid.uuid4())
        parent_markdown = "| Year | Revenue | Debt |\n|------|---------|------|\n| FY24 | 43,000  | 16,000|\n| FY23 | 34,000  | 20,000|"
        emb_parent = await embed_text(client, "Tata Motors Balance Sheet Summary FY24 vs FY23")
        await conn.execute(text("""
            INSERT INTO annual_report_chunks (id, company, ticker, fiscal_year, doc_type, chunk_type, content, embedding)
            VALUES (:id, 'Tata Motors', 'TATAMOTORS', 2024, 'Annual Report', 'table', :cnt, CAST(:emb AS vector(768)))
        """), {"id": parent_id, "cnt": parent_markdown, "emb": emb_parent})

        # 2. Create the CHILD Rows (Highly searchable exact metrics)
        child_rows = [
            "Tata Motors FY24 Revenue was 43,000 Crores. Debt was 16,000 Crores.",
            "Tata Motors FY23 Revenue was 34,000 Crores. Debt was 20,000 Crores."
        ]
        for row in child_rows:
            child_id = str(uuid.uuid4())
import asyncio
import os
import uuid
import json
from google import genai
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

async def embed_text(client, txt: str) -> str:
    """Helper to embed text and return pgvector string format."""
    # Reverting to gemini-embedding-001 as the user's API key does not support text-embedding-004
    emb = await asyncio.to_thread(
        client.models.embed_content,
        model="gemini-embedding-001",
        contents=txt,
    )
    return "[" + ",".join(str(x) for x in emb.embeddings[0].values[:768]) + "]"

async def seed():
    api_key = os.environ["GOOGLE_API_KEY"]
    client = genai.Client(api_key=api_key)
    from db.session import get_isolated_engine
    from db.models import Base

    engine = get_isolated_engine()
    
    # Recreate tables to apply the new schema (parent_id, chunk_type, metadata)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        # Create HNSW index for fast vector search
        await conn.execute(text("CREATE INDEX ON annual_report_chunks USING hnsw (embedding vector_cosine_ops);"))

    async with engine.begin() as conn:
        print("Inserting 1: Standard Text Chunk")
        text_id = str(uuid.uuid4())
        emb_text = await embed_text(client, "Tata Motors reported a 20% increase in EV sales for FY24.")
        await conn.execute(text("""
            INSERT INTO annual_report_chunks (id, company, ticker, fiscal_year, doc_type, chunk_type, content, embedding)
            VALUES (:id, 'Tata Motors', 'TATAMOTORS', 2024, 'Annual Report', 'text', :cnt, CAST(:emb AS vector(768)))
        """), {"id": text_id, "cnt": "Tata Motors reported a 20% increase in EV sales for FY24.", "emb": emb_text})

        print("Inserting 2: Parent-Child Table (Balance Sheet)")
        # 1. Create the PARENT Table (Full Markdown)
        parent_id = str(uuid.uuid4())
        parent_markdown = "| Year | Revenue | Debt |\n|------|---------|------|\n| FY24 | 43,000  | 16,000|\n| FY23 | 34,000  | 20,000|"
        emb_parent = await embed_text(client, "Tata Motors Balance Sheet Summary FY24 vs FY23")
        await conn.execute(text("""
            INSERT INTO annual_report_chunks (id, company, ticker, fiscal_year, doc_type, chunk_type, content, embedding)
            VALUES (:id, 'Tata Motors', 'TATAMOTORS', 2024, 'Annual Report', 'table', :cnt, CAST(:emb AS vector(768)))
        """), {"id": parent_id, "cnt": parent_markdown, "emb": emb_parent})

        # 2. Create the CHILD Rows (Highly searchable exact metrics)
        child_rows = [
            "Tata Motors FY24 Revenue was 43,000 Crores. Debt was 16,000 Crores.",
            "Tata Motors FY23 Revenue was 34,000 Crores. Debt was 20,000 Crores."
        ]
        for row in child_rows:
            child_id = str(uuid.uuid4())
            emb_child = await embed_text(client, row)
            await conn.execute(text("""
                INSERT INTO annual_report_chunks (id, parent_id, company, ticker, fiscal_year, doc_type, chunk_type, content, embedding, metadata_json)
                VALUES (:id, :pid, 'Tata Motors', 'TATAMOTORS', 2024, 'Annual Report', 'table_row', :cnt, CAST(:emb AS vector(768)), :meta)
            """), {"id": child_id, "pid": parent_id, "cnt": row, "emb": emb_child, "meta": json.dumps({"source_table": "Balance Sheet"})})

        print("Inserting 3: Multimodal Image/Chart Summary")
        # Simulating what happens when you pass a chart image to Gemini Vision
        chart_id = str(uuid.uuid4())
        chart_summary = "Image Summary: A bar chart showing Tata Motors quarterly EBITDA margin. Q1 FY24 is 12%, Q2 is 13.5%, Q3 is 14.3%, Q4 is 14.8%. Upward trend driven by JLR."
        emb_chart = await embed_text(client, chart_summary)
        await conn.execute(text("""
            INSERT INTO annual_report_chunks (id, company, ticker, fiscal_year, doc_type, chunk_type, content, embedding, metadata_json)
            VALUES (:id, 'Tata Motors', 'TATAMOTORS', 2024, 'Annual Report', 'chart_summary', :cnt, CAST(:emb AS vector(768)), :meta)
        """), {"id": chart_id, "cnt": chart_summary, "emb": emb_chart, "meta": json.dumps({"image_url": "s3://reports/tata_fy24_chart1.png"})})
        
        print("Inserting 4: Graph RAG Entities (Nodes and Edges)")
        # 1. Insert Nodes (Entities)
        nodes = [
            {"id": "COMP_TATAMOTORS", "type": "COMPANY", "name": "Tata Motors"},
            {"id": "COMP_JLR", "type": "SUBSIDIARY", "name": "Jaguar Land Rover"},
            {"id": "PERSON_CHANDRA", "type": "DIRECTOR", "name": "N Chandrasekaran"}
        ]
        for node in nodes:
            emb_node = await embed_text(client, f"{node['type']} Entity: {node['name']}")
            await conn.execute(text("""
                INSERT INTO knowledge_nodes (id, node_type, name, properties, embedding)
                VALUES (:id, :type, :name, :prop, CAST(:emb AS vector(768)))
            """), {"id": node["id"], "type": node["type"], "name": node["name"], "prop": json.dumps({}), "emb": emb_node})
            
        # 2. Insert Edges (Relationships)
        edges = [
            {"src": "COMP_TATAMOTORS", "tgt": "COMP_JLR", "rel": "OWNS_SUBSIDIARY", "desc": "Tata Motors acquired JLR in 2008"},
            {"src": "PERSON_CHANDRA", "tgt": "COMP_TATAMOTORS", "rel": "IS_CHAIRMAN_OF", "desc": "N Chandrasekaran is the Chairman of Tata Motors"}
        ]
        for edge in edges:
            await conn.execute(text("""
                INSERT INTO knowledge_edges (id, source_id, target_id, relation_type, description)
                VALUES (:id, :src, :tgt, :rel, :desc)
            """), {"id": str(uuid.uuid4()), "src": edge["src"], "tgt": edge["tgt"], "rel": edge["rel"], "desc": edge["desc"]})
            
    await engine.dispose()
    print("Graph RAG & Multimodal Knowledge Base Seeding Complete.")

if __name__ == "__main__":
    asyncio.run(seed())
