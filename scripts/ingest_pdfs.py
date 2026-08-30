import asyncio
import os
import uuid
import json
import glob
from pypdf import PdfReader
from google import genai
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

# We will use the Google GenAI SDK to auto-classify the PDFs and embed them!
api_key = os.environ.get("GOOGLE_API_KEY")
client = genai.Client(api_key=api_key)

async def auto_classify_pdf(first_page_text: str) -> dict:
    """Uses Gemini to read the title page and figure out which company this is."""
    prompt = f"""
    Analyze the first page of this Indian financial document.
    Extract the following details as a strict JSON object:
    - "company": Full name of the company (e.g., "Tata Motors Limited"). If not found, use "Unknown".
    - "ticker": The BSE/NSE ticker symbol (e.g., "TATAMOTORS"). If not found, guess based on company name.
    - "fiscal_year": The primary year this report covers as an integer (e.g., 2024).
    - "doc_type": Either "Annual Report", "Concall Transcript", or "SEBI Disclosure".
    
    TEXT:
    {first_page_text[:3000]}
    """
    
    resp = await asyncio.to_thread(
        client.models.generate_content,
        model="gemini-3.6-flash",
        contents=prompt,
        config={"response_mime_type": "application/json"}
    )
    
    try:
        clean_text = resp.text.strip().strip('```json').strip('```').strip()
        return json.loads(clean_text)
    except Exception as e:
        print(f"Warning: Auto-classification failed ({e}). Defaulting to Unknown.")
        return {"company": "Unknown", "ticker": "UNKNOWN", "fiscal_year": 2024, "doc_type": "Unknown Document"}

async def embed_text_with_retry(txt: str, max_retries=5) -> str:
    """Helper to embed text with exponential backoff for rate limits."""
    for attempt in range(max_retries):
        try:
            emb = await asyncio.to_thread(
                client.models.embed_content,
                model="gemini-embedding-001",
                contents=txt,
            )
            return "[" + ",".join(str(x) for x in emb.embeddings[0].values[:768]) + "]"
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                wait_time = (attempt + 1) * 5
                print(f"     [Rate Limit Hit] Waiting {wait_time} seconds before retrying...")
                await asyncio.sleep(wait_time)
            else:
                raise e
    raise Exception("Max retries exceeded for embedding.")

async def ingest_pdfs():
    from db.session import get_isolated_engine
    engine = get_isolated_engine()
    
    pdf_files = glob.glob("data/*.pdf")
    if not pdf_files:
        print("No PDF files found in the 'data/' directory.")
        return

    print(f"Found {len(pdf_files)} PDFs in the data folder.")
    
    async with engine.begin() as conn:
        for pdf_path in pdf_files:
            print(f"\n======================================")
            print(f"Processing: {pdf_path}")
            
            try:
                reader = PdfReader(pdf_path)
                total_pages = len(reader.pages)
                print(f"Total Pages: {total_pages}")
                
                # Step 1: Extract first page for Auto-Classification
                first_page_text = reader.pages[0].extract_text()
                print("Asking Gemini to classify the document...")
                metadata = await auto_classify_pdf(first_page_text)
                
                c = metadata.get('company', 'Unknown')
                t = metadata.get('ticker', 'UNKNOWN')
                fy = int(metadata.get('fiscal_year', 2024))
                dt = metadata.get('doc_type', 'Document')
                print(f"Identified -> Company: {c}, Ticker: {t}, Year: {fy}, Type: {dt}")
                
                # Step 2: Read pages and chunk them (1 page per chunk to avoid token limits)
                print("Chunking and Embedding text (this will take time due to rate limits)...")
                
                for i, page in enumerate(reader.pages):
                    page_text = page.extract_text()
                    if not page_text or len(page_text.strip()) < 50:
                        continue # Skip empty pages
                        
                    # Hard cap at 9000 chars per page to guarantee we stay under the embedding token limit
                    safe_chunk = page_text[:9000]
                    
                    try:
                        emb_vector = await embed_text_with_retry(safe_chunk)
                        
                        meta_json = json.dumps({"source_file": os.path.basename(pdf_path), "page": i+1})
                        
                        await conn.execute(text("""
                            INSERT INTO annual_report_chunks 
                            (id, company, ticker, fiscal_year, doc_type, chunk_type, content, embedding, metadata_json)
                            VALUES (:id, :c, :t, :fy, :dt, 'text', :cnt, CAST(:emb AS vector(768)), :meta)
                        """), {
                            "id": str(uuid.uuid4()), "c": c, "t": t, "fy": fy, "dt": dt,
                            "cnt": safe_chunk, "emb": emb_vector, "meta": meta_json
                        })
                        print(f"  -> Inserted Page {i+1} successfully.")
                        
                        # Aggressive sleep to respect Google Free Tier (15 Requests Per Minute)
                        await asyncio.sleep(4.1)
                        
                    except Exception as e:
                        print(f"  -> Failed to insert Page {i+1}: {e}")

            except Exception as e:
                print(f"Failed to read PDF {pdf_path}. Error: {e}")

    await engine.dispose()
    print("\n✅ All PDFs have been successfully embedded into the vector database!")

if __name__ == "__main__":
    asyncio.run(ingest_pdfs())
