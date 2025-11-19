#!/usr/bin/env python3
"""
Check embeddings in the database to verify they exist and are working.
"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

def check_embeddings():
    """Check if embeddings exist in the database."""
    print("🔍 Checking Embeddings in Database...")
    
    try:
        from group4py.src.databases.docker_proxy import get_database_connection
        
        db = get_database_connection()
        session = db.Session()
        
        # Check total chunks
        result = session.execute("SELECT COUNT(*) FROM doc_chunks")
        total_chunks = result.fetchone()[0]
        print(f"📊 Total chunks in database: {total_chunks}")
        
        # Check chunks with embeddings
        result = session.execute("""
            SELECT COUNT(*) FROM doc_chunks 
            WHERE transformer_embedding IS NOT NULL 
            AND word2vec_embedding IS NOT NULL
        """)
        chunks_with_embeddings = result.fetchone()[0]
        print(f"📊 Chunks with both embeddings: {chunks_with_embeddings}")
        
        # Check chunks by country
        result = session.execute("""
            SELECT 
                chunk_data->>'country' as country,
                COUNT(*) as chunk_count,
                COUNT(CASE WHEN transformer_embedding IS NOT NULL THEN 1 END) as transformer_count,
                COUNT(CASE WHEN word2vec_embedding IS NOT NULL THEN 1 END) as word2vec_count
            FROM doc_chunks 
            WHERE chunk_data->>'country' IS NOT NULL
            GROUP BY chunk_data->>'country'
            ORDER BY chunk_count DESC
            LIMIT 10
        """)
        
        print(f"\n🌍 Top 10 Countries by Chunk Count:")
        print(f"{'Country':<20} {'Total':<8} {'Transformer':<12} {'Word2Vec':<10}")
        print("-" * 60)
        for row in result.fetchall():
            country, total, transformer, word2vec = row
            print(f"{country:<20} {total:<8} {transformer:<12} {word2vec:<10}")
        
        # Check embedding dimensions
        result = session.execute("""
            SELECT 
                vector_dims(transformer_embedding) as transformer_dims,
                vector_dims(word2vec_embedding) as word2vec_dims
            FROM doc_chunks 
            WHERE transformer_embedding IS NOT NULL 
            AND word2vec_embedding IS NOT NULL
            LIMIT 1
        """)
        
        dims = result.fetchone()
        if dims:
            print(f"\n📐 Embedding Dimensions:")
            print(f"  Transformer: {dims[0]} dimensions")
            print(f"  Word2Vec: {dims[1]} dimensions")
        
        # Check Australia specifically
        result = session.execute("""
            SELECT 
                COUNT(*) as total_chunks,
                COUNT(CASE WHEN transformer_embedding IS NOT NULL THEN 1 END) as transformer_count,
                COUNT(CASE WHEN word2vec_embedding IS NOT NULL THEN 1 END) as word2vec_count
            FROM doc_chunks 
            WHERE chunk_data->>'country' = 'Australia'
        """)
        
        aus_data = result.fetchone()
        if aus_data:
            total, transformer, word2vec = aus_data
            print(f"\n🇦🇺 Australia Specific:")
            print(f"  Total chunks: {total}")
            print(f"  With transformer embeddings: {transformer}")
            print(f"  With word2vec embeddings: {word2vec}")
        
        session.close()
        print(f"\n✅ Database connection successful!")
        
    except Exception as e:
        print(f"❌ Error checking embeddings: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_embeddings()
