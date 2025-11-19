"""
Optimized HopRAG Graph Processor with consistent UUID handling and improved efficiency
Implements embeddings, relationship detection, and graph analysis
"""

import sys
from pathlib import Path
import numpy as np
import gc
import re
import logging
import networkx as nx
import traceback
import json
from typing import List, Dict, Optional, Union
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.neighbors import NearestNeighbors
from sqlalchemy import text
import uuid

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

import group4py
from exceptions import ModelLoadError, EmbeddingGenerationError, GraphProcessingError, RelationshipDetectionError, DatabaseConnectionError
from databases.auth import PostgresConnection
from databases.models import LogicalRelationshipORM
from databases.operations import upload
from schemas.hopragdata import ChunkData, RelationshipScore, GraphAnalysisResult, NodeClassification
from constants.regex import HOPRAG_PATTERNS

logger = logging.getLogger(__name__)


class MemoryOptimizedEmbedder:
    """Memory-efficient embedding generator"""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", batch_size: int = 32):
        self.batch_size = batch_size
        
        try:
            self.model = SentenceTransformer(model_name)
            logger.info(f"Loaded sentence transformer model: {model_name}")
        except Exception as e:
            logger.error(f"Failed to load {model_name}: {e}")
            try:
                fallback_model = "all-MiniLM-L6-v2"
                logger.info(f"Falling back to: {fallback_model}")
                self.model = SentenceTransformer(fallback_model)
            except Exception as e2:
                logger.critical(f"Failed to load fallback model: {e2}")
                raise ModelLoadError(f"Could not load any embedding model: {e2}") from e2
            
        self.embedding_dim = self.model.get_sentence_embedding_dimension()
        logger.info(f"Embedding dimension: {self.embedding_dim}")

    def encode_batch(self, texts: List[str]) -> np.ndarray:
        """Encode texts in batches to manage memory"""
        if not texts:
            logger.warning("No texts provided for encoding")
            return np.array([])
            
        if not hasattr(self, 'model') or self.model is None:
            logger.error("No embedding model available")
            raise ModelLoadError("No embedding model available for encoding")
            
        embeddings = []
        
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            try:
                batch_embeddings = self.model.encode(batch, show_progress_bar=False)
                # Validate embeddings are not all zeros
                if np.all(batch_embeddings == 0):
                    logger.warning(f"Generated all-zero embeddings for batch {i//self.batch_size}")
                
                embeddings.append(batch_embeddings)
            except Exception as e:
                logger.error(f"Error encoding batch {i//self.batch_size}: {e}")
                raise EmbeddingGenerationError(f"Error encoding batch {i//self.batch_size}: {e}")
            
            if i % (self.batch_size * 10) == 0:
                gc.collect()
        
        return np.vstack(embeddings) if embeddings else np.array([])

class OptimizedRelationshipDetector:
    """Optimized relationship detection with consistent UUID handling"""
    
    def __init__(self):
        self.climate_patterns = HOPRAG_PATTERNS
    
    def detect_relationships_batch(self, source_chunks: List[ChunkData], 
                                 target_chunks: List[ChunkData]) -> List[RelationshipScore]:
        """Detect relationships maintaining UUID consistency"""
        if not source_chunks or not target_chunks:
            logger.warning("Empty source or target chunks for relationship detection")
            return []
            
        try:
            relationships = []
            
            for source_chunk in source_chunks:
                for target_chunk in target_chunks:
                    if source_chunk.chunk_id != target_chunk.chunk_id:
                        relationship = self._detect_single_relationship(source_chunk, target_chunk)
                        if relationship and relationship.confidence > 0.5:
                            relationships.append(relationship)
            
            return relationships
        except Exception as e:
            logger.error(f"Error in relationship detection: {e}")
            raise RelationshipDetectionError(f"Error in relationship detection: {e}")
    
    def _detect_single_relationship(self, source: ChunkData, target: ChunkData) -> Optional[RelationshipScore]:
        """Detect relationship between two chunks"""
        best_relationship = None
        best_confidence = 0.0
        
        source_text = source.content.lower()
        target_text = target.content.lower()
        
        for rel_type, patterns in self.climate_patterns.items():
            for source_pattern, target_pattern in patterns:
                if (re.search(source_pattern, source_text, re.IGNORECASE) and 
                    re.search(target_pattern, target_text, re.IGNORECASE)):
                    
                    confidence = self._calculate_confidence(source, target, source_pattern, target_pattern)
                    
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_relationship = RelationshipScore(
                            source_id=source.chunk_id,
                            target_id=target.chunk_id,
                            relationship_type=rel_type,
                            confidence=confidence,
                            evidence=f"Pattern: {source_pattern} -> {target_pattern}",
                            method="pattern_matching"
                        )
        
        return best_relationship
    
    def _calculate_confidence(self, source: ChunkData, target: ChunkData, 
                            source_pattern: str, target_pattern: str) -> float:
        """Optimized confidence calculation"""
        # Semantic similarity component
        if source.embedding is not None and target.embedding is not None:
            semantic_sim = cosine_similarity(
                source.embedding.reshape(1, -1), 
                target.embedding.reshape(1, -1)
            )[0][0]
        else:
            semantic_sim = 0.3
        
        # Pattern strength
        pattern_strength = 0.8 if r'\d+' in source_pattern else 0.6
        
        # Use chunk_index for distance if available, otherwise use semantic similarity
        if source.chunk_index is not None and target.chunk_index is not None:
            distance_penalty = max(0.1, 1.0 - abs(source.chunk_index - target.chunk_index) * 0.001)
            confidence = (
                0.3 * semantic_sim + 
                0.5 * pattern_strength + 
                0.2 * distance_penalty
            )
        else:
            # No distance penalty available, rely more on semantic similarity
            confidence = (
                0.6 * semantic_sim + 
                0.4 * pattern_strength
            )
        
        # Ensure confidence is never None or invalid
        if confidence is None or confidence < 0.0:
            confidence = 0.1  # Default minimum confidence
        elif confidence > 1.0:
            confidence = 1.0
        
        return confidence

class HopRAGGraphProcessor:
    """Optimized graph processor with consistent UUID handling"""
    
    def __init__(self, embedding_model: str = "all-MiniLM-L6-v2"):
        self.db_connection = PostgresConnection()
        self.embedder = MemoryOptimizedEmbedder(embedding_model)
        self.relationship_detector = OptimizedRelationshipDetector()
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        logger.info(f"Optimized HopRAG processor initialized with model: {embedding_model}")

    def is_model_ready(self) -> bool:
        """Check if the embedding model is properly initialized and ready to use"""
        return (hasattr(self.embedder, 'model') and 
                self.embedder.model is not None and 
                hasattr(self.embedder, 'embedding_dim'))

    async def initialize(self):
        """Initialize database connections"""
        success = self.db_connection.connect()
        if not success:
            logger.error("Failed to connect to database")
            raise DatabaseConnectionError("Failed to connect to database for HopRAG processing")
        logger.info("Optimized graph processor initialized")

    async def process_embeddings_batch(self, batch_size: int = 500):
        """Generate embeddings with optimized UUID handling"""

        # Get chunks without embeddings
        with self.db_connection.connect() as conn:
            chunks_data = conn.execute(text("""
                SELECT id, content 
                FROM doc_chunks 
                WHERE hoprag_embedding IS NULL 
                ORDER BY id
                LIMIT :batch_limit
            """), {"batch_limit": batch_size * 5}).fetchall()
        
        if not chunks_data:
            logger.info("No chunks need embeddings")
            return
        
        logger.info(f"Processing embeddings for {len(chunks_data)} chunks")
        
        # Check if embedding model is ready
        if not self.is_model_ready():
            logger.error("HopRAG embedding model not initialized properly. Cannot generate embeddings.")
            # Print diagnostic information
            logger.error(f"Model attributes: {dir(self.embedder)}")
            if hasattr(self.embedder, 'model'):
                logger.error(f"Model exists but may be invalid: {self.embedder.model}")
            return
            
        # Print model diagnostic information
        logger.info(f"Using embedding model: {type(self.embedder.model).__name__}")
        logger.info(f"Embedding dimension: {self.embedder.embedding_dim}")
        
        # Process in smaller batches to manage memory
        for i in range(0, len(chunks_data), batch_size):
            batch = chunks_data[i:i + batch_size]
            
            # Extract texts and generate embeddings
            texts = [row.content for row in batch]
            
            # Sample a small text for debugging
            if i == 0 and texts:
                sample_text = texts[0][:100] + "..." if len(texts[0]) > 100 else texts[0]
                logger.info(f"Sample text being embedded: '{sample_text}'")
                
            embeddings = self.embedder.encode_batch(texts)
            
            if embeddings.size == 0:
                logger.error(f"Failed to generate embeddings for batch {i//batch_size + 1}")
                continue
                
            # Debug first embedding if available
            if i == 0 and len(embeddings) > 0:
                sample_embedding = embeddings[0]
                logger.info(f"Sample embedding shape: {sample_embedding.shape}")
                logger.info(f"Sample embedding stats: min={np.min(sample_embedding):.4f}, max={np.max(sample_embedding):.4f}, mean={np.mean(sample_embedding):.4f}")
                
            # Update database - direct UUID usage, no conversions
            successful_updates = 0
            with self.db_connection.connect() as conn:
                for j, row in enumerate(batch):
                    # Skip empty or all-zero embeddings
                    if j >= len(embeddings) or embeddings[j].size == 0 or np.all(embeddings[j] == 0):
                        logger.warning(f"Skipping invalid embedding for chunk {row.id}")
                        continue
                        
                    try:
                        # Convert floating point embeddings to scaled integers (multiply by 10000 and cast to int)
                        # This addresses the type mismatch between float arrays and the integer array column in the database
                        int_embedding = (embeddings[j] * 10000).astype(np.int64).tolist()
                        
                        conn.execute(text(
                            "UPDATE doc_chunks SET hoprag_embedding = :embedding WHERE id = :chunk_id"
                        ), {
                            "embedding": int_embedding,
                            "chunk_id": row.id  # Direct UUID usage
                        })
                        successful_updates += 1
                    except Exception as e:
                        logger.error(f"Error updating embedding for chunk {row.id}: {e}")
                        logger.error(f"Embedding type: {type(embeddings[j])}, shape: {embeddings[j].shape}")
                        # Try alternative approach if the first one fails
                        try:
                            # Try with a different approach - use array constructor
                            embedding_str = '{' + ','.join(str(int(val * 10000)) for val in embeddings[j]) + '}'
                            conn.execute(text(
                                "UPDATE doc_chunks SET hoprag_embedding = :embedding::bigint[] WHERE id = :chunk_id"
                            ), {
                                "embedding": embedding_str,
                                "chunk_id": row.id
                            })
                            successful_updates += 1
                            logger.info(f"Successfully updated with alternative approach for chunk {row.id}")
                        except Exception as e2:
                            logger.error(f"Alternative approach also failed: {e2}")
                        
                conn.commit()
            
            logger.info(f"Updated embeddings for batch {i//batch_size + 1}, successful updates: {successful_updates}/{len(batch)}")
            
            # Force garbage collection
            del embeddings, texts
            gc.collect()

    async def get_doc_chunk_count(self, doc_id: str) -> int:
        """Get the number of chunks for a specific document"""
        doc_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, doc_id)

        with self.db_connection.connect() as conn:
            result = conn.execute(text("""
                SELECT COUNT(*) FROM doc_chunks 
                WHERE doc_id = :doc_id
            """), {"doc_id": doc_uuid}).scalar()
            
        return result or 0

    async def build_relationships_sparse(self, max_neighbors: int = 50, min_confidence: float = 0.6, 
                                       doc_id: str = None, force_commit: bool = False, session: Optional[None] = None):
        """Build relationships with optimized UUID handling and memory management"""
        
        # Get chunks with embeddings - maintain UUID objects from start
        with self.db_connection.connect() as conn:            
            if doc_id:
                logger.info(f"Building relationships for document: {doc_id}")
                doc_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, doc_id)
                
                chunks_data = conn.execute(text("""
                    SELECT id, content, hoprag_embedding, chunk_index
                    FROM doc_chunks 
                    WHERE hoprag_embedding IS NOT NULL
                    AND doc_id = :doc_id
                    ORDER BY id
                """), {"doc_id": doc_uuid}).fetchall()
            else:
                chunks_data = conn.execute(text("""
                    SELECT id, content, hoprag_embedding, chunk_index
                    FROM doc_chunks 
                    WHERE hoprag_embedding IS NOT NULL
                    ORDER BY id
                """)).fetchall()
        
        if len(chunks_data) < 2:
            logger.warning(f"Not enough chunks with embeddings {f'for document {doc_id}' if doc_id else ''}")
            return
        
        logger.info(f"Building relationships for {len(chunks_data)} chunks")
        
        # Create ChunkData objects with consistent UUID handling from the start
        chunk_objects = []
        embeddings_list = []
        
        for row in chunks_data:
            # Convert row.id to UUID if needed
            chunk_uuid = row.id if isinstance(row.id, uuid.UUID) else uuid.UUID(row.id) if isinstance(row.id, str) else None
            
            if chunk_uuid is None:
                logger.warning(f"Invalid chunk ID format: {row.id}")
                continue
            
            # Parse embedding efficiently
            try:
                if isinstance(row.hoprag_embedding, str):
                    clean_str = row.hoprag_embedding.strip('[]')
                    embedding_values = [float(x.strip()) for x in clean_str.split(',')]
                    embedding_array = np.array(embedding_values)
                else:
                    # Convert from database representation to numpy array
                    embedding_array = np.array(row.hoprag_embedding, dtype=np.float32)
                
                # Convert integer embeddings back to float (scale back down)
                # Check if values are large integers (our converted embeddings)
                if np.abs(embedding_array).max() > 1000:
                    embedding_array = embedding_array / 10000.0
                
                # Validate embedding
                if embedding_array.size == 0 or embedding_array.ndim == 0:
                    logger.warning(f"Empty embedding for chunk {row.id}, skipping")
                    continue
                
                if embedding_array.ndim == 2 and embedding_array.shape[0] == 1:
                    embedding_array = embedding_array.flatten()
                
                if len(embedding_array) < 10:  # Filter out suspicious embeddings
                    logger.warning(f"Suspiciously small embedding for chunk {row.id}: {len(embedding_array)} dimensions")
                    continue
                    
                # Log embedding stats for the first few chunks to help with debugging
                if len(chunk_objects) < 3:
                    logger.info(f"Sample embedding {len(chunk_objects)}: shape={embedding_array.shape}, min={embedding_array.min():.6f}, max={embedding_array.max():.6f}, mean={embedding_array.mean():.6f}")
                
                chunk_obj = ChunkData(
                    chunk_id=chunk_uuid,
                    content=row.content,
                    embedding=embedding_array,
                    chunk_index=row.chunk_index
                )
                
                chunk_objects.append(chunk_obj)
                embeddings_list.append(embedding_array)
                
            except Exception as e:
                logger.warning(f"Error processing embedding for chunk {row.id}: {e}")
                continue
        
        if not chunk_objects:
            logger.error("No valid embeddings found after filtering")
            return
        
        logger.info(f"Valid chunk objects created: {len(chunk_objects)}")
        
        # Stack embeddings for nearest neighbor search
        embeddings = np.vstack(embeddings_list)
        logger.info(f"Created embeddings matrix with shape: {embeddings.shape}")
        
        # Use approximate nearest neighbors for efficiency
        nbrs = NearestNeighbors(n_neighbors=min(max_neighbors, len(chunk_objects)), 
                              algorithm='auto', metric='euclidean')
        nbrs.fit(embeddings)
        
        all_relationships = []
        batch_size = 100
        
        # Process in batches
        for i in range(0, len(chunk_objects), batch_size):
            batch_end = min(i + batch_size, len(chunk_objects))
            batch_chunks = chunk_objects[i:batch_end]
            
            for k, source_chunk in enumerate(batch_chunks):
                actual_index = i + k
                
                # Get nearest neighbors
                distances, neighbor_indices = nbrs.kneighbors([embeddings[actual_index]])
                
                # Create target chunks from neighbors
                target_chunks = []
                for neighbor_idx in neighbor_indices[0]:
                    if neighbor_idx != actual_index:
                        target_chunks.append(chunk_objects[neighbor_idx])
                
                # Detect relationships - no UUID conversions needed
                relationships = self.relationship_detector.detect_relationships_batch(
                    [source_chunk], target_chunks
                )
                
                # Filter by confidence - relationships already have UUID objects
                for rel in relationships:
                    if rel.confidence >= min_confidence:
                        all_relationships.append(rel)
            
            logger.info(f"Processed batch {i//batch_size + 1}/{(len(chunk_objects) + batch_size - 1)//batch_size}")
            gc.collect()
        
        # Insert relationships with optimized handling
        if all_relationships:
            await self._insert_relationships_optimized(all_relationships, session=session)
        else:
            logger.warning("No relationships detected to insert")
        
        # Cleanup
        del embeddings, all_relationships, chunk_objects
        gc.collect()

    async def _insert_relationships_optimized(self, relationships: List[RelationshipScore], session=Optional[None]):
        """Insert relationships with optimized UUID handling"""
        logger.info(f"Inserting {len(relationships)} relationships into database")
        
        # Convert RelationshipScore objects to LogicalRelationshipORM objects
        relationship_orms = []
        for rel in relationships:
            try:
                # Ensure confidence is never None or invalid
                confidence_value = rel.confidence
                if confidence_value is None or confidence_value < 0.0:
                    confidence_value = 0.1  # Default minimum confidence
                elif confidence_value > 1.0:
                    confidence_value = 1.0
                
                relationship_orm = LogicalRelationshipORM(
                    id=uuid.uuid4(),
                    source_chunk_id=rel.source_id,  # Direct UUID usage
                    target_chunk_id=rel.target_id,  # Direct UUID usage
                    relationship_type=rel.relationship_type,
                    confidence=float(confidence_value),
                    evidence=rel.evidence,
                    method=rel.method
                )
                relationship_orms.append(relationship_orm)
                
            except Exception as e:
                logger.warning(f"Failed to create relationship ORM for {rel.source_id} -> {rel.target_id}: {e}")
                continue
        
        logger.info(f"Successfully created {len(relationship_orms)} relationship ORM objects")
        
        # Use batch processing for database insertion
        try:
            batch_size = 100
            successful_uploads = 0
            
            for i in range(0, len(relationship_orms), batch_size):
                batch = relationship_orms[i:i+batch_size]
                
                success = upload(session, batch, table='logical_relationships')
                
                if not success:
                    logger.error(f"Failed to upload relationship batch {i//batch_size + 1}")
                    continue
                
                successful_uploads += len(batch)
                logger.info(f"Uploaded relationship batch {i//batch_size + 1} of {(len(relationship_orms) + batch_size - 1)//batch_size}")
            
            logger.info(f"Successfully uploaded {successful_uploads}/{len(relationship_orms)} relationships")
            
        except Exception as e:
            logger.error(f"Error uploading relationships: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")

    async def bfs_multi_hop_retrieve(self, query: str, max_hops: int = 3, 
                                   top_k: int = 20) -> List[Dict]:
        """Optimized BFS multi-hop retrieval"""
        
        with self.db_connection.connect() as conn:
            # Fixed BFS query with correct CTE syntax            
            result = conn.execute(text("""
                WITH RECURSIVE hop_expansion AS (
                    -- Initial query matching (no ORDER BY or LIMIT allowed here)
                    SELECT 
                        dc.id as chunk_id,
                        dc.content,
                        ARRAY[dc.id] as path,
                        0 as hops,
                        CAST(1.0 AS DOUBLE PRECISION) as confidence,
                        CAST(ts_rank(to_tsvector('english', dc.content), plainto_tsquery('english', :query)) AS DOUBLE PRECISION) as initial_relevance
                    FROM doc_chunks dc
                    WHERE to_tsvector('english', dc.content) @@ plainto_tsquery('english', :query)
                    
                    UNION ALL
                    
                    -- Recursive expansion with optimizations
                    SELECT 
                        lr.target_chunk_id as chunk_id,
                        dc.content,
                        he.path || lr.target_chunk_id,
                        he.hops + 1,
                        he.confidence * lr.confidence * 0.9 as confidence,
                        he.initial_relevance * 0.8
                    FROM hop_expansion he
                    JOIN logical_relationships lr ON he.chunk_id = lr.source_chunk_id
                    JOIN doc_chunks dc ON lr.target_chunk_id = dc.id
                    WHERE he.hops < :max_hops 
                      AND lr.confidence > 0.7
                      AND he.confidence > 0.4
                      AND NOT (lr.target_chunk_id = ANY(he.path))
                      AND array_length(he.path, 1) < 20
                ),
                -- Separate CTE to get top initial matches
                top_initial AS (
                    SELECT chunk_id, content, hops, confidence, initial_relevance
                    FROM hop_expansion
                    WHERE hops = 0
                    ORDER BY initial_relevance DESC
                    LIMIT 5
                ),
                -- Combine top initial matches with their expansions
                filtered_expansion AS (
                    SELECT he.chunk_id, he.content, he.hops, he.confidence, he.initial_relevance
                    FROM hop_expansion he
                    WHERE he.hops = 0 
                      AND he.chunk_id IN (SELECT chunk_id FROM top_initial)
                    
                    UNION ALL
                    
                    SELECT he.chunk_id, he.content, he.hops, he.confidence, he.initial_relevance
                    FROM hop_expansion he
                    WHERE he.hops > 0
                      AND EXISTS (
                          SELECT 1 FROM top_initial ti 
                          WHERE ti.chunk_id = ANY(he.path)
                      )
                )
                SELECT DISTINCT 
                    chunk_id, 
                    content, 
                    hops, 
                    confidence,
                    initial_relevance
                FROM filtered_expansion
                WHERE confidence > 0.3
                ORDER BY confidence DESC, initial_relevance DESC, hops ASC
                LIMIT :top_k;
            """), {"query": query, "max_hops": max_hops, "top_k": top_k * 2}).fetchall()
        
        return [dict(row._mapping) for row in result]
    
    async def analyze_graph_structure(self, chunk_ids: List[str]) -> List[GraphAnalysisResult]:  # Changed parameter type
        """Analyze graph structure and compute centrality measures"""
        
        if not chunk_ids:
            return []

        # Get subgraph data with correct table names
        with self.db_connection.connect() as conn:
            # Get nodes - convert chunk_ids to list for PostgreSQL array compatibility
            nodes_data = conn.execute(text("""
                SELECT id as chunk_id, content 
                FROM doc_chunks 
                WHERE id = ANY(:chunk_ids)
            """), {"chunk_ids": chunk_ids}).fetchall()
            
            # Get edges within subgraph
            edges_data = conn.execute(text("""
                SELECT source_chunk_id, target_chunk_id, confidence, relationship_type
                FROM logical_relationships 
                WHERE source_chunk_id = ANY(:chunk_ids) AND target_chunk_id = ANY(:chunk_ids)
                AND confidence > 0.5
            """), {"chunk_ids": chunk_ids}).fetchall()
        
        if not edges_data:
            # Return basic results if no relationships
            return [
                GraphAnalysisResult(
                    chunk_id=row.chunk_id,
                    content=row.content,
                    centrality_scores={'degree': 0.0, 'pagerank': 1.0/len(nodes_data), 'betweenness': 0.0},
                    community_id=0,
                    final_score=0.5
                )
                for row in nodes_data
            ]
        
        # Build NetworkX graph for analysis
        G = nx.DiGraph()
        
        # Add nodes
        for row in nodes_data:
            G.add_node(row.chunk_id, content=row.content)
        
        # Add edges
        for row in edges_data:
            G.add_edge(row.source_chunk_id, row.target_chunk_id, 
                      weight=row.confidence, type=row.relationship_type)
        
        # Compute centrality measures
        try:
            degree_centrality = nx.degree_centrality(G)
            pagerank = nx.pagerank(G, weight='weight', max_iter=100)
            
            # Betweenness centrality (expensive, so limit to smaller graphs)
            if len(G.nodes()) < 1000:
                betweenness_centrality = nx.betweenness_centrality(G, weight='weight')
            else:
                betweenness_centrality = {node: 0.0 for node in G.nodes()}
            
        except Exception as e:
            logger.warning(f"Centrality calculation failed: {e}")
            # Fallback to simple measures
            degree_centrality = {node: G.degree(node) for node in G.nodes()}
            max_degree = max(degree_centrality.values()) if degree_centrality else 1
            degree_centrality = {k: v/max_degree for k, v in degree_centrality.items()}
            
            pagerank = {node: 1.0/len(G.nodes()) for node in G.nodes()}
            betweenness_centrality = {node: 0.0 for node in G.nodes()}
        
        # Community detection
        try:
            # Convert to undirected for community detection
            G_undirected = G.to_undirected()
            communities = nx.community.greedy_modularity_communities(G_undirected)
            
            # Create community mapping
            community_map = {}
            for i, community in enumerate(communities):
                for node in community:
                    community_map[node] = i
        except:
            # Fallback: single community
            community_map = {node: 0 for node in G.nodes()}
        
        # Create analysis results
        results = []
        for row in nodes_data:
            chunk_id = row.chunk_id
            
            centrality_scores = {
                'degree': degree_centrality.get(chunk_id, 0.0),
                'pagerank': pagerank.get(chunk_id, 0.0),
                'betweenness': betweenness_centrality.get(chunk_id, 0.0)
            }
            
            # Calculate final score (weighted combination)
            final_score = (
                0.3 * centrality_scores['degree'] +
                0.5 * centrality_scores['pagerank'] +
                0.2 * centrality_scores['betweenness']
            )
            
            results.append(GraphAnalysisResult(
                chunk_id=chunk_id,
                content=row.content,
                centrality_scores=centrality_scores,
                community_id=community_map.get(chunk_id, 0),
                final_score=final_score
            ))
        
        return sorted(results, key=lambda x: x.final_score, reverse=True)
    
    async def get_top_ranked_nodes(self, query: str, max_hops: int = 3) -> Dict:
        """Get top 20 ranked nodes using BFS + graph analysis"""
        
        start_time = datetime.utcnow()
        
        # Step 1: BFS retrieval
        bfs_results = await self.bfs_multi_hop_retrieve(query, max_hops, top_k=50)
        
        if not bfs_results:
            return {
                "query": query,
                "total_nodes": 0,
                "top_nodes": [],
                "execution_time_ms": 0,
                "method": "bfs_graph_analysis"
            }
        
        # Step 2: Graph analysis
        chunk_ids = [result['chunk_id'] for result in bfs_results]
        analysis_results = await self.analyze_graph_structure(chunk_ids)
        
        # Step 3: Combine BFS relevance with graph analysis
        bfs_scores = {result['chunk_id']: result['confidence'] for result in bfs_results}
        
        final_results = []
        for analysis in analysis_results:
            bfs_score = bfs_scores.get(analysis.chunk_id, 0.0)
            
            # Combined score: BFS relevance + graph centrality
            combined_score = 0.6 * bfs_score + 0.4 * analysis.final_score
            
            final_results.append({
                "chunk_id": analysis.chunk_id,
                "content": analysis.content,
                "bfs_confidence": bfs_score,
                "centrality_scores": analysis.centrality_scores,
                "community_id": analysis.community_id,
                "combined_score": combined_score
            })
        
        # Sort by combined score and take top 20
        final_results.sort(key=lambda x: x['combined_score'], reverse=True)
        top_20 = final_results[:20]
        
        execution_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        return {
            "query": query,
            "total_nodes": len(final_results),
            "top_nodes": top_20,
            "execution_time_ms": execution_time,
            "method": "bfs_graph_analysis",
            "graph_stats": {
                "communities_found": len(set(r["community_id"] for r in final_results)),
                "max_centrality": max(r["centrality_scores"]["pagerank"] for r in final_results) if final_results else 0
            }
        }
    
    async def close(self):
        """Cleanup resources"""
        self.executor.shutdown(wait=True)
        logger.info("Optimized graph processor closed")


class HopRAGClassifier:
    """
    Classifier that categorizes nodes based on centrality score thresholds
    and ranks top 20 nodes into different importance categories
    """
    
    def __init__(self):
        # Hard-coded thresholds for centrality scores
        self.thresholds = {
            'degree': {
                'high': 0.7,    # High connectivity nodes
                'medium': 0.4,  # Medium connectivity nodes
                'low': 0.0      # Low connectivity nodes (everything else)
            },
            'pagerank': {
                'high': 0.15,   # High influence nodes
                'medium': 0.05, # Medium influence nodes
                'low': 0.0      # Low influence nodes (everything else)
            },
            'betweenness': {
                'high': 0.3,    # High bridging nodes
                'medium': 0.1,  # Medium bridging nodes
                'low': 0.0      # Low bridging nodes (everything else)
            }
        }
        
        # Classification categories
        self.categories = {
            'CORE_HUB': 'High centrality in all measures - critical knowledge nodes',
            'AUTHORITY': 'High PageRank - influential reference nodes',
            'CONNECTOR': 'High betweenness - bridge nodes between topics',
            'PERIPHERAL': 'Lower centrality - supporting information nodes'
        }
    
    def classify_nodes(self, processor_results: Dict) -> Dict:
        """
        Classify nodes from processor results into categories based on centrality thresholds
        
        Args:
            processor_results: Results from processor.get_top_ranked_nodes()
        
        Returns:
            Dict: Structured classification results with rankings
        """
        if not processor_results.get('top_nodes'):
            return self._empty_classification_result(processor_results)
        
        top_nodes = processor_results['top_nodes'][:20]  # Ensure we only take top 20
        
        # Classify each node
        classified_nodes = []
        for node in top_nodes:
            classification = self._classify_single_node(node)
            classified_nodes.append(classification)
        
        # Group by classification and rank within each group
        classification_groups = self._group_and_rank_nodes(classified_nodes)
        
        # Generate final structured output
        result = self._generate_classification_output(
            processor_results, 
            classification_groups, 
            classified_nodes
        )
        
        return result
    
    def _classify_single_node(self, node: Dict) -> NodeClassification:
        """Classify a single node based on its centrality scores"""
        centrality = node['centrality_scores']
        
        # Extract centrality values
        degree = centrality.get('degree', 0.0)
        pagerank = centrality.get('pagerank', 0.0)
        betweenness = centrality.get('betweenness', 0.0)
        
        # Determine classification category
        classification = self._determine_category(degree, pagerank, betweenness)
        
        # Determine confidence level based on score distribution
        confidence_level = self._determine_confidence_level(degree, pagerank, betweenness)
        
        return NodeClassification(
            chunk_id=node['chunk_id'],
            content=node['content'],
            centrality_scores=centrality,
            combined_score=node['combined_score'],
            classification=classification,
            rank_within_class=0,  # Will be set during grouping
            confidence_level=confidence_level
        )
    
    def _determine_category(self, degree: float, pagerank: float, betweenness: float) -> str:
        """Determine the category based on centrality thresholds"""
        
        # Count how many measures are "high"
        high_counts = sum([
            degree >= self.thresholds['degree']['high'],
            pagerank >= self.thresholds['pagerank']['high'],
            betweenness >= self.thresholds['betweenness']['high']
        ])
        
        # Specific classification logic
        if high_counts >= 2:
            return 'CORE_HUB'
        elif pagerank >= self.thresholds['pagerank']['high']:
            return 'AUTHORITY'
        elif betweenness >= self.thresholds['betweenness']['high']:
            return 'CONNECTOR'
        else:
            return 'PERIPHERAL'
    
    def _determine_confidence_level(self, degree: float, pagerank: float, betweenness: float) -> str:
        """Determine confidence level based on score magnitude"""
        avg_score = (degree + pagerank + betweenness) / 3
        
        if avg_score >= 0.6:
            return 'HIGH'
        elif avg_score >= 0.3:
            return 'MEDIUM'
        else:
            return 'LOW'
    
    def _group_and_rank_nodes(self, classified_nodes: List[NodeClassification]) -> Dict[str, List[NodeClassification]]:
        """Group nodes by classification and rank within each group"""
        groups = {category: [] for category in self.categories.keys()}
        
        # Group nodes
        for node in classified_nodes:
            groups[node.classification].append(node)
        
        # Sort and rank within each group
        for category, nodes in groups.items():
            # Sort by combined score descending
            nodes.sort(key=lambda x: x.combined_score, reverse=True)
            
            # Assign ranks within the group
            for i, node in enumerate(nodes):
                node.rank_within_class = i + 1
        
        return groups
    
    def _generate_classification_output(self, processor_results: Dict, 
                                      classification_groups: Dict[str, List[NodeClassification]], 
                                      all_classified_nodes: List[NodeClassification]) -> Dict:
        """Generate the final structured JSON output"""
        
        # Summary statistics
        total_nodes = len(all_classified_nodes)
        category_counts = {cat: len(nodes) for cat, nodes in classification_groups.items()}
        
        # Detailed results for each category
        category_details = {}
        for category, nodes in classification_groups.items():
            category_details[category] = {
                'description': self.categories[category],
                'count': len(nodes),
                'nodes': [
                    {
                        'chunk_id': node.chunk_id,
                        'content': node.content[:200] + "..." if len(node.content) > 200 else node.content,
                        'centrality_scores': node.centrality_scores,
                        'combined_score': round(node.combined_score, 4),
                        'rank_within_category': node.rank_within_class,
                        'confidence_level': node.confidence_level
                    }
                    for node in nodes
                ]
            }
        
        # Overall ranking (all nodes sorted by combined score)
        all_classified_nodes.sort(key=lambda x: x.combined_score, reverse=True)
        overall_ranking = [
            {
                'overall_rank': i + 1,
                'chunk_id': node.chunk_id,
                'classification': node.classification,
                'combined_score': round(node.combined_score, 4),
                'confidence_level': node.confidence_level
            }
            for i, node in enumerate(all_classified_nodes)
        ]
        
        # Threshold information
        threshold_info = {
            'thresholds_used': self.thresholds,
            'classification_criteria': {
                'CORE_HUB': 'High centrality in 2+ measures',
                'AUTHORITY': 'High PageRank score',
                'CONNECTOR': 'High betweenness centrality',
                'PERIPHERAL': 'Lower centrality scores'
            }
        }
        
        return {
            'metadata': {
                'query': processor_results.get('query', ''),
                'processing_method': processor_results.get('method', 'unknown'),
                'total_nodes_processed': processor_results.get('total_nodes', 0),
                'top_nodes_classified': total_nodes,
                'execution_time_ms': processor_results.get('execution_time_ms', 0),
                'classification_timestamp': datetime.utcnow().isoformat(),
                'graph_stats': processor_results.get('graph_stats', {})
            },
            'classification_summary': {
                'total_classified': total_nodes,
                'category_distribution': category_counts,
                'confidence_distribution': {
                    'HIGH': len([n for n in all_classified_nodes if n.confidence_level == 'HIGH']),
                    'MEDIUM': len([n for n in all_classified_nodes if n.confidence_level == 'MEDIUM']),
                    'LOW': len([n for n in all_classified_nodes if n.confidence_level == 'LOW'])
                }
            },
            'category_details': category_details,
            'overall_ranking': overall_ranking,
            'classification_config': threshold_info
        }
    
    def _empty_classification_result(self, processor_results: Dict) -> Dict:
        """Return empty result structure when no nodes to classify"""
        return {
            'metadata': {
                'query': processor_results.get('query', ''),
                'processing_method': processor_results.get('method', 'unknown'),
                'total_nodes_processed': 0,
                'top_nodes_classified': 0,
                'execution_time_ms': processor_results.get('execution_time_ms', 0),
                'classification_timestamp': datetime.utcnow().isoformat(),
                'graph_stats': {}
            },
            'classification_summary': {
                'total_classified': 0,
                'category_distribution': {cat: 0 for cat in self.categories.keys()},
                'confidence_distribution': {'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
            },
            'category_details': {
                cat: {'description': desc, 'count': 0, 'nodes': []}
                for cat, desc in self.categories.items()
            },
            'overall_ranking': [],
            'classification_config': {
                'thresholds_used': self.thresholds,
                'classification_criteria': {
                    'CORE_HUB': 'High centrality in 2+ measures',
                    'AUTHORITY': 'High PageRank score',
                    'CONNECTOR': 'High betweenness centrality',
                    'PERIPHERAL': 'Lower centrality scores'
                }
            }
        }
    
    def save_classification_results(self, results: Dict, filename: Optional[str] = None) -> str:
        """Save classification results to JSON file"""
        if filename is None:
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            filename = f"hoprag_classification_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, default=str, ensure_ascii=False)
        
        logger.info(f"Classification results saved to: {filename}")
        return filename
    
    def print_classification_summary(self, results: Dict):
        """Print a human-readable summary of classification results"""
        metadata = results['metadata']
        summary = results['classification_summary']
        
        logger.info(f"\n=== HopRAG Classification Results ===")
        logger.info(f"Query: {metadata['query']}")
        logger.info(f"Nodes Classified: {summary['total_classified']}")
        logger.info(f"Processing Time: {metadata['execution_time_ms']}ms")
        
        logger.info(f"\n--- Category Distribution ---")
        for category, count in summary['category_distribution'].items():
            logger.info(f"{category}: {count} nodes")
        
        logger.info(f"\n--- Confidence Distribution ---")
        for level, count in summary['confidence_distribution'].items():
            logger.info(f"{level}: {count} nodes")
        
        logger.info(f"\n--- Top 5 Overall Ranking ---")
        for i, node in enumerate(results['overall_ranking'][:5]):
            logger.info(f"{i+1}. Chunk {node['chunk_id']} ({node['classification']}) - Score: {node['combined_score']}")