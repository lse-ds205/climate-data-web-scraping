"""
Script for retrieving and evaluating document chunks for RAG system.
"""

import sys
import traceback
from pathlib import Path
from typing import List, Dict, Any, Optional
from sqlalchemy import text
import argparse
import json
import logging
from datetime import datetime
import re

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))
import group4py
from helpers.internal import Logger
from schemas.general import UUIDEncoder
from databases.docker_proxy import get_database_connection
from constants.entities import extract_country_from_query, extract_entities_from_query, EntityType
from evaluator import (
    VectorComparison,
    RegexComparison,
    FuzzyRegexComparison,
    GraphHopRetriever,
)
from embed.transformer import TransformerEmbedding
from embed.word2vec import Word2VecEmbedding
from constants.prompts import (
    QUESTION_PROMPT_1,
    QUESTION_PROMPT_2,
    QUESTION_PROMPT_3,
    QUESTION_PROMPT_4,
    QUESTION_PROMPT_5,
    QUESTION_PROMPT_6,
    QUESTION_PROMPT_7,
    QUESTION_PROMPT_8,
    HOP_KEYWORDS,
    GENERAL_NDC_KEYWORDS
)


QUESTION_PROMPTS = {
    1: QUESTION_PROMPT_1,
    2: QUESTION_PROMPT_2,
    3: QUESTION_PROMPT_3,
    4: QUESTION_PROMPT_4,
    5: QUESTION_PROMPT_5,
    6: QUESTION_PROMPT_6,
    7: QUESTION_PROMPT_7,
    8: QUESTION_PROMPT_8
}
logger = logging.getLogger(__name__)
db = get_database_connection()  # Use Docker proxy on Windows

# Country extraction now handled by the centralized entity management system
# See constants.entities for the new modular approach

def extract_metadata_from_query(query: str) -> Dict[str, Any]:
    """
    Extract all relevant metadata from a query using the entity management system.
    
    Args:
        query: The search query text
        
    Returns:
        Dictionary containing extracted entities and metadata
    """
    # Extract all entity types
    entity_matches = extract_entities_from_query(query)
    
    # Organize by entity type
    metadata = {
        'countries': [],
        'companies': [],
        'banks': [],
        'all_entities': entity_matches
    }
    
    for match in entity_matches:
        if match.entity_type == EntityType.COUNTRY:
            metadata['countries'].append(match.entity_name)
        elif match.entity_type == EntityType.COMPANY:
            metadata['companies'].append(match.entity_name)
        elif match.entity_type == EntityType.BANK:
            metadata['banks'].append(match.entity_name)
    
    # Log extracted metadata
    if any(metadata.values()):
        logger.info(f"[4_RETRIEVE] Extracted metadata from query: {metadata}")
    else:
        logger.info(f"[4_RETRIEVE] No entities detected in query: '{query[:50]}...'")
    
    return metadata


def embed_prompt(prompt):
    """
    Embed a prompt using both transformer and word2vec embedding models.
    
    Args:
        prompt: The text string to embed
        
    Returns:
        tuple: (transformer_embedding, word2vec_embedding) - both as lists of floats
    """
    try:
        w2v_model_path = project_root / "local_models" / "word2vec"
        # Initialize both embedding models
        transformer_model = TransformerEmbedding()
        transformer_model.load_models()
        
        word2vec_model = Word2VecEmbedding()
        word2vec_model.load_global_model(str(w2v_model_path))

        # Embed the prompt using both models
        transformer_embedding = transformer_model.embed_transformer(prompt)
        word2vec_embedding = word2vec_model.embed_text(prompt)
        
        return transformer_embedding, word2vec_embedding
    
    except Exception as e:
        # Log the exception
        logger.info(f"Error embedding prompt: {e}")
        raise e


def evaluate_chunks(
    prompt: str,
    chunks: List[Dict[str, Any]],
    transformer_embedding: List[float] = None,
    word2vec_embedding: List[float] = None
) -> List[Dict[str, Any]]:
    """
    Evaluate chunks using multiple comparison methods: transformer similarity,
    word2vec similarity, regex patterns, and fuzzy matching.
    """
    if not chunks:
        return []

    try:
        chunks_with_similarity = []

        # Initialize VectorComparison with proper database connection
        vector_comp = VectorComparison()
        
        # Get chunk IDs for batch similarity calculation
        chunk_ids = [chunk['id'] for chunk in chunks]
        
        # Calculate transformer similarities
        transformer_similarities = {}
        if transformer_embedding is not None:
            transformer_similarities = vector_comp.batch_similarity_calculation(
                chunk_ids=chunk_ids,
                query_embedding=transformer_embedding,
                embedding_type='transformer'
            )
        
        # Calculate word2vec similarities
        word2vec_similarities = {}
        if word2vec_embedding is not None:
            word2vec_similarities = vector_comp.batch_similarity_calculation(
                chunk_ids=chunk_ids,
                query_embedding=word2vec_embedding,
                embedding_type='word2vec'
            )
        
        # Add both similarity scores to chunks
        for chunk in chunks:
            chunk_id = chunk['id']
            
            # Get transformer similarity
            transformer_score = transformer_similarities.get(chunk_id, 0.0)
            transformer_score = transformer_similarities.get(
                str(chunk_id), transformer_score
            )
            chunk['transformer_similarity'] = transformer_score
            
            # Get word2vec similarity
            word2vec_score = word2vec_similarities.get(chunk_id, 0.0)
            word2vec_score = word2vec_similarities.get(
                str(chunk_id), word2vec_score
            )
            chunk['word2vec_similarity'] = word2vec_score
            
            chunks_with_similarity.append(chunk)
        
        # Initialize comparison engines
        regex_comparison = RegexComparison()
        fuzzy_regex_comparison = FuzzyRegexComparison()
        
        evaluated_chunks = []
        
        for i, chunk in enumerate(chunks_with_similarity):
            chunk_content = chunk.get('content', '')
            if not chunk_content:
                evaluated_chunks.append(chunk)
                continue
            
            # Start with the chunk as-is
            evaluated_chunk = chunk.copy()
            
            # Apply regex evaluation (keyword-based)
            try:
                regex_eval = regex_comparison.evaluate_chunk_score(
                    chunk_content, prompt
                )
                evaluated_chunk['regex_evaluation'] = regex_eval
                evaluated_chunk['regex_score'] = regex_eval['regex_score']
                evaluated_chunk['keyword_matches'] = regex_eval['keyword_matches']
                evaluated_chunk['query_types'] = regex_eval.get('query_types', [])
                
                highlights = regex_comparison.get_keyword_highlights(
                    chunk_content, prompt
                )
                if highlights:
                    evaluated_chunk['keyword_highlights'] = highlights
                
            except Exception as e:
                evaluated_chunk['regex_score'] = 0.0
                evaluated_chunk['keyword_matches'] = 0
                evaluated_chunk['regex_evaluation'] = {'error': str(e)}
            
            # Apply fuzzy regex evaluation (context-based)
            try:
                fuzzy_eval = fuzzy_regex_comparison.evaluate_chunk_relevance(
                    chunk_content, prompt
                )
                evaluated_chunk['fuzzy_evaluation'] = fuzzy_eval
                evaluated_chunk['fuzzy_score'] = fuzzy_eval['final_score']
                evaluated_chunk['semantic_patterns'] = fuzzy_eval.get(
                    'semantic_patterns', []
                )
                
            except Exception as e:
                evaluated_chunk['fuzzy_score'] = 0.0
                evaluated_chunk['fuzzy_evaluation'] = {'error': str(e)}
            
            # Calculate combined score using all available methods
            transformer_score = evaluated_chunk.get('transformer_similarity', 0.0)
            word2vec_score = evaluated_chunk.get('word2vec_similarity', 0.0)
            regex_score = evaluated_chunk.get('regex_score', 0.0)
            fuzzy_score = evaluated_chunk.get('fuzzy_score', 0.0)
            
            # Configurable weights for different scoring methods
            transformer_weight = 0.25  # Transformer similarity
            word2vec_weight = 0.20     # Word2Vec similarity  
            regex_weight = 0.30        # Direct keyword matches
            fuzzy_weight = 0.25        # Fuzzy contextual matching
            
            # Combine scores
            combined_score = (
                transformer_weight * transformer_score +
                word2vec_weight * word2vec_score +
                regex_weight * regex_score +
                fuzzy_weight * fuzzy_score
            )
            
            evaluated_chunk['combined_score'] = combined_score
            
            # Add information about how the score was calculated
            evaluated_chunk['score_weights'] = {
                'transformer_weight': transformer_weight,
                'word2vec_weight': word2vec_weight,
                'regex_weight': regex_weight,
                'fuzzy_weight': fuzzy_weight
            }
            
            # Keep legacy 'similarity_score' for backward compatibility
            evaluated_chunk['similarity_score'] = (
                transformer_score + word2vec_score
            ) / 2
            
            evaluated_chunks.append(evaluated_chunk)
        
        # Sort by combined score (highest first)
        evaluated_chunks.sort(
            key=lambda x: x.get('combined_score', 0), reverse=True
        )
        
        return evaluated_chunks
        
    except Exception as e:
        logger.info(f"Error evaluating chunks: {e}")
        # Return original chunks with 0.0 similarity scores if evaluation fails
        for chunk in chunks:
            if 'transformer_similarity' not in chunk:
                chunk['transformer_similarity'] = 0.0
            if 'word2vec_similarity' not in chunk:
                chunk['word2vec_similarity'] = 0.0
        return chunks


def retrieve_chunks(
    embedded_prompts,
    prompt,
    top_k=20,
    ensure_indices=True,
    country=None,
    n_per_doc=None,
    min_similarity=0.0,
    document_type=None,
    year=None,
    sector=None,
    custom_filter=None,
    entity_type=None,
    entity_name=None
):
    """
    Retrieve and evaluate the most similar chunks from the database using
    comprehensive evaluation with optimized SQL filtering and flexible metadata filtering.
    
    Args:
        embedded_prompts: Tuple of (transformer_embedding, word2vec_embedding)
        prompt: Original text prompt for evaluation
        top_k: Number of top similar chunks to retrieve
        ensure_indices: Whether to ensure vector indices exist before querying
        country: Optional country name to filter documents by (SQL-level optimization)
        n_per_doc: Optional number of chunks to return per document (overrides top_k)
        min_similarity: Minimum similarity threshold (0-1)
        document_type: Optional document type filter (e.g., 'NDC', 'Sustainability Report')
        year: Optional minimum year filter (e.g., 2020)
        sector: Optional sector filter (e.g., 'Technology', 'Energy')
        custom_filter: Optional custom filter function for complex logic
        entity_type: Optional entity type filter ('country', 'company', 'bank')
        entity_name: Optional entity name filter (e.g., 'Apple', 'Angola', 'JPMorgan')
        
    Returns:
        List of dictionaries containing evaluated chunks with comprehensive scores
    """
    try:
        # Unpack the embeddings
        transformer_embedding, word2vec_embedding = embedded_prompts
        
        # Auto-detect entities from query if not provided
        if country is None and entity_name is None:
            country = extract_country_from_query(prompt)
        
        # Extract additional metadata for enhanced filtering
        metadata = extract_metadata_from_query(prompt)
        
        # Determine entity filtering strategy
        entity_filter = None
        if country:
            entity_filter = {'type': 'country', 'name': country, 'field': 'country'}
        elif entity_name and entity_type:
            entity_filter = {'type': entity_type, 'name': entity_name, 'field': entity_type}
        elif entity_name:
            # Try to auto-detect entity type from name
            if entity_name in [match.entity_name for match in metadata.get('all_entities', [])]:
                for match in metadata.get('all_entities', []):
                    if match.entity_name == entity_name:
                        entity_filter = {'type': match.entity_type.value, 'name': entity_name, 'field': match.entity_type.value}
                        break
        
        # Ensure vector indices exist if requested
        if ensure_indices:
            if not VectorComparison.create_vector_indices():
                pass  # Continue anyway
        
        # Build optimized SQL query with entity filtering
        session = db.Session()
        try:
            if entity_filter:
                # Use entity-specific SQL filtering for performance
                # Include all metadata fields needed for source verification
                query = text(f"""
                    SELECT 
                        id, 
                        content, 
                        doc_id, 
                        chunk_data,
                        page,
                        chunk_index,
                        paragraph,
                        language
                    FROM doc_chunks 
                    WHERE LOWER(chunk_data->>'{entity_filter['field']}') = LOWER(:entity_name)
                """)
                result = session.execute(query, {"entity_name": entity_filter['name']})
                logger.info(f"[4_RETRIEVE] Filtering chunks by {entity_filter['type']}: {entity_filter['name']}")
            else:
                # Get all chunks if no entity specified
                # Include all metadata fields needed for source verification
                query = text("""
                    SELECT 
                        id, 
                        content, 
                        doc_id, 
                        chunk_data,
                        page,
                        chunk_index,
                        paragraph,
                        language
                    FROM doc_chunks
                """)
                result = session.execute(query)
                logger.info("[4_RETRIEVE] Retrieving chunks from all entities")
            
            # Convert results to chunk dictionaries with all metadata
            all_chunks = []
            for row in result:
                chunk = {
                    'id': str(row[0]),  # id
                    'content': row[1],  # content
                    'doc_id': str(row[2]),  # doc_id
                    'chunk_data': row[3] if len(row) > 3 else {},  # chunk_data
                    'page': row[4] if len(row) > 4 else None,  # page
                    'chunk_index': row[5] if len(row) > 5 else None,  # chunk_index
                    'paragraph': row[6] if len(row) > 6 else None,  # paragraph
                    'language': row[7] if len(row) > 7 else None  # language
                }
                all_chunks.append(chunk)
            
            session.close()
            
            # Log retrieval statistics
            if all_chunks:
                logger.info(f"[4_RETRIEVE] Retrieved {len(all_chunks)} chunks from database")
                
                # Show entity distribution for debugging
                if not entity_filter:  # Only show entity breakdown if not filtering
                    entity_counts = {}
                    for chunk in all_chunks:
                        chunk_data = chunk.get('chunk_data', {})
                        # Check for different entity types
                        for entity_type in ['country', 'company', 'bank']:
                            entity_name = chunk_data.get(entity_type, 'Unknown')
                            if entity_name != 'Unknown':
                                entity_counts[f"{entity_type}:{entity_name}"] = entity_counts.get(f"{entity_type}:{entity_name}", 0) + 1
                    
                    logger.info(f"[4_RETRIEVE] Entity distribution: {dict(sorted(entity_counts.items()))}")
            else:
                logger.info("[4_RETRIEVE] No chunks retrieved from database")
                
                # Debug: Check if database has any chunks
                try:
                    session = db.Session()
                    total_count = session.execute(text("SELECT COUNT(*) FROM doc_chunks")).scalar()
                    logger.info(f"[4_RETRIEVE] Database contains {total_count} total chunks")
                    
                    if entity_filter:
                        # Check if entity exists in database
                        entity_count = session.execute(text(f"""
                            SELECT COUNT(*) FROM doc_chunks 
                            WHERE LOWER(chunk_data->>'{entity_filter['field']}') = LOWER(:entity_name)
                        """), {"entity_name": entity_filter['name']}).scalar()
                        logger.info(f"[4_RETRIEVE] Database contains {entity_count} chunks for {entity_filter['type']} '{entity_filter['name']}'")
                    
                    session.close()
                except Exception as db_error:
                    logger.info(f"[4_RETRIEVE] Error checking database: {db_error}")
                    if session:
                        session.close()
                    return []
            
        except Exception as e:
            logger.info(f"[4_RETRIEVE] Error retrieving chunks: {e}")
            if session:
                session.close()
            return []

        # Apply additional flexible filtering if specified
        if document_type or year or sector or custom_filter:
            logger.info(f"[4_RETRIEVE] Applying flexible filtering: document_type={document_type}, year={year}, sector={sector}")
            
            filtered_chunks = []
            for chunk in all_chunks:
                chunk_data = chunk.get('chunk_data', {})
                
                # Document type filtering
                if document_type and chunk_data.get('document_type') != document_type:
                    continue
                
                # Year filtering
                if year and chunk_data.get('year', 0) < year:
                    continue
                
                # Sector filtering
                if sector and chunk_data.get('sector') != sector:
                    continue
                
                # Custom filter function
                if custom_filter and not custom_filter(chunk):
                    continue
                
                filtered_chunks.append(chunk)
            
            all_chunks = filtered_chunks
            logger.info(f"[4_RETRIEVE] After flexible filtering: {len(all_chunks)} chunks remaining")

        # Run comprehensive evaluation on filtered chunks
        evaluated_chunks = evaluate_chunks(
            prompt=prompt, 
            chunks=all_chunks,
            transformer_embedding=transformer_embedding,
            word2vec_embedding=word2vec_embedding
        )

        if not evaluated_chunks:
            logger.info("[4_RETRIEVE] No chunks passed evaluation")
            return []
        
        # Apply minimum similarity filter after evaluation
        if min_similarity > 0.0:
            before_count = len(evaluated_chunks)
            evaluated_chunks = [
                chunk for chunk in evaluated_chunks 
                if chunk.get('combined_score', 0) >= min_similarity
            ]
            after_count = len(evaluated_chunks)
            logger.info(f"[4_RETRIEVE] Filtered by similarity threshold {min_similarity}: {before_count} -> {after_count} chunks")
        
        # Handle n_per_doc constraint if specified
        if n_per_doc is not None:
            doc_chunk_counts = {}
            final_chunks = []
            
            for chunk in evaluated_chunks:
                doc_id = chunk.get('doc_id', 'unknown')
                if doc_chunk_counts.get(doc_id, 0) < n_per_doc:
                    final_chunks.append(chunk)
                    doc_chunk_counts[doc_id] = doc_chunk_counts.get(doc_id, 0) + 1
                
                # Stop if we have enough chunks
                if len(final_chunks) >= top_k:
                    break
            
            evaluated_chunks = final_chunks
            logger.info(f"[4_RETRIEVE] Applied n_per_doc={n_per_doc} constraint: {len(evaluated_chunks)} chunks")
        
        # Limit to requested top_k
        if len(evaluated_chunks) > top_k:
            evaluated_chunks = evaluated_chunks[:top_k]
            logger.info(f"[4_RETRIEVE] Limited to top_k={top_k}: {len(evaluated_chunks)} chunks")
        
        logger.info(f"[4_RETRIEVE] Returning {len(evaluated_chunks)} final chunks")
        return evaluated_chunks
            
    except Exception as e:
        logger.info(f"Error retrieving chunks: {e}")
        return []


def retrieve_chunks_with_hop(
    prompt: str,
    top_k: int = 20,
    country: Optional[str] = None,
    question_number: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Retrieve chunks using graph-based multi-hop reasoning through 
    relationship-based navigation with optimized country filtering.
    """
    try:
        # Auto-detect country from query if not provided
        if country is None:
            country = extract_country_from_query(prompt)
        
        logger.info(
            f"[HOP_RETRIEVE] Starting hop retrieval for country: {country}, "
            f"query: '{prompt[:50]}...'"
        )
        
        # Enhanced query should include country context
        enhanced_query = prompt
        
        if question_number is not None and question_number in HOP_KEYWORDS:
            keywords = HOP_KEYWORDS[question_number]
            selected_keywords = " ".join(keywords[:8])
            
            # Include country in the enhanced query for better filtering
            if country:
                enhanced_query = f"{country} {selected_keywords} {prompt}"
            else:
                enhanced_query = f"{selected_keywords} {prompt}"
                
            logger.info(
                f"[HOP_RETRIEVE] Enhanced query with country and keywords: "
                f"{enhanced_query[:100]}..."
            )
        else:
            selected_keywords = " ".join(GENERAL_NDC_KEYWORDS[:5])
            if country:
                enhanced_query = f"{country} {selected_keywords} {prompt}"
            else:
                enhanced_query = f"{selected_keywords} {prompt}"
            logger.info(
                f"[HOP_RETRIEVE] Using general keywords with country: "
                f"{enhanced_query[:100]}..."
            )
        
        # Initialize the GraphHopRetriever
        hop_retriever = GraphHopRetriever()
        
        logger.info(f"[HOP_RETRIEVE] Executing hop reasoning for country: {country}")
        results = hop_retriever.retrieve_with_hop_reasoning(
            query=enhanced_query,
            top_k=top_k * 2,  # Get more results to allow for filtering
            country=country
        )
        
        # CRITICAL FIX: Filter results by country since hop retriever isn't doing it
        if country and results:
            logger.info(f"[HOP_RETRIEVE] Pre-filter: {len(results)} chunks")
            
            # Get chunk metadata from database to properly filter
            session = db.Session()
            try:
                chunk_ids = [str(result['id']) for result in results]
                
                # Query to get proper country information for these chunks
                chunk_query = text("""
                    SELECT c.id::text, c.chunk_data->>'country' as country,
                           c.content, c.doc_id
                    FROM doc_chunks c
                    WHERE c.id::text = ANY(:chunk_ids)
                      AND LOWER(c.chunk_data->>'country') = LOWER(:country)
                """)
                
                valid_chunks = session.execute(chunk_query, {
                    'chunk_ids': chunk_ids,
                    'country': country
                }).fetchall()
                
                logger.info(
                    f"[HOP_RETRIEVE] Found {len(valid_chunks)} chunks for "
                    f"country '{country}'"
                )
                
                # Create lookup for valid chunks
                valid_chunk_lookup = {
                    row[0]: {'country': row[1], 'content': row[2], 'doc_id': row[3]} 
                    for row in valid_chunks
                }
                
                # Filter and update results
                filtered_results = []
                for result in results:
                    chunk_id = str(result['id'])
                    if chunk_id in valid_chunk_lookup:
                        # Update result with proper metadata
                        chunk_info = valid_chunk_lookup[chunk_id]
                        result['chunk_data'] = {'country': chunk_info['country']}
                        result['content'] = chunk_info['content']
                        result['doc_id'] = chunk_info['doc_id']
                        filtered_results.append(result)
                
                results = filtered_results[:top_k]  # Limit to requested top_k
                logger.info(
                    f"[HOP_RETRIEVE] After country filtering: "
                    f"{len(results)} chunks for {country}"
                )
                
            finally:
                session.close()
        
        # Debug the final results
        if results:
            countries_in_results = set()
            for result in results:
                result_country = result.get('chunk_data', {}).get('country', 'Unknown')
                countries_in_results.add(result_country)
            logger.info(
                f"[HOP_RETRIEVE] Final results contain chunks from countries: "
                f"{countries_in_results}"
            )
        
        return results
        
    except Exception as e:
        logger.info(f"[HOP_RETRIEVE] Error in graph hop retrieval: {e}")
        traceback.print_exc()
        return []


@Logger.log(log_file=project_root / "logs/retrieve.log", log_level="INFO")
def run_script(
    question: str = None,
    country: Optional[str] = None,
    use_hop_retrieval: bool = False
) -> List[Dict[str, Any]]:
    """
    Main function to run the retrieval script.
    
    Args:
        question: The question number (1-8) for predefined prompts OR custom question text.
                 If None, runs all predefined questions.
        country: Optional country name to filter documents by.
        use_hop_retrieval: Whether to use graph-based hop retrieval in addition
                          to vector retrieval.
    
    Returns:
        List of retrieved chunks with metadata.
    """
    try:
        # Create retrieve directories if they don't exist
        retrieve_dir = project_root / "data" / "retrieve"
        retrieve_dir.mkdir(parents=True, exist_ok=True)
        
        retrieve_hop_dir = project_root / "data" / "retrieve_hop"
        retrieve_hop_dir.mkdir(parents=True, exist_ok=True)
        
        all_evaluated_chunks = []
        
        # Determine which questions to run
        if question is not None:
            # Check if it's a predefined question number
            try:
                question_num = int(question)
                if question_num in QUESTION_PROMPTS:
                    questions_to_run = [question_num]
                    logger.info(f"[4_RETRIEVE] Using predefined question {question_num}")
                else:
                    raise ValueError(f"Question number {question_num} not in range 1-8")
            except ValueError:
                # It's a custom question text
                questions_to_run = [question]
                logger.info(f"[4_RETRIEVE] Using custom question: {question}")
        else:
            questions_to_run = list(range(1, 9))  # Run all predefined questions 1-8
            logger.info(f"[4_RETRIEVE] Running all predefined questions: {questions_to_run}")
        
        logger.info(f"[4_RETRIEVE] Questions to run: {questions_to_run}")
        
        # If no specific country is provided, get all countries from database
        if country is None:
            session = db.Session()
            try:
                # Extract countries from chunk_data JSON
                countries_result = session.execute(text(
                    "SELECT DISTINCT chunk_data->>'country' FROM doc_chunks "
                    "WHERE chunk_data->>'country' IS NOT NULL "
                    "ORDER BY chunk_data->>'country'"
                )).fetchall()
                countries_to_process = [row[0] for row in countries_result if row[0]]
                session.close()
                logger.info(f"[4_RETRIEVE] Processing all {len(countries_to_process)} countries from database")
            except Exception as e:
                logger.info(f"[4_RETRIEVE] Error getting countries: {e}")
                countries_to_process = []
                if session:
                    session.close()
        else:
            countries_to_process = [country]
            logger.info(f"[4_RETRIEVE] Processing specific country: {country}")
        
        logger.info(f"[4_RETRIEVE] Processing countries: {countries_to_process}")
        
        # Process each country
        for country_name in countries_to_process:
            logger.info(f"[4_RETRIEVE] Processing country: {country_name}")
            
            # Initialize country data structures (separate for standard and hop)
            standard_country_data = {
                "metadata": {
                    "country": country_name,
                    "timestamp": datetime.now().isoformat(),
                    "total_questions": len(questions_to_run),
                    "retrieval_method": "vector_similarity"
                },
                "questions": {}
            }
            
            # Only create hop data if hop retrieval is requested
            if use_hop_retrieval:
                hop_country_data = {
                    "metadata": {
                        "country": country_name,
                        "timestamp": datetime.now().isoformat(),
                        "total_questions": len(questions_to_run),
                        "retrieval_method": "graph_hop"
                    },
                    "questions": {}
                }
            
            # Process each question for this country
            for q_item in questions_to_run:
                logger.info(f"[4_RETRIEVE] Processing question {q_item} for {country_name}")
                
                # Get the prompt text - either from predefined prompts or custom question
                if isinstance(q_item, int) and q_item in QUESTION_PROMPTS:
                    prompt = QUESTION_PROMPTS[q_item]
                    question_key = f"question_{q_item}"
                else:
                    # Custom question text
                    prompt = q_item
                    question_key = f"custom_question"
                
                # Always do standard vector-based retrieval for all questions
                # Step 1: Embed the prompt using both models
                transformer_embedding, word2vec_embedding = embed_prompt(prompt)

                # Step 2: Retrieve and evaluate chunks
                standard_chunks = retrieve_chunks(
                    embedded_prompts=(transformer_embedding, word2vec_embedding),
                    prompt=prompt,
                    top_k=20,
                    ensure_indices=True,
                    n_per_doc=None,
                    country=country_name,
                    min_similarity=0.2
                )
                
                # Store standard retrieval data
                standard_question_data = {
                    "question_number": q_item if isinstance(q_item, int) else None,
                    "question": prompt,
                    "timestamp": datetime.now().isoformat(),
                    "chunk_count": len(standard_chunks),
                    "top_k_chunks": standard_chunks
                }
                
                standard_country_data["questions"][question_key] = (
                    standard_question_data
                )
                
                # Add to overall collection
                all_evaluated_chunks.extend(standard_chunks)
                
                logger.info(
                    f"[4_RETRIEVE] Question {q_item} for {country_name}: "
                    f"{len(standard_chunks)} chunks retrieved (vector)"
                )
                
                # If hop retrieval is requested, also perform hop retrieval
                if use_hop_retrieval:
                    logger.info(f"[4_RETRIEVE] Using graph hop retrieval for question {q_item}")
                    hop_chunks = retrieve_chunks_with_hop(
                        prompt=prompt,
                        top_k=20,
                        country=country_name,
                        question_number=q_item if isinstance(q_item, int) else None  # Pass question number to hop retrieval
                    )
                    
                    # Store hop retrieval data
                    hop_question_data = {
                        "question_number": q_item if isinstance(q_item, int) else None,
                        "question": prompt,
                        "timestamp": datetime.now().isoformat(),
                        "chunk_count": len(hop_chunks),
                        "top_k_chunks": hop_chunks
                    }
                    
                    hop_country_data["questions"][question_key] = hop_question_data
                    
                    # Add hop chunks to overall collection as well
                    all_evaluated_chunks.extend(hop_chunks)
                    
                    logger.info(
                        f"[4_RETRIEVE] Question {q_item} for {country_name}: "
                        f"{len(hop_chunks)} chunks retrieved (hop)"
                    )
            
            # Save country file with all questions
            # Clean country name for filename
            clean_country_name = "".join(
                c for c in country_name if c.isalnum() or c in (' ', '-', '_')
            ).strip()
            clean_country_name = clean_country_name.replace(' ', '_')
            
            # Create the filenames
            retrieve_filename = f"{clean_country_name}.json"
            
            # Always save standard vector results
            standard_output_path = retrieve_dir / retrieve_filename
            logger.info(f"[4_RETRIEVE] Saving vector retrieval results to: {standard_output_path}")
            
            with open(standard_output_path, "w", encoding="utf-8") as f:
                # Use the custom encoder to handle UUID objects
                json.dump(
                    standard_country_data, f, ensure_ascii=False, indent=2, cls=UUIDEncoder
                )
            
            standard_total_chunks = sum(
                len(q_data["top_k_chunks"])
                for q_data in standard_country_data["questions"].values()
            )
            logger.info(
                f"[4_RETRIEVE] Saved {len(questions_to_run)} questions with "
                f"{standard_total_chunks} total chunks for {country_name} (vector)"
            )
            
            # If hop retrieval was used, also save hop results
            if use_hop_retrieval and hop_country_data:
                hop_output_path = retrieve_hop_dir / retrieve_filename
                logger.info(
                    f"[4_RETRIEVE] Saving hop retrieval results to: {hop_output_path}"
                )
                
                with open(hop_output_path, "w", encoding="utf-8") as f:
                    # Use the custom encoder to handle UUID objects
                    json.dump(
                        hop_country_data, f, ensure_ascii=False, indent=2, cls=UUIDEncoder
                    )
                
                hop_total_chunks = sum(
                    len(q_data["top_k_chunks"])
                    for q_data in hop_country_data["questions"].values()
                )
                logger.info(
                    f"[4_RETRIEVE] Saved {len(questions_to_run)} questions with "
                    f"{hop_total_chunks} total chunks for {country_name} (hop)"
                )
        
        logger.info(
            f"[4_RETRIEVE] Completed processing {len(countries_to_process)} countries "
            f"with {len(questions_to_run)} questions each"
        )
        return all_evaluated_chunks

    except Exception as e:
        logger.info(f"Error in run_script: {e}")
        traceback.print_exc()
        raise e


if __name__ == "__main__":
    """
    Command-line interface for the retrieval script.
    
    This module provides a command-line interface for retrieving and evaluating
    document chunks from the database. When executed directly, it parses the
    following arguments:
    
    - question: Selects which predefined prompt to use (1-8)
    - country: Filters documents by country name (optional)
    - hop: Enables graph-based retrieval alongside vector retrieval
    
    Usage examples:
    - python 4_retrieve.py --hop                                 > Creates both vector and hop retrieval JSONs
    - python 4_retrieve.py --question 1 --country "Japan"        > Vector retrieval only
    - python 4_retrieve.py --question 4                          > Creates JSONs for all countries
    - python 4_retrieve.py --question 1 --country "Japan" --hop  > Both methods
    """
    
    parser = argparse.ArgumentParser(
        description='Run the retrieval script with a specified question number.'
    )
    parser.add_argument(
        '--question', type=str,
        help='Question number (1-8) for predefined prompts OR custom question text.'
    )
    parser.add_argument(
        '--country', type=str,
        help='Country to filter documents by (optional).'
    )
    parser.add_argument(
        '--hop', action='store_true',
        help='Use graph-based hop retrieval in addition to vector retrieval.'
    )
    args = parser.parse_args()
    run_script(
        question=args.question,
        country=args.country,
        use_hop_retrieval=args.hop
    )