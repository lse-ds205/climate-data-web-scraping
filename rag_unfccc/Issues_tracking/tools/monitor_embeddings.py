#!/usr/bin/env python3
"""
Monitor embedding progress and verify that embeddings are being created correctly.
This script helps track the embedding process and verify data integrity.
"""

import sys
import os
from pathlib import Path
import time
from sqlalchemy import text

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from group4py.src.databases.docker_proxy import get_database_connection
from group4py.src.databases.auth import PostgresConnection

def get_embedding_stats():
    """Get current embedding statistics from the database."""
    try:
        # Use Docker proxy connection directly
        from group4py.src.databases.docker_proxy import execute_sql_via_docker
        
        # Get total chunks
        total_result = execute_sql_via_docker("SELECT COUNT(*) FROM doc_chunks")
        total_chunks = int(total_result[0][0]) if total_result else 0
        
        # Get chunks with transformer embeddings
        transformer_result = execute_sql_via_docker("""
            SELECT COUNT(*) FROM doc_chunks 
            WHERE transformer_embedding IS NOT NULL
        """)
        transformer_count = int(transformer_result[0][0]) if transformer_result else 0
        
        # Get chunks with Word2Vec embeddings
        word2vec_result = execute_sql_via_docker("""
            SELECT COUNT(*) FROM doc_chunks 
            WHERE word2vec_embedding IS NOT NULL
        """)
        word2vec_count = int(word2vec_result[0][0]) if word2vec_result else 0
        
        # Get chunks with both embeddings
        both_result = execute_sql_via_docker("""
            SELECT COUNT(*) FROM doc_chunks 
            WHERE transformer_embedding IS NOT NULL 
            AND word2vec_embedding IS NOT NULL
        """)
        both_count = int(both_result[0][0]) if both_result else 0
        
        # Get embedding dimensions using vector_dims function
        dim_result = execute_sql_via_docker("""
            SELECT 
                vector_dims(transformer_embedding) as transformer_dims,
                vector_dims(word2vec_embedding) as word2vec_dims
            FROM doc_chunks 
            WHERE transformer_embedding IS NOT NULL 
            AND word2vec_embedding IS NOT NULL
            LIMIT 1
        """)
        
        transformer_dims = None
        word2vec_dims = None
        if dim_result and len(dim_result) > 0:
            transformer_dims = int(dim_result[0][0]) if dim_result[0][0] else None
            word2vec_dims = int(dim_result[0][1]) if dim_result[0][1] else None
        
        return {
            'total_chunks': total_chunks,
            'transformer_count': transformer_count,
            'word2vec_count': word2vec_count,
            'both_count': both_count,
            'transformer_dims': transformer_dims,
            'word2vec_dims': word2vec_dims
        }
        
    except Exception as e:
        print(f"Error getting embedding stats: {e}")
        return None

def monitor_embeddings(interval=30):
    """Monitor embedding progress with periodic updates."""
    print("🔍 Embedding Progress Monitor")
    print("=" * 50)
    print(f"Monitoring every {interval} seconds...")
    print("Press Ctrl+C to stop monitoring")
    print()
    
    try:
        while True:
            stats = get_embedding_stats()
            if stats:
                print(f"📊 Embedding Progress - {time.strftime('%H:%M:%S')}")
                print(f"   Total chunks: {stats['total_chunks']:,}")
                print(f"   Transformer embeddings: {stats['transformer_count']:,} ({stats['transformer_count']/stats['total_chunks']*100:.1f}%)")
                print(f"   Word2Vec embeddings: {stats['word2vec_count']:,} ({stats['word2vec_count']/stats['total_chunks']*100:.1f}%)")
                print(f"   Both embeddings: {stats['both_count']:,} ({stats['both_count']/stats['total_chunks']*100:.1f}%)")
                
                if stats['transformer_dims'] and stats['word2vec_dims']:
                    print(f"   Dimensions - Transformer: {stats['transformer_dims']}, Word2Vec: {stats['word2vec_dims']}")
                
                # Check if complete
                if stats['both_count'] == stats['total_chunks']:
                    print("✅ EMBEDDING COMPLETE! All chunks have both embeddings.")
                    break
                    
                print()
            else:
                print("❌ Error getting embedding stats")
            
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print("\n🛑 Monitoring stopped by user")
    except Exception as e:
        print(f"\n❌ Error during monitoring: {e}")

def verify_sample_embeddings(sample_size=5):
    """Verify a sample of embeddings to ensure they're valid."""
    print("🔍 Verifying Sample Embeddings")
    print("=" * 40)
    
    try:
        from group4py.src.databases.docker_proxy import execute_sql_via_docker
        
        # Get sample chunks with embeddings
        result = execute_sql_via_docker(f"""
            SELECT id, content, 
                   vector_dims(transformer_embedding) as transformer_dims,
                   vector_dims(word2vec_embedding) as word2vec_dims,
                   transformer_embedding[1:3] as transformer_sample,
                   word2vec_embedding[1:3] as word2vec_sample
            FROM doc_chunks 
            WHERE transformer_embedding IS NOT NULL 
            AND word2vec_embedding IS NOT NULL
            LIMIT {sample_size}
        """)
        
        if not result:
            print("❌ No chunks with embeddings found!")
            return
        
        print(f"✅ Found {len(result)} chunks with embeddings")
        print()
        
        for i, row in enumerate(result, 1):
            print(f"Chunk {i}: {row[0]}")
            print(f"  Content: {row[1][:100]}...")
            print(f"  Transformer: {row[2]} dims, sample: {row[4]}")
            print(f"  Word2Vec: {row[3]} dims, sample: {row[5]}")
            print()
        
    except Exception as e:
        print(f"❌ Error verifying embeddings: {e}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Monitor embedding progress")
    parser.add_argument("--monitor", action="store_true", help="Start monitoring mode")
    parser.add_argument("--verify", action="store_true", help="Verify sample embeddings")
    parser.add_argument("--interval", type=int, default=30, help="Monitoring interval in seconds")
    parser.add_argument("--sample", type=int, default=5, help="Number of samples to verify")
    
    args = parser.parse_args()
    
    if args.monitor:
        monitor_embeddings(args.interval)
    elif args.verify:
        verify_sample_embeddings(args.sample)
    else:
        # Default: show current stats
        stats = get_embedding_stats()
        if stats:
            print("📊 Current Embedding Status")
            print("=" * 30)
            print(f"Total chunks: {stats['total_chunks']:,}")
            print(f"Transformer: {stats['transformer_count']:,} ({stats['transformer_count']/stats['total_chunks']*100:.1f}%)")
            print(f"Word2Vec: {stats['word2vec_count']:,} ({stats['word2vec_count']/stats['total_chunks']*100:.1f}%)")
            print(f"Both: {stats['both_count']:,} ({stats['both_count']/stats['total_chunks']*100:.1f}%)")
            
            if stats['transformer_dims'] and stats['word2vec_dims']:
                print(f"Dimensions - Transformer: {stats['transformer_dims']}, Word2Vec: {stats['word2vec_dims']}")
        else:
            print("❌ Could not get embedding stats")
