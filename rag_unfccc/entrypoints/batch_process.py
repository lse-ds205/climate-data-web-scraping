#!/usr/bin/env python3
"""
Batch Processing Script for Entity Type Analysis
Processes all entities of a type with prompts from a TPI Centre ID and generates aggregated CSV outputs.

Usage:
    # Process all countries with EP4a prompt
    python entrypoints/batch_process.py --entity-type countries --tpi-centre-id EP4a
    
    # Process specific countries only
    python entrypoints/batch_process.py --entity-type countries --entities "Australia,Brazil" --tpi-centre-id EP4a
"""

import sys
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
import json
from datetime import datetime
import logging

# Setup logger early
logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Import functions from other modules
import importlib.util

# Import 4_retrieve functions
retrieve_path = project_root / "entrypoints" / "4_retrieve.py"
spec_retrieve = importlib.util.spec_from_file_location("retrieve_module", retrieve_path)
retrieve_module = importlib.util.module_from_spec(spec_retrieve)
spec_retrieve.loader.exec_module(retrieve_module)
embed_prompt = retrieve_module.embed_prompt
retrieve_chunks = retrieve_module.retrieve_chunks

# Import 5_llm_response functions
llm_path = project_root / "entrypoints" / "5_llm_response.py"
spec_llm = importlib.util.spec_from_file_location("llm_module", llm_path)
llm_module = importlib.util.module_from_spec(spec_llm)
spec_llm.loader.exec_module(llm_module)
setup_llm = llm_module.setup_llm
get_llm_response = llm_module.get_llm_response
process_response = llm_module.process_response

# Import new prompt system
from questions import (
    get_tpi_centre_mapping,
    get_prompt,
    get_project_config,
    get_prompts_for_tpi_centre,
    list_tpi_centres
)

# Import entity manager
from group4py.src.constants.entities import EntityManager, EntityType

# Import output functions
output_path = project_root / "entrypoints" / "6_output.py"
spec_output = importlib.util.spec_from_file_location("output_module", output_path)
output_module = importlib.util.module_from_spec(spec_output)
spec_output.loader.exec_module(output_module)
export_batch_aggregated = output_module.export_batch_aggregated


def get_entities_by_type(entity_type: str, entity_names: Optional[List[str]] = None) -> List[str]:
    """
    Get list of entities for a given type.
    
    Args:
        entity_type: Type of entity ('countries', 'companies', 'banks')
        entity_names: Optional list of specific entity names to filter
        
    Returns:
        List of entity names
    """
    try:
        # Map entity_type string to EntityType enum
        type_map = {
            'countries': EntityType.COUNTRY,
            'companies': EntityType.COMPANY,
            'banks': EntityType.BANK
        }
        
        if entity_type not in type_map:
            raise ValueError(f"Unknown entity type: {entity_type}. Must be one of: {list(type_map.keys())}")
        
        enum_type = type_map[entity_type]
        
        # Create EntityManager but only load the specific entity type we need
        # This avoids loading companies/banks when we only need countries
        from pathlib import Path
        project_root = Path(__file__).resolve().parent.parent
        config_dir = project_root / "data" / "entities"
        
        # Create EntityManager without loading all entities (lazy loading)
        entity_manager = EntityManager(config_dir=config_dir, load_all=False)
        
        # Only load the specific entity type we need (skip others)
        entity_config = entity_manager._configs.get(enum_type)
        if entity_config and entity_config.enabled:
            try:
                entity_manager._load_entity_type(enum_type, entity_config)
            except Exception as e:
                logger.warning(f"Failed to load {entity_type}: {e}")
        
        # Get all entities of this type using the correct method
        entity_list = entity_manager.get_entities_by_type(enum_type)
        
        # Filter to specific entities if provided
        if entity_names:
            # Normalize names for matching
            entity_set = set(name.strip() for name in entity_names)
            original_count = len(entity_list)
            entity_list = [e for e in entity_list if e in entity_set]
            
            # Log which entities were found and which were missing
            found_entities = set(entity_list)
            missing_entities = entity_set - found_entities
            if missing_entities:
                logger.warning(
                    f"Some requested entities not found in {entity_type} list: {missing_entities}. "
                    f"Found {len(found_entities)}/{len(entity_set)} requested entities."
                )
            if not entity_list:
                logger.warning(f"No matching entities found for {entity_type} with names: {entity_names}")
            else:
                logger.info(f"Filtered {entity_type}: {original_count} total -> {len(entity_list)} requested entities")
        
        return entity_list
        
    except Exception as e:
        logger.error(f"Error getting entities for type {entity_type}: {e}")
        # Fallback: return entity_names if provided, otherwise empty
        return entity_names if entity_names else []


def validate_tpi_centre_id(tpi_centre_id: str) -> None:
    """
    Validate that a TPI Centre ID exists in the new prompt system.
    
    Args:
        tpi_centre_id: TPI Centre ID to validate
        
    Raises:
        ValueError: If TPI Centre ID is not found
    """
    mapping = get_tpi_centre_mapping(tpi_centre_id)
    if not mapping:
        available = ', '.join(list_tpi_centres())
        raise ValueError(
            f"TPI Centre ID '{tpi_centre_id}' not found. "
            f"Available TPI Centre IDs: {available}"
        )


def process_entity_question(
    entity_name: str,
    question_id: int,
    question_text: str,
    top_k: int = 3,
    min_similarity: float = 0.1,
    llm_client: Any = None,
    max_retries: int = 2
) -> Dict[str, Any]:
    """
    Process a single entity/question combination.
    
    Args:
        entity_name: Name of the entity
        question_id: Question ID number
        question_text: Full question text
        top_k: Number of chunks to retrieve
        min_similarity: Minimum similarity threshold
        llm_client: Pre-initialized LLM client (optional)
        
    Returns:
        Dictionary with processing results
    """
    result = {
        'entity': entity_name,
        'question_id': question_id,
        'question': question_text,
        'status': 'pending',
        'chunks_retrieved': 0,
        'llm_response': None,
        'error': None
    }
    
    try:
        # Step 1: Retrieve chunks
        logger.info(f"[BATCH] Processing {entity_name} - Question {question_id}")
        
        transformer_embedding, word2vec_embedding = embed_prompt(question_text)
        
        chunks = retrieve_chunks(
            embedded_prompts=(transformer_embedding, word2vec_embedding),
            prompt=question_text,
            top_k=top_k,
            country=entity_name,  # Note: works for any entity type
            min_similarity=min_similarity
        )
        
        if not chunks:
            result['status'] = 'no_chunks'
            result['error'] = 'No chunks found'
            return result
        
        result['chunks_retrieved'] = len(chunks)
        result['chunks'] = chunks  # Store original chunks for metadata lookup
        
        # Step 2: Get LLM response with retry logic
        if llm_client is None:
            llm_client = setup_llm()
        
        # Retry LLM call up to max_retries times
        llm_response = None
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                llm_response = get_llm_response(
                    llm_client=llm_client,
                    question=question_text,
                    chunks=chunks
                )
                if llm_response:
                    break  # Success, exit retry loop
            except Exception as e:
                last_error = str(e)
                if attempt < max_retries:
                    logger.warning(f"[BATCH] LLM call failed (attempt {attempt + 1}/{max_retries + 1}), retrying...")
                    import time
                    time.sleep(1)  # Brief delay before retry
                else:
                    logger.error(f"[BATCH] LLM call failed after {max_retries + 1} attempts: {e}")
        
        if llm_response:
            processed = process_response(
                llm_response=llm_response,
                original_chunks=chunks,
                question=question_text
            )
            result['llm_response'] = processed
            result['status'] = 'success'
        else:
            result['status'] = 'llm_error'
            result['error'] = f'LLM response was None after {max_retries + 1} attempts' + (f': {last_error}' if last_error else '')
            
    except Exception as e:
        logger.error(f"[BATCH] Error processing {entity_name} - Question {question_id}: {e}")
        result['status'] = 'error'
        result['error'] = str(e)
    
    return result


def batch_process(
    entity_type: str,
    tpi_centre_id: str,
    entity_names: Optional[List[str]] = None,
    top_k: int = 3,
    min_similarity: float = 0.1,
    output_format: str = "both"
) -> Dict[str, Any]:
    """
    Batch process multiple entities with prompts from a TPI Centre ID.
    
    Args:
        entity_type: Type of entity ('countries', 'companies', 'banks')
        tpi_centre_id: TPI Centre ID (e.g., 'EP4a')
        entity_names: Optional list of specific entity names to process
        top_k: Number of top chunks to retrieve (overridden by prompt metadata if set)
        min_similarity: Minimum similarity threshold for chunks
        output_format: Output format ("csv", "excel", or "both")
        
    Returns:
        Dictionary with processing results
    """
    print("=" * 80)
    print("BATCH PROCESSING MODE")
    print("=" * 80)
    print(f"Entity Type: {entity_type}")
    print(f"TPI Centre ID: {tpi_centre_id}")
    print(f"Output Format: {output_format}")
    print("=" * 80)
    print()
    
    # Get entities
    entities = get_entities_by_type(entity_type, entity_names)
    
    if not entities:
        return {
            'status': 'error',
            'error': f'No entities found for type {entity_type}',
            'results': []
        }
    
    # Initialize LLM client once (reuse for all calls)
    llm_client = None
    try:
        llm_client = setup_llm()
    except Exception as e:
        logger.warning(f"Could not initialize LLM client: {e}. Will initialize per call.")
    
    # Get TPI Centre mapping and prompts
    mapping = get_tpi_centre_mapping(tpi_centre_id)
    if not mapping:
        raise ValueError(f"TPI Centre ID '{tpi_centre_id}' not found")
    
    prompt_ids = mapping.prompt_ids
    
    # Get project config to determine entity type if not provided
    project_config = get_project_config(mapping.project)
    if project_config:
        entity_type = project_config.entity_type
    
    # Process all combinations
    all_results = []
    original_chunks_map = {}  # Map entity_prompt_id -> original chunks
    failures = []  # Track failures for re-run
    
    total = len(entities) * len(prompt_ids)
    current = 0
    
    for entity_name in entities:
        entity_results = []
        
        for prompt_id in prompt_ids:
            current += 1
            prompt = get_prompt(prompt_id)
            if not prompt:
                logger.error(f"Prompt {prompt_id} not found")
                continue
            
            # Get prompt text for this entity type
            question_text = prompt.get_text_for_entity(entity_type)
            
            # Use prompt's top_k if available
            prompt_top_k = prompt.metadata.top_k if prompt.metadata.top_k else top_k
            
            print(f"[{current}/{total}] {entity_name} - {prompt_id} (TPI Centre: {tpi_centre_id})")
            
            result = process_entity_question(
                entity_name=entity_name,
                question_id=prompt_id,  # Use prompt_id as identifier
                question_text=question_text,
                top_k=prompt_top_k,
                min_similarity=min_similarity,
                llm_client=llm_client
            )
            
            # Store with prompt_id for aggregation
            result['prompt_id'] = prompt_id
            result['tpi_centre_id'] = tpi_centre_id
            
            # Store original chunks
            key = f"{entity_name}_{prompt_id}"
            if result.get('chunks'):
                original_chunks_map[key] = result['chunks']
            
            entity_results.append(result)
            all_results.append(result)
            
            # Print status
            if result['status'] == 'success':
                print(f"  ✅ Success ({result['chunks_retrieved']} chunks)")
            elif result['status'] == 'no_chunks':
                print(f"  ⚠️  No chunks found")
            else:
                print(f"  ❌ Error: {result.get('error', 'Unknown error')}")
            print()
    
    # Aggregate results by entity
    aggregated_results = {}
    original_chunks_map = {}  # Map entity_question_id -> original chunks
    failures = []  # Track failures for re-run
    
    for result in all_results:
        entity = result['entity']
        if entity not in aggregated_results:
            aggregated_results[entity] = []
        aggregated_results[entity].append(result)
        
        # Store original chunks if available (from retrieval step)
        if 'chunks_retrieved' in result and result.get('chunks'):
            entity_question_key = f"{entity}_{result.get('question_id')}"
            original_chunks_map[entity_question_key] = result.get('chunks', [])
        
        # Track failures for re-run
        if result.get('status') != 'success':
            failures.append({
                'entity': entity,
                'question_id': result.get('question_id'),
                'question': result.get('question', ''),
                'status': result.get('status'),
                'error': result.get('error', 'Unknown error'),
                'chunks_retrieved': result.get('chunks_retrieved', 0)
            })
    
    # Save failures to JSON file for easy re-run
    if failures:
        failures_file = project_root / "outputs" / "failures" / f"failures_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        failures_file.parent.mkdir(parents=True, exist_ok=True)
        with open(failures_file, 'w', encoding='utf-8') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'entity_type': entity_type,
                'tpi_centre_id': tpi_centre_id,
                'total_failures': len(failures),
                'failures': failures
            }, f, indent=2, ensure_ascii=False)
        print(f"📋 Saved {len(failures)} failure(s) to: {failures_file}")
        print(f"   To re-run failures, use: python entrypoints/batch_process.py --retry-failures {failures_file}")
        print()
    
    # Export aggregated CSV
    print("=" * 80)
    print("EXPORTING AGGREGATED RESULTS")
    print("=" * 80)
    
    try:
        output_files = export_batch_aggregated(
            batch_results=aggregated_results,
            entity_type=entity_type,
            question_ids=prompt_ids,  # List of prompt ID strings
            tpi_centre_id=tpi_centre_id,
            output_format=output_format,
            original_chunks_map=original_chunks_map
        )
        
        print(f"✅ Exported {len(output_files)} file(s):")
        for file_path in output_files:
            print(f"   {file_path}")
        
    except Exception as e:
        logger.error(f"Error exporting aggregated results: {e}")
        print(f"❌ Export error: {e}")
        output_files = []
    
    return {
        'status': 'completed',
        'entity_type': entity_type,
        'tpi_centre_id': tpi_centre_id,
        'entities_processed': len(entities),
        'prompts_processed': len(prompt_ids),
        'total_combinations': total,
        'successful': sum(1 for r in all_results if r['status'] == 'success'),
        'failed': sum(1 for r in all_results if r['status'] != 'success'),
        'results': all_results,
        'output_files': output_files
    }


def main():
    """Main entry point for batch processing."""
    parser = argparse.ArgumentParser(
        description="Batch process entities with multiple questions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process all countries with questions 1-5
  python entrypoints/batch_process.py --entity-type countries --questions 1,2,3,4,5
  
  # Process specific countries only
  python entrypoints/batch_process.py --entity-type countries --entities "Australia,Brazil" --questions 9
  
  # Process companies with all questions
  python entrypoints/batch_process.py --entity-type companies --questions all
  
  # Process banks with specific questions, Excel only
  python entrypoints/batch_process.py --entity-type banks --questions 1,2,3 --output-format excel
        """
    )
    
    parser.add_argument(
        "--entity-type",
        type=str,
        required=True,
        choices=['countries', 'companies', 'banks'],
        help="Type of entity to process"
    )
    
    parser.add_argument(
        "--questions",
        type=str,
        default=None,
        help="Comma-separated question IDs (e.g., '1,2,3') or 'all' for all questions (optional if --tpi-centre-id is used)"
    )
    
    parser.add_argument(
        "--tpi-centre-id",
        type=str,
        default=None,
        help="TPI Centre ID to use (e.g., 'net_zero_centre'). Overrides --questions if provided."
    )
    
    parser.add_argument(
        "--entities",
        type=str,
        default=None,
        help="Optional: Comma-separated list of specific entity names to process (default: all)"
    )
    
    parser.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="Number of chunks to retrieve per question (default: 3)"
    )
    
    parser.add_argument(
        "--min-similarity",
        type=float,
        default=0.1,
        help="Minimum similarity threshold (default: 0.1)"
    )
    
    parser.add_argument(
        "--output-format",
        type=str,
        default="both",
        choices=['csv', 'excel', 'both'],
        help="Output format (default: both)"
    )
    
    args = parser.parse_args()
    
    # Validate TPI Centre ID
    if not args.tpi_centre_id:
        print("❌ --tpi-centre-id is required")
        print(f"\nAvailable TPI Centre IDs: {', '.join(list_tpi_centres())}")
        return
    
    try:
        validate_tpi_centre_id(args.tpi_centre_id)
        mapping = get_tpi_centre_mapping(args.tpi_centre_id)
        print(f"📋 TPI Centre ID: {args.tpi_centre_id}")
        print(f"   Project: {mapping.project}")
        print(f"   Description: {mapping.description}")
        print(f"   Prompts: {', '.join(mapping.prompt_ids)}")
        print()
    except ValueError as e:
        print(f"❌ {e}")
        return
    
    # Parse entity names if provided
    entity_names = None
    if args.entities:
        entity_names = [name.strip() for name in args.entities.split(',')]
    
    # Run batch processing
    results = batch_process(
        entity_type=args.entity_type,
        tpi_centre_id=args.tpi_centre_id,
        entity_names=entity_names,
        top_k=args.top_k,
        min_similarity=args.min_similarity,
        output_format=args.output_format
    )
    
    # Print summary
    print()
    print("=" * 80)
    print("BATCH PROCESSING SUMMARY")
    print("=" * 80)
    print(f"Status: {results['status']}")
    print(f"Entities Processed: {results['entities_processed']}")
    print(f"Prompts Processed: {results['prompts_processed']}")
    print(f"Total Combinations: {results['total_combinations']}")
    print(f"Successful: {results['successful']}")
    print(f"Failed: {results['failed']}")
    print("=" * 80)


if __name__ == "__main__":
    main()

