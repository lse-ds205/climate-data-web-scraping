"""
This module contains the SQLAlchemy ORM models for the database.
"""

import uuid
from pgvector.sqlalchemy import Vector
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import ARRAY, DOUBLE_PRECISION
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy import (
    Column, 
    Integer, 
    String, 
    Float, 
    DateTime, 
    ForeignKey, 
    Text, 
    CheckConstraint
)
from sqlalchemy.dialects.postgresql import (
    UUID, 
    ARRAY, 
    JSONB
)


Base = declarative_base()


class NDCDocumentORM(Base):
    """SQLAlchemy ORM model for NDC documents"""
    __tablename__ = "documents"
    
    doc_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    country = Column(String, nullable=False, index=True)
    title = Column(String)
    url = Column(String, nullable=True)
    language = Column(String)
    submission_date = Column(DateTime)
    file_path = Column(String)
    file_size = Column(Float)
    scraped_at = Column(DateTime(timezone=True), nullable=True)
    downloaded_at = Column(DateTime(timezone=True))
    processed_at = Column(DateTime(timezone=True))
    last_download_attempt = Column(DateTime(timezone=True))
    download_error = Column(String)
    download_attempts = Column(Integer, default=0)
    extracted_text = Column(Text)
    document_type = Column(String, nullable=True, index=True)  # KEY METADATA: NDC, BTR, LTS, Law, Policy, etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class DocChunkORM(Base):
    """SQLAlchemy ORM model for document chunks"""
    __tablename__ = "doc_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doc_id = Column(UUID(as_uuid=True), ForeignKey("documents.doc_id", ondelete="CASCADE"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    page = Column(Integer)
    paragraph = Column(Integer)
    language = Column(String)
    transformer_embedding = Column(Vector)
    word2vec_embedding = Column(Vector)
    hoprag_embedding = Column(ARRAY(Float))
    content_hash = Column(String(64))
    chunk_data = Column(JSONB, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class LogicalRelationshipORM(Base):
    """SQLAlchemy ORM model for logical relationships between chunks"""
    __tablename__ = "logical_relationships"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_chunk_id = Column(UUID(as_uuid=True), ForeignKey("doc_chunks.id", ondelete="CASCADE"), nullable=False)
    target_chunk_id = Column(UUID(as_uuid=True), ForeignKey("doc_chunks.id", ondelete="CASCADE"), nullable=False)
    relationship_type = Column(String(50), nullable=False)
    confidence = Column(Float, nullable=False)
    evidence = Column(Text)
    method = Column(String(50), default="rule_based")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        CheckConstraint('relationship_type IN (\'SUPPORTS\', \'EXPLAINS\', \'CONTRADICTS\', \'FOLLOWS\', \'TEMPORAL_FOLLOWS\', \'CAUSES\')', name='valid_relationship_types'),
        CheckConstraint('confidence >= 0.0 AND confidence <= 1.0', name='valid_confidence_range'),
        CheckConstraint('source_chunk_id != target_chunk_id', name='no_self_relationships')
    )


def establish_python_level_relationships():
    DocChunkORM.source_relationships = relationship("LogicalRelationshipORM", 
                                                foreign_keys=[LogicalRelationshipORM.source_chunk_id],
                                                backref="source_chunk", 
                                                cascade="all, delete-orphan")

    DocChunkORM.target_relationships = relationship("LogicalRelationshipORM", 
                                                foreign_keys=[LogicalRelationshipORM.target_chunk_id],
                                                backref="target_chunk", 
                                                cascade="all, delete-orphan")