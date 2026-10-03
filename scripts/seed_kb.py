import asyncio
import os
import uuid
import json
from sentence_transformers import SentenceTransformer
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

async def embed_text(model: SentenceTransformer, txt: str) -> str:
    """Helper to embed text and return pgvector string format."""
    emb = await asyncio.to_thread(model.encode, txt)
    return "[" + ",".join(str(x) for x in emb.tolist()) + "]"

async def seed():
    model = SentenceTransformer('all-MiniLM-L6-v2')
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
        emb_text = await embed_text(model, "Tata Motors reported a 20% increase in EV sales for FY24.")
        await conn.execute(text("""
            INSERT INTO annual_report_chunks (id, company, ticker, fiscal_year, doc_type, chunk_type, content, embedding)
            VALUES (:id, 'Tata Motors', 'TATAMOTORS', 2024, 'Annual Report', 'text', :cnt, CAST(:emb AS vector(384)))
        """), {"id": text_id, "cnt": "Tata Motors reported a 20% increase in EV sales for FY24.", "emb": emb_text})

        print("Inserting 1b: Standard Text Chunk FY25")
        text_id_fy25 = str(uuid.uuid4())
        emb_text_fy25 = await embed_text(model, "Tata Motors reported a 35% increase in EV sales for FY25.")
        await conn.execute(text("""
            INSERT INTO annual_report_chunks (id, company, ticker, fiscal_year, doc_type, chunk_type, content, embedding)
            VALUES (:id, 'Tata Motors', 'TATAMOTORS', 2025, 'Annual Report', 'text', :cnt, CAST(:emb AS vector(384)))
        """), {"id": text_id_fy25, "cnt": "Tata Motors reported a 35% increase in EV sales for FY25.", "emb": emb_text_fy25})

        print("Inserting 2: Parent-Child Table (Balance Sheet)")
        # 1. Create the PARENT Table (Full Markdown)
        parent_id = str(uuid.uuid4())
        parent_markdown = "| Year | Revenue | Debt |\n|------|---------|------|\n| FY25 | 52,000  | 12,000|\n| FY24 | 43,000  | 16,000|\n| FY23 | 34,000  | 20,000|"
        emb_parent = await embed_text(model, "Tata Motors Balance Sheet Summary FY25 vs FY24 vs FY23")
        await conn.execute(text("""
            INSERT INTO annual_report_chunks (id, company, ticker, fiscal_year, doc_type, chunk_type, content, embedding)
            VALUES (:id, 'Tata Motors', 'TATAMOTORS', 2025, 'Annual Report', 'table', :cnt, CAST(:emb AS vector(384)))
        """), {"id": parent_id, "cnt": parent_markdown, "emb": emb_parent})

        # 2. Create the CHILD Rows (Highly searchable exact metrics)
        child_rows = [
            "Tata Motors FY25 Revenue was 52,000 Crores. Debt was 12,000 Crores.",
            "Tata Motors FY24 Revenue was 43,000 Crores. Debt was 16,000 Crores.",
            "Tata Motors FY23 Revenue was 34,000 Crores. Debt was 20,000 Crores."
        ]
        for row in child_rows:
            child_id = str(uuid.uuid4())
            emb_child = await embed_text(model, row)
            await conn.execute(text("""
                INSERT INTO annual_report_chunks (id, parent_id, company, ticker, fiscal_year, doc_type, chunk_type, content, embedding, metadata_json)
                VALUES (:id, :pid, 'Tata Motors', 'TATAMOTORS', 2024, 'Annual Report', 'table_row', :cnt, CAST(:emb AS vector(384)), :meta)
            """), {"id": child_id, "pid": parent_id, "cnt": row, "emb": emb_child, "meta": json.dumps({"source_table": "Balance Sheet"})})

        print("Inserting 3: Multimodal Image/Chart Summary")
        # Simulating what happens when you pass a chart image to Gemini Vision
        chart_id = str(uuid.uuid4())
        chart_summary = "Image Summary: A bar chart showing Tata Motors quarterly EBITDA margin. Q1 FY25 is 15.2%, Q2 is 15.8%, Q3 is 16.1%, Q4 is 16.5%. Q1 FY24 is 12%, Q2 is 13.5%, Q3 is 14.3%, Q4 is 14.8%. Upward trend driven by JLR."
        emb_chart = await embed_text(model, chart_summary)
        await conn.execute(text("""
            INSERT INTO annual_report_chunks (id, company, ticker, fiscal_year, doc_type, chunk_type, content, embedding, metadata_json)
            VALUES (:id, 'Tata Motors', 'TATAMOTORS', 2024, 'Annual Report', 'chart_summary', :cnt, CAST(:emb AS vector(384)), :meta)
        """), {"id": chart_id, "cnt": chart_summary, "emb": emb_chart, "meta": json.dumps({"image_url": "s3://reports/tata_fy25_chart1.png"})})
        
        print("Inserting 4: Graph RAG Entities (Nodes and Edges)")
        # 1. Insert Nodes (Entities)
        nodes = [
            {"id": "COMP_TATAMOTORS", "type": "COMPANY", "name": "Tata Motors"},
            {"id": "COMP_JLR", "type": "SUBSIDIARY", "name": "Jaguar Land Rover"},
            {"id": "PERSON_CHANDRA", "type": "DIRECTOR", "name": "N Chandrasekaran"}
        ]
        for node in nodes:
            emb_node = await embed_text(model, f"{node['type']} Entity: {node['name']}")
            await conn.execute(text("""
                INSERT INTO knowledge_nodes (id, node_type, name, properties, embedding)
                VALUES (:id, :type, :name, :prop, CAST(:emb AS vector(384)))
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
