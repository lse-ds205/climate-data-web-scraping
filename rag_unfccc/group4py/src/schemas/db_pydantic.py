from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from uuid import UUID


class NDCDocumentModel(BaseModel):
    """Pydantic model for NDC documents with all fields."""
    doc_id: UUID
    country: str
    title: Optional[str] = None
    url: str
    language: Optional[str] = None
    submission_date: Optional[date] = None
    file_path: Optional[str] = None
    file_size: Optional[float] = None
    scraped_at: Optional[datetime] = None
    downloaded_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    last_download_attempt: Optional[datetime] = None
    download_error: Optional[str] = None
    download_attempts: int = 0
    extracted_text: Optional[str] = None
    document_type: Optional[str] = None  # KEY METADATA: NDC, BTR, LTS, Law, Policy, Sustainability Report, etc.
    chunks: Optional[List[Dict[str, Any]]] = None
    created_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()

    class Config:
        from_attributes = True
