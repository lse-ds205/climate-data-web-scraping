# How to Inspect Chunks in Database

You have **three ways** to inspect chunks:

---

## 🐍 Method 1: Python Script (Recommended - Pretty Output!)

### Install dependency (if needed):
```powershell
pip install rich
```

### Interactive Mode (Best for exploring):
```powershell
python Issues_tracking/tools/inspect_chunks.py
```

This opens a menu where you can:
- View overview statistics
- See chunks by country
- View sample chunks
- Search for specific content
- Filter by country

### Command-Line Mode (Quick queries):

**Overview:**
```powershell
python tools/inspect_chunks.py --overview
```

**By Country:**
```powershell
python tools/inspect_chunks.py --by-country
```

**Sample Chunks:**
```powershell
# Show 10 random chunks
python tools/inspect_chunks.py --sample 10

# Show 5 chunks from China
python tools/inspect_chunks.py --sample 5 --country China
```

**Search:**
```powershell
# Find chunks containing "emission"
python tools/inspect_chunks.py --search "emission"

# Find "climate action" in USA documents
python tools/inspect_chunks.py --search "climate action" --country USA
```

**Combine multiple options:**
```powershell
python tools/inspect_chunks.py --overview --by-country --sample 5
```

---

## 🗄️ Method 2: SQL Queries (Direct Database Access)

### Using Docker (Windows):

```powershell
# Open psql in Docker
docker exec -it NDC_rag psql -U climate -d climate

# Then run any query from tools/inspect_chunks.sql
# For example:
SELECT COUNT(*) FROM doc_chunks;
```

### Run SQL file queries:

```powershell
# Run specific query (copy from tools/inspect_chunks.sql)
docker exec -it NDC_rag psql -U climate -d climate -c "
SELECT 
    d.country,
    COUNT(dc.id) as num_chunks
FROM documents d
JOIN doc_chunks dc ON d.doc_id = dc.doc_id
GROUP BY d.country
ORDER BY num_chunks DESC;
"
```

### Common Quick Queries:

**Total chunks:**
```sql
SELECT COUNT(*) FROM doc_chunks;
```

**Chunks by country:**
```sql
SELECT d.country, COUNT(dc.id) as chunks
FROM documents d
JOIN doc_chunks dc ON d.doc_id = dc.doc_id
GROUP BY d.country;
```

**View a chunk:**
```sql
SELECT content FROM doc_chunks LIMIT 1;
```

**Search chunks:**
```sql
SELECT d.country, dc.content
FROM documents d
JOIN doc_chunks dc ON d.doc_id = dc.doc_id
WHERE dc.content ILIKE '%climate change%'
LIMIT 5;
```

---

## 🖥️ Method 3: Database GUI Tools

### Option A: pgAdmin
1. Connect to `localhost:5432`
2. Database: `climate`
3. User: `climate`
4. Browse `doc_chunks` table

### Option B: DBeaver (Free, Cross-platform)
1. Download from https://dbeaver.io/
2. Create PostgreSQL connection:
   - Host: `localhost`
   - Port: `5432`
   - Database: `climate`
   - User: `climate`
3. Browse tables and run queries

### Option C: VS Code Extension
1. Install "PostgreSQL" extension by Chris Kolkman
2. Connect to database
3. Browse and query

---

## 📊 Most Useful Queries

### 1. Quick Status Check
```powershell
python tools/inspect_chunks.py --overview --by-country
```

### 2. See What's Actually in Your Chunks
```powershell
python tools/inspect_chunks.py --sample 10
```

### 3. Check Specific Country
```powershell
python tools/inspect_chunks.py --country "China" --sample 5
```

### 4. Search for Content
```powershell
python tools/inspect_chunks.py --search "net zero"
```

### 5. Quality Check (via SQL)
```sql
-- Find suspiciously short chunks
SELECT country, chunk_index, length(content), content
FROM doc_chunks dc
JOIN documents d ON dc.doc_id = d.doc_id
WHERE length(content) < 50
ORDER BY length(content);

-- Find suspiciously long chunks
SELECT country, chunk_index, length(content), left(content, 100)
FROM doc_chunks dc
JOIN documents d ON dc.doc_id = d.doc_id
WHERE length(content) > 1000
ORDER BY length(content) DESC;
```

---

## 🎯 Recommended Workflow

1. **Check overview** to see what's been processed:
   ```powershell
   python tools/inspect_chunks.py --overview --by-country
   ```

2. **Look at sample chunks** to verify quality:
   ```powershell
   python tools/inspect_chunks.py --sample 10
   ```

3. **Check specific countries** you care about:
   ```powershell
   python tools/inspect_chunks.py --country "USA" --sample 5
   python tools/inspect_chunks.py --country "China" --sample 5
   ```

4. **Test search** to see if content is indexed properly:
   ```powershell
   python tools/inspect_chunks.py --search "emission reduction"
   python tools/inspect_chunks.py --search "renewable energy"
   ```

5. **Interactive exploration** when you need to dig deeper:
   ```powershell
   python tools/inspect_chunks.py
   # Then use menu to navigate
   ```

---

## 💡 Tips

- **Start with overview** to see the big picture
- **Use Python script** for nice formatting and easy browsing
- **Use SQL** when you need precise queries or exports
- **Check multiple countries** to verify non-English processing
- **Search for key terms** to validate your content is retrievable

---

## 🐛 Troubleshooting

**"Error: rich module not found"**
```powershell
pip install rich
```

**"No chunks found"**
- Check if chunking completed: `python tools/inspect_chunks.py --overview`
- If processed_documents = 0, chunking hasn't run yet
- If total_chunks = 0 but processed_documents > 0, there was a processing error

**"Connection error"**
- Make sure Docker is running: `docker ps`
- Make sure NDC_rag container is up: `docker ps | findstr NDC_rag`
- Try restarting: `docker-compose restart`

---

## 📝 Export Chunks

**To CSV (for Excel/analysis):**
```sql
\copy (SELECT d.country, d.title, dc.chunk_index, dc.page, dc.content, length(dc.content) as length FROM documents d JOIN doc_chunks dc ON d.doc_id = dc.doc_id ORDER BY d.country, dc.chunk_index) TO 'chunks_export.csv' WITH CSV HEADER;
```

**To JSON (for processing):**
```python
import sys
from pathlib import Path
import json

# Add project to path
sys.path.insert(0, str(Path.cwd()))

from tools.inspect_chunks import get_sample_chunks

chunks = get_sample_chunks(limit=1000)
with open('chunks_export.json', 'w', encoding='utf-8') as f:
    json.dump(chunks, f, indent=2, ensure_ascii=False)
```

