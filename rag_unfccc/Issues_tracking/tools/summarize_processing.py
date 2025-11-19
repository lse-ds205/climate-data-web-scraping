"""
Processing Summary Script

Generates a summary of which countries were successfully processed and which failed
by analyzing scraper and chunker logs.

Usage:
    python Issues_tracking/tools/summarize_processing.py
    python Issues_tracking/tools/summarize_processing.py --detailed  # Show more details
"""

import sys
import re
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Set

# Fix path: from Issues_tracking/tools/ we need to go up 2 levels to project root
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

# Import database connection for embedding checks
try:
    from databases.docker_proxy import get_database_connection
    from sqlalchemy import text
    DB_AVAILABLE = True
except ImportError:
    try:
        # Fallback to full path
        from group4py.src.databases.docker_proxy import get_database_connection
        from sqlalchemy import text
        DB_AVAILABLE = True
    except ImportError:
        DB_AVAILABLE = False

def extract_country_from_filename(filename: str) -> str:
    """Extract country name from filename like 'Country_Language_Date.pdf'"""
    parts = filename.split('_')
    if parts:
        return parts[0].replace('\\', '').replace('/', '')
    return "Unknown"

def parse_scrape_log(log_file: Path) -> Dict[str, Dict]:
    """Parse scraper log and extract country processing info"""
    results = {
        'successful': defaultdict(int),
        'failed': defaultdict(list),
        'excluded': set(),
        'summary': {}
    }
    
    if not log_file.exists():
        return results
    
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    # Extract successful downloads
    successful_pattern = r'Successfully downloaded document to .+?/([^/]+)\.pdf'
    for match in re.finditer(successful_pattern, content):
        filename = match.group(1)
        country = extract_country_from_filename(filename)
        results['successful'][country] += 1
    
    # Extract failed downloads
    failed_pattern = r'Failed to download .+?: (.+?)\n'
    failed_url_pattern = r'Downloading document: ([^-]+) - .+? from (.+?)\n'
    
    # Get all download attempts
    download_attempts = list(re.finditer(r'Downloading document: ([^-]+) - .+? from (.+?)\n', content))
    failed_downloads = list(re.finditer(r'Failed to download (.+?): (.+?)\n', content))
    
    # Match failed downloads with countries
    for fail_match in failed_downloads:
        failed_url = fail_match.group(1)
        error_msg = fail_match.group(2)
        
        # Find the country for this URL
        for attempt in download_attempts:
            if failed_url in attempt.group(2):
                country = attempt.group(1).strip()
                results['failed'][country].append({
                    'url': failed_url,
                    'error': error_msg[:100]  # Truncate long errors
                })
                break
    
    # Extract excluded countries
    excluded_pattern = r'Sample of excluded countries: (.+?)\n'
    match = re.search(excluded_pattern, content)
    if match:
        excluded_str = match.group(1)
        excluded_countries = [c.strip() for c in excluded_str.split(',')]
        results['excluded'].update(excluded_countries)
    
    # Extract summary statistics
    summary_patterns = {
        'new_documents': r'New documents inserted: (\d+)',
        'downloaded': r'New documents downloaded: (\d+)',
        'failed_downloads': r'Failed downloads: (\d+)',
        'excluded_count': r'Documents excluded.*?: (\d+)',
    }
    
    for key, pattern in summary_patterns.items():
        match = re.search(pattern, content)
        if match:
            results['summary'][key] = int(match.group(1))
    
    return results

def parse_chunk_log(log_file: Path) -> Dict[str, Dict]:
    """Parse chunker log and extract country processing info"""
    results = {
        'successful': defaultdict(int),
        'failed': defaultdict(list),
        'skipped': defaultdict(int),
    }
    
    if not log_file.exists():
        return results
    
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    # Track processing context - map line numbers to countries being processed
    processing_context = {}  # line_num -> country
    
    for i, line in enumerate(lines):
        # Track when a file starts being processed
        if 'Processing file' in line:
            filename_match = re.search(r'Processing file .+?/([^/]+)\.pdf', line)
            if filename_match:
                filename = filename_match.group(1)
                country = extract_country_from_filename(filename)
                # Store context for next 50 lines (processing window)
                for j in range(i, min(i + 50, len(lines))):
                    processing_context[j] = country
        
        # Successful processing - look for upload message
        if '[3_CHUNK] Uploaded' in line and 'chunks to doc_chunks' in line:
            # Get country from processing context
            country = processing_context.get(i, None)
            if not country:
                # Fallback: look backwards for filename
                for j in range(max(0, i-20), i):
                    if 'Processing file' in lines[j]:
                        filename_match = re.search(r'Processing file .+?/([^/]+)\.pdf', lines[j])
                        if filename_match:
                            filename = filename_match.group(1)
                            country = extract_country_from_filename(filename)
                            break
            if country:
                results['successful'][country] += 1
        
        # Failed processing - only count errors that are in processing context
        if '[3_CHUNK] ERROR' in line or '[3_CHUNK] Error processing file' in line:
            # Get country from processing context or from line
            country = processing_context.get(i, None)
            if not country:
                # Try to extract from error line
                filename_match = re.search(r'Processing file .+?/([^/]+)\.pdf', line)
                if filename_match:
                    filename = filename_match.group(1)
                    country = extract_country_from_filename(filename)
                else:
                    # Fallback: look backwards
                    for j in range(max(0, i-20), i):
                        if 'Processing file' in lines[j]:
                            filename_match = re.search(r'Processing file .+?/([^/]+)\.pdf', lines[j])
                            if filename_match:
                                filename = filename_match.group(1)
                                country = extract_country_from_filename(filename)
                                break
            
            if country:
                # Get error message
                error_msg = line.split('ERROR')[1].strip() if 'ERROR' in line else line.strip()
                # Only add if it's a real processing error (not just any error)
                if 'Error processing file' in line or 'Chunking error' in line:
                    results['failed'][country].append({
                        'error': error_msg[:150]
                    })
        
        # Skipped (already processed)
        if 'has already been processed' in line:
            country = processing_context.get(i, None)
            if not country:
                # Look backwards
                for j in range(max(0, i-10), i):
                    if 'Processing file' in lines[j]:
                        filename_match = re.search(r'Processing file .+?/([^/]+)\.pdf', lines[j])
                        if filename_match:
                            filename = filename_match.group(1)
                            country = extract_country_from_filename(filename)
                            break
            if country:
                results['skipped'][country] += 1
    
    return results

def parse_embed_log(log_file: Path) -> Dict[str, Dict]:
    """Parse embedder log and extract processing info"""
    results = {
        'processed': 0,
        'failed': 0,
        'summary': {}
    }
    
    if not log_file.exists():
        return results
    
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    # Extract processed chunks count
    processed_pattern = r'Successfully generated embeddings for (\d+) chunks'
    match = re.search(processed_pattern, content)
    if match:
        results['processed'] = int(match.group(1))
    
    # Extract chunks needing embedding
    chunks_pattern = r'Found (\d+) chunks to process'
    match = re.search(chunks_pattern, content)
    if match:
        results['summary']['chunks_found'] = int(match.group(1))
    
    # Extract errors
    error_count = len(re.findall(r'\[3_EMBED\] ERROR', content))
    results['failed'] = error_count
    
    # Check if Word2Vec training happened
    if 'Training new global Word2Vec model' in content:
        results['summary']['word2vec_trained'] = True
    elif 'Loading existing Word2Vec model' in content:
        results['summary']['word2vec_loaded'] = True
    
    # Check if HopRAG processing happened
    if 'HopRAG processing completed successfully' in content:
        results['summary']['hoprag_completed'] = True
    
    return results

def check_embedding_status() -> Dict[str, Dict]:
    """Query database to check embedding status by country"""
    results = {
        'by_country': defaultdict(lambda: {'with_embeddings': 0, 'without_embeddings': 0}),
        'total_with': 0,
        'total_without': 0,
        'total_chunks': 0
    }
    
    if not DB_AVAILABLE:
        return results
    
    try:
        db = get_database_connection()
        with db.Session() as session:
            # Query chunks with their document countries and embedding status
            query = text("""
                SELECT 
                    d.country,
                    COUNT(*) FILTER (WHERE dc.transformer_embedding IS NOT NULL AND dc.word2vec_embedding IS NOT NULL) as with_embeddings,
                    COUNT(*) FILTER (WHERE dc.transformer_embedding IS NULL OR dc.word2vec_embedding IS NULL) as without_embeddings,
                    COUNT(*) as total_chunks
                FROM doc_chunks dc
                JOIN documents d ON dc.doc_id = d.doc_id
                GROUP BY d.country
                ORDER BY d.country
            """)
            
            result = session.execute(query)
            for row in result:
                country = row[0] or "Unknown"
                # Convert to int in case database returns strings
                with_emb = int(row[1]) if row[1] is not None else 0
                without_emb = int(row[2]) if row[2] is not None else 0
                total = int(row[3]) if row[3] is not None else 0
                
                results['by_country'][country] = {
                    'with_embeddings': with_emb,
                    'without_embeddings': without_emb,
                    'total': total
                }
                results['total_with'] += with_emb
                results['total_without'] += without_emb
                results['total_chunks'] += total
            
            # Also get overall stats
            overall_query = text("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE transformer_embedding IS NOT NULL AND word2vec_embedding IS NOT NULL) as with_embeddings,
                    COUNT(*) FILTER (WHERE transformer_embedding IS NULL OR word2vec_embedding IS NULL) as without_embeddings
                FROM doc_chunks
            """)
            
            overall_result = session.execute(overall_query)
            row = overall_result.fetchone()
            if row:
                # Convert to int in case database returns strings
                results['total_chunks'] = int(row[0]) if row[0] is not None else 0
                results['total_with'] = int(row[1]) if row[1] is not None else 0
                results['total_without'] = int(row[2]) if row[2] is not None else 0
                
    except Exception as e:
        results['error'] = str(e)
    
    return results

def generate_summary(detailed: bool = False):
    """Generate and print processing summary"""
    log_dir = project_root / "logs"
    scrape_log = log_dir / "scrape.log"
    chunk_log = log_dir / "chunk.log"
    
    print("=" * 80)
    print("PROCESSING SUMMARY")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print()
    
    # Parse scraper log
    print("📥 SCRAPER RESULTS")
    print("-" * 80)
    scrape_results = parse_scrape_log(scrape_log)
    
    if scrape_results['summary']:
        print(f"  New documents inserted: {scrape_results['summary'].get('new_documents', 0)}")
        print(f"  Successfully downloaded: {scrape_results['summary'].get('downloaded', 0)}")
        print(f"  Failed downloads: {scrape_results['summary'].get('failed_downloads', 0)}")
        print(f"  Excluded (not in allowed countries): {scrape_results['summary'].get('excluded_count', 0)}")
        print()
    
    if scrape_results['successful']:
        print(f"  ✅ Successfully downloaded ({len(scrape_results['successful'])} countries):")
        for country in sorted(scrape_results['successful'].keys()):
            count = scrape_results['successful'][country]
            print(f"     - {country}: {count} document(s)")
        print()
    
    if scrape_results['failed']:
        print(f"  ❌ Failed downloads ({len(scrape_results['failed'])} countries):")
        for country in sorted(scrape_results['failed'].keys()):
            failures = scrape_results['failed'][country]
            print(f"     - {country}: {len(failures)} failure(s)")
            if detailed:
                for failure in failures[:3]:  # Show first 3 errors
                    error = failure.get('error', 'Unknown error')
                    print(f"       • {error[:80]}")
        print()
    
    if scrape_results['excluded']:
        print(f"  ⏭️  Excluded countries ({len(scrape_results['excluded'])}):")
        excluded_list = sorted(list(scrape_results['excluded']))[:20]  # Show first 20
        print(f"     {', '.join(excluded_list)}")
        if len(scrape_results['excluded']) > 20:
            print(f"     ... and {len(scrape_results['excluded']) - 20} more")
        print()
    
    # Parse chunker log
    print("📄 CHUNKER RESULTS")
    print("-" * 80)
    chunk_results = parse_chunk_log(chunk_log)
    
    successful_countries = set(chunk_results['successful'].keys())
    failed_countries = set(chunk_results['failed'].keys())
    skipped_countries = set(chunk_results['skipped'].keys())
    
    total_processed = len(successful_countries | failed_countries | skipped_countries)
    
    if total_processed > 0:
        print(f"  Total countries processed: {total_processed}")
        print()
    
    if chunk_results['successful']:
        total_chunks = sum(chunk_results['successful'].values())
        print(f"  ✅ Successfully chunked ({len(chunk_results['successful'])} countries, {total_chunks} total chunks):")
        for country in sorted(chunk_results['successful'].keys()):
            count = chunk_results['successful'][country]
            print(f"     - {country}: {count} chunk(s)")
        print()
    
    if chunk_results['skipped']:
        print(f"  ⏭️  Skipped (already processed) ({len(chunk_results['skipped'])} countries):")
        for country in sorted(chunk_results['skipped'].keys()):
            count = chunk_results['skipped'][country]
            print(f"     - {country}: {count} document(s)")
        print()
    
    if chunk_results['failed']:
        print(f"  ❌ Failed chunking ({len(chunk_results['failed'])} countries):")
        for country in sorted(chunk_results['failed'].keys()):
            failures = chunk_results['failed'][country]
            print(f"     - {country}: {len(failures)} failure(s)")
            if detailed:
                for failure in failures[:2]:  # Show first 2 errors
                    error = failure.get('error', 'Unknown error')
                    # Clean up error message
                    error = error.replace('\n', ' ').strip()
                    print(f"       • {error[:100]}")
        print()
    
    # Parse embedder log and check database
    print("🔢 EMBEDDING RESULTS")
    print("-" * 80)
    embed_log = log_dir / "embed.log"
    embed_results = parse_embed_log(embed_log)
    embedding_status = check_embedding_status()
    
    if embedding_status.get('error'):
        print(f"  ⚠️  Could not query database: {embedding_status['error']}")
        print()
    else:
        total_chunks = embedding_status.get('total_chunks', 0)
        total_with = embedding_status.get('total_with', 0)
        total_without = embedding_status.get('total_without', 0)
        
        if total_chunks > 0:
            percentage = (total_with / total_chunks * 100) if total_chunks > 0 else 0
            print(f"  Overall Status:")
            print(f"    Total chunks: {total_chunks}")
            print(f"    With embeddings: {total_with} ({percentage:.1f}%)")
            print(f"    Without embeddings: {total_without} ({100-percentage:.1f}%)")
            print()
        
        # Show by country
        if embedding_status['by_country']:
            countries_with_missing = []
            countries_complete = []
            
            for country, stats in sorted(embedding_status['by_country'].items()):
                with_emb = stats['with_embeddings']
                without_emb = stats['without_embeddings']
                total = stats['total']
                
                if without_emb > 0:
                    countries_with_missing.append((country, with_emb, without_emb, total))
                else:
                    countries_complete.append((country, total))
            
            if countries_complete:
                print(f"  ✅ Countries with complete embeddings ({len(countries_complete)}):")
                for country, total in countries_complete[:15]:  # Show first 15
                    print(f"     - {country}: {total} chunk(s)")
                if len(countries_complete) > 15:
                    print(f"     ... and {len(countries_complete) - 15} more")
                print()
            
            if countries_with_missing:
                print(f"  ⚠️  Countries with missing embeddings ({len(countries_with_missing)}):")
                for country, with_emb, without_emb, total in countries_with_missing:
                    # Ensure all values are ints
                    with_emb = int(with_emb) if isinstance(with_emb, (str, int)) else 0
                    without_emb = int(without_emb) if isinstance(without_emb, (str, int)) else 0
                    total = int(total) if isinstance(total, (str, int)) else 0
                    percentage = (with_emb / total * 100) if total > 0 else 0
                    print(f"     - {country}: {with_emb}/{total} embedded ({percentage:.1f}%)")
                print()
        
        # Embed log summary
        if embed_results['processed'] > 0 or embed_results.get('summary'):
            print(f"  Embedding Process:")
            if embed_results['processed'] > 0:
                print(f"    Processed: {embed_results['processed']} chunks")
            if embed_results.get('summary', {}).get('chunks_found'):
                print(f"    Found: {embed_results['summary']['chunks_found']} chunks needing embedding")
            if embed_results.get('summary', {}).get('word2vec_trained'):
                print(f"    Word2Vec: Trained new model")
            elif embed_results.get('summary', {}).get('word2vec_loaded'):
                print(f"    Word2Vec: Loaded existing model")
            if embed_results.get('summary', {}).get('hoprag_completed'):
                print(f"    HopRAG: Processing completed")
            print()
    
    # Overall summary
    print("=" * 80)
    print("OVERALL SUMMARY")
    print("=" * 80)
    
    scrape_success = len(scrape_results['successful'])
    scrape_failed = len(scrape_results['failed'])
    chunk_success = len(chunk_results['successful'])
    chunk_failed = len(chunk_results['failed'])
    
    # Embedding stats
    embedding_status = check_embedding_status()
    total_chunks = embedding_status.get('total_chunks', 0)
    total_with_emb = embedding_status.get('total_with', 0)
    total_without_emb = embedding_status.get('total_without', 0)
    
    print(f"  Scraper: {scrape_success} successful, {scrape_failed} failed")
    print(f"  Chunker: {chunk_success} successful, {chunk_failed} failed")
    if total_chunks > 0:
        emb_percentage = (total_with_emb / total_chunks * 100) if total_chunks > 0 else 0
        print(f"  Embeddings: {total_with_emb}/{total_chunks} chunks embedded ({emb_percentage:.1f}%)")
    print()
    
    # Countries that need attention
    all_failed = set(scrape_results['failed'].keys()) | set(chunk_results['failed'].keys())
    
    # Add countries with missing embeddings
    countries_missing_emb = set()
    if embedding_status.get('by_country'):
        for country, stats in embedding_status['by_country'].items():
            # Handle both int and str types
            without_emb = stats.get('without_embeddings', 0)
            if isinstance(without_emb, str):
                without_emb = int(without_emb) if without_emb.isdigit() else 0
            if without_emb > 0:
                countries_missing_emb.add(country)
    
    all_issues = all_failed | countries_missing_emb
    
    if all_issues:
        print(f"  ⚠️  Countries needing attention ({len(all_issues)}):")
        issues_list = []
        for country in sorted(all_issues):
            issues = []
            if country in scrape_results['failed']:
                issues.append("scraper failed")
            if country in chunk_results['failed']:
                issues.append("chunker failed")
            if country in countries_missing_emb:
                missing = embedding_status['by_country'][country]['without_embeddings']
                # Ensure it's an int
                if isinstance(missing, str):
                    missing = int(missing) if missing.isdigit() else 0
                issues.append(f"{missing} chunks missing embeddings")
            issues_list.append(f"{country} ({', '.join(issues)})")
        print(f"     {', '.join(issues_list[:10])}")  # Show first 10
        if len(issues_list) > 10:
            print(f"     ... and {len(issues_list) - 10} more")
    else:
        print("  ✅ No failures detected!")
    
    print("=" * 80)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate processing summary from logs")
    parser.add_argument("--detailed", "-d", action="store_true", 
                       help="Show detailed error messages")
    
    args = parser.parse_args()
    generate_summary(detailed=args.detailed)


