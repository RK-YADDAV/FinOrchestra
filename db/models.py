"""SQLAlchemy ORM models for FinOrchestra India.

These models mirror the PostgreSQL DDL schema.
For Supabase: run the DDL in the SQL Editor to create tables,
then use these models for ORM-based access.
"""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text, DateTime, ForeignKey,
    Index, CheckConstraint, UniqueConstraint, func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector


class Base(DeclarativeBase):
    pass


class Job(Base):
    __tablename__ = "jobs"

    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    company: Mapped[Optional[str]] = mapped_column(String(100))
    ticker: Mapped[Optional[str]] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    model_used: Mapped[str] = mapped_column(String(50), default="gemini-2.5-flash")

    # Relationships
    events: Mapped[List["ExecutionEvent"]] = relationship(back_populates="job", cascade="all, delete-orphan")
    tool_calls: Mapped[List["ToolCall"]] = relationship(back_populates="job", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("status IN ('running', 'done', 'failed')", name="ck_jobs_status"),
        Index("idx_jobs_status", "status"),
        Index("idx_jobs_created", "created_at"),
    )


class ExecutionEvent(Base):
    __tablename__ = "execution_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.job_id", ondelete="CASCADE"), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    agent: Mapped[str] = mapped_column(String(50), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    prompt_sent: Mapped[Optional[str]] = mapped_column(Text)
    output_received: Mapped[Optional[str]] = mapped_column(Text)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    job: Mapped["Job"] = relationship(back_populates="events")

    __table_args__ = (
        Index("idx_events_job", "job_id"),
    )


class ToolCall(Base):
    __tablename__ = "tool_calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.job_id", ondelete="CASCADE"), nullable=False)
    agent_id: Mapped[str] = mapped_column(String(50), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(50), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    input_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    output_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    numerical_output: Mapped[Optional[float]] = mapped_column(Float)
    latency_ms: Mapped[Optional[float]] = mapped_column(Float)
    accepted: Mapped[Optional[bool]] = mapped_column(Boolean)
    error_code: Mapped[Optional[str]] = mapped_column(String(50))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    job: Mapped["Job"] = relationship(back_populates="tool_calls")

    __table_args__ = (
        CheckConstraint("attempt_number BETWEEN 1 AND 3", name="ck_tool_calls_attempt"),
        Index("idx_tool_calls_job", "job_id"),
        Index("idx_tool_calls_input_gin", "input_json", postgresql_using="gin"),
    )


class AnnualReportChunk(Base):
    __tablename__ = "annual_report_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("annual_report_chunks.id", ondelete="CASCADE"), nullable=True)
    company: Mapped[str] = mapped_column(String(100), nullable=False)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    doc_type: Mapped[str] = mapped_column(String(50), nullable=False)
    chunk_type: Mapped[str] = mapped_column(String(20), nullable=False, default="text") # 'text', 'table', 'table_row', 'image_summary', 'chart_summary'
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    embedding = mapped_column(Vector(384), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Parent-child relationships
    parent: Mapped[Optional["AnnualReportChunk"]] = relationship("AnnualReportChunk", remote_side=[id], back_populates="children")
    children: Mapped[List["AnnualReportChunk"]] = relationship("AnnualReportChunk", back_populates="parent", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_report_chunks_ticker", "ticker", "fiscal_year"),
        Index("idx_report_chunks_parent", "parent_id"),
        Index("idx_report_chunks_type", "chunk_type"),
        # HNSW index created via DDL: idx_report_chunks_hnsw
    )

class KnowledgeNode(Base):
    """Graph RAG: Represents an entity (Company, Director, Subsidiary, Auditor, etc.)"""
    __tablename__ = "knowledge_nodes"

    id: Mapped[str] = mapped_column(String(255), primary_key=True) # e.g. "TATA_MOTORS", "N_CHANDRASEKARAN"
    node_type: Mapped[str] = mapped_column(String(50), nullable=False) # 'COMPANY', 'PERSON', 'METRIC', 'SUBSIDIARY'
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    properties: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB) # extra info
    embedding = mapped_column(Vector(384), nullable=True) # Optional vector representation of the entity

    # Relationships
    outgoing_edges: Mapped[List["KnowledgeEdge"]] = relationship("KnowledgeEdge", foreign_keys="[KnowledgeEdge.source_id]", back_populates="source_node", cascade="all, delete-orphan")
    incoming_edges: Mapped[List["KnowledgeEdge"]] = relationship("KnowledgeEdge", foreign_keys="[KnowledgeEdge.target_id]", back_populates="target_node", cascade="all, delete-orphan")

class KnowledgeEdge(Base):
    """Graph RAG: Represents a relationship between two entities"""
    __tablename__ = "knowledge_edges"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[str] = mapped_column(String(255), ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), nullable=False)
    target_id: Mapped[str] = mapped_column(String(255), ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), nullable=False)
    relation_type: Mapped[str] = mapped_column(String(100), nullable=False) # 'IS_DIRECTOR_OF', 'OWNS_SUBSIDIARY', 'AUDITED_BY', 'HAS_METRIC'
    description: Mapped[Optional[str]] = mapped_column(Text) # e.g., "Holds 45% stake"

    source_node: Mapped["KnowledgeNode"] = relationship("KnowledgeNode", foreign_keys=[source_id], back_populates="outgoing_edges")
    target_node: Mapped["KnowledgeNode"] = relationship("KnowledgeNode", foreign_keys=[target_id], back_populates="incoming_edges")

    __table_args__ = (
        Index("idx_graph_edges_source", "source_id"),
        Index("idx_graph_edges_target", "target_id"),
        Index("idx_graph_edges_relation", "relation_type"),
    )


class EvalResult(Base):
    __tablename__ = "eval_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    test_case_id: Mapped[str] = mapped_column(String(20), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    math_accuracy: Mapped[Optional[float]] = mapped_column(Float)
    citation_accuracy: Mapped[Optional[float]] = mapped_column(Float)
    premise_rejection: Mapped[Optional[float]] = mapped_column(Float)
    tool_efficiency: Mapped[Optional[float]] = mapped_column(Float)
    # composite_score is GENERATED ALWAYS in DDL — read-only from ORM
    composite_score: Mapped[Optional[float]] = mapped_column(Float, server_default=None)
    justifications: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    final_memo: Mapped[Optional[str]] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("run_id", "test_case_id", name="uq_eval_run_case"),
    )
