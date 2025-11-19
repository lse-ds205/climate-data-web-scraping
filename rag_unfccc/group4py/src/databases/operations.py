from datetime import datetime
import sys
import uuid
from pathlib import Path
from sqlalchemy import text
import logging
from typing import List, Optional, Dict, Any
import traceback
import json

project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))
import group4py
from databases.models import NDCDocumentORM
from databases.auth import PostgresConnection

logger = logging.getLogger(__name__)


def check_document_processed(session, doc_id: str) -> tuple[bool, Optional[NDCDocumentORM]]:
    """
    Check if a document has already been processed.
    
    Args:
        doc_id: Document ID to check (string filename)
        
    Returns:
        Tuple of (is_processed, document) where is_processed is True if document exists
    """

    try:
        # Convert string doc_id to UUID using deterministic UUID5 - SAME AS PROCESSING CODE
        doc_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, doc_id)
        
        # Check if we're using Docker proxy (which only supports raw SQL)
        from databases.docker_proxy import DockerProxyConnection
        if hasattr(session, '_DockerProxySession__proxy') or session.__class__.__name__ == 'DockerProxySession':
            # Use raw SQL for Docker proxy
            result = session.execute(text("""
                SELECT doc_id, country, title, url, language, submission_date, 
                       scraped_at, processed_at, updated_at
                FROM documents 
                WHERE doc_id = :doc_uuid
                LIMIT 1
            """), {'doc_uuid': str(doc_uuid)})
            row = result.fetchone()
            if row:
                # Manually create NDCDocumentORM object from row data
                document = NDCDocumentORM()
                document.doc_id = uuid.UUID(row[0]) if isinstance(row[0], str) else row[0]
                document.country = row[1]
                document.title = row[2]
                document.url = row[3]
                document.language = row[4]
                document.submission_date = row[5]
                document.scraped_at = row[6]
                document.processed_at = row[7]
                document.updated_at = row[8]
                is_processed = document.processed_at is not None
                return is_processed, document
            else:
                return False, None
        else:
            # Use ORM for regular connections
            document = session.query(NDCDocumentORM).filter(NDCDocumentORM.doc_id == doc_uuid).first()
            if document:
                # Check if document has been processed (has processed_at timestamp)
                is_processed = document.processed_at is not None
                return is_processed, document
            else:
                return False, None
    finally:
        session.close()

def upload(session, items: List, table: str = None) -> bool:
    """
    Upload items to the database.
    
    Args:
        items: List of SQLAlchemy ORM objects to upload
        table: Table name (not used, kept for compatibility)
        
    Returns:
        True if successful, False otherwise
    """
    if not items:
        logger.warning("No items to upload")
        return True
        
    try:
        # Debug first item to check types
        if items:
            first_item = items[0]
            logger.debug(f"Uploading {len(items)} items of type: {type(first_item).__name__}")
            
            # Special debugging for LogicalRelationshipORM
            if hasattr(first_item, 'source_chunk_id'):
                logger.debug(f"First relationship: id={first_item.id} (type: {type(first_item.id)}), "
                            f"source={first_item.source_chunk_id} (type: {type(first_item.source_chunk_id)}), "
                            f"target={first_item.target_chunk_id} (type: {type(first_item.target_chunk_id)})")
        
        # Check if we're using Docker proxy (which only supports raw SQL)
        from databases.docker_proxy import DockerProxyConnection
        from databases.models import DocChunkORM, LogicalRelationshipORM
        
        if hasattr(session, '_DockerProxySession__proxy') or session.__class__.__name__ == 'DockerProxySession':
            # Use raw SQL for Docker proxy
            logger.debug("Using raw SQL for upload (Docker proxy mode)")
            
            for i, item in enumerate(items):
                try:
                    # Determine item type and use appropriate INSERT SQL
                    if isinstance(item, NDCDocumentORM):
                        session.execute(text("""
                            INSERT INTO documents (doc_id, country, title, url, language, submission_date, scraped_at, processed_at, updated_at)
                            VALUES (:doc_id, :country, :title, :url, :language, :submission_date, :scraped_at, :processed_at, :updated_at)
                        """), {
                            'doc_id': str(item.doc_id),
                            'country': item.country,
                            'title': item.title,
                            'url': item.url,
                            'language': item.language,
                            'submission_date': item.submission_date,
                            'scraped_at': item.scraped_at or datetime.now(),
                            'processed_at': item.processed_at,
                            'updated_at': item.updated_at or datetime.now()
                        })
                    elif isinstance(item, DocChunkORM):
                        session.execute(text("""
                            INSERT INTO doc_chunks (id, doc_id, chunk_index, page, content, transformer_embedding, word2vec_embedding, created_at)
                            VALUES (:id, :doc_id, :chunk_index, :page, :content, :transformer_embedding, :word2vec_embedding, :created_at)
                        """), {
                            'id': str(item.id),
                            'doc_id': str(item.doc_id),
                            'chunk_index': item.chunk_index,
                            'page': getattr(item, 'page', None),
                            'content': item.content,
                            'transformer_embedding': getattr(item, 'transformer_embedding', None),
                            'word2vec_embedding': getattr(item, 'word2vec_embedding', None),
                            'created_at': getattr(item, 'created_at', None) or datetime.now()
                        })
                    elif isinstance(item, LogicalRelationshipORM):
                        # Validate UUIDs
                        item_id = str(item.id) if not isinstance(item.id, str) else item.id
                        source_id = str(item.source_chunk_id) if not isinstance(item.source_chunk_id, str) else item.source_chunk_id
                        target_id = str(item.target_chunk_id) if not isinstance(item.target_chunk_id, str) else item.target_chunk_id
                        
                        # Ensure confidence is never None or invalid
                        confidence_value = getattr(item, 'confidence', None)
                        if confidence_value is None or confidence_value < 0.0:
                            confidence_value = 0.1  # Default minimum confidence
                        elif confidence_value > 1.0:
                            confidence_value = 1.0
                        
                        session.execute(text("""
                            INSERT INTO logical_relationships (id, source_chunk_id, target_chunk_id, relationship_type, confidence, evidence, method, created_at)
                            VALUES (:id, :source_chunk_id, :target_chunk_id, :relationship_type, :confidence, :evidence, :method, :created_at)
                        """), {
                            'id': item_id,
                            'source_chunk_id': source_id,
                            'target_chunk_id': target_id,
                            'relationship_type': item.relationship_type,
                            'confidence': confidence_value,
                            'evidence': getattr(item, 'evidence', None),
                            'method': getattr(item, 'method', 'rule_based'),
                            'created_at': item.created_at or datetime.now()
                        })
                    else:
                        logger.warning(f"Unknown item type: {type(item).__name__}, skipping")
                        
                except Exception as item_error:
                    logger.error(f"Error adding item {i} of type {type(item).__name__}: {item_error}")
                    continue
            
            session.commit()
            logger.info(f"Successfully uploaded {len(items)} items to database")
            return True
        else:
            # Use ORM for regular connections
            for i, item in enumerate(items):
                try:
                    # Validate UUID fields for LogicalRelationshipORM
                    if hasattr(item, 'source_chunk_id'):
                        # Ensure all UUID fields are proper UUID objects
                        if isinstance(item.id, str):
                            item.id = uuid.UUID(item.id)
                        if isinstance(item.source_chunk_id, str):
                            item.source_chunk_id = uuid.UUID(item.source_chunk_id)
                        if isinstance(item.target_chunk_id, str):
                            item.target_chunk_id = uuid.UUID(item.target_chunk_id)
                    
                    session.add(item)
                    
                except Exception as item_error:
                    logger.error(f"Error adding item {i}: {item_error}")
                    # Skip this item and continue
                    continue
            
            session.commit()
            logger.info(f"Successfully uploaded {len(items)} items to database")
            return True
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error uploading items to database: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Additional debugging for UUID-related errors
        if "UUID" in str(e) or "sentinel" in str(e):
            logger.error("UUID-related error detected. Checking item types...")
            for i, item in enumerate(items[:3]):  # Check first 3 items
                if hasattr(item, 'source_chunk_id'):
                    logger.error(f"Item {i}: id={item.id} ({type(item.id)}), "
                                f"source={item.source_chunk_id} ({type(item.source_chunk_id)}), "
                                f"target={item.target_chunk_id} ({type(item.target_chunk_id)})")
        
        return False
    finally:
        session.close()


def update_processed(session, model_class, doc_id: str, chunks=None, table: str = None):
        """
        Update the processed status of a document.
        
        Args:
            model_class: SQLAlchemy model class (NDCDocumentORM)
            doc_id: Document ID to update (string filename)
            chunks: Chunks data (optional)
            table: Table name (not used, kept for compatibility)
        """
        try:
            # Convert string doc_id to UUID using deterministic UUID5 - SAME AS PROCESSING CODE
            doc_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, doc_id)
            
            # Check if we're using Docker proxy (which only supports raw SQL)
            from databases.docker_proxy import DockerProxyConnection
            if hasattr(session, '_DockerProxySession__proxy') or session.__class__.__name__ == 'DockerProxySession':
                # Use raw SQL for Docker proxy
                result = session.execute(text("""
                    UPDATE documents
                    SET processed_at = :processed_at
                    WHERE doc_id = :doc_uuid
                """), {
                    'processed_at': datetime.now(),
                    'doc_uuid': str(doc_uuid)
                })
                session.commit()
                logger.info(f"Updated processed status for document {doc_id}")
            else:
                # Use ORM for regular connections
                document = session.query(model_class).filter(model_class.doc_id == doc_uuid).first()
                if document:
                    document.processed_at = datetime.now()
                    if chunks:
                        # Optionally store chunk count or other metadata
                        pass
                    session.commit()
                    logger.info(f"Updated processed status for document {doc_id}")
                else:
                    logger.warning(f"Document {doc_id} not found for update")
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating processed status for {doc_id}: {e}")
        finally:
            session.close()



class LLMResponseUploader:
    """Handles uploading LLM responses to PostgreSQL database using SQLAlchemy."""
    
    def __init__(self):
        """Initialize database connection using auth module."""
        self.db = PostgresConnection()
        logger.info("Database connection initialized via auth module")
    
    def is_valid_uuid(self, uuid_string: str) -> bool:
        """
        Validate if a string is a proper UUID format.
        
        Args:
            uuid_string: String to validate
            
        Returns:
            True if valid UUID format, False otherwise
        """
        try:
            # Try to create a UUID object from the string
            uuid.UUID(str(uuid_string))
            return True
        except (ValueError, TypeError):
            return False
    
    def validate_prerequisites(self, session, country_name: str, question_numbers: List[int]) -> Dict[str, Any]:
        """
        Validate that required countries and questions exist in database.
        
        Args:
            session: SQLAlchemy session
            country_name: Country name to validate
            question_numbers: List of question numbers to validate
            
        Returns:
            Dict with validation results
        """
        validation_results = {
            'country_exists': False,
            'questions_exist': [],
            'missing_questions': []
        }
        
        # Check if country exists using entity system (primary) or database (fallback)
        try:
            from group4py.src.constants.entities import EntityManager, EntityType
            from pathlib import Path
            
            # Get the config directory
            current_file = Path(__file__)
            project_root = current_file.parent.parent.parent.parent
            config_dir = project_root / "data" / "entities"
            
            # Create EntityManager and check country
            entity_manager = EntityManager(config_dir=config_dir, load_all=False)
            entity_config = entity_manager._configs.get(EntityType.COUNTRY)
            if entity_config and entity_config.enabled:
                entity_manager._load_entity_type(EntityType.COUNTRY, entity_config)
            
            countries = entity_manager.get_entities_by_type(EntityType.COUNTRY)
            validation_results['country_exists'] = country_name in countries
        except Exception:
            # Fallback to database check
            result = session.execute(text("SELECT id FROM countries WHERE id = :country"), 
                                   {"country": country_name})
            validation_results['country_exists'] = result.fetchone() is not None
        
        # Check which questions exist
        for q_num in question_numbers:
            result = session.execute(text("SELECT id FROM questions WHERE id = :question_id"), 
                                   {"question_id": q_num})
            if result.fetchone():
                validation_results['questions_exist'].append(q_num)
            else:
                validation_results['missing_questions'].append(q_num)
        
        return validation_results
    
    def validate_chunk_exists(self, session, chunk_uuid: str) -> bool:
        """
        Validate that a chunk UUID exists in doc_chunks table.
        
        Args:
            session: SQLAlchemy session
            chunk_uuid: UUID string to validate
            
        Returns:
            True if chunk exists, False otherwise
        """
        # First validate UUID format to prevent transaction aborts
        if not self.is_valid_uuid(chunk_uuid):
            logger.warning(f"Invalid UUID format: {chunk_uuid}")
            return False
            
        try:
            result = session.execute(text("SELECT id FROM doc_chunks WHERE id = :chunk_id"), 
                                   {"chunk_id": chunk_uuid})
            return result.fetchone() is not None
        except Exception as e:
            logger.warning(f"Error validating chunk {chunk_uuid}: {e}")
            return False
    
    def extract_chunk_uuid_from_citation(self, citation: Dict[str, Any]) -> Optional[str]:
        """
        Extract the actual chunk UUID from citation data.
        
        The UUID is located in chunk_metadata.id, not the top-level id field.
        
        Args:
            citation: Citation dictionary from LLM response
            
        Returns:
            UUID string or None if not found
        """
        # Primary location: chunk_metadata.id
        chunk_metadata = citation.get('chunk_metadata', {})
        if isinstance(chunk_metadata, dict) and 'id' in chunk_metadata:
            chunk_uuid = str(chunk_metadata['id'])
            logger.debug(f"Found chunk UUID in metadata: {chunk_uuid}")
            return chunk_uuid
        
        # Log the structure for debugging if UUID not found
        logger.warning(f"No chunk UUID found in chunk_metadata.id. Citation structure: {json.dumps(citation, indent=2)}")
        return None
    
    def check_for_duplicates(self, session, country_name: str, question_number: int) -> bool:
        """
        Check if a question-answer already exists for this country-question combination.
        
        Args:
            session: SQLAlchemy session
            country_name: Country name
            question_number: Question number
            
        Returns:
            True if duplicate exists, False otherwise
        """
        result = session.execute(text("""
            SELECT id FROM questions_answers 
            WHERE country = :country AND question = :question
        """), {"country": country_name, "question": question_number})
        
        return result.fetchone() is not None
    
    def upload_single_question(
        self, 
        session,
        country_name: str, 
        question_data: Dict[str, Any], 
        file_metadata: Dict[str, Any]
    ) -> Dict[str, int]:
        """
        Upload a single question's LLM response to database.
        
        Args:
            session: SQLAlchemy session
            country_name: Name of the country
            question_data: Question data from JSON
            file_metadata: Metadata from the JSON file
            
        Returns:
            Statistics for this question upload
        """
        question_number = question_data.get('question_number')
        llm_response = question_data.get('llm_response', {})
        
        if not question_number or not llm_response:
            raise ValueError(f"Invalid question data structure")
        
        # Check for duplicates first
        if self.check_for_duplicates(session, country_name, question_number):
            logger.warning(f"Duplicate found for {country_name} question {question_number}, skipping...")
            return {
                'qa_inserted': 0,
                'citations_inserted': 0,
                'citations_invalid': 0
            }
        
        # Generate UUID for questions_answers record
        qa_uuid = str(uuid.uuid4())
        
        # Extract answer components
        answer = llm_response.get('answer', {})
        summary = answer.get('summary', '')
        detailed_response = answer.get('detailed_response', '')
        citations_data = llm_response.get('citations', [])
        
        # Create timestamp
        timestamp = datetime.now()
        if 'timestamp' in file_metadata:
            try:
                timestamp = datetime.fromisoformat(file_metadata['timestamp'].replace('Z', '+00:00'))
            except:
                pass  # Use current timestamp as fallback
        
        # INSERT QUESTIONS_ANSWERS RECORD FIRST
        session.execute(text("""
            INSERT INTO questions_answers 
            (id, country, timestamp, question, summary, detailed_response)
            VALUES (:id, :country, :timestamp, :question, :summary, :detailed_response)
        """), {
            "id": qa_uuid,
            "country": country_name,
            "timestamp": timestamp,
            "question": question_number,
            "summary": summary,
            "detailed_response": detailed_response
        })
        
        # NOW PROCESS CITATIONS THAT REFERENCE THE EXISTING QUESTIONS_ANSWERS RECORD
        citation_uuids = []
        citations_inserted = 0
        citations_invalid = 0
        
        for citation in citations_data:
            try:
                # Extract chunk UUID from citation
                chunk_uuid = self.extract_chunk_uuid_from_citation(citation)
                
                if not chunk_uuid:
                    logger.warning("No chunk UUID found in citation")
                    citations_invalid += 1
                    continue
                
                # Validate chunk exists in database
                if not self.validate_chunk_exists(session, chunk_uuid):
                    logger.warning(f"Chunk UUID {chunk_uuid} not found in database")
                    citations_invalid += 1
                    continue
                
                # Create citation record (now that questions_answers exists)
                citation_uuid = str(uuid.uuid4())
                
                session.execute(text("""
                    INSERT INTO citations (id, cited_chunk_id, cited_in_answer_id)
                    VALUES (:id, :cited_chunk_id, :cited_in_answer_id)
                """), {
                    "id": citation_uuid,
                    "cited_chunk_id": chunk_uuid,
                    "cited_in_answer_id": qa_uuid
                })
                
                citation_uuids.append(citation_uuid)
                citations_inserted += 1
                
            except Exception as e:
                logger.error(f"Error processing citation: {e}")
                citations_invalid += 1
                continue
        
        logger.info(f"Uploaded question {question_number} for {country_name} with {citations_inserted} citations")
        
        return {
            'qa_inserted': 1,
            'citations_inserted': citations_inserted,
            'citations_invalid': citations_invalid
        }
    
    def upload_llm_response_file(self, json_file_path: Path) -> Dict[str, Any]:
        """
        Upload a single LLM response JSON file to database.
        
        Args:
            json_file_path: Path to the JSON file
            
        Returns:
            Upload statistics and results
        """
        try:
            logger.info(f"Processing file: {json_file_path}")
            
            # Load JSON data
            with open(json_file_path, 'r', encoding='utf-8') as f:
                llm_data = json.load(f)
            
            # Extract metadata
            metadata = llm_data.get('metadata', {})
            country_name = metadata.get('country_name')
            
            if not country_name:
                raise ValueError("No country_name found in metadata")
            
            # Extract questions data
            questions_data = llm_data.get('questions', {})
            if not questions_data:
                raise ValueError("No questions data found")
            
            # Process with database session
            with self.db.get_session() as session:
                # Get question numbers for validation
                question_numbers = []
                for q_key, q_data in questions_data.items():
                    q_num = q_data.get('question_number')
                    if q_num:
                        question_numbers.append(q_num)
                
                # Validate prerequisites
                validation = self.validate_prerequisites(session, country_name, question_numbers)
                
                if not validation['country_exists']:
                    logger.error(f"Country '{country_name}' does not exist in database")
                    return {'success': False, 'error': f"Country '{country_name}' not found"}
                
                if validation['missing_questions']:
                    logger.warning(f"Missing questions in database: {validation['missing_questions']}")
                
                # Process each question
                upload_stats = {
                    'questions_answers_inserted': 0,
                    'citations_inserted': 0,
                    'citations_invalid': 0,
                    'questions_processed': 0
                }
                
                for question_key, question_data in questions_data.items():
                    try:
                        result = self.upload_single_question(
                            session, country_name, question_data, metadata
                        )
                        
                        upload_stats['questions_answers_inserted'] += result['qa_inserted']
                        upload_stats['citations_inserted'] += result['citations_inserted']
                        upload_stats['citations_invalid'] += result['citations_invalid']
                        upload_stats['questions_processed'] += 1
                        
                    except Exception as e:
                        logger.error(f"Error processing question {question_key}: {e}")
                        # Continue with other questions
                        continue
            
            logger.info(f"Successfully uploaded {json_file_path}")
            return {
                'success': True,
                'file': str(json_file_path),
                **upload_stats
            }
            
        except Exception as e:
            logger.error(f"Failed to upload {json_file_path}: {e}")
            return {
                'success': False,
                'file': str(json_file_path),
                'error': str(e)
            }


class LLMUploadManager:
    """Manager class for batch processing LLM response files."""
    
    def __init__(self):
        """Initialize the upload manager."""
        self.uploader = LLMResponseUploader()
    
    def process_single_file(self, file_path: Path) -> Dict[str, Any]:
        """Process a single JSON file."""
        return self.uploader.upload_llm_response_file(file_path)
    
    def process_all_files(self, llm_dir: Path) -> List[Dict[str, Any]]:
        """Process all JSON files in the LLM directory."""
        json_files = list(llm_dir.glob("*.json"))
        
        if not json_files:
            logger.error(f"No JSON files found in {llm_dir}")
            return []
        
        logger.info(f"Found {len(json_files)} JSON files to process")
        
        results = []
        for file_path in json_files:
            result = self.process_single_file(file_path)
            results.append(result)
        
        return results
    
    def print_summary(self, results: List[Dict[str, Any]]):
        """Print upload summary statistics."""
        successful = [r for r in results if r.get('success', False)]
        failed = [r for r in results if not r.get('success', False)]
        
        total_qa = sum(r.get('questions_answers_inserted', 0) for r in successful)
        total_citations = sum(r.get('citations_inserted', 0) for r in successful)
        total_invalid = sum(r.get('citations_invalid', 0) for r in successful)
        total_questions = sum(r.get('questions_processed', 0) for r in successful)
        
        print("\n" + "="*60)
        print("UPLOAD SUMMARY")
        print("="*60)
        print(f"Files processed: {len(results)}")
        print(f"Successful: {len(successful)}")
        print(f"Failed: {len(failed)}")
        print(f"Questions processed: {total_questions}")
        print(f"Questions/Answers inserted: {total_qa}")
        print(f"Citations inserted: {total_citations}")
        print(f"Invalid citations skipped: {total_invalid}")
        
        if failed:
            print(f"\nFAILED FILES:")
            for failure in failed:
                print(f"  {failure.get('file', 'Unknown')}: {failure.get('error', 'Unknown error')}")
        
        print("="*60)