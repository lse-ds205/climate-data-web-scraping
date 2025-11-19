import sys
from pathlib import Path
import traceback
import logging
import asyncio
from dotenv import load_dotenv
from datetime import date
import uuid
from tqdm import tqdm
from sqlalchemy import select

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))
import group4py
from exceptions import ChunkingError, TextExtractionError, PDFExtractionError, ChunkProcessingError, ChunkCleaningError, ChunkStorageError, DocumentProcessingError
from group4py.src.chunk.extractor import extract_text_from_pdf
from group4py.src.chunk.chunker import DocChunker
from group4py.src.constants.settings import FILE_PROCESSING_CONCURRENCY
from helpers.internal import Logger
from databases.docker_proxy import get_database_connection
from databases.models import NDCDocumentORM, DocChunkORM, LogicalRelationshipORM
from databases.operations import check_document_processed, update_processed, upload
from group4py.src.scrape.document_type import infer_document_type

logger = logging.getLogger(__name__)
load_dotenv()
db = get_database_connection()  # Use Docker proxy on Windows


def get_file_paths():
    """
    Get the file paths of PDF files in the data/pdfs folder.
    """
    pdf_directory = project_root / "data" / "pdfs"
    if not pdf_directory.exists():
        logger.warning(f"[3_CHUNK] PDF directory not found: {pdf_directory}")
        return []
    
    pdf_files = list(pdf_directory.glob("*.pdf"))
    logger.info(f"[3_CHUNK] Found {len(pdf_files)} PDF files in {pdf_directory}")
    
    # Convert Path objects to strings
    return [str(file_path) for file_path in pdf_files]


async def chunk_file_one(file_path: str, force_reprocess: bool = False):
    """
    Process a file and create chunks (without embeddings).
    
    Args:
        file_path: Path to the PDF file
        force_reprocess: If True, reprocess the file even if it has been processed before
        
    Raises:
        DocumentProcessingError: If there is an error processing the document
        PDFExtractionError: If there is an error extracting text from the PDF
        ChunkProcessingError: If there is an error processing document chunks
        ChunkStorageError: If there is an error storing chunks to the database
    """
    try:
        # Initialize database connection
        with db.Session() as session:
            # Extract file name to be used as document ID
            file_name = Path(file_path).stem
            logger.info(f"[3_CHUNK] Processing file {file_path}")


            # Check if document has already been processed
            doc_id = file_name
            is_processed, document = check_document_processed(session, doc_id)
            
            if is_processed and not force_reprocess:
                logger.info(f"[3_CHUNK] Document {doc_id} has already been processed. Skipping.")
                return None
                
            # If force_reprocess is True and document exists, delete existing chunks and relationships
            if force_reprocess and document:
                logger.info(f"[3_CHUNK] Force reprocessing document {doc_id}")

                try:
                    # Convert string doc_id to UUID using deterministic UUID5
                    doc_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, doc_id)
                    
                    # Check if we're using Docker proxy (which only supports raw SQL)
                    if hasattr(session, '_DockerProxySession__proxy') or session.__class__.__name__ == 'DockerProxySession':
                        # Use raw SQL for Docker proxy
                        from sqlalchemy import text
                        
                        # First, delete any logical relationships that reference this document's chunks
                        result = session.execute(text("""
                            DELETE FROM logical_relationships
                            WHERE source_chunk_id IN (
                                SELECT id FROM doc_chunks WHERE doc_id = :doc_uuid
                            )
                            OR target_chunk_id IN (
                                SELECT id FROM doc_chunks WHERE doc_id = :doc_uuid
                            )
                        """), {'doc_uuid': str(doc_uuid)})
                        
                        # Get count of deleted relationships (may not be available in all cases)
                        deleted_relationships = result.rowcount if hasattr(result, 'rowcount') else 0
                        
                        if deleted_relationships > 0:
                            logger.info(f"[3_CHUNK] Deleted {deleted_relationships} relationships for document {doc_id}")
                        
                        # Now delete the chunks
                        result = session.execute(text("""
                            DELETE FROM doc_chunks WHERE doc_id = :doc_uuid
                        """), {'doc_uuid': str(doc_uuid)})
                        
                        deleted_chunks = result.rowcount if hasattr(result, 'rowcount') else 0
                        logger.info(f"[3_CHUNK] Removed {deleted_chunks} existing chunks for document {doc_id}")
                        
                        session.commit()
                    else:
                        # Use ORM for regular connections
                        # First, delete any logical relationships that reference this document's chunks
                        # Get all chunk IDs for this document using explicit select
                        chunk_ids_query = select(DocChunkORM.id).filter(DocChunkORM.doc_id == doc_uuid)
                        
                        # Delete relationships where either source or target chunk belongs to this document
                        deleted_relationships = session.query(LogicalRelationshipORM).filter(
                            (LogicalRelationshipORM.source_chunk_id.in_(chunk_ids_query)) |
                            (LogicalRelationshipORM.target_chunk_id.in_(chunk_ids_query))
                        ).delete(synchronize_session=False)
                        
                        if deleted_relationships > 0:
                            logger.info(f"[3_CHUNK] Deleted {deleted_relationships} relationships for document {doc_id}")
                        
                        # Now delete the chunks
                        deleted_chunks = session.query(DocChunkORM).filter(DocChunkORM.doc_id == doc_uuid).delete()
                        logger.info(f"[3_CHUNK] Removed {deleted_chunks} existing chunks for document {doc_id}")
                        
                        session.commit()
                except Exception as e:
                    logger.error(f"[3_CHUNK] Error removing existing chunks and relationships: {e}")
                    logger.error(f"[3_CHUNK] Traceback: {traceback.format_exc()}")
                    session.rollback()
                    raise DocumentProcessingError(f"Failed to remove existing chunks for document {doc_id}: {str(e)}") from e
            
            # If document doesn't exist, create it first before proceeding with chunk processing
            if not document:
                logger.info(f"[3_CHUNK] Document {doc_id} not found in database. Creating record...")

                try:
                    # Extract document metadata from filename
                    parts = doc_id.split('_')
                    country = parts[0].replace('_', ' ').title() if len(parts) > 0 else ''
                    language = parts[1] if len(parts) > 1 else ''
                    
                    # Try to parse date if available (format: YYYYMMDD)
                    submission_date = None
                    if len(parts) > 2 and len(parts[2]) >= 8:
                        date_str = parts[2][:8]  # Extract YYYYMMDD portion
                        try:
                            year = int(date_str[:4])
                            month = int(date_str[4:6])
                            day = int(date_str[6:8])
                            submission_date = date(year, month, day)
                        except (ValueError, IndexError):
                            logger.warning(f"[3_CHUNK] Could not parse date from filename: {parts[2]}")
                    
                    # Create document record
                    doc_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, doc_id)
                    file_size_mb = Path(file_path).stat().st_size / (1024 * 1024)
                    
                    # Infer document_type from file path (KEY METADATA)
                    # Don't assume NDC - let inference determine from file path
                    document_type = infer_document_type(file_path=file_path)
                    
                    # Generate title based on inferred document type or use generic format
                    if document_type:
                        title = f"{country} {document_type}"
                    else:
                        # Fallback: use filename or generic title
                        file_stem = Path(file_path).stem
                        title = f"{country} Document" if not file_stem else file_stem.replace('_', ' ')
                    
                    # Check if we're using Docker proxy (which only supports raw SQL)
                    if hasattr(session, '_DockerProxySession__proxy') or session.__class__.__name__ == 'DockerProxySession':
                        # Use raw SQL for Docker proxy
                        from sqlalchemy import text
                        from datetime import datetime
                        
                        session.execute(text("""
                            INSERT INTO documents (doc_id, country, title, url, language, submission_date, file_path, file_size, scraped_at, updated_at, document_type)
                            VALUES (:doc_id, :country, :title, :url, :language, :submission_date, :file_path, :file_size, :scraped_at, :updated_at, :document_type)
                        """), {
                            'doc_id': str(doc_uuid),
                            'country': country,
                            'title': title,  # Use inferred title, not hardcoded "NDC"
                            'url': "",
                            'language': language,
                            'submission_date': submission_date,
                            'file_path': file_path,
                            'file_size': file_size_mb,
                            'scraped_at': datetime.now(),
                            'updated_at': datetime.now(),
                            'document_type': document_type  # KEY METADATA
                        })
                        session.commit()
                        logger.info(f"[3_CHUNK] Created document record for {doc_id} (raw SQL)")
                        
                        # Create a temporary document object for tracking
                        document = NDCDocumentORM(
                            doc_id=doc_uuid,
                            country=country,
                            title=title,  # Use inferred title
                            url="",
                            language=language,
                            submission_date=submission_date,
                            file_path=file_path,
                            file_size=file_size_mb,
                            document_type=document_type  # KEY METADATA
                        )
                    else:
                        # Use ORM for regular connections
                        new_document = NDCDocumentORM(
                            doc_id=doc_uuid,
                            country=country,
                            title=title,  # Use inferred title, not hardcoded "NDC"
                            url="",  # Empty URL since we're processing local files
                            language=language,
                            submission_date=submission_date,
                            file_path=file_path,
                            file_size=file_size_mb,
                            document_type=document_type  # KEY METADATA
                        )
                        
                        session.add(new_document)
                        session.commit()
                        logger.info(f"[3_CHUNK] Created document record for {doc_id}")
                        document = new_document
                except Exception as e:
                    logger.error(f"[3_CHUNK] Error creating document record: {e}")
                    session.rollback()
                    raise DocumentProcessingError(f"Failed to create document record for {doc_id}: {str(e)}") from e
            
            # 1. Extract text from PDF with multiple strategies, stopping once one succeeds
            extracted_elements = None
            extraction_strategies = ['fast', 'auto', 'ocr_only']
            
            extraction_error = None
            for strategy in extraction_strategies:
                try:
                    logger.info(f"[3_CHUNK] Attempting text extraction with strategy: {strategy}")
                    raw_extracted_elements = extract_text_from_pdf(file_path, strategy=strategy)

                    # Check if we got meaningful content from the extraction function
                    if raw_extracted_elements and len(raw_extracted_elements) > 0:
                        logger.info(f"[3_CHUNK] Strategy {strategy} extracted {len(raw_extracted_elements)} elements")
                        
                        # Handle different element structures - some may be dicts, others may be objects
                        text_content = []
                        for elem in raw_extracted_elements:
                            try:
                                # Try dict-like access first
                                if hasattr(elem, 'get'):
                                    text = elem.get('text', '').strip()
                                    metadata = elem.get('metadata', {})
                                # Try object attribute access
                                elif hasattr(elem, 'text'):
                                    text = getattr(elem, 'text', '').strip()
                                    metadata = getattr(elem, 'metadata', {})
                                # Try direct string conversion
                                elif isinstance(elem, str):
                                    text = elem.strip()
                                    metadata = {}
                                # Try converting object to dict
                                elif hasattr(elem, '__dict__'):
                                    elem_dict = elem.__dict__
                                    text = elem_dict.get('text', '').strip()
                                    metadata = elem_dict.get('metadata', {})
                                else:
                                    text = str(elem).strip()
                                    metadata = {}
                                
                                if text:
                                    # Create standardized element structure
                                    standardized_elem = {
                                        'text': text,
                                        'metadata': metadata if isinstance(metadata, dict) else {}
                                    }
                                    text_content.append(standardized_elem)
                            except Exception as elem_error:
                                logger.warning(f"[3_CHUNK] Error processing element with strategy {strategy}: {elem_error}")
                                continue
                        
                        if text_content:
                            logger.info(f"[3_CHUNK] Successfully extracted {len(text_content)} text elements using {strategy} strategy")
                            extracted_elements = text_content
                            break  # Success! Stop trying other strategies
                        else:
                            logger.warning(f"[3_CHUNK] Strategy {strategy} returned elements but no actual text content")
                    else:
                        logger.warning(f"[3_CHUNK] Strategy {strategy} returned no elements")
                        
                except TextExtractionError as e:
                    logger.warning(f"[3_CHUNK] Strategy {strategy} failed with TextExtractionError: {e}")
                    extraction_error = e
                    extracted_elements = None
                    continue
                except Exception as e:
                    logger.warning(f"[3_CHUNK] Strategy {strategy} failed with unexpected error: {e}")
                    extraction_error = e
                    extracted_elements = None
                    continue
            
            # If all extraction strategies failed, create a minimal fallback
            if not extracted_elements:
                logger.error(f"[3_CHUNK] All text extraction strategies failed for {file_path}")
                
                if extraction_error:
                    logger.error(f"[3_CHUNK] Last extraction error: {extraction_error}")
                
                # Create a minimal fallback chunk with filename information
                fallback_text = f"Document: {Path(file_path).name}\nNote: Text extraction failed - document may be image-based or corrupted."
                
                extracted_elements = [{
                    'text': fallback_text,
                    'metadata': {
                        'page_number': 1,
                        'paragraph_number': 1,
                        'extraction_method': 'fallback',
                        'extraction_status': 'failed'
                    }
                }]
                
                logger.warning(f"[3_CHUNK] Using fallback content for {file_path}")
            
            logger.info(f"[3_CHUNK] Final extracted elements count: {len(extracted_elements)}")
            
            # 2. Create chunks from the extracted text
            try:
                chunks = DocChunker.chunk_document_by_sentences(extracted_elements)
                logger.info(f"[3_CHUNK] Created {len(chunks)} chunks from {file_path}")
            except ChunkProcessingError as e:
                logger.error(f"[3_CHUNK] Error during chunk creation: {e}")
                raise
            
            # 3. Clean chunks
            try:
                cleaned_chunks = DocChunker.cleaning_function(chunks)
                logger.info(f"[3_CHUNK] Finished cleaning chunks from {file_path}, got {len(cleaned_chunks)} cleaned chunks")
            except ChunkCleaningError as e:
                logger.error(f"[3_CHUNK] Error during chunk cleaning: {e}")
                # Fall back to using the original chunks if cleaning fails
                logger.info(f"[3_CHUNK] Falling back to original chunks")
                cleaned_chunks = chunks
            except Exception as e:
                logger.error(f"[3_CHUNK] Unexpected error during chunk cleaning: {e}")
                # Fall back to using the original chunks if cleaning fails
                logger.info(f"[3_CHUNK] Falling back to original chunks")
                cleaned_chunks = chunks
                
            # Validate cleaned chunks before proceeding
            if not cleaned_chunks or len(cleaned_chunks) == 0:
                logger.error(f"[3_CHUNK] No valid chunks after cleaning for {file_path}")
                raise ChunkProcessingError(f"No valid chunks after cleaning for {file_path}")
            
            # 4. Get document metadata (URL and dates) from database to include in chunk metadata
            # First, get the doc_uuid (deterministic UUID from filename)
            doc_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, file_name)
            
            doc_url = ""
            doc_metadata = {}  # Store date fields and other metadata
            
            try:
                # Check if we're using Docker proxy (which only supports raw SQL)
                if hasattr(session, '_DockerProxySession__proxy') or session.__class__.__name__ == 'DockerProxySession':
                    # Use raw SQL for Docker proxy - get URL and date fields
                    from sqlalchemy import text
                    result = session.execute(text("""
                        SELECT url, submission_date, scraped_at, downloaded_at, processed_at
                        FROM documents WHERE doc_id = :doc_uuid
                    """), {'doc_uuid': str(doc_uuid)})
                    row = result.fetchone()
                    if row:
                        doc_url = row[0] or ""
                        # Add date fields to metadata (convert to ISO format strings for JSON storage)
                        if row[1]:  # submission_date
                            doc_metadata['submission_date'] = row[1].isoformat() if hasattr(row[1], 'isoformat') else str(row[1])
                        if row[2]:  # scraped_at
                            doc_metadata['scraped_at'] = row[2].isoformat() if hasattr(row[2], 'isoformat') else str(row[2])
                        if row[3]:  # downloaded_at
                            doc_metadata['downloaded_at'] = row[3].isoformat() if hasattr(row[3], 'isoformat') else str(row[3])
                        if row[4]:  # processed_at
                            doc_metadata['processed_at'] = row[4].isoformat() if hasattr(row[4], 'isoformat') else str(row[4])
                else:
                    # Use ORM for regular connections
                    if document:
                        if hasattr(document, 'url') and document.url:
                            doc_url = document.url
                        # Get date fields from document object
                        if hasattr(document, 'submission_date') and document.submission_date:
                            doc_metadata['submission_date'] = document.submission_date.isoformat() if hasattr(document.submission_date, 'isoformat') else str(document.submission_date)
                        if hasattr(document, 'scraped_at') and document.scraped_at:
                            doc_metadata['scraped_at'] = document.scraped_at.isoformat() if hasattr(document.scraped_at, 'isoformat') else str(document.scraped_at)
                        if hasattr(document, 'downloaded_at') and document.downloaded_at:
                            doc_metadata['downloaded_at'] = document.downloaded_at.isoformat() if hasattr(document.downloaded_at, 'isoformat') else str(document.downloaded_at)
                        if hasattr(document, 'processed_at') and document.processed_at:
                            doc_metadata['processed_at'] = document.processed_at.isoformat() if hasattr(document.processed_at, 'isoformat') else str(document.processed_at)
                    else:
                        # Query the document again to get URL and dates
                        doc_query = session.query(NDCDocumentORM).filter(NDCDocumentORM.doc_id == doc_uuid).first()
                        if doc_query:
                            if doc_query.url:
                                doc_url = doc_query.url
                            # Get date fields
                            if doc_query.submission_date:
                                doc_metadata['submission_date'] = doc_query.submission_date.isoformat() if hasattr(doc_query.submission_date, 'isoformat') else str(doc_query.submission_date)
                            if doc_query.scraped_at:
                                doc_metadata['scraped_at'] = doc_query.scraped_at.isoformat() if hasattr(doc_query.scraped_at, 'isoformat') else str(doc_query.scraped_at)
                            if doc_query.downloaded_at:
                                doc_metadata['downloaded_at'] = doc_query.downloaded_at.isoformat() if hasattr(doc_query.downloaded_at, 'isoformat') else str(doc_query.downloaded_at)
                            if doc_query.processed_at:
                                doc_metadata['processed_at'] = doc_query.processed_at.isoformat() if hasattr(doc_query.processed_at, 'isoformat') else str(doc_query.processed_at)
            except Exception as e:
                logger.warning(f"[3_CHUNK] Could not retrieve document metadata for {doc_id}: {e}")
                doc_url = ""
                doc_metadata = {}
            
            if doc_url or doc_metadata:
                logger.info(f"[3_CHUNK] Retrieved metadata for document {doc_id}: URL={'Yes' if doc_url else 'No'}, Dates={len(doc_metadata)} fields")
            else:
                logger.warning(f"[3_CHUNK] No metadata found for document {doc_id} - chunks will be created without document metadata")
            
            # 5. Create DocChunk objects for database storage (without embeddings)
            db_chunks = []
            for i, chunk in enumerate(cleaned_chunks):
                # Skip empty chunks
                if not chunk.get('text', '').strip():
                    logger.warning(f"[3_CHUNK] Skipping empty chunk {i} from {file_path}")
                    continue
                
                # Get existing metadata and add document URL and dates
                chunk_metadata = chunk.get('metadata', {}).copy() if chunk.get('metadata') else {}
                
                # Add URL if available
                if doc_url:
                    chunk_metadata['url'] = doc_url
                    chunk_metadata['document_url'] = doc_url  # Add both for compatibility
                
                # Add date fields from document metadata (only if not already in chunk metadata)
                for date_key, date_value in doc_metadata.items():
                    if date_key not in chunk_metadata:  # Don't overwrite existing metadata
                        chunk_metadata[date_key] = date_value
                    
                # Create a DocChunkORM object without embeddings
                chunk_model = DocChunkORM(
                    id=uuid.uuid4(),
                    doc_id=doc_uuid,
                    content=chunk.get('text', ''),
                    chunk_index=i,
                    page=chunk.get('metadata', {}).get('page_number', 0),
                    paragraph=chunk.get('metadata', {}).get('paragraph_numbers', 0)[0] if chunk.get('metadata', {}).get('paragraph_numbers') else None,
                    language=chunk.get('metadata', {}).get('language'),
                    chunk_data=chunk_metadata,
                    # Note: transformer_embedding and word2vec_embedding are left as None
                    # They will be filled in by 3.5_embed.py
                )

                db_chunks.append(chunk_model)
            
            # Verify we have chunks to upload
            if not db_chunks:
                logger.error(f"[3_CHUNK] No valid chunks to upload for {file_path}")
                raise ChunkStorageError(f"No valid chunks to upload for {file_path}")
                
            # 5. Upload chunks to the database (without embeddings)
            try:
                logger.info(f"[3_CHUNK] Attempting to upload {len(db_chunks)} chunks to database for {file_path}")
                upload_success = upload(session, db_chunks, table='doc_chunks')
                if not upload_success:
                    logger.error(f"[3_CHUNK] Failed to upload chunks to database for {file_path}")
                    raise ChunkStorageError(f"Failed to upload chunks to database for {file_path}")
                    
                logger.info(f"[3_CHUNK] Uploaded {len(db_chunks)} chunks to doc_chunks table")
            except Exception as e:
                logger.error(f"[3_CHUNK] Error uploading chunks to database: {e}")
                raise ChunkStorageError(f"Failed to upload chunks to database: {str(e)}") from e

            # 6. Update documents table that the document has been processed (chunked)
            try:
                update_processed(session, NDCDocumentORM, doc_id, chunks=cleaned_chunks, table='documents')
                logger.info(f"[3_CHUNK] Updated processed status in documents table for {doc_id}")
            except Exception as e:
                logger.error(f"[3_CHUNK] Error updating document processed status: {e}")
                raise DocumentProcessingError(f"Failed to update document processed status: {str(e)}") from e
            
            logger.info(f"[3_CHUNK] File {file_path} chunked successfully")
            return db_chunks
    
    except ChunkingError as e:
        # Handle specific chunking errors without re-wrapping them
        logger.error(f"[3_CHUNK] Chunking error processing file {file_path}: {e}")
        logger.error(f"[3_CHUNK] Traceback: {traceback.format_exc()}")
        raise
    except Exception as e:
        logger.error(f"[3_CHUNK] Error processing file {file_path}: {e}\n\n")
        logger.error(f"[3_CHUNK] Traceback: {traceback.format_exc()}")
        raise DocumentProcessingError(f"Failed to process document {file_path}: {str(e)}") from e


async def chunk_file_many(file_path): 
    """Process a single file with concurrency control."""
    semaphore = asyncio.Semaphore(FILE_PROCESSING_CONCURRENCY)
    async with semaphore:
        return await chunk_file_one(file_path)


@Logger.log(log_file = project_root / "logs/chunk.log", log_level="INFO")
async def run_script(force_reprocess: bool = False):
    """
    Main function to process all PDF files and create chunks.
    
    Args:
        force_reprocess: If True, reprocess all documents even if already processed
    """
    try:
        logger.warning(f"\n\n[3_CHUNK] Running chunking script with force_reprocess={force_reprocess}...")
        file_paths = get_file_paths()
        
        if not file_paths:
            logger.warning(f"[3_CHUNK] No PDF files found to process")
            return
        
        # Show the progress bar for all file processing
        with tqdm(total=len(file_paths), desc="Chunking PDF files", unit="file") as pbar:
            # Create a wrapped version that updates the progress bar
            async def process_with_progress(file_path):
                try:
                    # Pass the force_reprocess parameter to chunk_file_one
                    result = await chunk_file_one(file_path, force_reprocess=force_reprocess)
                    # Update progress bar after processing each file
                    pbar.update(1)
                    # Add the filename to the progress bar description when it completes
                    pbar.set_postfix_str(f"Last: {Path(file_path).name}")
                    return result
                except ChunkingError as e:
                    # Still update progress even on error
                    pbar.update(1)
                    # Show error in progress bar
                    pbar.set_postfix_str(f"Chunking error with {Path(file_path).name}")
                    logger.error(f"[3_CHUNK] Chunking error in process_with_progress: {e}")
                    return None
                except Exception as e:
                    # Still update progress even on error
                    pbar.update(1)
                    # Show error in progress bar
                    pbar.set_postfix_str(f"Error with {Path(file_path).name}")
                    logger.error(f"[3_CHUNK] Error in process_with_progress: {e}")
                    return None
                    
            # Process files with progress tracking
            tasks = [process_with_progress(file_path) for file_path in file_paths]
            chunk_results = await asyncio.gather(*tasks)
        
        # Filter out None results and empty lists
        valid_chunks = [chunks for chunks in chunk_results if chunks is not None and len(chunks) > 0]
        
        if not valid_chunks:
            logger.warning(f"[3_CHUNK] No valid chunks created")
        else:
            total_chunks = sum(len(chunks) for chunks in valid_chunks)
            logger.warning(f"[3_CHUNK] All files processed successfully. {total_chunks} chunks created")
            logger.warning(f"[3_CHUNK] Chunking script completed successfully. Ready for embedding.")
            
    except Exception as e:
        logger.critical(f"\n\n\n\n[PIPELINE BROKE!] - Error in 3_chunk.py: {e}\n\n")
        logger.critical(f"[3_CHUNK] Traceback: {traceback.format_exc()}")
        raise e


if __name__ == "__main__":
    import argparse
    
    # Create argument parser
    parser = argparse.ArgumentParser(description="Extract text and create chunks from PDF files")
    parser.add_argument("--force", "-f", action="store_true", help="Force reprocessing of all documents, even if already processed")
    
    # Parse arguments
    args = parser.parse_args()
    
    # Run the script with force_reprocess parameter
    asyncio.run(run_script(force_reprocess=args.force))