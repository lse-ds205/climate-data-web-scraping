"""Database operations for document scraping."""

import logging
from datetime import datetime
from typing import List
import uuid
from pathlib import Path
import sys
from sqlalchemy import text

project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))
import group4py
from databases.docker_proxy import get_database_connection
from databases.models import NDCDocumentORM
from schemas.db_pydantic import NDCDocumentModel
from exceptions import DatabaseConnectionError, DocumentValidationError
from scrape.document_type import infer_document_type

logger = logging.getLogger(__name__)
db = get_database_connection()


def _parse_datetime(dt_str):
    """Parse datetime string from database into datetime object."""
    if dt_str is None:
        return None
    if isinstance(dt_str, datetime):
        return dt_str
    if isinstance(dt_str, str):
        # Try parsing with timezone info
        try:
            # Handle PostgreSQL timestamp format with timezone (e.g., '2025-10-23 00:14:14.922611+00')
            # Remove microseconds and timezone for simpler parsing
            dt_str_clean = dt_str.strip()
            # Try parsing with fromisoformat first (handles most cases)
            if '+' in dt_str_clean:
                # Split on '+' to remove timezone
                dt_str_clean = dt_str_clean.split('+')[0].strip()
            elif dt_str_clean.endswith('Z'):
                dt_str_clean = dt_str_clean[:-1].strip()
            
            # Replace space with T for ISO format
            if ' ' in dt_str_clean and 'T' not in dt_str_clean:
                dt_str_clean = dt_str_clean.replace(' ', 'T', 1)
            
            return datetime.fromisoformat(dt_str_clean)
        except (ValueError, AttributeError):
            # Fallback to strptime
            try:
                # Remove microseconds if present
                dt_str_no_micro = dt_str.split('.')[0] if '.' in dt_str else dt_str
                return datetime.strptime(dt_str_no_micro, '%Y-%m-%d %H:%M:%S')
            except:
                logger.warning(f"Could not parse datetime: {dt_str}")
                return None
    return None


def retrieve_allowed_countries() -> List[str]:
    """
    Retrieve the list of allowed countries from the entity system (JSON file).
    This uses the EntityManager as the single source of truth for countries.
    
    Returns:
        List of country names that should be scraped
        
    Raises:
        DatabaseConnectionError: If entity system fails to load
    """
    logger.info("Retrieving allowed countries from entity system")
    
    try:
        from group4py.src.constants.entities import EntityManager, EntityType
        from pathlib import Path
        
        # Get the config directory (assuming we're in the project root structure)
        # Try to find the data/entities directory relative to this file
        current_file = Path(__file__)
        # Navigate from group4py/src/scrape/db_operations.py to project root
        project_root = current_file.parent.parent.parent.parent
        config_dir = project_root / "data" / "entities"
        
        # Create EntityManager and load countries
        entity_manager = EntityManager(config_dir=config_dir, load_all=False)
        entity_config = entity_manager._configs.get(EntityType.COUNTRY)
        if entity_config and entity_config.enabled:
            entity_manager._load_entity_type(EntityType.COUNTRY, entity_config)
        
        countries = entity_manager.get_entities_by_type(EntityType.COUNTRY)
        logger.info(f"Retrieved {len(countries)} allowed countries from entity system")
        return sorted(countries)  # Return sorted for consistency
    except Exception as e:
        logger.error(f"Entity system error: {str(e)}")
        # Fallback to database if entity system fails
        logger.warning("Falling back to database countries table")
        try:
            with db.Session() as session:
                result = session.execute(text("SELECT id FROM countries ORDER BY id"))
                countries = [row[0] for row in result]
                logger.info(f"Retrieved {len(countries)} allowed countries from database (fallback)")
                return countries
        except Exception as db_error:
            logger.error(f"Database connection error: {str(db_error)}")
            raise DatabaseConnectionError(f"Failed to retrieve countries: {str(e)}") from e


def retrieve_existing_documents() -> List[NDCDocumentModel]:
    """
    Retrieve existing documents from the database.
    
    Returns:
        List of documents currently in the database
        
    Raises:
        DatabaseConnectionError: If database connection fails
    """
    logger.info("Retrieving existing documents from database")
    
    try:
        # Check if we're using Docker proxy mode (doesn't support ORM)
        from databases.docker_proxy import DockerProxyConnection
        if isinstance(db, DockerProxyConnection):
            # Use raw SQL for Docker proxy
            logger.info("Using raw SQL query (Docker proxy mode)")
            with db.Session() as session:
                result = session.execute(text("""
                    SELECT doc_id, country, title, url, language, submission_date,
                           file_path, file_size, scraped_at, downloaded_at, processed_at,
                           last_download_attempt, download_error, download_attempts, extracted_text,
                           created_at, updated_at
                    FROM documents
                """))
                existing_docs = []
                for row in result:
                    # Parse UUID
                    doc_id = row[0]
                    if isinstance(doc_id, str):
                        doc_id = uuid.UUID(doc_id)
                    
                    doc_data = {
                        "doc_id": doc_id,
                        "country": row[1] or "",
                        "title": row[2],
                        "url": row[3] or "",  # url is required, use empty string if None
                        "language": row[4],
                        "submission_date": row[5],  # Already a date or None
                        "file_path": row[6],
                        "file_size": row[7],
                        "scraped_at": _parse_datetime(row[8]),
                        "downloaded_at": _parse_datetime(row[9]),
                        "processed_at": _parse_datetime(row[10]),
                        "last_download_attempt": _parse_datetime(row[11]),
                        "download_error": row[12],
                        "download_attempts": row[13] or 0,
                        "extracted_text": row[14],
                        "created_at": _parse_datetime(row[15]) or datetime.now(),  # Use default if None
                        "updated_at": _parse_datetime(row[16]) or datetime.now(),  # Use default if None
                    }
                    existing_docs.append(NDCDocumentModel(**doc_data))
                logger.info(f"Retrieved {len(existing_docs)} existing documents from database")
                return existing_docs
        else:
            # Use ORM for regular connections
            with db.Session() as session:
                db_documents = session.query(NDCDocumentORM).all()
                existing_docs = [_convert_db_to_model(db_doc) for db_doc in db_documents]
                logger.info(f"Retrieved {len(existing_docs)} existing documents from database")
                return existing_docs
    except Exception as e:
        logger.error(f"Database connection error: {str(e)}")
        raise DatabaseConnectionError(f"Database connection failed: {str(e)}") from e


def insert_new_documents(new_docs: List[NDCDocumentModel]) -> int:
    """
    Insert new documents into the database.
    
    Args:
        new_docs: List of new documents to insert
        
    Returns:
        Number of successfully inserted documents
        
    Raises:
        DatabaseConnectionError: If database connection fails
        DocumentValidationError: If document validation fails
    """
    if not new_docs:
        logger.info("No new documents to insert")
        return 0
    
    logger.info(f"Inserting {len(new_docs)} new documents into database")
    
    try:
        # Check if we're using Docker proxy mode
        from databases.docker_proxy import DockerProxyConnection
        if isinstance(db, DockerProxyConnection):
            # Use raw SQL for Docker proxy
            logger.info("Using raw SQL INSERT (Docker proxy mode)")
            inserted_count = 0
            with db.Session() as session:
                for doc in new_docs:
                    try:
                        doc_id = uuid.uuid5(uuid.NAMESPACE_URL, doc.url)
                        # Infer document_type if not already set (KEY METADATA)
                        document_type = doc.document_type or infer_document_type(
                            url=doc.url,
                            title=doc.title
                        )
                        sql = text("""
                            INSERT INTO documents (doc_id, country, title, url, language, submission_date, scraped_at, document_type)
                            VALUES (:doc_id, :country, :title, :url, :language, :submission_date, :scraped_at, :document_type)
                        """)
                        session.execute(sql, {
                            'doc_id': str(doc_id),
                            'country': doc.country,
                            'title': doc.title,
                            'url': doc.url,
                            'language': doc.language,
                            'submission_date': doc.submission_date,
                            'scraped_at': datetime.now(),
                            'document_type': document_type  # KEY METADATA
                        })
                        inserted_count += 1
                    except Exception as e:
                        logger.error(f"Error inserting document {doc.url}: {str(e)}")
                        continue
                
                session.commit()
                logger.info(f"Successfully inserted {inserted_count} new documents")
                return inserted_count
        else:
            # Use ORM for regular connections
            with db.Session() as session:
                db_documents = []
                for doc in new_docs:
                    try:
                        db_doc = _convert_base_to_db(doc)
                        db_documents.append(db_doc)
                    except Exception as e:
                        logger.error(f"Error creating database object for {doc.url}: {str(e)}")
                        raise DocumentValidationError(f"Document validation failed for {doc.url}: {str(e)}") from e
                
                if not db_documents:
                    logger.warning("No valid documents to insert after conversion")
                    return 0
                
                session.add_all(db_documents)
                session.commit()
                logger.info(f"Successfully inserted {len(db_documents)} new documents")
                return len(db_documents)
    except (DatabaseConnectionError, DocumentValidationError):
        raise
    except Exception as e:
        logger.error(f"Error during document insertion: {str(e)}")
        raise DatabaseConnectionError(f"Document insertion failed: {str(e)}") from e


def update_existing_documents(updated_docs: List[NDCDocumentModel]) -> int:
    """
    Update existing documents in the database with new metadata.
    
    Args:
        updated_docs: List of documents with updated metadata
        
    Returns:
        Number of successfully updated documents
        
    Raises:
        DatabaseConnectionError: If database connection fails
    """
    if not updated_docs:
        logger.info("No documents to update")
        return 0
    
    logger.info(f"Updating {len(updated_docs)} existing documents in database")
    
    try:
        # Check if we're using Docker proxy mode
        from databases.docker_proxy import DockerProxyConnection
        if isinstance(db, DockerProxyConnection):
            # Use raw SQL for Docker proxy
            logger.info("Using raw SQL UPDATE (Docker proxy mode)")
            updated_count = 0
            with db.Session() as session:
                for doc in updated_docs:
                    try:
                        sql = text("""
                            UPDATE documents 
                            SET title = :title,
                                language = :language,
                                submission_date = :submission_date,
                                country = :country,
                                updated_at = :updated_at
                            WHERE url = :url
                        """)
                        result = session.execute(sql, {
                            'title': doc.title,
                            'language': doc.language,
                            'submission_date': doc.submission_date,
                            'country': doc.country,
                            'updated_at': datetime.now(),
                            'url': doc.url
                        })
                        # Note: result.rowcount doesn't work with Docker proxy, so we assume success
                        updated_count += 1
                        logger.debug(f"Updated document: {doc.url}")
                    except Exception as e:
                        logger.error(f"Error updating document {doc.url}: {str(e)}")
                        continue
                
                session.commit()
                logger.info(f"Successfully updated {updated_count} documents")
                return updated_count
        else:
            # Use ORM for regular connections
            with db.Session() as session:
                updated_count = 0
                
                for doc in updated_docs:
                    try:
                        existing_doc = session.query(NDCDocumentORM).filter(NDCDocumentORM.url == doc.url).first()
                        
                        if existing_doc:
                            _update_document_metadata(existing_doc, doc)
                            updated_count += 1
                            logger.debug(f"Updated document: {existing_doc.doc_id}")
                        else:
                            logger.warning(f"Document not found for update: {doc.url}")
                    except Exception as e:
                        logger.error(f"Error updating document {doc.url}: {str(e)}")
                        continue
                
                session.commit()
                logger.info(f"Successfully updated {updated_count} documents")
                return updated_count
    except Exception as e:
        logger.error(f"Error during document updates: {str(e)}")
        raise DatabaseConnectionError(f"Document update failed: {str(e)}") from e


def _convert_db_to_model(db_doc: NDCDocumentORM) -> NDCDocumentModel:
    """Convert SQLAlchemy NDCDocumentORM to NDCDocumentModel."""
    # Create a dictionary of non-None attributes to pass to NDCDocumentModel
    doc_data = {
        "doc_id": db_doc.doc_id,
        "country": db_doc.country,
        "url": db_doc.url,
        "title": db_doc.title,
        "language": db_doc.language,
        "submission_date": db_doc.submission_date,
        "file_path": db_doc.file_path,
        "file_size": db_doc.file_size,
        "scraped_at": db_doc.scraped_at,
        "downloaded_at": db_doc.downloaded_at,
        "processed_at": db_doc.processed_at,
        "last_download_attempt": db_doc.last_download_attempt,
        "download_error": db_doc.download_error,
        "download_attempts": db_doc.download_attempts or 0,
        "extracted_text": db_doc.extracted_text,
        "document_type": db_doc.document_type,  # KEY METADATA
    }
    
    # Only add created_at and updated_at if they're not None
    if db_doc.created_at is not None:
        doc_data["created_at"] = db_doc.created_at
    
    if db_doc.updated_at is not None:
        doc_data["updated_at"] = db_doc.updated_at
    
    return NDCDocumentModel(**doc_data)


def _convert_base_to_db(doc: NDCDocumentModel) -> NDCDocumentORM:
    """Convert NDCDocumentModel to SQLAlchemy NDCDocumentORM."""
    doc_id = uuid.uuid5(uuid.NAMESPACE_URL, doc.url)
    # Infer document_type if not already set (KEY METADATA)
    document_type = doc.document_type or infer_document_type(
        url=doc.url,
        title=doc.title
    )
    return NDCDocumentORM(
        doc_id=doc_id,
        country=doc.country,
        title=doc.title,
        url=doc.url,
        language=doc.language,
        submission_date=doc.submission_date,
        scraped_at=datetime.now(),
        document_type=document_type  # KEY METADATA
    )


def _update_document_metadata(existing_doc: NDCDocumentORM, new_doc: NDCDocumentModel) -> None:
    """Update existing document with new metadata."""
    existing_doc.title = new_doc.title
    existing_doc.language = new_doc.language
    existing_doc.submission_date = new_doc.submission_date
    existing_doc.country = new_doc.country
    existing_doc.updated_at = datetime.now()


def filter_documents_by_countries(documents: List[NDCDocumentModel], allowed_countries: List[str]) -> tuple[List[NDCDocumentModel], List[NDCDocumentModel]]:
    """
    Filter documents to only include those from allowed countries.
    
    Args:
        documents: List of all scraped documents
        allowed_countries: List of country names to include
        
    Returns:
        Tuple of (filtered_documents, excluded_documents)
    """
    if not allowed_countries:
        logger.warning("No allowed countries specified - returning all documents")
        return documents, []
    
    # Create a set for faster lookups (case-insensitive)
    allowed_set = {country.lower().strip() for country in allowed_countries}
    
    filtered = []
    excluded = []
    
    for doc in documents:
        doc_country = doc.country.lower().strip() if doc.country else ""
        
        if doc_country in allowed_set:
            filtered.append(doc)
        else:
            excluded.append(doc)
    
    logger.info(f"Filtered documents: {len(filtered)} included, {len(excluded)} excluded from {len(documents)} total")
    
    if excluded:
        # Log first few excluded countries for debugging
        excluded_countries = list(set([doc.country for doc in excluded[:10]]))
        logger.info(f"Sample of excluded countries: {', '.join(excluded_countries[:5])}")
    
    return filtered, excluded 