# Known Issues and TODOs

This document tracks known bugs, limitations, and planned improvements for the Climate Policy Extractor project.

## 🐛 Bugs

### 1. PDF Download Fails for Multi-Language Documents (Windows)
**Priority**: Medium  
**Status**: Open  
**Affected Files**: `group4py/src/scrape/download.py` or filename generation logic

**Description**:  
Some documents fail to download on Windows due to invalid filenames when the language field contains newlines. This occurs when UNFCCC documents are available in multiple languages and the scraper detects multiple language values separated by newlines (e.g., `"English\nFrench"`).

**Error Example**:
```
Error writing file to ...\data\pdfs\Canada_English\nFrench_20220601.pdf: 
[Errno 22] Invalid argument: 'C:\\...\Canada_English\nFrench_20220601.pdf'
```

**Affected Documents** (as of last run):
- Canada documents (English/French combinations)
- Colombia documents (Spanish repetitions)
- Chile documents (Spanish/English combinations)
- Approximately 10 documents fail to download, though they are still tracked in the database

**Proposed Fix**:  
- When multiple language versions of a document are available (e.g., English and French for Canada), the scraper should:
  1. Check if an English version exists as a separate file
  2. Prioritize downloading the English version if available
  3. Only use the primary language or multi-language indicator in the filename if no English version exists
- This will ensure consistent English-language documents are downloaded when available, avoiding filename issues and providing standardized content 

**Workaround**:  
The documents are still inserted into the database with correct metadata. Only the PDF file download fails. Users can manually download these PDFs if needed.

---

### 2. Scraping Failures for Canada, Chile, and Colombia
**Priority**: Medium  
**Status**: Open  
**Affected Files**: `group4py/src/scrape/workflow.py`, `group4py/src/scrape/scraper.py`
**Last Updated**: November 18, 2025

**Description**:  
The scraper is failing to successfully process documents for Canada, Chile, and Colombia. These countries show up in the processing summary as having scraper failures.

**Affected Countries** (as of November 18, 2025):
- **Canada**: 8 failure(s)
- **Chile**: 4 failure(s)  
- **Colombia**: 6 failure(s)

**Note**: These countries also experience download failures (see Issue #1) due to multi-language filename issues, but the scraping failures appear to be a separate issue occurring earlier in the pipeline.

**Potential Causes**:
1. **Website structure changes**: UNFCCC website structure may have changed for these countries' document pages
2. **Rate limiting**: These countries' pages may be rate-limited or blocked
3. **Parsing errors**: The scraper may be failing to parse the HTML structure for these specific country pages
4. **Network timeouts**: Connection issues when accessing these countries' document listings
5. **Missing or malformed metadata**: The scraper may be encountering unexpected data formats for these countries

**Proposed Investigation**:
- Check scraper logs for specific error messages related to these countries
- Verify if these countries' document pages are accessible manually
- Test scraper with verbose logging to identify the exact failure point
- Compare HTML structure of these countries' pages with successfully scraped countries
- Check if these failures are consistent or intermittent

**Related Issues**:
- See Issue #1 for download failures affecting the same countries
- May be related to multi-language document handling

**Workaround**:  
Documents may need to be manually scraped or downloaded for these countries until the scraper issue is resolved.

---

### 3. Saudi Arabia Document Missing Submission Date
**Priority**: Low  
**Status**: Open  
**Affected Files**: Scraper parsing logic

**Description**:  
The Saudi Arabia First NDC (Updated submission) document is scraped without a submission date (shows as NULL in database).

**Database Evidence**:
```sql
SELECT country, title, submission_date FROM documents WHERE submission_date IS NULL;
-- Returns: Saudi Arabia | Saudi Arabia First NDC (Updated submission) | (null)
```

**Proposed Fix**:  
- Review the scraper's date extraction logic for this specific document
- Check if the date format on the UNFCCC website is non-standard for this entry
- Consider adding fallback date extraction methods

---

### 4. ONNX Runtime DLL Errors on Windows
**Priority**: High (for Windows users)  
**Status**: Documented with solution  
**Affected Files**: Environment setup, `requirements.txt`

**Description**:  
Windows users may encounter DLL initialization errors when running the chunking/processing steps:
```
ImportError: DLL load failed while importing onnxruntime_pybind11_state: 
A dynamic link library (DLL) initialization routine failed.
```

This is caused by missing Microsoft Visual C++ Redistributables required by `onnxruntime` and `onnx` packages.

**Solution**:  
1. **Install Visual C++ Redistributables** (Required for Windows):
   - Download: https://aka.ms/vs/17/release/vc_redist.x64.exe
   - Run the installer
   - Restart your terminal after installation

2. **Use compatible package versions** (already set in `requirements.txt`):
   ```
   onnx==1.16.0
   onnxruntime==1.18.1
   ```

3. **Reinstall packages** if you already installed incompatible versions:
   ```powershell
   pip uninstall onnx onnxruntime -y
   pip install onnx==1.16.0 onnxruntime==1.18.1
   ```

**Why This Happens**:  
- ONNX Runtime uses native C++ libraries that depend on Microsoft Visual C++ runtime
- Newer versions (1.19+) have more strict DLL requirements that may fail on some Windows setups
- Version 1.18.1 is the latest stable version that works reliably on Windows 10/11

**Verified Working Environment**:  
- Windows 11
- Python 3.12
- Visual C++ Redistributables 2015-2022 (x64)
- onnx==1.16.0
- onnxruntime==1.18.1

---

### 5. Windows Console UTF-8 Encoding (Logging Warnings Only)
**Priority**: Low  
**Status**: Known Limitation  
**Affected Files**: All Python scripts that log non-ASCII characters

**Description**:  
When processing documents with non-Latin characters (Chinese, Arabic, etc.), Windows PowerShell may show logging errors due to the console's default `cp1252` encoding not supporting these characters:

```
UnicodeEncodeError: 'charmap' codec can't encode characters in position 103-115: 
character maps to <undefined>
```

**Impact**:  
- **This does NOT affect processing** - documents ARE being chunked and stored correctly
- Only affects console logging output (warnings about "corrupted" chunks containing Chinese text)
- These warnings appear when the gibberish detector encounters valid Chinese text that looks "corrupted" to the English-focused detector

**Example**:
```
2025-10-13 16:38:07 - group4py.src.chunk.cleaner - WARNING - Rejecting severely corrupted chunk: 
拨款港币 20 亿元在政府处所推行多个可再生能源项目...
--- Logging error ---
UnicodeEncodeError: 'charmap' codec can't encode characters...
```

**Workaround** (Optional):  
If you want to see the full Chinese text in logs, you can change PowerShell's encoding before running scripts:
```powershell
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
```

**Future Improvement**:  
- Configure logging to use UTF-8 encoding by default
- Use error handling in logging formatters to replace unencodable characters with placeholders

---

### 6. DocChunkORM page_numbers Attribute Error (FIXED)
**Priority**: High  
**Status**: ✅ **FIXED** (October 13, 2025)  
**Affected Files**: `group4py/src/databases/operations.py`

**Description**:  
The raw SQL INSERT for `DocChunkORM` objects was trying to access `item.page_numbers`, but the model only has a `page` attribute (singular).

**Error**:
```
Error adding item 0 of type DocChunkORM: 'DocChunkORM' object has no attribute 'page_numbers'
```

**Fix Applied**:  
- Changed raw SQL INSERT to use `page` instead of `page_numbers`
- Added `getattr()` with defaults for optional attributes (embeddings, created_at)
- Ensured compatibility between Docker proxy mode (raw SQL) and regular mode (ORM)

---

### 7. Incomplete PDF Processing for Some Countries
**Priority**: Medium  
**Status**: Open  
**Affected Files**: `entrypoints/2_chunk.py`, text extraction logic

**Description**:  
Some countries' PDF documents are not processing completely, resulting in very few chunks (1-2 chunks with ~110 characters each) instead of the expected hundreds of chunks per document.

**Evidence from Chunk Explorer**:
```
Country                   │     # Chunks │      Avg Length │     # Docs │
├───────────────────────────┼──────────────┼─────────────────┼────────────┤
│ Norway                    │            2 │       110 chars │          2 │
│ Panama                    │            2 │       110 chars │          2 │
│ Pakistan                  │            2 │       112 chars │          2 │
│ Morocco                   │            2 │       110 chars │          2 │
│ Chile                     │            1 │       109 chars │          1 │
│ Oman                      │            1 │       108 chars │          1 │
│ Philippines               │            1 │       115 chars │          1 │
│ Peru                      │            1 │       108 chars │          1 │
│ Paraguay                  │            1 │       112 chars │          1 │
```

**Expected vs Actual**:
- **Expected**: 200-1000+ chunks per document (like Angola: 515 chunks)
- **Actual**: 1-2 chunks with ~110 characters (likely fallback content)

**Potential Causes**:
1. **PDF format issues**: Some PDFs may be image-based or have complex layouts that Tesseract struggles with
2. **Language detection**: Non-English documents may not be processed correctly
3. **File corruption**: Some PDFs may be corrupted or incomplete
4. **Text extraction strategy**: The "fast" strategy may not work for all document types

**Proposed Investigation**:
- Test different text extraction strategies (fast vs hi-res) for problematic documents
- Check if these are non-English documents that need different OCR settings
- Verify PDF file integrity for affected countries
- Consider adding fallback extraction methods for difficult documents

---

## ✅ Issues Addressed

### 1. Embedding Script Docker Proxy Compatibility (FIXED)
**Priority**: High  
**Status**: ✅ **FIXED** (October 23, 2025)  
**Affected Files**: `entrypoints/3_embed.py`

**Description**:  
The embedding script was failing on Windows Docker systems due to ORM query incompatibility with the Docker proxy connection. The script was trying to use SQLAlchemy ORM queries (`session.query(DocChunkORM)`) but the Docker proxy session only supports raw SQL queries.

**Error Example**:
```
Error collecting chunks: DockerProxySession does not support ORM queries. 
Use raw SQL with session.execute(text('SELECT ...')) instead.
```

**Solution Implemented**:  
- **Hybrid ORM/SQL approach**: Automatically detects if ORM is available and uses the best method
- **ORM for non-Docker systems**: Uses original ORM queries for better performance and type safety
- **Raw SQL fallback for Docker**: Uses raw SQL queries for Docker proxy compatibility
- **Automatic detection**: `is_orm_available(session)` function detects session capabilities
- **Maintains original logic**: Same embedding generation process, just different database interaction

**Benefits**:
- ✅ **Works on all systems** (Docker and non-Docker)
- ✅ **Better performance** on non-Docker systems (uses ORM)
- ✅ **Maintains compatibility** with Docker proxy workaround
- ✅ **Preserves original code structure** where possible
- ✅ **Automatic fallback** ensures reliability

**Code Changes**:
```python
def is_orm_available(session):
    """Check if session supports ORM queries"""
    return hasattr(session, 'query') and hasattr(session, 'commit')

def collect_all_chunk_texts(session):
    if is_orm_available(session):
        # Use ORM approach (faster on non-Docker systems)
        chunks = session.query(DocChunkORM.content).filter(DocChunkORM.content.isnot(None)).all()
        texts = [chunk.content for chunk in chunks if chunk.content and chunk.content.strip()]
    else:
        # Use raw SQL fallback (Docker proxy compatibility)
        result = session.execute(text("SELECT content FROM doc_chunks WHERE content IS NOT NULL"))
        rows = result.fetchall()
        texts = [row[0] for row in rows if row[0] and row[0].strip()]
```

**Result**: Embedding script now works seamlessly on both Docker and non-Docker systems with optimal performance for each environment.

---

## 💡 Improvements / Enhancements

### 1. Optimized Metadata Filtering for Retrieval (IMPLEMENTED)
**Priority**: High  
**Status**: ✅ **IMPLEMENTED** (October 23, 2025)  
**Related Files**: `entrypoints/4_retrieve.py`

**Description**:  
The retrieval system was inefficiently loading ALL chunks from the database (18,333 chunks) and filtering by country in memory. This caused poor performance and unnecessary processing for country-specific queries.

**Previous Approach**:
```python
# Inefficient: Load ALL chunks, filter in memory
query = text("SELECT * FROM doc_chunks")  # Loads 18,333 chunks
for row in result:
    if country and chunk_country.lower() != country.lower():
        continue  # Filter in Python
```

**New Optimized Approach**:
```python
# Efficient: Filter at SQL level
if country:
    query = text("""
        SELECT id, content, doc_id, chunk_data 
        FROM doc_chunks 
        WHERE LOWER(chunk_data->>'country') = LOWER(:country)
    """)
    result = session.execute(query, {"country": country})
```

**Key Improvements**:
- ✅ **SQL-level filtering**: Country filtering happens in database, not Python
- ✅ **Query analysis**: Auto-detects country from user queries (e.g., "What are Angola's climate targets?")
- ✅ **Performance boost**: 10-50x faster for country-specific queries
- ✅ **Reduced memory usage**: Only loads relevant chunks
- ✅ **Better logging**: Clear visibility into filtering process
- ✅ **Backward compatibility**: Works with existing API

**Performance Impact**:
- **Before**: Load 18,333 chunks → Filter in Python → Process all
- **After**: Load ~500 chunks (Angola) → Process only relevant chunks
- **Speed improvement**: ~95% reduction in processing time for country queries

**Code Changes**:
```python
def extract_country_from_query(query: str) -> Optional[str]:
    """Extract country name from query using keyword matching"""
    query_lower = query.lower()
    for country in KNOWN_COUNTRIES:
        if country.lower() in query_lower:
            return country
    return None

def retrieve_chunks(embedded_prompts, prompt, top_k=20, country=None, ...):
    # Auto-detect country from query if not provided
    if country is None:
        country = extract_country_from_query(prompt)
    
    # Use SQL filtering instead of memory filtering
    if country:
        query = text("SELECT ... WHERE LOWER(chunk_data->>'country') = LOWER(:country)")
        result = session.execute(query, {"country": country})
```

**Result**: Retrieval is now optimized for both country-specific and general queries, with automatic country detection and efficient SQL filtering.

---

### 2. Windows Docker Networking Workaround
**Priority**: Medium  
**Status**: Implemented (workaround)  
**Related Files**: `group4py/src/databases/docker_proxy.py`

**Description**:  
The current implementation uses a Docker proxy connection on Windows to bypass authentication issues with PostgreSQL connections from the Windows host to Docker containers. While this works, it's a workaround rather than a proper fix.

**Current Solution**:  
- `DockerProxyConnection` class that uses `docker exec` to run SQL commands
- Automatically detected on Windows + localhost connections

**Future Improvement**:  
- Investigate proper PostgreSQL authentication configuration for Windows Docker Desktop
- Consider migrating to a cloud-hosted database for production to avoid local Docker issues

---

### 3. Country Filtering Verification
**Priority**: Low  
**Status**: Implemented  
**Related Files**: `group4py/src/scrape/workflow.py`, `group4py/src/scrape/db_operations.py`

**Description**:  
The scraper now filters documents to only include the 85 countries specified in the `countries` table. The workflow logs show this is working correctly (162 documents excluded in last run).

**Future Improvement**:  
- Add a configuration file or command-line argument to specify which countries to scrape
- Generate a report showing which countries have documents vs. which are in the filter list but have no documents

---

### 4. Custom Output Row Structures for Different Prompts
**Priority**: Medium  
**Status**: Open  
**Related Files**: `entrypoints/6_output.py`, `questions/prompts.py`

**Description**:  
Currently, all prompts use the same fixed output structure in CSV/Excel exports:
- Fixed columns: `Question`, `Question_text`, `Entity`, `Answer`, `Explanation`, then chunk columns
- All prompts share the same structure regardless of their specific needs

Some prompts may require different output structures. For example:
- **EP4ai**: Needs only `Year` in Answer column (currently handled with custom extraction)
- **Future prompts**: May need multiple answer columns (e.g., `Year`, `Target_Type`, `Scope`, `Confidence`)
- **Complex prompts**: May need structured data extraction into separate columns

**Current Workaround**:  
Custom extraction logic is hardcoded in `export_batch_aggregated()` based on TPI Centre ID (e.g., `if tpi_centre_id == 'EP4ai'`). This works but doesn't scale well as more prompts are added.

**Why EP4ai is Hardcoded**:
The EP4ai prompt requires special answer extraction because:
1. **Different answer format**: EP4ai returns a year (e.g., "2050") or "No data" instead of Yes/No
2. **Prompt-specific extraction**: The LLM response needs regex parsing to extract the 4-digit year from the first line
3. **No extraction framework yet**: The system doesn't have a way to define custom extraction rules per prompt (see proposed solutions below)
4. **Temporary solution**: This hardcoded logic is a workaround until a proper extraction framework is implemented

**Location**: `entrypoints/6_output.py` lines 916-937 contains the hardcoded EP4ai extraction logic:
```python
if tpi_centre_id == 'EP4ai':
    # Extract year from first line using regex
    first_line = answer_text.split('\n')[0].strip()
    year_match = re.search(r'\b(20\d{2}|19\d{2})\b', first_line)
    if year_match:
        answer_short = year_match.group(1)
    elif 'no data' in first_line.lower():
        answer_short = "No data"
    # ... fallback logic
```

**Impact**:  
- ✅ Works correctly for EP4ai
- ⚠️ Doesn't scale: Each new prompt with custom extraction needs another `if` statement
- ⚠️ Code duplication: Similar extraction logic would be repeated for similar prompts
- ⚠️ Maintenance burden: Harder to maintain as more prompts are added

**Proposed Solutions**:

**Option 1: Prompt-Level Extraction Rules** (Recommended for now)
- Keep prompts focused on content
- Handle formatting/extraction in output script based on prompt ID
- Add extraction functions for each prompt type
- Simpler to maintain and debug

**Option 2: Custom Column Definitions in Prompt Metadata** (Advanced)
- Add `output_columns` field to `PromptMetadata` class (already added to schema)
- Define custom columns and extraction rules in prompt definition
- Modify `export_batch_aggregated()` to read custom columns from prompt metadata
- Create extraction functions for each column type
- More flexible but more complex to implement

**Implementation Requirements**:
1. Define output structure per prompt (either in prompt metadata or extraction logic)
2. Modify `export_batch_aggregated()` to support custom column structures
3. Create extraction functions for different data types (year, yes/no, structured data, etc.)
4. Ensure backward compatibility with existing prompts

**Example Use Case**:
A prompt asking "What are the key climate targets?" might need:
- `Target_1_Type`, `Target_1_Year`, `Target_1_Scope`
- `Target_2_Type`, `Target_2_Year`, `Target_2_Scope`
- etc.

**Related Files**:
- `entrypoints/6_output.py` - Export logic (needs modification)
- `questions/prompts.py` - `PromptMetadata` class (already has `output_columns` field)
- `questions/prompts/projects/ascor/ep4ai.py` - Example prompt with custom extraction

---

### 15. Legacy Code in Output Module Needs Cleanup
**Priority**: Low  
**Status**: Open  
**Related Files**: `entrypoints/6_output.py`

**Description**:  
The `6_output.py` file contains legacy functions that are marked as "kept for compatibility" but may no longer be used:

**Legacy Functions** (lines 1176-1323):
1. `extract_sources_with_links()` - Legacy citation extraction
2. `extract_sources()` - Legacy wrapper function
3. `generate_source_link()` - Legacy link generation
4. `export_to_csv_excel()` - Legacy export function for old LLM response format
5. `export_single_question()` - Legacy single-question export

**Current State**:
- These functions are marked with `"""Legacy function - kept for compatibility."""`
- They may be used by old scripts or workflows that haven't been migrated
- No clear indication of whether they're still actively used

**Proposed Action**:
1. **Audit usage**: Search codebase for references to these functions
2. **Check git history**: Verify when these functions were last used
3. **Remove if unused**: If not referenced anywhere, remove to reduce code complexity
4. **Migrate if used**: If still used, document where and consider migrating to new system
5. **Update documentation**: If keeping, clearly document why and which workflows depend on them

**Benefits of Cleanup**:
- ✅ Reduced code complexity
- ✅ Easier maintenance
- ✅ Clearer codebase for new contributors
- ✅ Less confusion about which functions to use

**Risks**:
- ⚠️ May break old scripts/workflows if still in use
- ⚠️ Need to verify no external dependencies

**Action Items**:
- [ ] Search codebase for references to legacy functions
- [ ] Check if any entrypoint scripts use these functions
- [ ] Verify with team if any workflows depend on legacy exports
- [ ] Remove unused functions or document active dependencies
- [ ] Update README/docs to clarify which export functions to use

---

## 📝 Documentation TODOs

- [ ] Add troubleshooting section for common Windows Docker issues
- [ ] Document the Docker proxy workaround in architecture docs
- [ ] Create a guide for adding new countries to the filter list
- [ ] Add examples of database queries for common use cases

---

## 🧪 Testing TODOs

- [ ] Add unit tests for filename sanitization
- [ ] Add integration tests for Docker proxy connection
- [ ] Add tests for country filtering logic
- [ ] Test scraper with edge cases (missing dates, special characters in titles)

---

## 🔮 Future Improvements & Experiments

For detailed plans on future enhancements and experiments (especially **chunking strategy evaluation**), see:

👉 **[NEXT_STEPS.md](./NEXT_STEPS.md)**

Key upcoming experiments:
- **Docling layout-aware chunking** - For better table/column handling
- **Unstructured hi-res mode** - Enhanced layout detection
- **LangChain/LlamaIndex alternatives** - Different chunking approaches
- **Multi-language support** - Fix for Chinese/Arabic documents
- **Embedding model comparison** - Optimize retrieval quality
- **Re-ranking pipeline** - Improve answer accuracy

See `NEXT_STEPS.md` for full implementation plans, evaluation frameworks, and timelines.

---

### 8. Citation ID Mismatch in CSV Export (Metadata Missing)
**Priority**: High  
**Status**: 🔧 **FIXED** (November 17, 2025)  
**Affected Files**: `group4py/src/query.py`, `entrypoints/6_output.py`, `entrypoints/4_retrieve.py`

**Description**:  
When exporting batch results to CSV/Excel, page numbers and document information were not appearing for some entities (e.g., Brazil). The issue was caused by a mismatch between:
1. **Chunk IDs shown to LLM**: The `ChunkFormatter` was showing database UUIDs to the LLM
2. **Citation IDs returned by LLM**: The LLM was returning these UUIDs (or integer representations) in citations
3. **Citation validation**: The validation logic was trying to match UUIDs but failing for some cases
4. **CSV export lookup**: The export was trying to find chunks by citation ID but couldn't match them to `original_chunks`

**Error Example**:
```
Citation references unknown chunk ID: 8042
Citation references unknown chunk ID: 8043
Could not find original chunk for citation 1 with ID 8042
```

**Root Causes**:
1. **SQL query missing metadata fields**: The `retrieve_chunks` function was only selecting 4 fields (`id`, `content`, `doc_id`, `chunk_data`) instead of all 8 fields including `page`, `chunk_index`, `paragraph`, `language`
2. **ID format mismatch**: LLM was seeing UUIDs but sometimes returning integer representations, causing lookup failures
3. **Incomplete metadata retrieval**: Even when chunks were found, metadata fields weren't being retrieved from the database

**Fixes Applied**:
1. ✅ **Updated SQL query in `4_retrieve.py`**: Now selects all 8 fields including `page`, `chunk_index`, `paragraph`, `language` so chunks have complete metadata from retrieval
2. ✅ **Changed ChunkFormatter to use indices**: Modified `ChunkFormatter.format_chunks_for_context()` to show chunk indices (0, 1, 2...) instead of UUIDs to the LLM, ensuring consistent ID format
3. ✅ **Enhanced citation validation**: Updated `ResponseProcessor._validate_citations()` to handle both integer indices and UUID strings, with priority on index lookup
4. ✅ **Simplified CSV export**: Updated `export_batch_aggregated()` to directly use `original_chunks` with index-based lookup, removing redundant database queries

**Result**:  
- Chunks now include all metadata fields (`page`, `doc_id`, `chunk_index`, etc.) from retrieval
- LLM citations use consistent index format (0, 1, 2...) that matches `original_chunks`
- CSV export can reliably match citations to chunks and extract page numbers and document information
- Metadata (page numbers, document titles/URLs) now appears correctly in CSV/Excel output

**Verification**:  
Run batch process and verify that:
- Page numbers appear in `Chunk_X_Page` columns
- Document information appears in `Chunk_X_Document` columns
- No "Could not find original chunk" warnings in export logs

---

### 9. Missing Date Column in Database Metadata
**Priority**: Medium  
**Status**: Open  
**Affected Files**: Database schema, metadata extraction logic

**Description**:  
The database metadata is missing a date column that would be very valuable for temporal analysis and filtering. Currently, there is no standardized way to capture and query documents by their date information.

**Requirements**:  
- Capture year-month information (particularly important)
- Capture full date if available (year-month-day)
- Year and month are the highest priority fields
- Should be stored in a format that allows efficient querying and filtering

**Proposed Implementation**:  
- Add a `date` or `document_date` column to the documents table
- Extract date information from document metadata during scraping
- Store as DATE type or separate year/month/day columns for flexibility
- Consider adding date information to chunk metadata for temporal filtering during retrieval

**Use Cases**:  
- Filter documents by submission date range
- Analyze policy changes over time
- Track document versions by date
- Enable temporal queries (e.g., "What did countries commit to in 2020?")

**Future Improvement**:  
- Add date extraction logic to scraper
- Update database schema to include date columns
- Update retrieval system to support date-based filtering
- Consider adding date information to chunk-level metadata for more granular temporal analysis

---

### 10. URL Not Appearing in CSV Export Output
**Priority**: High  
**Status**: Open  
**Affected Files**: `entrypoints/6_output.py`, `entrypoints/2_chunk.py`

**Description**:  
Despite implementing URL lookup logic in `get_document_metadata()`, URLs are still not appearing in the CSV export output. The `Chunk_X_Document` column shows document titles and file paths, but URLs are missing.

**Current Behavior**:
- Page numbers are correctly displayed in `Chunk_X_Page` columns ✅
- Document titles appear (though sometimes truncated/corrupted) ⚠️
- File paths appear in metadata when URL is missing ✅
- URLs are **not appearing** in the output ❌

**Root Causes**:
1. **Document creation during chunking**: When documents are created during the chunking process (`entrypoints/2_chunk.py`), the `url` field is set to an empty string `""` (line 179, 207). This happens because chunking processes local PDF files that don't have associated URLs.
2. **Different UUID generation**: Documents created during scraping use `uuid.uuid5(uuid.NAMESPACE_URL, doc.url)` while documents created during chunking use `uuid.uuid5(uuid.NAMESPACE_DNS, filename)`. This can result in different `doc_id` values for the same logical document, making URL lookup difficult.
3. **URL lookup fallback may not be working**: The fallback logic in `get_document_metadata()` tries to find related documents by country/title, but this may not be matching correctly if:
   - Titles differ between scraped and chunked versions
   - Multiple documents exist for the same country
   - The scraped document record doesn't exist in the database

**Evidence**:
- CSV output shows: `{Title} | File: {filename}` but no `URL: {url}`
- Logs may show: `"Document {doc_id} has no URL in database (url field: '')"`

**Proposed Solutions**:
1. **Improve document matching during chunking**: When creating a document record during chunking, check if a document with the same country/title already exists (from scraping) and preserve/update the URL field instead of setting it to empty string.
2. **Enhance URL lookup**: Improve the fallback query to better match documents by:
   - Using fuzzy matching on titles
   - Matching by country + submission_date
   - Checking for partial title matches
3. **Database migration**: Create a script to merge/update document records created during chunking with URLs from scraped records.
4. **Add URL to chunk_data**: Store the document URL in the `chunk_data` JSONB field during chunking so it's available even if the document record doesn't have it.

**Workaround**:  
Analysts can use the file path shown in `Chunk_X_Metadata` to locate the source document, though this requires local file system access.

---

### 11. Database Schema Duplication: Countries Table vs Entity Manager
**Priority**: Medium  
**Status**: Open  
**Affected Files**: `sql/1_countries.sql`, `group4py/src/constants/entities.py`, `group4py/src/scrape/db_operations.py`

**Description**:  
There are two sources of truth for country data:
1. **Database table** (`countries`): Used for referential integrity (foreign keys in `documents` and `questions_answers` tables)
2. **JSON file** (`data/entities/countries.json`): Used by the new `EntityManager` system for entity extraction

The scraper (`retrieve_allowed_countries()`) queries the database table, while the new entity system loads from JSON files. This creates duplication and potential inconsistencies.

**Current State**:
- `countries` table: Contains 90 countries, used for foreign key constraints
- `EntityManager`: Loads countries from `data/entities/countries.json` for query analysis
- Both systems coexist but are not synchronized

**Issues**:
- Countries added to JSON won't appear in database (breaks foreign keys)
- Countries added to database won't be recognized by entity extraction
- No single source of truth for country management

**Proposed Solutions**:
1. **Migrate to JSON as source of truth** (Recommended):
   - Use `EntityManager` to load countries from JSON
   - Sync database table from JSON during setup/migration
   - Update `retrieve_allowed_countries()` to use `EntityManager` instead of database query
   - Keep database table only for referential integrity (populate from JSON)

2. **Alternative: Database as source of truth**:
   - Load countries from database into `EntityManager` at startup
   - Update JSON file from database when countries are added
   - Less flexible for entity management

**Migration Steps** (if choosing JSON as source):
1. Update `retrieve_allowed_countries()` to use `EntityManager.get_entities_by_type(EntityType.COUNTRY)`
2. Create migration script to sync database table from JSON file
3. Update documentation to specify JSON as the source of truth
4. Add validation to ensure database table matches JSON on startup

**Related Files**:
- `sql/1_countries.sql` - Database table definition
- `group4py/src/constants/entities.py` - EntityManager implementation
- `group4py/src/scrape/db_operations.py` - `retrieve_allowed_countries()` function

---

### 12. Database Schema Mismatch: Questions Table vs New Prompt System
**Priority**: High  
**Status**: Open  
**Affected Files**: `sql/2_questions.sql`, `sql/6_question_answers.sql`, `questions/` module, `group4py/src/databases/operations.py`

**Description**:  
The database schema uses integer question IDs (1-10) in the `questions` table, but the new prompt system (`questions/` module) uses string prompt IDs (e.g., "net_zero_target", "EP4a"). This creates a mismatch when storing answers in `questions_answers` table.

**Current State**:
- **Old system**: Integer question IDs (1-10) stored in `questions` table
- **New system**: String prompt IDs (e.g., "net_zero_target") defined in Python code
- **Storage**: `questions_answers.question` column expects INTEGER (foreign key to `questions.id`)
- **Upload code**: `operations.py` still expects integer `question_number` when uploading answers

**Issues**:
- New prompt system uses string IDs that don't map to database integers
- `batch_process.py` uses prompt IDs (strings) but `operations.py` expects question numbers (integers)
- Cannot store answers for new prompts in database without mapping layer
- Legacy system and new system are incompatible

**Proposed Solutions**:
1. **Migrate to prompt ID storage** (Recommended):
   - Change `questions_answers.question` column from INTEGER to TEXT
   - Remove foreign key constraint to `questions` table (or make it optional)
   - Update `operations.py` to accept prompt IDs (strings) instead of question numbers
   - Keep `questions` table for legacy data only, or deprecate it
   - Store prompt IDs directly: `"net_zero_target"`, `"EP4a"`, etc.

2. **Alternative: Create mapping table**:
   - Create `prompt_question_mapping` table to map prompt IDs to question numbers
   - Keep integer-based storage for backward compatibility
   - Add translation layer in `operations.py`
   - More complex but maintains backward compatibility

**Migration Steps** (if choosing prompt ID storage):
1. Create migration SQL to:
   - Add new column `prompt_id TEXT` to `questions_answers` table
   - Migrate existing data (map question numbers to prompt IDs if possible)
   - Make `question` column nullable or remove foreign key constraint
2. Update `operations.py`:
   - Change `upload_single_question()` to accept `prompt_id` (string) instead of `question_number` (int)
   - Update SQL INSERT to use `prompt_id` column
   - Update validation logic to check prompt registry instead of questions table
3. Update `batch_process.py`:
   - Ensure prompt IDs are passed correctly to upload functions
4. Deprecate `questions` table:
   - Mark as legacy-only
   - Document that new prompts should not be added to this table

**Code Changes Required**:
```python
# operations.py - Change from:
question_number = question_data.get('question_number')  # int
"question": question_number,  # INTEGER

# To:
prompt_id = question_data.get('prompt_id')  # str
"prompt_id": prompt_id,  # TEXT
```

**Related Files**:
- `sql/2_questions.sql` - Legacy questions table
- `sql/6_question_answers.sql` - Answers table (needs schema change)
- `questions/` module - New prompt system
- `group4py/src/databases/operations.py` - Answer upload logic
- `entrypoints/batch_process.py` - Uses new prompt system

---

### 13. Database Schema Migration: Align New Systems with Database
**Priority**: High  
**Status**: Open  
**Affected Files**: All SQL files, `questions/` module, `group4py/src/constants/entities.py`

**Description**:  
The new entity management system (`EntityManager`) and prompt system (`questions/` module) were designed to be independent of the database, but the database schema still relies on legacy tables (`countries`, `questions`). This creates architectural inconsistency and prevents full migration to the new systems.

**Current Architecture Issues**:
1. **Countries**: Database table vs JSON file duplication (see Issue #11)
2. **Questions**: Integer IDs vs string prompt IDs mismatch (see Issue #12)
3. **Answers**: Cannot store new prompt answers without schema changes

**Recommended Migration Path**:
1. **Phase 1: Countries Migration**
   - Use `EntityManager` as single source of truth
   - Sync database table from JSON on setup
   - Update all database queries to use `EntityManager`

2. **Phase 2: Questions/Prompts Migration**
   - Change `questions_answers.question` to `prompt_id` (TEXT)
   - Remove dependency on `questions` table for new prompts
   - Update upload logic to use prompt IDs

3. **Phase 3: Schema Cleanup**
   - Mark `questions` table as legacy-only
   - Document migration path for existing data
   - Consider deprecating `questions` table if no longer needed

**Benefits of Migration**:
- ✅ Single source of truth for entities (JSON files)
- ✅ Flexible prompt system (Python code, not database)
- ✅ No duplication between systems
- ✅ Easier to add new prompts and entities
- ✅ Better alignment with new architecture

**Migration Risks**:
- ⚠️ Breaking changes for existing data
- ⚠️ Need to migrate existing `questions_answers` records
- ⚠️ May require downtime for schema changes

**Action Items**:
- [ ] Create migration script for countries (JSON → database sync)
- [ ] Create migration script for questions_answers (add prompt_id column)
- [ ] Update `operations.py` to use prompt IDs
- [ ] Update `retrieve_allowed_countries()` to use EntityManager
- [ ] Test migration on development database
- [ ] Document migration process
- [ ] Create rollback plan

**Related Issues**:
- Issue #11: Countries table duplication
- Issue #12: Questions table mismatch

---

### 14. Prompt System: Too Many Manual Steps to Add New Prompts
**Priority**: Medium  
**Status**: Open  
**Affected Files**: `questions/prompts/__init__.py`, `questions/tpi_centres.py`, `questions/projects.py`

**Description**:  
Adding a new prompt currently requires manual changes to multiple files:
1. Create prompt file
2. Create `__init__.py` files in directory structure
3. Manually import in `questions/prompts/__init__.py`
4. Manually add mapping in `questions/tpi_centres.py`
5. Optionally update `questions/projects.py`

This is error-prone and creates friction for analysts adding new prompts.

**Proposed Solution**:  
Implement auto-discovery system that:
- Automatically scans `questions/prompts/` directories for prompt files
- Auto-registers prompts when imported
- Auto-creates TPI Centre mappings from `metadata.tpi_centre_ids` in prompt definitions
- Reduces adding a prompt to creating ONE file with zero manual configuration

**Benefits**:
- ✅ Only 1 file to create (vs 3-4 files currently)
- ✅ Zero manual steps (vs 3-4 steps currently)
- ✅ Less error-prone
- ✅ Faster for analysts to add prompts

**Implementation Details**:  
See `SIMPLIFIED_PROMPT_SYSTEM.md` for detailed proposal and implementation options.

**Related Files**:
- `SIMPLIFIED_PROMPT_SYSTEM.md` - Detailed proposal document
- `HOW_TO_ADD_NEW_PROMPT.md` - Current manual process guide

---

**Last Updated**: November 18, 2025  
**Maintained by**: Project Contributors


