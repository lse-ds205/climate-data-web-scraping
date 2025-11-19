"""
Script for generating LLM responses using retrieved chunks.
"""

import sys
from pathlib import Path
import logging
import traceback
from typing import List, Dict, Any, Tuple, Optional
import argparse
import json
from datetime import datetime

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))
import group4py
from helpers.internal import Logger
from databases.operations import LLMUploadManager
from query import (
    LLMClient,
    ResponseProcessor,
    ChunkFormatter,
    ConfidenceClassification
)

logger = logging.getLogger(__name__)


def _extract_document_metadata_from_chunks(chunks: List[Dict[str, Any]]) -> Dict[str, set]:
    """
    Extract unique document types and publication years from chunks.
    
    Args:
        chunks: List of chunk dictionaries with doc_id references
        
    Returns:
        Dictionary with 'document_types' and 'years' as sets
    """
    doc_info = {'document_types': set(), 'years': set()}
    
    # Import here to avoid circular imports
    import importlib.util
    output_path = project_root / "entrypoints" / "6_output.py"
    spec_output = importlib.util.spec_from_file_location("output_module", output_path)
    output_module = importlib.util.module_from_spec(spec_output)
    spec_output.loader.exec_module(output_module)
    get_document_metadata = output_module.get_document_metadata
    
    # Track processed doc_ids to avoid duplicate queries
    processed_docs = set()
    
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        
        # Get doc_id from chunk
        doc_id = chunk.get('doc_id')
        if not doc_id or doc_id in processed_docs:
            continue
        
        processed_docs.add(doc_id)
        
        # Get document metadata
        doc_meta = get_document_metadata(str(doc_id))
        
        if doc_meta.get('document_type'):
            doc_info['document_types'].add(doc_meta['document_type'])
        
        if doc_meta.get('publication_year'):
            doc_info['years'].add(doc_meta['publication_year'])
    
    return doc_info


def _format_document_metadata(doc_info: Dict[str, set]) -> str:
    """
    Format document metadata into a readable string.
    
    Args:
        doc_info: Dictionary with 'document_types' and 'years' sets
        
    Returns:
        Formatted string with document types and years
    """
    parts = []
    
    if doc_info.get('document_types'):
        doc_types = sorted(doc_info['document_types'])
        if len(doc_types) == 1:
            parts.append(f"Document type: {doc_types[0]}")
        else:
            parts.append(f"Document types: {', '.join(doc_types)}")
    
    if doc_info.get('years'):
        years = sorted(doc_info['years'])
        if len(years) == 1:
            parts.append(f"Publication year: {years[0]}")
        else:
            parts.append(f"Publication years: {', '.join(years)}")
    
    if parts:
        return "Source information: " + "; ".join(parts)
    
    return ""


def setup_llm(supports_guided_json: bool = True) -> LLMClient:
    """
    Setup and initialize the LLM client.
    
    Args:
        supports_guided_json: Whether the LLM API supports guided JSON responses
        
    Returns:
        Initialized LLMClient instance
    """
    try:
        logger.info(
            f"[5_LLM_RESPONSE] Setting up LLM client "
            f"(guided_json: {supports_guided_json})..."
        )
        
        llm_client = LLMClient(supports_guided_json=supports_guided_json)
        
        if not llm_client.client:
            raise Exception("Failed to initialize LLM client - check API credentials")
            
        logger.info("[5_LLM_RESPONSE] LLM client setup completed successfully")
        return llm_client
        
    except Exception as e:
        traceback_string = traceback.format_exc()
        logger.error(
            f"[5_LLM_RESPONSE] Error in setup_llm: {e}\n"
            f"Traceback: {traceback_string}"
        )
        raise e


def load_chunks_and_prompt_from_file(filepath: str) -> Tuple[List[Dict[str, Any]], str]:
    """
    Load chunks and prompt from a JSON file.
    
    Args:
        filepath: Path to the JSON file containing chunks and prompt
        
    Returns:
        Tuple of (chunks_list, prompt_string)
        
    Raises:
        ValueError: If prompt is not found in the JSON structure
        FileNotFoundError: If the file doesn't exist
        json.JSONDecodeError: If the JSON is invalid
    """
    try:
        logger.info(f"[5_LLM_RESPONSE] Loading chunks and prompt from file: {filepath}")
        
        # Convert to Path object for better handling
        file_path = Path(filepath)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Chunks file not found: {filepath}")
            
        if not file_path.suffix.lower() == '.json':
            raise ValueError(f"File must be a JSON file, got: {file_path.suffix}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Extract prompt and chunks based on JSON structure
        prompt = None
        chunks = None
        
        if isinstance(data, dict):
            # First check for the metadata structure from 4_retrieve.py
            if 'metadata' in data and isinstance(data['metadata'], dict):
                metadata = data['metadata']
                prompt = metadata.get('query_text') or metadata.get('prompt') or metadata.get('query')
            
            # If no prompt found in metadata, look for direct keys
            if not prompt:
                prompt_keys = ['prompt', 'query', 'question', 'user_prompt', 'user_query']
                for key in prompt_keys:
                    if key in data and data[key]:
                        prompt = data[key]
                        break
            
            # Look for chunks - check for evaluated_chunks first (from 4_retrieve.py)
            if 'evaluated_chunks' in data and isinstance(data['evaluated_chunks'], list):
                chunks = data['evaluated_chunks']
            else:
                # Look for other chunk keys
                chunk_keys = ['chunks', 'retrieved_chunks', 'context_chunks', 'documents']
                for key in chunk_keys:
                    if key in data and isinstance(data[key], list):
                        chunks = data[key]
                        break
            
            # If chunks not found in nested structure, check if the entire dict is chunk data
            if chunks is None and 'content' in data:
                # Single chunk as dict
                chunks = [data]
        elif isinstance(data, list):
            # Direct list of chunks - prompt should be in metadata or first chunk
            chunks = data
            # Try to find prompt in the first chunk's metadata
            if chunks and isinstance(chunks[0], dict):
                chunk_meta = chunks[0].get('metadata', {}) or chunks[0].get('chunk_metadata', {})
                if isinstance(chunk_meta, dict):
                    prompt = (
                        chunk_meta.get('prompt') or 
                        chunk_meta.get('query') or 
                        chunk_meta.get('query_text')
                    )
        else:
            raise ValueError(f"Invalid JSON structure in file: {filepath}")
        
        # Validate that we found both prompt and chunks
        if not prompt:
            # Additional debugging for the specific structure
            logger.error(
                f"[5_LLM_RESPONSE] JSON structure debug: "
                f"{list(data.keys()) if isinstance(data, dict) else type(data)}"
            )
            if isinstance(data, dict) and 'metadata' in data:
                logger.error(
                    f"[5_LLM_RESPONSE] Metadata keys: {list(data['metadata'].keys())}"
                )
            raise ValueError(
                "No prompt found in JSON file. Expected keys: ['query_text' in metadata, "
                "'prompt', 'query', 'question', 'user_prompt', 'user_query']"
            )
        if not chunks:
            raise ValueError(
                "No chunks found in JSON file. Expected keys: ['evaluated_chunks', "
                "'chunks', 'retrieved_chunks', 'context_chunks', 'documents']"
            )
        if not isinstance(chunks, list):
            raise ValueError(f"Chunks must be a list, got: {type(chunks)}")
        
        logger.info(
            f"[5_LLM_RESPONSE] Successfully loaded {len(chunks)} chunks and "
            f"prompt from file"
        )
        logger.info(
            f"[5_LLM_RESPONSE] Prompt: {prompt[:100]}"
            f"{'...' if len(prompt) > 100 else ''}"
        )
        
        return chunks, prompt
        
    except FileNotFoundError as e:
        logger.error(f"[5_LLM_RESPONSE] File not found: {e}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"[5_LLM_RESPONSE] Invalid JSON in file {filepath}: {e}")
        raise
    except ValueError as e:
        logger.error(f"[5_LLM_RESPONSE] Data structure error: {e}")
        raise
    except Exception as e:
        logger.error(
            f"[5_LLM_RESPONSE] Error loading chunks and prompt from file {filepath}: {e}"
        )
        raise


def extract_main_question(query_text: str) -> str:
    """
    Extract the main question from a detailed query that may contain bullet points.
    
    Args:
        query_text: Full query text that may contain detailed instructions
        
    Returns:
        Clean main question without bullet points or detailed instructions
    """
    # Split by common separators that indicate additional instructions
    separators = [
        '\n\nPlease extract:', '\n\nPlease identify:',
        '\n\nPlease analyze:', '\n\nPlease determine:'
    ]
    
    main_question = query_text
    for separator in separators:
        if separator in query_text:
            main_question = query_text.split(separator)[0].strip()
            break
    
    # Clean up any remaining formatting
    main_question = main_question.strip().rstrip('?') + '?'
    
    return main_question


def get_llm_response(
    llm_client: LLMClient, 
    question: str, 
    chunks: List[Dict[str, Any]]
) -> Any:
    """
    Get structured response from LLM using the provided chunks and question.
    
    Args:
        llm_client: Initialized LLM client
        question: User's question/prompt (can be detailed)
        chunks: List of chunk dictionaries to use as context
        
    Returns:
        Structured LLM response (LLMResponseModel or None on error)
    """
    try:
        logger.info(
            f"[5_LLM_RESPONSE] Getting LLM response for question: {question[:100]}..."
        )
        logger.info(f"[5_LLM_RESPONSE] Using {len(chunks)} chunks as context")
        
        # Format chunks for LLM
        chunk_formatter = ChunkFormatter()
        formatted_context = chunk_formatter.format_chunks_for_context(chunks)
        
        # Create prompt using the full detailed question
        full_prompt = llm_client.create_llm_prompt(question, formatted_context)
        
        # Get structured LLM response
        structured_response = llm_client.call_llm(full_prompt)
        
        if not structured_response:
            logger.error("[5_LLM_RESPONSE] No response from LLM")
            return None
        
        logger.info("[5_LLM_RESPONSE] Successfully received structured LLM response")
        return structured_response
        
    except Exception as e:
        traceback_string = traceback.format_exc()
        logger.error(
            f"[5_LLM_RESPONSE] Error in get_llm_response: {e}\n"
            f"Traceback: {traceback_string}"
        )
        return None


def process_response(
    llm_response: Any, 
    original_chunks: List[Dict[str, Any]], 
    question: str, 
    main_question: str = None
) -> Dict[str, Any]:
    """
    Process and validate the LLM response into final JSON format.
    Automatically enriches explanations with document type and publication year from chunk metadata.

    Args:
        llm_response: Structured response from LLM (LLMResponseModel or None)
        original_chunks: Original chunk data for validation
        question: Original detailed question for error context
        main_question: Short version of the question for JSON storage
        
    Returns:
        Final JSON-serializable response dictionary
    """
    try:
        logger.info("[5_LLM_RESPONSE] Processing LLM response...")
        
        # Create response processor
        response_processor = ResponseProcessor()
        
        # Process the response with original chunks for citation validation
        final_response = response_processor.process_llm_response(
            llm_response=llm_response,
            original_chunks=original_chunks
        )
        
        # Override the question field with the short version if provided
        if main_question and 'question' in final_response:
            final_response['question'] = main_question
        
        # Enrich explanation with document metadata from chunks
        if final_response and isinstance(final_response, dict):
            answer = final_response.get('answer', {})
            if isinstance(answer, dict):
                detailed_response = answer.get('detailed_response', '')
                if detailed_response and original_chunks:
                    # Extract unique document types and years from cited chunks
                    doc_info = _extract_document_metadata_from_chunks(original_chunks)
                    if doc_info:
                        # Append document metadata to explanation
                        metadata_text = _format_document_metadata(doc_info)
                        if metadata_text:
                            # Only append if not already present (avoid duplication)
                            if metadata_text.lower() not in detailed_response.lower():
                                answer['detailed_response'] = f"{detailed_response}\n\n{metadata_text}"
                                final_response['answer'] = answer
        
        logger.info("[5_LLM_RESPONSE] Successfully processed LLM response")
        return final_response
        
    except Exception as e:
        traceback_string = traceback.format_exc()
        logger.error(
            f"[5_LLM_RESPONSE] Error in process_response: {e}\n"
            f"Traceback: {traceback_string}"
        )
        
        # Return error response with main question if available
        return {
            "answer": f"Error processing response: {str(e)}",
            "citations": [],
            "confidence": 0.0,
            "question": main_question or question,
            "error": True,
            "error_details": str(e)
        }


def process_country_file(
    country_name: str, 
    retrieve_dir: Path, 
    retrieve_hop_dir: Path
) -> Dict[str, Any]:
    """
    Process a single country by merging data from both retrieve and retrieve_hop directories.
    
    Args:
        country_name: Name of the country to process
        retrieve_dir: Path to the retrieve directory
        retrieve_hop_dir: Path to the retrieve_hop directory
        
    Returns:
        Dictionary containing the processed responses
    """
    try:
        logger.info(f"Processing country: {country_name}")
        
        # Load the country retrieve data to get question structure
        retrieve_file = retrieve_dir / f"{country_name}.json"
        retrieve_hop_file = retrieve_hop_dir / f"{country_name}.json"
        
        # Start with retrieve data as the base structure
        retrieve_data = {}
        if retrieve_file.exists():
            with open(retrieve_file, 'r', encoding='utf-8') as f:
                retrieve_data = json.load(f)
        elif retrieve_hop_file.exists():
            # If only retrieve_hop exists, use that as base
            with open(retrieve_hop_file, 'r', encoding='utf-8') as f:
                retrieve_data = json.load(f)
        else:
            logger.error(f"No data files found for country: {country_name}")
            return {}
        
        # Initialize LLM client and confidence classifier
        llm_client = LLMClient()
        confidence_classifier = ConfidenceClassification()
        
        # Process each question in the retrieve data
        results = {}
        for question_id in retrieve_data.get('questions', {}).keys():
            logger.info(f"Processing question ID {question_id}")
            
            # Merge chunks from both directories
            merged_chunks, full_query_text = merge_chunks_from_directories(
                country_name, question_id, retrieve_dir, retrieve_hop_dir
            )
            
            if not full_query_text or not merged_chunks:
                logger.warning(
                    f"Question ID {question_id} has no valid question text or chunks"
                )
                continue
            
            # Extract just the main question for JSON storage
            main_question = extract_main_question(full_query_text)
            logger.info(f"Main question extracted: {main_question}")
            logger.info(
                f"Using {len(merged_chunks)} merged chunks for question {question_id}"
            )
            
            # Get LLM response using the FULL detailed query (not just main question)
            llm_response = get_llm_response(llm_client, full_query_text, merged_chunks)
            
            # Process the LLM response, but store the main question in the JSON
            processed_response = process_response(
                llm_response, merged_chunks, full_query_text, main_question
            )
            
            # Store the processed response
            results[question_id] = processed_response
        
        # After processing all questions, classify responses
        results = confidence_classifier.classify_response(results, retrieve_data)
        
        return results        
    except Exception as e:
        logger.error(f"Error processing {country_name}: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            "metadata": {
                "country_name": country_name,
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            },
            "questions": {}
        }


def merge_chunks_from_directories(
    country_name: str, 
    question_id: str, 
    retrieve_dir: Path, 
    retrieve_hop_dir: Path
) -> Tuple[List[Dict[str, Any]], str]:
    """
    Merge chunks from both retrieve and retrieve_hop directories for a given
    country and question.
    
    Args:
        country_name: Name of the country
        question_id: ID of the question (e.g., 'question_1')
        retrieve_dir: Path to the retrieve directory
        retrieve_hop_dir: Path to the retrieve_hop directory
        
    Returns:
        Tuple of (merged_chunks_list, question_text)
    """
    try:
        # File paths for both directories
        retrieve_file = retrieve_dir / f"{country_name}.json"
        retrieve_hop_file = retrieve_hop_dir / f"{country_name}.json"
        
        merged_chunks = []
        question_text = None
        chunk_ids_seen = set()  # To avoid duplicates
        
        # Load from retrieve directory
        if retrieve_file.exists():
            logger.info(f"Loading chunks from retrieve file: {retrieve_file}")
            with open(retrieve_file, 'r', encoding='utf-8') as f:
                retrieve_data = json.load(f)
            
            question_data = retrieve_data.get('questions', {}).get(question_id, {})
            if question_data:
                question_text = question_data.get('question')
                chunks = question_data.get('top_k_chunks', [])
                
                for chunk in chunks:
                    chunk_id = chunk.get('id')
                    if chunk_id and chunk_id not in chunk_ids_seen:
                        merged_chunks.append(chunk)
                        chunk_ids_seen.add(chunk_id)
                    elif not chunk_id:  # Handle chunks without IDs
                        merged_chunks.append(chunk)
                
                logger.info(f"Added {len(chunks)} chunks from retrieve directory")
        
        # Load from retrieve_hop directory
        if retrieve_hop_file.exists():
            logger.info(f"Loading chunks from retrieve_hop file: {retrieve_hop_file}")
            with open(retrieve_hop_file, 'r', encoding='utf-8') as f:
                retrieve_hop_data = json.load(f)
            
            question_data = retrieve_hop_data.get('questions', {}).get(question_id, {})
            if question_data:
                # Use question text from retrieve_hop if not already set
                if not question_text:
                    question_text = question_data.get('question')
                
                chunks = question_data.get('top_k_chunks', [])
                new_chunks_count = 0
                
                for chunk in chunks:
                    chunk_id = chunk.get('id')
                    if chunk_id and chunk_id not in chunk_ids_seen:
                        merged_chunks.append(chunk)
                        chunk_ids_seen.add(chunk_id)
                        new_chunks_count += 1
                    elif not chunk_id:  # Handle chunks without IDs
                        merged_chunks.append(chunk)
                        new_chunks_count += 1
                
                logger.info(
                    f"Added {new_chunks_count} new chunks from retrieve_hop directory"
                )
        
        if not question_text:
            logger.warning(f"No question text found for {country_name} - {question_id}")
            question_text = (
                f"Question {question_id.split('_')[1] if '_' in question_id else question_id}"
            )
        
        total_chunks = len(merged_chunks)
        logger.info(
            f"Total merged chunks for {country_name} - {question_id}: {total_chunks}"
        )
        
        return merged_chunks, question_text
        
    except Exception as e:
        logger.error(f"Error merging chunks for {country_name} - {question_id}: {str(e)}")
        logger.error(traceback.format_exc())
        return [], f"Error loading question {question_id}"


def upload_llm_json_responses_to_database(file_path: Optional[str] = None) -> None:
    """
    Thin wrapper function to upload LLM responses to database.
    
    Args:
        file_path: Optional specific file path. If None, processes all files in data/llm/
    """
    manager = LLMUploadManager()
    
    if file_path:
        # Process single file
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            logger.error(f"File not found: {file_path_obj}")
            sys.exit(1)
        
        logger.info(f"Processing single file: {file_path_obj}")
        result = manager.process_single_file(file_path_obj)
        manager.print_summary([result])
    else:
        # Process all files in data/llm directory
        script_dir = Path(__file__).parent
        llm_dir = script_dir.parent / "data" / "llm"
        
        if not llm_dir.exists():
            logger.error(f"LLM directory not found: {llm_dir}")
            sys.exit(1)
        
        logger.info(f"Processing all files in: {llm_dir}")
        results = manager.process_all_files(llm_dir)
        manager.print_summary(results)


@Logger.log(log_file=project_root / "logs/llm_response.log", log_level="INFO")
def main():
    """
    Main execution function for the LLM response pipeline.
    """
    try:
        logger.info("[5_LLM_RESPONSE] Starting LLM response pipeline...")
        
        # Set up directories
        retrieve_dir = project_root / "data" / "retrieve"
        retrieve_hop_dir = project_root / "data" / "retrieve_hop"
        llm_output_dir = project_root / "data" / "llm"
        
        # Create output directory if it doesn't exist
        llm_output_dir.mkdir(parents=True, exist_ok=True)
        
        # Find all JSON files in both retrieve directories
        retrieve_files = set()
        if retrieve_dir.exists():
            retrieve_files.update([f.stem for f in retrieve_dir.glob("*.json")])
        if retrieve_hop_dir.exists():
            retrieve_files.update([f.stem for f in retrieve_hop_dir.glob("*.json")])
        
        if not retrieve_files:
            logger.error(
                f"No JSON files found in {retrieve_dir} or {retrieve_hop_dir}"
            )
            return
        
        logger.info(f"Found {len(retrieve_files)} unique countries to process")
        
        # Process each country
        for country_name in retrieve_files:
            try:
                logger.info(f"Processing country: {country_name}")
                
                # Process the country with merged data from both directories
                llm_results = process_country_file(
                    country_name, retrieve_dir, retrieve_hop_dir
                )
                
                # Create output filename with timestamp
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_filename = f"{country_name}_{timestamp}.json"
                output_path = llm_output_dir / output_filename
                
                # Load original retrieve data to get query texts
                retrieve_file = retrieve_dir / f"{country_name}.json"
                retrieve_hop_file = retrieve_hop_dir / f"{country_name}.json"
                
                retrieve_data = {}
                source_file_name = f"{country_name}.json"
                
                if retrieve_file.exists():
                    with open(retrieve_file, 'r', encoding='utf-8') as f:
                        retrieve_data = json.load(f)
                    source_file_name = retrieve_file.name
                elif retrieve_hop_file.exists():
                    with open(retrieve_hop_file, 'r', encoding='utf-8') as f:
                        retrieve_data = json.load(f)
                    source_file_name = retrieve_hop_file.name                
                # Create the final output structure
                final_output = {
                    "metadata": {
                        "country_name": country_name,
                        "timestamp": datetime.now().isoformat(),
                        "source_file": source_file_name,
                        "description": (
                            f"LLM-generated responses for {country_name} based on "
                            f"merged chunks from retrieve and retrieve_hop"
                        ),
                        "question_count": 0
                    },
                    "questions": {}
                }
                
                # Process each question result - llm_results keys are question IDs
                question_count = 0
                for question_id, question_result in llm_results.items():
                    if question_id == "metadata":  # Skip metadata
                        continue
                    
                    question_count += 1
                    
                    # Get corresponding retrieve data for this question
                    retrieve_question_data = retrieve_data.get(
                        'questions', {}
                    ).get(question_id, {})
                    query_text = retrieve_question_data.get('question', 'Unknown')
                    
                    # Count total chunks used (from both directories)
                    total_chunks_used = len(question_result.get('citations', []))
                    
                    # Build the question structure
                    final_output["questions"][question_id] = {
                        "question_number": (
                            int(question_id.split('_')[1]) 
                            if '_' in question_id else question_count
                        ),
                        "query_text": query_text,
                        "llm_response": question_result,
                        "chunk_count": total_chunks_used
                    }
                
                # Update question count in metadata
                final_output["metadata"]["question_count"] = question_count
                
                # Save the LLM response file
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(final_output, f, indent=2, ensure_ascii=False)
                
                logger.info(
                    f"Saved LLM responses to: {output_path} "
                    f"({question_count} questions processed)"
                )
                
            except Exception as e:
                logger.error(f"Error processing {country_name}: {e}")
                logger.error(traceback.format_exc())
                continue
        
        # Finally, upload the LLM responses to the database
        upload_llm_json_responses_to_database()
        
        logger.info("[5_LLM_RESPONSE] LLM response pipeline completed successfully")
        
    except Exception as e:
        traceback_string = traceback.format_exc()
        logger.error(
            f"[5_LLM_RESPONSE] Error in main: {e}\n"
            f"Traceback: {traceback_string}"
        )
        logger.error(f"Error: {e}")


if __name__ == "__main__":
    """
    Command-line interface for the LLM response generation script.
    
    This script generates LLM responses using retrieved chunks. It can be run in two modes:
    1. Primary mode: Processes all files from the data/retrieve directory
    2. Legacy mode: Accepts a JSON string of chunks via command line argument
    
    Examples:
        # Primary method (processes all files from data/retrieve directory):
        python 5_llm_response.py
        
        # With prompt override:
        python 5_llm_response.py --prompt "Override question?"
        
        # Without guided JSON (fallback mode):
        python 5_llm_response.py --no-guided-json
        
        # Legacy method (JSON string with prompt required):
        python 5_llm_response.py --chunks '[{"id": 1, "content": "test"}]' --prompt "What is this about?"
    """

    parser = argparse.ArgumentParser(
        description='Run the LLM response script with chunks and prompt from JSON files.'
    )
    
    # Optional arguments
    parser.add_argument(
        '--prompt', type=str,
        help='Optional prompt override (if not provided, reads from JSON file)'
    )
    parser.add_argument(
        '--no-guided-json', action='store_true',
        help='Disable guided JSON (use fallback parsing)'
    )
    
    # Legacy support for old argument names
    parser.add_argument(
        '--chunks', type=str,
        help='JSON string of chunks (legacy support).'
    )
    
    args = parser.parse_args()
    
    try:
        if args.chunks:
            # Legacy support: create temporary file from JSON string
            logger.info("Using legacy JSON string input (--chunks parameter)")
            
            try:
                chunks_list = json.loads(args.chunks)
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing chunks JSON string: {e}")
                logger.error(
                    json.dumps(
                        {"error": f"Invalid chunks JSON: {str(e)}"}, 
                        indent=2, ensure_ascii=False
                    )
                )
                sys.exit(1)
            
            # Create temporary file with both chunks and prompt
            import tempfile
            temp_data = {
                'chunks': chunks_list,
                'prompt': args.prompt or "No prompt provided"
            }
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
                json.dump(temp_data, temp_file, indent=2)
                temp_filepath = temp_file.name
            
            try:
                # Override the chunks file path for main()
                sys.argv = [sys.argv[0], temp_filepath]
                main()
            finally:
                # Clean up temporary file
                import os
                os.unlink(temp_filepath)
        else:
            # Primary method: process retrieve files directly
            main()
        
    except Exception as e:
        logger.error(f"Error in main execution: {e}")
        logger.error(
            json.dumps(
                {"error": f"Execution error: {str(e)}"}, 
                indent=2, ensure_ascii=False
            )
        )
        sys.exit(1)