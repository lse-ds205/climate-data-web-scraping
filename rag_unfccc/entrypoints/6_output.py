import json
import sys
import glob
import logging
import argparse
import uuid
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
)
from sqlalchemy import text

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))
import group4py
from helpers.internal import Logger
from constants.styles import (
    FONT_NAME,
    FONT_SIZE_TITLE,
    FONT_SIZE_HEADING,
    FONT_SIZE_BODY,
    COLORS
)
from databases.docker_proxy import get_database_connection

OUTPUT_DIR = project_root / "outputs" / "factsheets"
CSV_OUTPUT_DIR = project_root / "outputs" / "csv"
DATA_DIR = project_root / "data" / "llm"
logger = logging.getLogger(__name__)


def detect_entity_type(entity_name: str) -> str:
    """
    Detect entity type (country, company, bank) from entity name.
    
    Args:
        entity_name: Name of the entity
        
    Returns:
        Entity type folder name: "countries", "companies", "banks"
    """
    try:
        from group4py.src.constants.entities import EntityManager, EntityType
        
        entity_manager = EntityManager()
        
        # Check each entity type
        for entity_type in [EntityType.COUNTRY, EntityType.COMPANY, EntityType.BANK]:
            entities = entity_manager.get_entities_by_type(entity_type)
            if entity_name in entities:
                if entity_type == EntityType.COUNTRY:
                    return "countries"
                elif entity_type == EntityType.COMPANY:
                    return "companies"
                elif entity_type == EntityType.BANK:
                    return "banks"
        
        # Default to countries
        return "countries"
    except Exception as e:
        logger.warning(f"Could not detect entity type for {entity_name}: {e}")
        return "countries"  # Default


def get_question_identifier(question: str, max_length: int = 50) -> str:
    """
    Create a safe identifier from question text for filenames.
    
    Args:
        question: Question text
        max_length: Maximum length of identifier
        
    Returns:
        Safe identifier string
    """
    import re
    
    # Get first line/question
    clean_question = question.split('\n')[0].strip()
    clean_question = re.sub(r'[^\w\s-]', '', clean_question)
    clean_question = re.sub(r'\s+', '_', clean_question)
    
    # Take first few words
    words = clean_question.split('_')[:5]
    identifier = '_'.join(words).lower()
    
    # Truncate if needed
    if len(identifier) > max_length:
        identifier = identifier[:max_length].rstrip('_')
    
    return identifier or "question"


def ensure_output_directory():
    """Create output directory if it doesn't exist."""
    if not OUTPUT_DIR.exists():
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if not CSV_OUTPUT_DIR.exists():
        CSV_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def get_available_llm_files():
    """Get list of all available LLM response JSON files in the data/llm directory."""
    file_pattern = str(DATA_DIR / "*.json")
    return glob.glob(file_pattern)


def load_llm_response_data(json_path):
    """Load and parse LLM response data from the specified JSON file."""
    if not Path(json_path).exists():
        raise FileNotFoundError(f"LLM response file not found: {json_path}")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Extract country name from metadata if available
    country_name = data.get('metadata', {}).get('country_name', 'Unknown')
    
    return country_name, data


def create_pdf_style():
    """Create and return ReportLab styles with enhanced colors."""
    styles = getSampleStyleSheet()
    
    # Add custom styles with colors
    styles.add(ParagraphStyle(
        name='CustomTitle',
        parent=styles['Heading1'],
        fontSize=FONT_SIZE_TITLE,
        spaceAfter=30,
        alignment=1,  # Center alignment
        textColor=COLORS['title'],
        borderWidth=1,
        borderColor=COLORS['border'],
        borderPadding=10,
        backColor=colors.white
    ))
    
    styles.add(ParagraphStyle(
        name='CustomHeading',
        parent=styles['Heading2'],
        fontSize=FONT_SIZE_HEADING,
        spaceAfter=12,
        spaceBefore=20,
        textColor=COLORS['heading'],
        borderWidth=0,
        borderRadius=5,
        borderPadding=6,
        backColor=COLORS['question_bg']
    ))
    
    styles.add(ParagraphStyle(
        name='CustomBody',
        parent=styles['Normal'],
        fontSize=FONT_SIZE_BODY,
        spaceAfter=12,
        textColor=colors.black
    ))
    
    # Add more specific styles
    styles.add(ParagraphStyle(
        name='SummaryStyle',
        parent=styles['CustomBody'],
        backColor=COLORS['summary_bg'],
        borderPadding=10,
        borderRadius=5,
        borderWidth=1,
        borderColor=COLORS['border']
    ))
    
    styles.add(ParagraphStyle(
        name='DetailStyle',
        parent=styles['CustomBody'],
        backColor=COLORS['detail_bg'],
        borderPadding=10,
        borderRadius=5,
        borderWidth=1,
        borderColor=COLORS['border']
    ))
    
    styles.add(ParagraphStyle(
        name='CitationStyle',
        parent=styles['CustomBody'],
        backColor=COLORS['citation_bg'],
        borderPadding=6,
        borderRadius=3,
        borderWidth=1,
        borderColor=COLORS['border'],
        fontSize=FONT_SIZE_BODY-1
    ))
    
    return styles


def create_metadata_table(response_data, styles, country_name):
    """Create a table for metadata information from LLM response with enhanced colors."""
    # Get the first question's data to extract common metadata
    first_question_key = next(iter(response_data.get('questions', {})), None)
    question_data = response_data.get('questions', {}).get(first_question_key, {})
    llm_response = question_data.get('llm_response', {})
    
    # Extract metadata
    citations_count = len(llm_response.get('citations', []))
    
    # Get countries from citations
    countries = set([country_name])  # Include the main country
    for citation in llm_response.get('citations', []):
        if citation.get('country'):
            countries.add(citation['country'])
    
    # Get timestamp from metadata or current time
    timestamp = response_data.get('metadata', {}).get(
        'timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    )
    
    data = [
        ['Country', country_name],
        ['Question Count', str(len(response_data.get('questions', {})))],
        ['Citations Count', str(citations_count)],
        ['Generated', timestamp]
    ]
    
    # Update table styling with colors
    table = Table(data, colWidths=[2*inch, 4*inch])
    table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), FONT_NAME),
        ('FONTSIZE', (0, 0), (-1, -1), FONT_SIZE_BODY),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('BACKGROUND', (0, 0), (0, -1), COLORS['metadata_header']),
        ('BACKGROUND', (1, 0), (1, -1), COLORS['metadata_bg']),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.black),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, COLORS['border']),
        ('ROUNDEDCORNERS', [5, 5, 5, 5]),
    ]))
    return table


def create_answer_section(response_data, styles):
    """Create answer section content from LLM response with enhanced colors."""
    elements = []
    
    # Process each question in the data
    for question_num, question_data in sorted(
            response_data.get('questions', {}).items()):
        llm_response = question_data.get('llm_response', {})
        question_text = llm_response.get('question', f"Question {question_num}")
        
        # Extract question number safely from question_num
        if isinstance(question_num, str):
            # Handle formats like 'question_1' or just '1'
            if '_' in question_num:
                display_num = question_num.split('_')[-1]
            else:
                display_num = question_num
        else:
            display_num = str(question_num)
        
        # Add question heading with background color
        elements.append(Paragraph(
            f"QUESTION {display_num}: {question_text}", 
            styles['CustomHeading']
        ))
        elements.append(Spacer(1, 12))
        
        # Get answer content with error handling for malformed structures
        answer = llm_response.get('answer', {})
        
        try:
            if isinstance(answer, dict):
                # Check if this is a malformed JSON string structure
                summary = answer.get('summary', '')
                detailed = answer.get('detailed_response', '')
                
                # Handle case where summary/detailed contain JSON strings
                if isinstance(summary, str) and summary.startswith('{'):
                    try:
                        summary = json.loads(summary)
                        if isinstance(summary, dict):
                            summary = summary.get('summary', str(summary))
                    except:
                        pass
                
                if isinstance(detailed, str) and detailed.startswith('{'):
                    try:
                        detailed = json.loads(detailed)
                        if isinstance(detailed, dict):
                            detailed = detailed.get('detailed_response', str(detailed))
                    except:
                        pass
                
                # Use summary if available, otherwise detailed
                answer_text = summary if summary else detailed
            else:
                answer_text = str(answer)
            
            # Add summary section
            if answer_text:
                elements.append(Paragraph("Summary:", styles['CustomHeading']))
                elements.append(Paragraph(answer_text, styles['SummaryStyle']))
                elements.append(Spacer(1, 12))
            
            # Add detailed response if different from summary
            if isinstance(answer, dict):
                detailed = answer.get('detailed_response', '')
                if detailed and detailed != answer_text:
                    elements.append(Paragraph("Detailed Response:", styles['CustomHeading']))
                    elements.append(Paragraph(detailed, styles['DetailStyle']))
                    elements.append(Spacer(1, 12))
        
        except Exception as e:
            logger.error(f"Error processing answer: {e}")
            elements.append(Paragraph(f"Error processing answer: {str(e)}", styles['CustomBody']))
        
        # Add citations
        citations = llm_response.get('citations', [])
        if citations:
            elements.append(Paragraph("Citations:", styles['CustomHeading']))
            for i, citation in enumerate(citations, 1):
                cite_text = f"[{i}] {citation.get('content', 'No content')[:200]}..."
                elements.append(Paragraph(cite_text, styles['CitationStyle']))
                elements.append(Spacer(1, 6))
        
        elements.append(Spacer(1, 20))
    
    return elements


def generate_pdf_from_llm_response(response_data, country_name, output_path):
    """Generate a PDF report from LLM response data."""
    try:
        logger.info(f"[6_OUTPUT] Generating PDF for {country_name}...")
        
        # Create PDF document
        doc = SimpleDocTemplate(str(output_path), pagesize=letter)
        elements = []
        
        # Create styles
        styles = create_pdf_style()
        
        # Add title
        elements.append(Paragraph(f"Climate Policy Analysis: {country_name}", styles['CustomTitle']))
        elements.append(Spacer(1, 30))
        
        # Add metadata table
        elements.append(create_metadata_table(response_data, styles, country_name))
        elements.append(Spacer(1, 30))
        
        # Add answer sections
        answer_elements = create_answer_section(response_data, styles)
        elements.extend(answer_elements)
        
        # Build PDF
        doc.build(elements)
        
        logger.info(f"[6_OUTPUT] PDF generated successfully: {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"[6_OUTPUT] Error generating PDF: {e}")
        raise


@Logger.log(log_file=project_root / "logs/output.log", log_level="INFO")
def main():
    """Main function to orchestrate the PDF generation process."""
    try:
        logger.info("[6_OUTPUT] Starting PDF generation from LLM response files...")
        
        # Ensure output directory exists
        ensure_output_directory()
        
        # Get list of all LLM response files
        llm_files = get_available_llm_files()
        
        if not llm_files:
            logger.error(f"[6_OUTPUT] No LLM response files found in {DATA_DIR}")
            return None
        
        logger.info(f"[6_OUTPUT] Found {len(llm_files)} LLM response files")
        
        # Create styles
        styles = create_pdf_style()
        
        # Process each file
        for json_file in llm_files:
            try:
                country_name, response_data = load_llm_response_data(json_file)
                
                # Generate PDF filename
                safe_country = country_name.replace(' ', '_')
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                pdf_filename = f"{safe_country}_factsheet_{timestamp}.pdf"
                pdf_path = OUTPUT_DIR / pdf_filename
                
                # Generate PDF
                generate_pdf_from_llm_response(response_data, country_name, pdf_path)
                
                logger.info(f"[6_OUTPUT] Successfully generated PDF for {country_name}")
                
            except Exception as e:
                logger.error(f"[6_OUTPUT] Error processing {json_file}: {e}")
                continue
        
        logger.info("[6_OUTPUT] PDF generation completed")
        
    except Exception as e:
        logger.error(f"[6_OUTPUT] Fatal error in main: {e}")
        raise


def extract_answer_text(llm_response: Dict[str, Any]) -> str:
    """Extract answer text from LLM response, preferring summary."""
    # Ensure llm_response is a dict
    if not isinstance(llm_response, dict):
        return str(llm_response) if llm_response else "No response"
    
    answer = llm_response.get('answer', {})
    
    if isinstance(answer, dict):
        # Prefer summary, fallback to detailed_response
        summary = answer.get('summary', '')
        detailed = answer.get('detailed_response', '')
        
        # Return summary if available, otherwise detailed
        if summary:
            return summary
        elif detailed:
            return detailed
        else:
            return str(answer)
    else:
        return str(answer)


def get_document_metadata(doc_id: str) -> Dict[str, Optional[str]]:
    """
    Get document metadata (title, URL, file_path, document_type, publication_year) from doc_id.
    CRITICAL: This function must return at least the title for analyst verification.
    
    Args:
        doc_id: Document ID (string or UUID)
        
    Returns:
        Dictionary with 'url', 'file_path', 'title', 'document_type', 'publication_year' keys
    """
    try:
        db = get_database_connection()
        
        # Convert string doc_id to UUID if needed
        if isinstance(doc_id, str):
            try:
                # Try to parse as UUID first
                doc_uuid = uuid.UUID(doc_id)
            except ValueError:
                # If not a valid UUID, convert using deterministic UUID5
                doc_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, doc_id)
        else:
            doc_uuid = doc_id
        
        with db.Session() as session:
            # Query document metadata - include document_type and dates for publication year
            # First, get the primary document record
            result = session.execute(text("""
                SELECT title, url, file_path, country, document_type, submission_date, scraped_at
                FROM documents
                WHERE doc_id = :doc_uuid
                LIMIT 1
            """), {'doc_uuid': str(doc_uuid)})
            
            row = result.fetchone()
            if row and len(row) >= 7:
                # Handle both tuple and Row objects
                try:
                    doc_title = row[0] if row[0] is not None else None
                    doc_url_raw = row[1] if row[1] is not None else None
                    doc_file_path = row[2] if row[2] is not None else None
                    doc_country = row[3] if row[3] is not None else None
                    doc_type = row[4] if row[4] is not None else None
                    submission_date = row[5] if row[5] is not None else None
                    scraped_at = row[6] if row[6] is not None else None
                    
                    # Extract publication year from submission_date (preferred) or scraped_at (fallback)
                    publication_year = None
                    if submission_date:
                        if hasattr(submission_date, 'year'):
                            publication_year = str(submission_date.year)
                        elif isinstance(submission_date, str):
                            # Try to extract year from date string
                            import re
                            year_match = re.search(r'\d{4}', submission_date)
                            if year_match:
                                publication_year = year_match.group(0)
                    elif scraped_at:
                        if hasattr(scraped_at, 'year'):
                            publication_year = str(scraped_at.year)
                        elif isinstance(scraped_at, str):
                            import re
                            year_match = re.search(r'\d{4}', scraped_at)
                            if year_match:
                                publication_year = year_match.group(0)
                    
                    # Clean URL - treat empty strings as None
                    doc_url = doc_url_raw if (doc_url_raw and doc_url_raw.strip()) else None
                    
                    # If URL is missing, try to find a related document with a URL
                    # (Documents might have been created during chunking with empty URL,
                    # but a scraped version with URL might exist for the same country/title)
                    if not doc_url and doc_country:
                        # First try: Find a document with the same country and title that has a URL
                        url_result = session.execute(text("""
                            SELECT url
                            FROM documents
                            WHERE country = :country
                              AND title = :title
                              AND url IS NOT NULL
                              AND url != ''
                              AND doc_id != :doc_uuid
                            LIMIT 1
                        """), {
                            'country': doc_country,
                            'title': doc_title,
                            'doc_uuid': str(doc_uuid)
                        })
                        url_row = url_result.fetchone()
                        if url_row and url_row[0]:
                            doc_url = url_row[0]
                            logger.debug(f"Found URL from related document (title match) for {doc_id}: {doc_url}")
                        else:
                            # Fallback: Find any document with the same country that has a URL
                            # (Title might differ between scraped and chunked versions)
                            url_result = session.execute(text("""
                                SELECT url
                                FROM documents
                                WHERE country = :country
                                  AND url IS NOT NULL
                                  AND url != ''
                                  AND doc_id != :doc_uuid
                                ORDER BY scraped_at DESC NULLS LAST
                                LIMIT 1
                            """), {
                                'country': doc_country,
                                'doc_uuid': str(doc_uuid)
                            })
                            url_row = url_result.fetchone()
                            if url_row and url_row[0]:
                                doc_url = url_row[0]
                                logger.debug(f"Found URL from related document (country match) for {doc_id}: {doc_url}")
                    
                    # Log warning if title is missing (critical field)
                    if not doc_title:
                        logger.warning(f"Document {doc_id} has no title in database")
                    
                    # Log if URL is still missing after lookup
                    if not doc_url:
                        logger.debug(f"Document {doc_id} has no URL in database (url field: '{doc_url_raw}')")
                    
                    return {
                        'title': doc_title,
                        'url': doc_url,
                        'file_path': doc_file_path,
                        'document_type': doc_type,
                        'publication_year': publication_year
                    }
                except (IndexError, TypeError) as e:
                    logger.debug(f"Error accessing row data: {e}, row type: {type(row)}, row: {row}")
                    return {
                        'title': None,
                        'url': None,
                        'file_path': None,
                        'document_type': None,
                        'publication_year': None
                    }
            else:
                # Document not found in database
                logger.warning(f"Document not found in database for doc_id: {doc_id} (UUID: {doc_uuid})")
                return {
                    'title': None,
                    'url': None,
                    'file_path': None,
                    'document_type': None,
                    'publication_year': None
                }
    except Exception as e:
        logger.warning(f"Error getting document metadata for {doc_id}: {e}")
        return {
            'title': None,
            'url': None,
            'file_path': None,
            'document_type': None,
            'publication_year': None
        }


def get_chunk_metadata_from_db(chunk_id: Any, original_chunks: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    Get chunk metadata from database using chunk ID.
    First tries to find in original_chunks (faster), then queries database.
    
    Args:
        chunk_id: Chunk ID (can be int index, str, or UUID)
        original_chunks: Optional list of original chunks from retrieval (for faster lookup)
        
    Returns:
        Dictionary with chunk metadata from database
    """
    # First, try to find in original_chunks if provided (much faster)
    if original_chunks:
        # chunk_id might be an integer index
        if isinstance(chunk_id, int) and 0 <= chunk_id < len(original_chunks):
            chunk = original_chunks[chunk_id]
            # Ensure chunk is a dict
            if not isinstance(chunk, dict):
                return {}
            
            # Safely get chunk_data (might be dict or string)
            chunk_data = chunk.get('chunk_data', {})
            if isinstance(chunk_data, str):
                try:
                    import json
                    chunk_data = json.loads(chunk_data)
                except:
                    chunk_data = {}
            if not isinstance(chunk_data, dict):
                chunk_data = {}
            
            # Extract metadata from original chunk
            # Page number: prefer direct 'page' field, fallback to chunk_data
            page_num = chunk.get('page')
            if page_num is None and chunk_data:
                page_num = chunk_data.get('page_number')
            
            return {
                'chunk_id': str(chunk.get('id', chunk_id)),
                'doc_id': str(chunk.get('doc_id', '')),
                'content': chunk.get('content', ''),
                'chunk_index': chunk.get('chunk_index'),
                'page': page_num,
                'paragraph': chunk.get('paragraph'),
                'language': chunk.get('language'),
                'chunk_data': chunk_data,
                'doc_url': None,  # Will need to query document for this
                'doc_file_path': None,  # Will need to query document for this
                'doc_title': None,  # Will need to query document for this
                'country': chunk_data.get('country') if chunk_data else chunk.get('country')
            }
        # Or try to find by id match
        for chunk in original_chunks:
            # Ensure chunk is a dict
            if not isinstance(chunk, dict):
                continue
                
            if str(chunk.get('id', '')) == str(chunk_id):
                # Safely get chunk_data (might be dict or string)
                chunk_data = chunk.get('chunk_data', {})
                if isinstance(chunk_data, str):
                    try:
                        import json
                        chunk_data = json.loads(chunk_data)
                    except:
                        chunk_data = {}
                if not isinstance(chunk_data, dict):
                    chunk_data = {}
                
                # Page number: prefer direct 'page' field, fallback to chunk_data
                page_num = chunk.get('page')
                if page_num is None and chunk_data:
                    page_num = chunk_data.get('page_number')
                
                return {
                    'chunk_id': str(chunk.get('id', chunk_id)),
                    'doc_id': str(chunk.get('doc_id', '')),
                    'content': chunk.get('content', ''),
                    'chunk_index': chunk.get('chunk_index'),
                    'page': page_num,
                    'paragraph': chunk.get('paragraph'),
                    'language': chunk.get('language'),
                    'chunk_data': chunk_data,
                    'doc_url': None,
                    'doc_file_path': None,
                    'doc_title': None,
                    'country': chunk_data.get('country') if chunk_data else chunk.get('country')
                }
    
    # If not found in original_chunks, query database
    try:
        db = get_database_connection()
        
        # Try to extract UUID from chunk_metadata if chunk_id is an integer
        # The actual UUID might be in chunk_metadata.id
        chunk_uuid = None
        if isinstance(chunk_id, int):
            # This is likely an index, not a UUID - we need the actual UUID
            # Try to find it in original_chunks first
            logger.debug(f"chunk_id is integer {chunk_id}, trying to find UUID in original chunks or citation metadata")
            return {}  # Can't query by index
        else:
            chunk_uuid = str(chunk_id)
        
        with db.Session() as session:
            # Query chunk metadata from database
            result = session.execute(text("""
                SELECT 
                    dc.id,
                    dc.doc_id,
                    dc.content,
                    dc.chunk_index,
                    dc.page,
                    dc.paragraph,
                    dc.language,
                    dc.chunk_data,
                    d.url,
                    d.file_path,
                    d.title,
                    d.country
                FROM doc_chunks dc
                JOIN documents d ON dc.doc_id = d.doc_id
                WHERE dc.id::text = :chunk_id
                LIMIT 1
            """), {'chunk_id': chunk_uuid})
            
            row = result.fetchone()
            if row and len(row) >= 12:
                try:
                    # Safely parse chunk_data (might be JSON string or dict)
                    chunk_data = row[7] if row[7] else {}
                    if isinstance(chunk_data, str):
                        try:
                            import json
                            chunk_data = json.loads(chunk_data)
                        except:
                            chunk_data = {}
                    if not isinstance(chunk_data, dict):
                        chunk_data = {}
                    
                    # Page number is directly in the page column (row[4]), not in chunk_data
                    page_num = row[4] if row[4] is not None else None
                    # Fallback to chunk_data if page column is NULL
                    if page_num is None and chunk_data:
                        page_num = chunk_data.get('page_number')
                    
                    return {
                        'chunk_id': str(row[0]),
                        'doc_id': str(row[1]),
                        'content': row[2] if row[2] else '',
                        'chunk_index': row[3] if row[3] is not None else None,
                        'page': page_num,
                        'paragraph': row[5] if row[5] is not None else None,
                        'language': row[6] if row[6] else None,
                        'chunk_data': chunk_data,
                        'doc_url': row[8] if row[8] else None,
                        'doc_file_path': row[9] if row[9] else None,
                        'doc_title': row[10] if row[10] else None,
                        'country': row[11] if row[11] else (chunk_data.get('country') if chunk_data else None)
                    }
                except (IndexError, TypeError) as e:
                    logger.debug(f"Error accessing chunk row data: {e}")
                    return {}
            else:
                return {}
    except Exception as e:
        logger.warning(f"Error getting chunk metadata from DB for {chunk_id}: {e}")
        return {}


def export_batch_aggregated(
    batch_results: Dict[str, List[Dict[str, Any]]],
    entity_type: str,
    question_ids: List[Any],  # Can be int (legacy) or str (new system prompt IDs)
    tpi_centre_id: Optional[str] = None,
    output_format: str = "both",
    original_chunks_map: Optional[Dict[str, List[Dict[str, Any]]]] = None
) -> List[Path]:
    """
    Export batch processing results to new structured CSV/Excel format.
    
    New Structure:
    - Question (TPI Centre ID, e.g., EP4a)
    - Question_text
    - Entity
    - Answer (Yes/No or as applicable)
    - Explanation
    - Source Chunk 1, Chunk 1 Page, Chunk 1 Document, Chunk 1 metadata, etc.
    
    File organization: {entity_type}/{TPI_Centre_ID}/{date}/
    
    Args:
        batch_results: Dictionary mapping entity names to lists of result dictionaries
        entity_type: Type of entity ('countries', 'companies', 'banks')
        question_ids: List of question IDs that were processed
        tpi_centre_id: Optional TPI Centre ID (e.g., 'EP4a')
        output_format: "csv", "excel", or "both"
        original_chunks_map: Optional map of entity_question_id -> original chunks list
        
    Returns:
        List of output file paths created
    """
    # Import new prompt system
    from questions import get_prompt, get_tpi_centre_mapping, TPI_CENTRE_MAPPINGS
    
    try:
        # Get TPI Centre ID (use provided or find from prompt)
        if not tpi_centre_id and len(question_ids) == 1:
            # Try to find TPI Centre ID for this prompt
            for centre_id, mapping in TPI_CENTRE_MAPPINGS.items():
                if question_ids[0] in mapping.prompt_ids:
                    if entity_type in mapping.entity_types:
                        tpi_centre_id = centre_id
                        break
        
        if not tpi_centre_id:
            # Use prompt ID as TPI Centre ID if not found
            tpi_centre_id = question_ids[0] if question_ids else "UNKNOWN"
        
        # Create output directory structure: {entity_type}/{TPI_Centre_ID}/{date}/
        date_str = datetime.now().strftime('%Y%m%d')
        output_dir = CSV_OUTPUT_DIR / entity_type / tpi_centre_id / date_str
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Get question text (use first prompt if multiple)
        prompt_id = question_ids[0] if question_ids else None
        if not prompt_id:
            raise ValueError("No prompt IDs provided")
        
        prompt = get_prompt(prompt_id)
        if prompt:
            question_text = prompt.get_text_for_entity(entity_type)
        else:
            question_text = f"Prompt {prompt_id}"
        
        # Build columns: Question, Question_text, Entity, Answer, Explanation, then chunks
        # We'll dynamically add chunk columns based on max citations
        max_citations = 0
        for entity_results in batch_results.values():
            if not isinstance(entity_results, list):
                continue
            for result in entity_results:
                if not isinstance(result, dict):
                    continue
                if result.get('status') == 'success':
                    llm_response = result.get('llm_response', {})
                    if isinstance(llm_response, dict):
                        citations = llm_response.get('citations', [])
                        if isinstance(citations, list):
                            max_citations = max(max_citations, len(citations))
        
        # Build column structure
        columns = ['Question', 'Question_text', 'Entity', 'Answer', 'Explanation']
        
        # Add chunk columns (Chunk 1, Chunk 1 Page, Chunk 1 Document, Chunk 1 metadata, etc.)
        for i in range(1, max_citations + 1):
            columns.extend([
                f'Source_Chunk_{i}',
                f'Chunk_{i}_Page',
                f'Chunk_{i}_Document',
                f'Chunk_{i}_Metadata'
            ])
        
        # Build rows: one per entity
        rows = []
        
        # Ensure batch_results is a dict
        if not isinstance(batch_results, dict):
            logger.error(f"batch_results is not a dict: {type(batch_results)}")
            return []
        
        for entity_name in sorted(batch_results.keys()):
            entity_results = batch_results[entity_name]
            
            # Ensure entity_results is a list
            if not isinstance(entity_results, list):
                logger.warning(f"entity_results is not a list for {entity_name}: {type(entity_results)}")
                entity_results = []
            
            # Find result for the question (use first question_id)
            question_result = None
            for result in entity_results:
                # Ensure result is a dict
                if not isinstance(result, dict):
                    logger.warning(f"Result is not a dict for {entity_name}: {type(result)}")
                    continue
                # Match by prompt_id
                result_prompt_id = result.get('prompt_id') or result.get('question_id')
                if result_prompt_id == prompt_id:
                    question_result = result
                    break
            
            # Create row dictionary
            row = {
                'Question': tpi_centre_id,
                'Question_text': question_text.split('\n')[0].strip(),  # First line only
                'Entity': entity_name
            }
            
            if question_result and question_result.get('status') == 'success':
                llm_response = question_result.get('llm_response', {})
                
                # Ensure llm_response is a dict (not a string or None)
                if not isinstance(llm_response, dict):
                    logger.warning(f"llm_response is not a dict for {entity_name}: {type(llm_response)}")
                    llm_response = {}
                
                # Extract answer (try to get year, Yes/No, or "No data" from summary)
                answer_text = extract_answer_text(llm_response)
                
                # For EP4ai (year-based answer), extract year or "No data"
                if tpi_centre_id == 'EP4ai':
                    # Try to extract year (4 digits) or "No data" from first line
                    import re
                    # Get first line (before newline) for the answer
                    first_line = answer_text.split('\n')[0].strip() if '\n' in answer_text else answer_text.strip()
                    # Look for year in first line
                    year_match = re.search(r'\b(20\d{2}|19\d{2})\b', first_line)
                    if year_match:
                        answer_short = year_match.group(1)
                    elif 'no data' in first_line.lower():
                        answer_short = "No data"
                    else:
                        # Try to find year anywhere in the text as fallback
                        year_match = re.search(r'\b(20\d{2}|19\d{2})\b', answer_text)
                        if year_match:
                            answer_short = year_match.group(1)
                        elif 'no data' in answer_text.lower():
                            answer_short = "No data"
                        else:
                            # Final fallback: take first 50 chars
                            answer_short = first_line[:50].strip()
                else:
                    # For other prompts, try to extract Yes/No
                    answer_short = "Yes" if answer_text.lower().startswith('yes') else "No" if answer_text.lower().startswith('no') else answer_text[:50]
                
                row['Answer'] = answer_short
                
                # Extract explanation (detailed response)
                answer_obj = llm_response.get('answer', {})
                if isinstance(answer_obj, dict):
                    explanation = answer_obj.get('detailed_response', answer_obj.get('summary', ''))
                else:
                    explanation = str(answer_obj)
                row['Explanation'] = explanation
                
                # Process citations - get metadata from database
                citations = llm_response.get('citations', []) if isinstance(llm_response, dict) else []
                
                # Ensure citations is a list
                if not isinstance(citations, list):
                    logger.warning(f"Citations is not a list for {entity_name}: {type(citations)}")
                    citations = []
                
                # Get original chunks for this entity/prompt if available
                original_chunks = None
                if original_chunks_map and isinstance(original_chunks_map, dict):
                    entity_chunks_key = f"{entity_name}_{prompt_id}"
                    original_chunks = original_chunks_map.get(entity_chunks_key)
                    # Ensure original_chunks is a list
                    if not isinstance(original_chunks, list):
                        original_chunks = None
                
                for i, citation in enumerate(citations, 1):
                    # Ensure citation is a dict
                    if not isinstance(citation, dict):
                        logger.warning(f"Citation {i} is not a dict: {type(citation)}")
                        continue
                    
                    chunk_id = citation.get('id')
                    confidence = citation.get('cos_similarity_score', citation.get('confidence', 0))
                    
                    # Citation ID is typically an integer index (0, 1, 2) into original_chunks
                    # This is the simplest and most reliable way to get metadata
                    original_chunk = None
                    
                    if isinstance(chunk_id, int) and original_chunks:
                        # Integer index - use directly (most common case)
                        if 0 <= chunk_id < len(original_chunks):
                            original_chunk = original_chunks[chunk_id]
                    elif original_chunks:
                        # Try to find by UUID in original chunks (fallback)
                        for chunk in original_chunks:
                            if str(chunk.get('id', '')) == str(chunk_id):
                                original_chunk = chunk
                                break
                    
                    # Get metadata from original_chunk (most reliable source)
                    # This now includes page, doc_id, chunk_index, paragraph, language directly
                    if original_chunk:
                        # Get page number - prefer direct 'page' field, fallback to chunk_data
                        page_num = original_chunk.get('page')
                        if page_num is None:
                            # Try chunk_data
                            chunk_data = original_chunk.get('chunk_data', {})
                            if isinstance(chunk_data, str):
                                try:
                                    import json
                                    chunk_data = json.loads(chunk_data)
                                except:
                                    chunk_data = {}
                            if isinstance(chunk_data, dict):
                                page_num = chunk_data.get('page_number')
                        
                        # CRITICAL: Get document metadata - ensure doc_id exists
                        doc_id_value = original_chunk.get('doc_id')
                        doc_meta = {}
                        if doc_id_value:
                            doc_meta = get_document_metadata(str(doc_id_value))
                            # Log if document metadata retrieval failed
                            if not doc_meta or not any([doc_meta.get('title'), doc_meta.get('url'), doc_meta.get('file_path')]):
                                logger.debug(f"Document metadata empty for doc_id: {doc_id_value}")
                        else:
                            logger.warning(f"No doc_id found in original_chunk for citation {i}")
                        
                        # Populate row with chunk information
                        chunk_content = original_chunk.get('content', citation.get('content', ''))
                        row[f'Source_Chunk_{i}'] = chunk_content[:500] if chunk_content else ''
                        
                        # Page number (CRITICAL - must be present for analyst verification)
                        row[f'Chunk_{i}_Page'] = str(page_num) if page_num is not None else ''
                        if not page_num:
                            logger.warning(f"No page number found for chunk {i} (chunk_id: {chunk_id})")
                        
                        # Document information (CRITICAL - must include title at minimum, URL ideally)
                        doc_title = doc_meta.get('title', '') if isinstance(doc_meta, dict) else ''
                        doc_url = doc_meta.get('url', '') if isinstance(doc_meta, dict) else ''
                        doc_file_path = doc_meta.get('file_path', '') if isinstance(doc_meta, dict) else ''
                        
                        # Build document string with priority: Title (required), URL (preferred), File path (fallback)
                        doc_info_parts = []
                        if doc_title:
                            doc_info_parts.append(doc_title)
                        else:
                            logger.warning(f"No document title found for chunk {i} (doc_id: {doc_id_value})")
                        
                        if doc_url:
                            doc_info_parts.append(f"URL: {doc_url}")
                        elif doc_file_path:
                            # Show just filename if full path
                            doc_filename = Path(doc_file_path).name if doc_file_path else ''
                            if doc_filename:
                                doc_info_parts.append(f"File: {doc_filename}")
                        
                        # Ensure at least something is in the Document column
                        row[f'Chunk_{i}_Document'] = " | ".join(doc_info_parts) if doc_info_parts else 'MISSING'
                        if not doc_info_parts:
                            logger.warning(f"No document information found for chunk {i} (doc_id: {doc_id_value})")
                        
                        # Additional metadata
                        metadata_parts = []
                        if confidence:
                            metadata_parts.append(f"Confidence: {confidence:.3f}")
                        if original_chunk.get('chunk_index') is not None:
                            metadata_parts.append(f"Chunk Index: {original_chunk.get('chunk_index')}")
                        if original_chunk.get('paragraph') is not None:
                            metadata_parts.append(f"Paragraph: {original_chunk.get('paragraph')}")
                        if original_chunk.get('language'):
                            metadata_parts.append(f"Language: {original_chunk.get('language')}")
                        if doc_file_path and not doc_url:  # Only add full path if URL not available
                            metadata_parts.append(f"Full Path: {doc_file_path}")
                        
                        row[f'Chunk_{i}_Metadata'] = " | ".join(metadata_parts) if metadata_parts else ''
                    else:
                        # Fallback: try to get from citation or database lookup
                        # This should rarely happen if original_chunks is properly passed
                        logger.warning(f"Could not find original chunk for citation {i} with ID {chunk_id}")
                        
                        # Try database lookup as last resort
                        db_meta = get_chunk_metadata_from_db(chunk_id, original_chunks)
                        
                        chunk_content = db_meta.get('content', citation.get('content', ''))
                        row[f'Source_Chunk_{i}'] = chunk_content[:500] if chunk_content else ''
                        
                        page_num = db_meta.get('page')
                        row[f'Chunk_{i}_Page'] = str(page_num) if page_num is not None else ''
                        
                        doc_title = db_meta.get('doc_title', '')
                        doc_url = db_meta.get('doc_url', '')
                        doc_file_path = db_meta.get('doc_file_path', '')
                        
                        doc_info_parts = []
                        if doc_title:
                            doc_info_parts.append(doc_title)
                        if doc_url:
                            doc_info_parts.append(f"URL: {doc_url}")
                        elif doc_file_path:
                            doc_filename = Path(doc_file_path).name if doc_file_path else ''
                            if doc_filename:
                                doc_info_parts.append(f"File: {doc_filename}")
                        
                        row[f'Chunk_{i}_Document'] = " | ".join(doc_info_parts) if doc_info_parts else ''
                        
                        metadata_parts = []
                        if confidence:
                            metadata_parts.append(f"Confidence: {confidence:.3f}")
                        row[f'Chunk_{i}_Metadata'] = " | ".join(metadata_parts) if metadata_parts else ''
                
                # Fill empty chunk columns
                for i in range(len(citations) + 1, max_citations + 1):
                    row[f'Source_Chunk_{i}'] = ''
                    row[f'Chunk_{i}_Page'] = ''
                    row[f'Chunk_{i}_Document'] = ''
                    row[f'Chunk_{i}_Metadata'] = ''
                    
            else:
                # No result or error
                error_msg = question_result.get('error', 'Not processed') if question_result and isinstance(question_result, dict) else 'Not processed'
                row['Answer'] = f"Error: {error_msg}"
                row['Explanation'] = ""
                # Fill empty chunk columns
                for i in range(1, max_citations + 1):
                    row[f'Source_Chunk_{i}'] = ''
                    row[f'Chunk_{i}_Page'] = ''
                    row[f'Chunk_{i}_Document'] = ''
                    row[f'Chunk_{i}_Metadata'] = ''
            
            rows.append(row)
        
        # Create DataFrame
        df = pd.DataFrame(rows, columns=columns)
        
        # Export files
        output_files = []
        timestamp = datetime.now().strftime('%H%M%S')
        safe_entity_type = entity_type.replace(' ', '_')
        
        # Export CSV
        if output_format in ["csv", "both"]:
            csv_file = output_dir / f"{tpi_centre_id}_{date_str}_{timestamp}.csv"
            df.to_csv(csv_file, index=False, encoding='utf-8-sig')
            output_files.append(csv_file)
            logger.info(f"[6_OUTPUT] Aggregated CSV exported: {csv_file}")
        
        # Export Excel
        if output_format in ["excel", "both"]:
            try:
                excel_file = output_dir / f"{tpi_centre_id}_{date_str}_{timestamp}.xlsx"
                df.to_excel(excel_file, index=False, engine='openpyxl')
                output_files.append(excel_file)
                logger.info(f"[6_OUTPUT] Aggregated Excel exported: {excel_file}")
            except ImportError:
                logger.warning("[6_OUTPUT] openpyxl not installed, skipping Excel export. Install with: pip install openpyxl")
            except Exception as e:
                logger.error(f"[6_OUTPUT] Error exporting Excel: {e}")
        
        return output_files
    
    except AttributeError as e:
        # This is the specific error we're seeing
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"[6_OUTPUT] AttributeError in export_batch_aggregated: {e}")
        logger.error(f"[6_OUTPUT] Error details: {error_details}")
        # Try to identify which object is a string
        logger.error(f"[6_OUTPUT] batch_results type: {type(batch_results)}")
        if isinstance(batch_results, dict):
            for key, value in list(batch_results.items())[:3]:  # Check first 3
                logger.error(f"[6_OUTPUT]   {key}: {type(value)}")
                if isinstance(value, list) and value:
                    logger.error(f"[6_OUTPUT]     First item: {type(value[0])}")
        raise
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"[6_OUTPUT] Error in export_batch_aggregated: {e}")
        logger.error(f"[6_OUTPUT] Error details: {error_details}")
        raise


# Keep old functions for backward compatibility
def extract_sources_with_links(llm_response: Dict[str, Any]) -> str:
    """Legacy function - kept for compatibility."""
    citations = llm_response.get('citations', [])
    if not citations:
        return "No citations"
    source_list = []
    for i, cite in enumerate(citations, 1):
        link = generate_source_link(cite)
        similarity = cite.get('cos_similarity_score', 0)
        source_list.append(f"{i}. {link} (similarity: {similarity:.3f})")
    return " | ".join(source_list)


def extract_sources(llm_response: Dict[str, Any]) -> str:
    """Legacy function - kept for compatibility."""
    return extract_sources_with_links(llm_response)


def generate_source_link(citation: Dict[str, Any]) -> str:
    """Legacy function - kept for compatibility."""
    doc_id = citation.get('doc_id', '')
    page = citation.get('chunk_metadata', {}).get('page_number') or citation.get('page')
    chunk_index = citation.get('chunk_index', '')
    
    doc_meta = get_document_metadata(doc_id)
    url = doc_meta.get('url')
    file_path = doc_meta.get('file_path')
    
    link_parts = []
    if url:
        if page and url.endswith('.pdf'):
            link = f"{url}#page={page}"
        else:
            link = url
        link_parts.append(f"URL: {link}")
    if file_path:
        if Path(file_path).exists():
            file_url = Path(file_path).as_uri()
            link_parts.append(f"File: {file_url}")
        else:
            link_parts.append(f"File: {file_path}")
    if page:
        link_parts.append(f"Page: {page}")
    if chunk_index is not None:
        link_parts.append(f"Chunk: {chunk_index}")
    
    return " | ".join(link_parts) if link_parts else f"Doc: {doc_id}"


def export_to_csv_excel(
    response_data: Dict[str, Any],
    entity_name: str,
    output_format: str = "both"
) -> List[Path]:
    """Legacy function - kept for compatibility."""
    entity_type = detect_entity_type(entity_name)
    entity_dir = CSV_OUTPUT_DIR / entity_type
    entity_dir.mkdir(parents=True, exist_ok=True)
    
    questions = response_data.get('questions', {})
    if not questions:
        logger.warning(f"No questions found in response data for {entity_name}")
        return []
    
    output_files = []
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_entity = entity_name.replace(' ', '_')
    
    for question_id, llm_response in questions.items():
        question_text = llm_response.get('question', 'Unknown question')
        question_id_safe = get_question_identifier(question_text)
        answer_text = extract_answer_text(llm_response)
        sources = extract_sources(llm_response)
        confidence = llm_response.get('confidence', 0.0)
        
        df = pd.DataFrame([{
            'Question': question_text,
            'Entity': entity_name,
            'Answer': answer_text,
            'Sources': sources,
            'Confidence': confidence,
            'Question_ID': question_id
        }])
        
        if output_format in ["csv", "both"]:
            csv_file = entity_dir / f"{safe_entity}_{question_id_safe}_{timestamp}.csv"
            df.to_csv(csv_file, index=False, encoding='utf-8-sig')
            output_files.append(csv_file)
            logger.info(f"[6_OUTPUT] CSV exported: {csv_file}")
        
        if output_format in ["excel", "both"]:
            try:
                excel_file = entity_dir / f"{safe_entity}_{question_id_safe}_{timestamp}.xlsx"
                df.to_excel(excel_file, index=False, engine='openpyxl')
                output_files.append(excel_file)
                logger.info(f"[6_OUTPUT] Excel exported: {excel_file}")
            except ImportError:
                logger.warning("[6_OUTPUT] openpyxl not installed, skipping Excel export. Install with: pip install openpyxl")
    
    return output_files


def export_single_question(
    question: str,
    entity_name: str,
    llm_response: Dict[str, Any],
    output_format: str = "both"
) -> List[Path]:
    """Legacy function - kept for compatibility."""
    entity_type = detect_entity_type(entity_name)
    entity_dir = CSV_OUTPUT_DIR / entity_type
    entity_dir.mkdir(parents=True, exist_ok=True)
    
    answer_text = extract_answer_text(llm_response)
    sources = extract_sources(llm_response)
    confidence = llm_response.get('confidence', 0.0)
    question_id_safe = get_question_identifier(question)
    
    df = pd.DataFrame([{
        'Question': question,
        'Entity': entity_name,
        'Answer': answer_text,
        'Sources': sources,
        'Confidence': confidence,
        'Question_ID': 'single'
    }])
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_entity = entity_name.replace(' ', '_')
    
    output_files = []
    if output_format in ["csv", "both"]:
        csv_file = entity_dir / f"{safe_entity}_{question_id_safe}_{timestamp}.csv"
        df.to_csv(csv_file, index=False, encoding='utf-8-sig')
        output_files.append(csv_file)
        logger.info(f"[6_OUTPUT] CSV exported: {csv_file}")
    
    if output_format in ["excel", "both"]:
        try:
            excel_file = entity_dir / f"{safe_entity}_{question_id_safe}_{timestamp}.xlsx"
            df.to_excel(excel_file, index=False, engine='openpyxl')
            output_files.append(excel_file)
            logger.info(f"[6_OUTPUT] Excel exported: {excel_file}")
        except ImportError:
            logger.warning("[6_OUTPUT] openpyxl not installed, skipping Excel export. Install with: pip install openpyxl")
    
    return output_files
