import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables before initializing everything
load_dotenv()

from api.routes import query

app = FastAPI(
    title="FinOrchestra India API",
    description="Multi-agent financial orchestrator for Indian equities",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(query.router)

@app.get("/health")
async def health_check():
    return {"status": "ok"}
