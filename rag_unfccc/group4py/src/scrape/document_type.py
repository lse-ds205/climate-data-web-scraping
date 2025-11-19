"""
Document Type Inference

Helper functions to infer document_type from URL, title, or file path.
This is a KEY METADATA field used for filtering in the prompt system.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Standardized document types (matches document_types table)
STANDARD_DOCUMENT_TYPES = {
    # ASCOR project types
    'NDC': ['ndc', 'nationally determined contribution'],
    'BTR': ['btr', 'biennial transparency report', 'biennial report'],
    'LTS': ['lts', 'long-term strategy', 'long term strategy', 'long-term low emissions'],
    'Law': ['law', 'legislation', 'act', 'statute'],
    'Policy': ['policy', 'strategy', 'plan', 'framework'],
    
    # Banking/Company project types
    'Sustainability Report': ['sustainability report', 'sustainability', 'sustainability disclosure'],
    'Annual Report': ['annual report', 'annual', 'yearly report'],
    'Climate Report': ['climate report', 'climate disclosure', 'climate risk'],
    'TCFD Report': ['tcfd', 'task force on climate-related financial disclosures'],
    'CDP Response': ['cdp', 'carbon disclosure project'],
    'ESG Report': ['esg', 'environmental social governance'],
}


def infer_document_type_from_url(url: str) -> Optional[str]:
    """
    Infer document type from URL.
    
    Args:
        url: Document URL
        
    Returns:
        Standardized document type or None
    """
    if not url:
        return None
    
    url_lower = url.lower()
    
    # Check for each document type
    for doc_type, keywords in STANDARD_DOCUMENT_TYPES.items():
        for keyword in keywords:
            if keyword in url_lower:
                logger.debug(f"Inferred document_type '{doc_type}' from URL: {url[:50]}...")
                return doc_type
    
    return None


def infer_document_type_from_title(title: str) -> Optional[str]:
    """
    Infer document type from title.
    
    Args:
        title: Document title
        
    Returns:
        Standardized document type or None
    """
    if not title:
        return None
    
    title_lower = title.lower()
    
    # Check for each document type
    for doc_type, keywords in STANDARD_DOCUMENT_TYPES.items():
        for keyword in keywords:
            if keyword in title_lower:
                logger.debug(f"Inferred document_type '{doc_type}' from title: {title[:50]}...")
                return doc_type
    
    return None


def infer_document_type_from_path(file_path: str) -> Optional[str]:
    """
    Infer document type from file path.
    
    Args:
        file_path: Path to document file
        
    Returns:
        Standardized document type or None
    """
    if not file_path:
        return None
    
    from pathlib import Path
    path_obj = Path(file_path)
    file_name = path_obj.stem.lower()  # Get filename without extension
    
    # Check for each document type
    for doc_type, keywords in STANDARD_DOCUMENT_TYPES.items():
        for keyword in keywords:
            if keyword in file_name:
                logger.debug(f"Inferred document_type '{doc_type}' from path: {file_path}")
                return doc_type
    
    return None


def infer_document_type(url: Optional[str] = None, 
                       title: Optional[str] = None, 
                       file_path: Optional[str] = None) -> Optional[str]:
    """
    Infer document type from URL, title, or file path (in that order of priority).
    
    Args:
        url: Document URL
        title: Document title
        file_path: Path to document file
        
    Returns:
        Standardized document type or None if cannot be inferred
    """
    # Try URL first (most reliable for scraped documents)
    if url:
        doc_type = infer_document_type_from_url(url)
        if doc_type:
            return doc_type
    
    # Try title second
    if title:
        doc_type = infer_document_type_from_title(title)
        if doc_type:
            return doc_type
    
    # Try file path last (for locally processed files)
    if file_path:
        doc_type = infer_document_type_from_path(file_path)
        if doc_type:
            return doc_type
    
    logger.warning(f"Could not infer document_type from url={url}, title={title}, file_path={file_path}")
    return None

