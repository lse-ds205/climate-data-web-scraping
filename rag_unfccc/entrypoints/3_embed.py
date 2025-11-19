import sys
import os
from pathlib import Path
import traceback
import logging
import asyncio
from typing import List, Dict, Any, Optional, Union, Tuple
from dotenv import load_dotenv
from sqlalchemy import text
from tqdm import tqdm

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))
import group4py
from embed.combined import CombinedEmbedding
from embed.hoprag import HopRAGGraphProcessor
from helpers.internal import Logger
from databases.docker_proxy import get_database_connection
from databases.auth import PostgresConnection
from databases.models import DocChunkORM

logger = logging.getLogger(__name__)
load_dotenv()

def verify_embeddings(session, chunk_id):
    """Verify that embeddings are being stored correctly in the database."""
    try:
        result = session.execute(text("""
            SELECT id, 
                   CASE WHEN transformer_embedding IS NOT NULL THEN 'YES' ELSE 'NO' END as has_transformer,
                   CASE WHEN word2vec_embedding IS NOT NULL THEN 'YES' ELSE 'NO' END as has_word2vec,
                   vector_dims(transformer_embedding) as transformer_dims,
                   vector_dims(word2vec_embedding) as word2vec_dims
            FROM doc_chunks 
            WHERE id = :chunk_id
        """), {"chunk_id": chunk_id})
        
        row = result.fetchone()
        if row:
            logger.info(f"[3_EMBED] VERIFICATION - Chunk {chunk_id}:")
            logger.info(f"[3_EMBED]   Transformer: {row[1]} ({row[3]} dims)")
            logger.info(f"[3_EMBED]   Word2Vec: {row[2]} ({row[4]} dims)")
        else:
            logger.warning(f"[3_EMBED] VERIFICATION - Chunk {chunk_id} not found in database")
    except Exception as e:
        logger.error(f"[3_EMBED] VERIFICATION ERROR: {e}")


def is_orm_available(session):
    """Check if session supports ORM queries"""
    # Check if it's a Docker proxy session (which doesn't support ORM)
    session_class_name = session.__class__.__name__
    if 'DockerProxySession' in session_class_name:
        logger.debug(f"[3_EMBED] Detected Docker proxy session: {session_class_name}")
        return False
    
    # Check for ORM capabilities
    has_query = hasattr(session, 'query')
    has_commit = hasattr(session, 'commit')
    has_container = hasattr(session, 'container_name')
    
    logger.debug(f"[3_EMBED] ORM check - query: {has_query}, commit: {has_commit}, container: {has_container}")
    return has_query and has_commit and not has_container

def collect_all_chunk_texts(session):
    """
    Collect all chunk texts from the database for global Word2Vec training.
    Uses ORM when available (faster), falls back to raw SQL for Docker proxy.
    
    Returns:
        List of chunk texts
    """
    logger.info("[3_EMBED] Collecting all chunks from database for global Word2Vec training...")
    
    try:
        orm_available = is_orm_available(session)
        logger.info(f"[3_EMBED] ORM available: {orm_available}")
        
        if orm_available:
            # Use ORM approach (faster on non-Docker systems)
            logger.debug("[3_EMBED] Using ORM queries for better performance")
            chunks = session.query(DocChunkORM.content).filter(DocChunkORM.content.isnot(None)).all()
            texts = [chunk.content for chunk in chunks if chunk.content and chunk.content.strip()]
        else:
            # Use raw SQL fallback (Docker proxy compatibility)
            logger.debug("[3_EMBED] Using raw SQL for Docker proxy compatibility")
            result = session.execute(text("SELECT content FROM doc_chunks WHERE content IS NOT NULL"))
            rows = result.fetchall()
            texts = [row[0] for row in rows if row[0] and row[0].strip()]
        
        logger.info(f"[3_EMBED] Collected {len(texts)} chunks from database")
        return texts
        
    except Exception as e:
        logger.error(f"[3_EMBED] Error collecting chunks: {e}")
        return []


async def embed_all_chunks(force_reembed: bool = False, db = Optional[PostgresConnection], session = Optional[None]):
    """
    Generate embeddings for all chunks in the database.
    
    Args:
        force_reembed: If True, regenerate embeddings even if they already exist
    """
    
    logger.info("[3_EMBED] Starting embedding generation process...")
    
    # Step 1: Collect all chunk texts and train global Word2Vec
    chunk_texts = collect_all_chunk_texts(session)
    
    if not chunk_texts:
        logger.error("[3_EMBED] No chunks found in database")
        return
    
    # Step 2: Initialize embedding models
    logger.info("[3_EMBED] Loading embedding models...")
    embedding_model = CombinedEmbedding()
    
    # Train or load Word2Vec model
    model_path = project_root / "local_models" / "word2vec"
    
    # Check if model already exists
    if model_path.exists() and not force_reembed:
        logger.info(f"[3_EMBED] Loading existing Word2Vec model from {model_path}")
        embedding_model.word2vec_embedder.load_global_model(str(model_path))
    else:
        logger.info("[3_EMBED] Training new global Word2Vec model...")
        success = embedding_model.train_word2vec_on_texts(chunk_texts, str(model_path))
        if not success:
            logger.error("[3_EMBED] Failed to train Word2Vec model")
            return
    
    # Load transformer models
    embedding_model.transformer_embedder.load_models()
    
    if not embedding_model.models_ready:
        logger.error("[3_EMBED] No embedding models loaded successfully")
        return

    # Step 3: Get all chunks from database (hybrid ORM/SQL approach)
    
    try:
        if is_orm_available(session):
            # Use ORM approach (faster on non-Docker systems)
            logger.debug("[3_EMBED] Using ORM queries for better performance")
            if force_reembed:
                chunks_query = session.query(DocChunkORM).all()
                logger.info(f"[3_EMBED] Force re-embedding: Processing all {len(chunks_query)} chunks")
            else:
                chunks_query = session.query(DocChunkORM).filter(
                    (DocChunkORM.transformer_embedding.is_(None)) | 
                    (DocChunkORM.word2vec_embedding.is_(None))
                ).all()
                logger.info(f"[3_EMBED] Processing {len(chunks_query)} chunks without embeddings")
            
            if not chunks_query:
                logger.info("[3_EMBED] No chunks need embedding. All done!")
                return
            
            # Step 4: Generate embeddings for all chunks (ORM approach)
            logger.info("[3_EMBED] Generating embeddings for chunks...")
            
            processed_count = 0
            for i, chunk in enumerate(tqdm(chunks_query, desc="Generating embeddings")):
                try:
                    if not chunk.content or not chunk.content.strip():
                        logger.warning(f"[3_EMBED] Skipping empty chunk {chunk.id}")
                        continue
                    
                    # Generate transformer embedding
                    transformer_embedding = embedding_model.transformer_embedder.embed_transformer(chunk.content)
                    
                    # Generate Word2Vec embedding using global model
                    word2vec_embedding = embedding_model.word2vec_embedder.embed_text(chunk.content)
                    
                    # Update chunk with embeddings (ORM approach)
                    if transformer_embedding and len(transformer_embedding) > 0:
                        # Ensure all elements are floats
                        transformer_embedding = [float(val) if not isinstance(val, float) else val for val in transformer_embedding]
                        
                        # Log embedding details for monitoring
                        logger.info(f"[3_EMBED] Processing chunk {i+1}/{len(chunks_query)}: {chunk.id}")
                        logger.info(f"[3_EMBED] Transformer embedding: {len(transformer_embedding)} dimensions, first 3 values: {transformer_embedding[:3]}")
                        
                        chunk.transformer_embedding = transformer_embedding
                    
                    if word2vec_embedding is not None and len(word2vec_embedding) > 0:
                        # Ensure all elements are floats and convert to list
                        word2vec_embedding = [float(val) if not isinstance(val, float) else val for val in word2vec_embedding.tolist()]
                        
                        # Log Word2Vec embedding details
                        logger.info(f"[3_EMBED] Word2Vec embedding: {len(word2vec_embedding)} dimensions, first 3 values: {word2vec_embedding[:3]}")
                        
                        chunk.word2vec_embedding = word2vec_embedding
                    
                    processed_count += 1
                    
                    # Verify embeddings every 100 chunks
                    if processed_count % 100 == 0:
                        verify_embeddings(session, chunk.id)
                    
                    # Commit periodically to avoid holding large transactions (every 500 chunks)
                    if processed_count % 500 == 0:
                        session.commit()
                        logger.info(f"[3_EMBED] Committed batch at {processed_count} chunks")
                        
                except Exception as e:
                    logger.error(f"[3_EMBED] Error processing chunk {str(chunk.id)}: {str(e)}")
                    logger.error(f"[3_EMBED] Traceback: {traceback.format_exc()}")
                    continue
            
            # Final commit
            session.commit()
            logger.info(f"[3_EMBED] Successfully generated embeddings for {processed_count} chunks")
            
        else:
            # Use raw SQL fallback (Docker proxy compatibility)
            logger.debug("[3_EMBED] Using raw SQL for Docker proxy compatibility")
            if force_reembed:
                result = session.execute(text("SELECT id, content FROM doc_chunks WHERE content IS NOT NULL"))
                logger.info(f"[3_EMBED] Force re-embedding: Processing all chunks")
            else:
                result = session.execute(text("""
                    SELECT id, content FROM doc_chunks 
                    WHERE content IS NOT NULL 
                    AND (transformer_embedding IS NULL OR word2vec_embedding IS NULL)
                """))
                logger.info(f"[3_EMBED] Processing chunks without embeddings")
            
            chunks_data = result.fetchall()
            
            if not chunks_data:
                logger.info("[3_EMBED] No chunks need embedding. All done!")
                return
            
            logger.info(f"[3_EMBED] Found {len(chunks_data)} chunks to process")
            
            # Step 4: Generate embeddings for all chunks (optimized sequential approach)
            logger.info("[3_EMBED] Generating embeddings for chunks...")
            
            processed_count = 0
            # Process in optimized batches for better performance
            batch_size = 500  # Process 500 chunks at a time for better performance
            for batch_start in range(0, len(chunks_data), batch_size):
                batch_end = min(batch_start + batch_size, len(chunks_data))
                batch_chunks = chunks_data[batch_start:batch_end]
                
                logger.info(f"[3_EMBED] Processing batch {batch_start//batch_size + 1}/{(len(chunks_data) + batch_size - 1)//batch_size} ({len(batch_chunks)} chunks)")
                
                for i, (chunk_id, content) in enumerate(tqdm(batch_chunks, desc=f"Batch {batch_start//batch_size + 1}")):
                    try:
                        if not content or not content.strip():
                            logger.warning(f"[3_EMBED] Skipping empty chunk {chunk_id}")
                            continue
                        
                        # Generate transformer embedding
                        transformer_embedding = embedding_model.transformer_embedder.embed_transformer(content)
                        
                        # Generate Word2Vec embedding using global model
                        word2vec_embedding = embedding_model.word2vec_embedder.embed_text(content)
                        
                        # Update chunk with embeddings using raw SQL
                        if transformer_embedding and len(transformer_embedding) > 0:
                            # Ensure all elements are floats
                            transformer_embedding = [float(val) if not isinstance(val, float) else val for val in transformer_embedding]
                            # Convert to PostgreSQL pgvector format (square brackets)
                            transformer_array = "[" + ",".join(map(str, transformer_embedding)) + "]"
                            
                            session.execute(text("""
                                UPDATE doc_chunks 
                                SET transformer_embedding = :embedding 
                                WHERE id = :chunk_id
                            """), {"embedding": transformer_array, "chunk_id": chunk_id})
                        
                        if word2vec_embedding is not None and len(word2vec_embedding) > 0:
                            # Ensure all elements are floats and convert to list
                            word2vec_embedding = [float(val) if not isinstance(val, float) else val for val in word2vec_embedding.tolist()]
                            # Convert to PostgreSQL pgvector format (square brackets)
                            word2vec_array = "[" + ",".join(map(str, word2vec_embedding)) + "]"
                            
                            session.execute(text("""
                                UPDATE doc_chunks 
                                SET word2vec_embedding = :embedding 
                                WHERE id = :chunk_id
                            """), {"embedding": word2vec_array, "chunk_id": chunk_id})
                        
                        processed_count += 1
                        
                        # Commit periodically to avoid holding large transactions (every 100 chunks)
                        if processed_count % 100 == 0:
                            session.commit()
                            logger.info(f"[3_EMBED] Committed batch at {processed_count} chunks")
                            
                    except Exception as e:
                        logger.error(f"[3_EMBED] Error processing chunk {chunk_id}: {str(e)}")
                        logger.error(f"[3_EMBED] Traceback: {traceback.format_exc()}")
                        continue
            
            # Final commit
            session.commit()
            logger.info(f"[3_EMBED] Successfully generated embeddings for {processed_count} chunks")
        
        # Step 5: Run HopRAG processing after embeddings are complete
        try:
            logger.info("[3_EMBED] Starting HopRAG processing...")
            processor = HopRAGGraphProcessor()
            
            # Check if the HopRAG embedding model is ready
            if not processor.is_model_ready():
                logger.error("[3_EMBED] HopRAG embedding model failed to initialize properly. Skipping HopRAG processing.")
                return
                
            # Generate embeddings if needed (HopRAG uses its own embedding format)
            logger.info("[3_EMBED] Processing HopRAG embeddings in batch...")
            await processor.process_embeddings_batch(batch_size=100)
              # Build relationships for all chunks with enhanced logging
            logger.info("[3_EMBED] Building logical relationships...")
            # Get the current relationship count before building
            rel_count_before = 0
            try:
                with db.connect() as conn:
                    result = conn.execute(text("SELECT COUNT(*) FROM logical_relationships"))
                    rel_count_before = result.scalar() or 0
                    logger.info(f"[3_EMBED] Current relationship count: {rel_count_before}")
            except Exception as e:
                logger.warning(f"[3_EMBED] Could not get relationship count: {str(e)}")
            
            # Build relationships with detailed parameters
            logger.info("[3_EMBED] Building relationships for all processed chunks...")
            await processor.build_relationships_sparse(
                max_neighbors=30, 
                min_confidence=0.55,
                force_commit=True,  # Ensure relationships are committed to database
                session=session
            )           
            
            # Check how many relationships were added
            try:
                with db.connect() as conn:
                    # Get total relationships
                    result = conn.execute(text("SELECT COUNT(*) FROM logical_relationships"))
                    rel_count_after = result.scalar() or 0
                    
                    new_rels = rel_count_after - rel_count_before
                    logger.info(f"[3_EMBED] Added {new_rels} new relationships. Total now: {rel_count_after}")
            except Exception as e:
                logger.warning(f"[3_EMBED] Could not get updated relationship count: {str(e)}")
            
            # Clean up HopRAG processor
            await processor.close()
            logger.info("[3_EMBED] HopRAG processing completed successfully")
            
            # Ensure any remaining changes from HopRAG are committed to the database
            session.commit()
            logger.info("[3_EMBED] Successfully committed HopRAG relationship changes")
            
        except Exception as e:
            session.rollback()  # Roll back any failed HopRAG changes
            logger.error(f"[3_EMBED] HopRAG processing failed: {str(e)}")
            logger.error(f"[3_EMBED] HopRAG Traceback: {traceback.format_exc()}")
            # Don't fail the entire process if HopRAG fails - embeddings are still valid
        
    except Exception as e:
        logger.error(f"[3_EMBED] Error during embedding generation: {str(e)}")
        session.rollback()
        raise
    finally:
        session.close()


@Logger.log(log_file = project_root / "logs/embed.log", log_level="INFO")
async def run_script(force_reembed: bool = False):
    """
    Main function to generate embeddings for all chunks.
    
    Args:
        force_reembed: If True, regenerate embeddings even if they already exist
    """
    db = get_database_connection()  # Use Docker proxy on Windows
    
    try:
        with db.Session() as session:
            logger.warning(f"\n\n[3_EMBED] Running embedding script with force_reembed={force_reembed}...")
            
            # Generate embeddings for all chunks
            await embed_all_chunks(force_reembed=force_reembed, db=db, session=session)
            
            logger.warning("[3_EMBED] Embedding and relationship processing completed successfully. All chunks now have embeddings and logical relationships.")
        
    except Exception as e:
        logger.critical(f"\n\n\n\n[PIPELINE BROKE!] - Error in 3_embed.py: {e}")
        logger.critical(f"[PIPELINE BROKE!] - Traceback: {traceback.format_exc()}")
        raise e


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate embeddings for document chunks using global Word2Vec and transformers")
    parser.add_argument("--force", "-f", action="store_true", help="Force regeneration of embeddings, even if they already exist")
    args = parser.parse_args()
    asyncio.run(run_script(force_reembed=args.force))
