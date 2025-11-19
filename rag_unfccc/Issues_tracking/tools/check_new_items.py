"""
Check New Items Script

Shows which countries have new documents, chunks, and embeddings added
within a specified time period.

Usage:
    python Issues_tracking/tools/check_new_items.py                    # Last 24 hours
    python Issues_tracking/tools/check_new_items.py --days 7            # Last 7 days
    python Issues_tracking/tools/check_new_items.py --hours 12          # Last 12 hours
    python Issues_tracking/tools/check_new_items.py --since "2025-11-18" # Since specific date
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, Optional

# Fix path: from Issues_tracking/tools/ we need to go up 2 levels to project root
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

# Import database connection
try:
    from databases.docker_proxy import get_database_connection
    from sqlalchemy import text
    DB_AVAILABLE = True
except ImportError:
    try:
        from group4py.src.databases.docker_proxy import get_database_connection
        from sqlalchemy import text
        DB_AVAILABLE = True
    except ImportError:
        DB_AVAILABLE = False
        print("⚠️  Database connection not available")


def parse_time_filter(args) -> Optional[datetime]:
    """Parse time filter arguments into a datetime threshold."""
    if args.since:
        try:
            # Parse date string (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)
            if ' ' in args.since:
                return datetime.strptime(args.since, '%Y-%m-%d %H:%M:%S')
            else:
                return datetime.strptime(args.since, '%Y-%m-%d')
        except ValueError:
            print(f"⚠️  Invalid date format: {args.since}. Use YYYY-MM-DD or YYYY-MM-DD HH:MM:SS")
            return None
    
    # Calculate from hours or days
    if args.hours:
        return datetime.now() - timedelta(hours=args.hours)
    elif args.days:
        return datetime.now() - timedelta(days=args.days)
    else:
        # Default: last 24 hours
        return datetime.now() - timedelta(hours=24)


def check_new_documents(since_time: datetime) -> Dict[str, Dict]:
    """Check for new documents by country."""
    results = defaultdict(lambda: {
        'new_documents': 0,
        'new_downloads': 0,
        'new_processed': 0,
        'documents': []
    })
    
    if not DB_AVAILABLE:
        return results
    
    try:
        db = get_database_connection()
        with db.Session() as session:
            # Get documents scraped, downloaded, or processed since the threshold
            query = text("""
                SELECT 
                    country,
                    doc_id,
                    title,
                    scraped_at,
                    downloaded_at,
                    processed_at,
                    created_at
                FROM documents
                WHERE 
                    scraped_at >= :since_time OR
                    downloaded_at >= :since_time OR
                    processed_at >= :since_time OR
                    created_at >= :since_time
                ORDER BY country, created_at DESC
            """)
            
            result = session.execute(query, {'since_time': since_time})
            for row in result:
                country = row[0] or "Unknown"
                doc_id = str(row[1])
                title = row[2] or "Untitled"
                scraped_at = row[3]
                downloaded_at = row[4]
                processed_at = row[5]
                created_at = row[6]
                
                # Determine what's new
                is_new_scrape = scraped_at and scraped_at >= since_time
                is_new_download = downloaded_at and downloaded_at >= since_time
                is_new_processed = processed_at and processed_at >= since_time
                
                if is_new_scrape:
                    results[country]['new_documents'] += 1
                if is_new_download:
                    results[country]['new_downloads'] += 1
                if is_new_processed:
                    results[country]['new_processed'] += 1
                
                results[country]['documents'].append({
                    'doc_id': doc_id,
                    'title': title[:60],  # Truncate long titles
                    'scraped_at': scraped_at,
                    'downloaded_at': downloaded_at,
                    'processed_at': processed_at,
                })
                
    except Exception as e:
        print(f"⚠️  Error querying documents: {e}")
    
    return results


def check_new_chunks(since_time: datetime) -> Dict[str, Dict]:
    """Check for new chunks by country."""
    results = defaultdict(lambda: {
        'new_chunks': 0,
        'total_chunks': 0
    })
    
    if not DB_AVAILABLE:
        return results
    
    try:
        db = get_database_connection()
        with db.Session() as session:
            # Get chunks created since the threshold, grouped by country
            query = text("""
                SELECT 
                    d.country,
                    COUNT(*) as total_chunks
                FROM doc_chunks dc
                JOIN documents d ON dc.doc_id = d.doc_id
                WHERE dc.created_at >= :since_time
                GROUP BY d.country
                ORDER BY d.country
            """)
            
            result = session.execute(query, {'since_time': since_time})
            for row in result:
                country = row[0] or "Unknown"
                count = int(row[1]) if row[1] is not None else 0
                results[country]['new_chunks'] = count
                results[country]['total_chunks'] = count
                
    except Exception as e:
        print(f"⚠️  Error querying chunks: {e}")
    
    return results


def check_new_embeddings(since_time: datetime) -> Dict[str, Dict]:
    """Check for new embeddings by country."""
    results = defaultdict(lambda: {
        'new_embeddings': 0,
        'transformer_only': 0,
        'word2vec_only': 0,
        'both': 0
    })
    
    if not DB_AVAILABLE:
        return results
    
    try:
        db = get_database_connection()
        with db.Session() as session:
            # Get chunks with embeddings updated/created since threshold
            # Check both created_at and updated_at (embeddings might update existing chunks)
            query = text("""
                SELECT 
                    d.country,
                    COUNT(*) FILTER (WHERE dc.transformer_embedding IS NOT NULL AND dc.word2vec_embedding IS NOT NULL) as both_embeddings,
                    COUNT(*) FILTER (WHERE dc.transformer_embedding IS NOT NULL AND dc.word2vec_embedding IS NULL) as transformer_only,
                    COUNT(*) FILTER (WHERE dc.transformer_embedding IS NULL AND dc.word2vec_embedding IS NOT NULL) as word2vec_only,
                    COUNT(*) as total_with_any_embedding
                FROM doc_chunks dc
                JOIN documents d ON dc.doc_id = d.doc_id
                WHERE 
                    (dc.created_at >= :since_time OR dc.updated_at >= :since_time)
                    AND (dc.transformer_embedding IS NOT NULL OR dc.word2vec_embedding IS NOT NULL)
                GROUP BY d.country
                ORDER BY d.country
            """)
            
            result = session.execute(query, {'since_time': since_time})
            for row in result:
                country = row[0] or "Unknown"
                both = int(row[1]) if row[1] is not None else 0
                transformer_only = int(row[2]) if row[2] is not None else 0
                word2vec_only = int(row[3]) if row[3] is not None else 0
                total = int(row[4]) if row[4] is not None else 0
                
                results[country]['new_embeddings'] = total
                results[country]['both'] = both
                results[country]['transformer_only'] = transformer_only
                results[country]['word2vec_only'] = word2vec_only
                
    except Exception as e:
        print(f"⚠️  Error querying embeddings: {e}")
    
    return results


def generate_report(since_time: datetime, show_details: bool = False):
    """Generate and print report of new items."""
    print("=" * 80)
    print("NEW ITEMS REPORT")
    print("=" * 80)
    print(f"Time period: Since {since_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print()
    
    if not DB_AVAILABLE:
        print("⚠️  Database connection not available. Cannot generate report.")
        return
    
    # Get data
    print("📊 Querying database...")
    doc_results = check_new_documents(since_time)
    chunk_results = check_new_chunks(since_time)
    embedding_results = check_new_embeddings(since_time)
    
    # Combine all countries
    all_countries = set(doc_results.keys()) | set(chunk_results.keys()) | set(embedding_results.keys())
    
    if not all_countries:
        print("\n✅ No new items found in the specified time period.")
        return
    
    # Group by country
    print(f"\n📥 NEW DOCUMENTS")
    print("-" * 80)
    countries_with_new_docs = [c for c in all_countries if doc_results[c]['new_documents'] > 0]
    if countries_with_new_docs:
        for country in sorted(countries_with_new_docs):
            stats = doc_results[country]
            print(f"  {country}:")
            print(f"    New documents scraped: {stats['new_documents']}")
            print(f"    New downloads: {stats['new_downloads']}")
            print(f"    New processed: {stats['new_processed']}")
            if show_details and stats['documents']:
                print(f"    Documents:")
                for doc in stats['documents'][:5]:  # Show first 5
                    print(f"      - {doc['title']}")
                    if doc['scraped_at']:
                        print(f"        Scraped: {doc['scraped_at']}")
                    if doc['downloaded_at']:
                        print(f"        Downloaded: {doc['downloaded_at']}")
                    if doc['processed_at']:
                        print(f"        Processed: {doc['processed_at']}")
                if len(stats['documents']) > 5:
                    print(f"      ... and {len(stats['documents']) - 5} more")
    else:
        print("  No new documents found.")
    print()
    
    print(f"📄 NEW CHUNKS")
    print("-" * 80)
    countries_with_new_chunks = [c for c in all_countries if chunk_results[c]['new_chunks'] > 0]
    if countries_with_new_chunks:
        for country in sorted(countries_with_new_chunks):
            stats = chunk_results[country]
            print(f"  {country}: {stats['new_chunks']} new chunk(s)")
    else:
        print("  No new chunks found.")
    print()
    
    print(f"🔢 NEW EMBEDDINGS")
    print("-" * 80)
    countries_with_new_embeddings = [c for c in all_countries if embedding_results[c]['new_embeddings'] > 0]
    if countries_with_new_embeddings:
        for country in sorted(countries_with_new_embeddings):
            stats = embedding_results[country]
            print(f"  {country}: {stats['new_embeddings']} new embedding(s)")
            if stats['both'] > 0:
                print(f"    - {stats['both']} with both transformer + word2vec")
            if stats['transformer_only'] > 0:
                print(f"    - {stats['transformer_only']} with transformer only")
            if stats['word2vec_only'] > 0:
                print(f"    - {stats['word2vec_only']} with word2vec only")
    else:
        print("  No new embeddings found.")
    print()
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"  Countries with new documents: {len(countries_with_new_docs)}")
    print(f"  Countries with new chunks: {len(countries_with_new_chunks)}")
    print(f"  Countries with new embeddings: {len(countries_with_new_embeddings)}")
    print()
    
    # Countries with activity
    active_countries = set(countries_with_new_docs) | set(countries_with_new_chunks) | set(countries_with_new_embeddings)
    if active_countries:
        print(f"  🌟 Active countries ({len(active_countries)}):")
        print(f"     {', '.join(sorted(active_countries))}")
    else:
        print("  ✅ No activity in the specified time period.")
    
    print("=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Check which countries have new documents, chunks, and embeddings",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python Issues_tracking/tools/check_new_items.py                    # Last 24 hours (default)
  python Issues_tracking/tools/check_new_items.py --days 7           # Last 7 days
  python Issues_tracking/tools/check_new_items.py --hours 12         # Last 12 hours
  python Issues_tracking/tools/check_new_items.py --since "2025-11-18"  # Since specific date
  python Issues_tracking/tools/check_new_items.py --since "2025-11-18 00:00:00" --detailed  # With details
        """
    )
    
    time_group = parser.add_mutually_exclusive_group()
    time_group.add_argument('--hours', type=int, help='Check items from last N hours')
    time_group.add_argument('--days', type=int, help='Check items from last N days')
    time_group.add_argument('--since', type=str, help='Check items since date (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)')
    
    parser.add_argument('--detailed', '-d', action='store_true',
                       help='Show detailed information (document titles, etc.)')
    
    args = parser.parse_args()
    
    since_time = parse_time_filter(args)
    if since_time:
        generate_report(since_time, show_details=args.detailed)
    else:
        print("⚠️  Could not parse time filter. Use --hours, --days, or --since")

