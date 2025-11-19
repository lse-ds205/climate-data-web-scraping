"""
Inspect chunks in the database with nice formatting.
Run: python tools/inspect_chunks.py
"""

import sys
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box
from sqlalchemy import text
from dotenv import load_dotenv

# Add project root to path
# From Issues_tracking/tools/ we need to go up 2 levels to project root
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

# Load environment variables from .env
load_dotenv()

# Import group4py first to set up paths
import group4py
from group4py.src.databases.docker_proxy import get_database_connection

console = Console()


def get_overview():
    """Get overview statistics."""
    db = get_database_connection()
    
    with db.Session() as session:
        query = text("""
            SELECT 
                COUNT(DISTINCT d.doc_id) as total_docs,
                COUNT(DISTINCT CASE WHEN d.processed_at IS NOT NULL THEN d.doc_id END) as processed_docs,
                COUNT(dc.id) as total_chunks,
                COALESCE(ROUND(AVG(LENGTH(dc.content)), 0), 0) as avg_length,
                COALESCE(MIN(LENGTH(dc.content)), 0) as min_length,
                COALESCE(MAX(LENGTH(dc.content)), 0) as max_length
            FROM documents d
            LEFT JOIN doc_chunks dc ON d.doc_id = dc.doc_id
        """)
        
        result = session.execute(query)
        row = result.fetchone()
        
        # Debug: log the row data (remove in production)
        # print(f"Debug: Raw row data: {row}")
        # print(f"Debug: Row length: {len(row) if row else 0}")
        
        return {
            'total_documents': int(row[0]) if row and len(row) > 0 and row[0] else 0,
            'processed_documents': int(row[1]) if row and len(row) > 1 and row[1] else 0,
            'total_chunks': int(row[2]) if row and len(row) > 2 and row[2] else 0,
            'avg_length': int(row[3]) if row and len(row) > 3 and row[3] else 0,
            'min_length': int(row[4]) if row and len(row) > 4 and row[4] else 0,
            'max_length': int(row[5]) if row and len(row) > 5 and row[5] else 0
        }


def get_chunks_by_country():
    """Get chunk counts by country."""
    db = get_database_connection()
    
    with db.Session() as session:
        query = text("""
            SELECT 
                d.country,
                COUNT(dc.id) as num_chunks,
                ROUND(AVG(LENGTH(dc.content)), 0) as avg_length,
                COUNT(DISTINCT d.doc_id) as num_docs
            FROM documents d
            LEFT JOIN doc_chunks dc ON d.doc_id = dc.doc_id
            WHERE d.processed_at IS NOT NULL
            GROUP BY d.country
            ORDER BY num_chunks DESC
        """)
        
        result = session.execute(query)
        return [
            {
                'country': row[0],
                'num_chunks': int(row[1]) if row[1] else 0,
                'avg_length': int(row[2]) if row[2] else 0,
                'num_docs': int(row[3]) if row[3] else 0
            }
            for row in result.fetchall()
        ]


def get_sample_chunks(country=None, limit=10):
    """Get sample chunks from database."""
    db = get_database_connection()
    
    with db.Session() as session:
        if country:
            query = text("""
                SELECT 
                    d.country,
                    d.title,
                    dc.chunk_index,
                    dc.page,
                    dc.content,
                    LENGTH(dc.content) as length,
                    dc.chunk_data
                FROM documents d
                JOIN doc_chunks dc ON d.doc_id = dc.doc_id
                WHERE d.country = :country
                ORDER BY dc.chunk_index
                LIMIT :limit
            """)
            result = session.execute(query, {'country': country, 'limit': limit})
        else:
            query = text("""
                SELECT 
                    d.country,
                    d.title,
                    dc.chunk_index,
                    dc.page,
                    dc.content,
                    LENGTH(dc.content) as length,
                    dc.chunk_data
                FROM documents d
                JOIN doc_chunks dc ON d.doc_id = dc.doc_id
                ORDER BY d.country, dc.chunk_index
                LIMIT :limit
            """)
            result = session.execute(query, {'limit': limit})
        
        return [
            {
                'country': row[0],
                'title': row[1],
                'chunk_index': row[2],
                'page': row[3],
                'content': row[4],
                'length': row[5],
                'metadata': row[6] if len(row) > 6 else {}
            }
            for row in result.fetchall()
        ]


def search_chunks(search_term, limit=10):
    """Search for chunks containing a term."""
    db = get_database_connection()
    
    with db.Session() as session:
        query = text("""
            SELECT 
                d.country,
                d.title,
                dc.chunk_index,
                dc.page,
                dc.content,
                LENGTH(dc.content) as length
            FROM documents d
            JOIN doc_chunks dc ON d.doc_id = dc.doc_id
            WHERE dc.content ILIKE :search_term
            ORDER BY d.country, dc.chunk_index
            LIMIT :limit
        """)
        
        result = session.execute(query, {
            'search_term': f'%{search_term}%',
            'limit': limit
        })
        
        return [
            {
                'country': row[0],
                'title': row[1],
                'chunk_index': row[2],
                'page': row[3],
                'content': row[4],
                'length': row[5]
            }
            for row in result.fetchall()
        ]


def display_overview():
    """Display overview statistics."""
    console.print("\n")
    console.print("=" * 80, style="cyan")
    console.print("📊 CHUNK DATABASE OVERVIEW", style="bold yellow", justify="center")
    console.print("=" * 80, style="cyan")
    
    stats = get_overview()
    
    table = Table(box=box.ROUNDED, show_header=False, padding=(0, 2))
    table.add_column("Metric", style="cyan", width=30)
    table.add_column("Value", style="green", justify="right", width=20)
    
    table.add_row("Total Documents", str(stats['total_documents']))
    table.add_row("Processed Documents", str(stats['processed_documents']))
    table.add_row("Total Chunks", f"{stats['total_chunks']:,d}")
    table.add_row("Average Chunk Length", f"{stats['avg_length']} chars")
    table.add_row("Min Chunk Length", f"{stats['min_length']} chars")
    table.add_row("Max Chunk Length", f"{stats['max_length']} chars")
    
    console.print(table)
    console.print()


def display_by_country():
    """Display chunks by country."""
    console.print("\n")
    console.print("=" * 80, style="cyan")
    console.print("🌍 CHUNKS BY COUNTRY", style="bold yellow", justify="center")
    console.print("=" * 80, style="cyan")
    console.print()
    
    countries = get_chunks_by_country()
    
    if not countries:
        console.print("[yellow]No chunks found in database[/yellow]")
        return
    
    table = Table(box=box.ROUNDED, show_header=True)
    table.add_column("Country", style="cyan", width=25)
    table.add_column("# Chunks", style="green", justify="right", width=12)
    table.add_column("Avg Length", style="blue", justify="right", width=15)
    table.add_column("# Docs", style="magenta", justify="right", width=10)
    
    for c in countries:
        table.add_row(
            c['country'],
            f"{c['num_chunks']:,d}",
            f"{c['avg_length']} chars",
            str(c['num_docs'])
        )
    
    console.print(table)
    console.print()


def display_sample_chunks(country=None, limit=5):
    """Display sample chunks."""
    title = f"📄 SAMPLE CHUNKS" + (f" FROM {country.upper()}" if country else "")
    
    console.print("\n")
    console.print("=" * 80, style="cyan")
    console.print(title, style="bold yellow", justify="center")
    console.print("=" * 80, style="cyan")
    console.print()
    
    chunks = get_sample_chunks(country, limit)
    
    if not chunks:
        console.print("[yellow]No chunks found[/yellow]")
        return
    
    for i, chunk in enumerate(chunks, 1):
        # Create header
        header = f"{chunk['country']} | Chunk {chunk['chunk_index']} | Page {chunk['page'] or 'N/A'} | {chunk['length']} chars"
        
        # Truncate content for display
        content = chunk['content']
        if len(content) > 500:
            content = content[:500] + "..."
        
        # Create panel
        panel = Panel(
            content,
            title=header,
            title_align="left",
            border_style="blue",
            padding=(1, 2)
        )
        console.print(panel)
        
        if i < len(chunks):
            console.print()


def display_search_results(search_term, limit=5):
    """Display search results."""
    console.print("\n")
    console.print("=" * 80, style="cyan")
    console.print(f'🔍 SEARCH RESULTS FOR "{search_term}"', style="bold yellow", justify="center")
    console.print("=" * 80, style="cyan")
    console.print()
    
    chunks = search_chunks(search_term, limit)
    
    if not chunks:
        console.print(f'[yellow]No chunks found containing "{search_term}"[/yellow]')
        return
    
    console.print(f"[green]Found {len(chunks)} chunks (showing first {limit})[/green]\n")
    
    for i, chunk in enumerate(chunks, 1):
        # Highlight search term in content
        content = chunk['content']
        
        # Truncate around search term if content is long
        if len(content) > 600:
            # Find search term position
            term_pos = content.lower().find(search_term.lower())
            if term_pos > 0:
                start = max(0, term_pos - 200)
                end = min(len(content), term_pos + 400)
                content = "..." + content[start:end] + "..."
            else:
                content = content[:600] + "..."
        
        # Create header
        header = f"{chunk['country']} | Chunk {chunk['chunk_index']} | Page {chunk['page'] or 'N/A'}"
        
        panel = Panel(
            content,
            title=header,
            title_align="left",
            border_style="green",
            padding=(1, 2)
        )
        console.print(panel)
        
        if i < len(chunks):
            console.print()


def interactive_menu():
    """Interactive menu for exploring chunks."""
    while True:
        console.print("\n")
        console.print("=" * 80, style="cyan")
        console.print("🔧 CHUNK INSPECTOR MENU", style="bold yellow", justify="center")
        console.print("=" * 80, style="cyan")
        console.print()
        console.print("[1] Overview Statistics")
        console.print("[2] Chunks by Country")
        console.print("[3] View Sample Chunks (All)")
        console.print("[4] View Chunks from Specific Country")
        console.print("[5] Search Chunks")
        console.print("[6] Exit")
        console.print()
        
        choice = console.input("[bold cyan]Select option (1-6):[/bold cyan] ").strip()
        
        if choice == "1":
            display_overview()
        elif choice == "2":
            display_by_country()
        elif choice == "3":
            limit = console.input("[cyan]How many chunks to show? (default: 5):[/cyan] ").strip()
            limit = int(limit) if limit.isdigit() else 5
            display_sample_chunks(limit=limit)
        elif choice == "4":
            country = console.input("[cyan]Enter country name:[/cyan] ").strip()
            limit = console.input("[cyan]How many chunks to show? (default: 5):[/cyan] ").strip()
            limit = int(limit) if limit.isdigit() else 5
            display_sample_chunks(country, limit)
        elif choice == "5":
            search_term = console.input("[cyan]Enter search term:[/cyan] ").strip()
            limit = console.input("[cyan]How many results to show? (default: 5):[/cyan] ").strip()
            limit = int(limit) if limit.isdigit() else 5
            display_search_results(search_term, limit)
        elif choice == "6":
            console.print("\n[green]Goodbye![/green]\n")
            break
        else:
            console.print("[red]Invalid choice. Please select 1-6.[/red]")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Inspect chunks in database")
    parser.add_argument("--overview", action="store_true", help="Show overview statistics")
    parser.add_argument("--by-country", action="store_true", help="Show chunks by country")
    parser.add_argument("--sample", type=int, metavar="N", help="Show N sample chunks")
    parser.add_argument("--country", type=str, help="Filter by country")
    parser.add_argument("--search", type=str, help="Search for term in chunks")
    parser.add_argument("--interactive", action="store_true", help="Interactive mode (default)")
    
    args = parser.parse_args()
    
    # If no args provided, run interactive mode
    if not any([args.overview, args.by_country, args.sample, args.search]):
        args.interactive = True
    
    try:
        if args.interactive:
            interactive_menu()
        else:
            if args.overview:
                display_overview()
            if args.by_country:
                display_by_country()
            if args.sample:
                display_sample_chunks(args.country, args.sample)
            if args.search:
                display_search_results(args.search, 10)
    
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]\n")
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]\n")
        import traceback
        traceback.print_exc()

