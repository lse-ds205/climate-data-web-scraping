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

### 2. Saudi Arabia Document Missing Submission Date
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

## 💡 Improvements / Enhancements

### 1. Windows Docker Networking Workaround
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

### 2. Country Filtering Verification
**Priority**: Low  
**Status**: Implemented  
**Related Files**: `group4py/src/scrape/workflow.py`, `group4py/src/scrape/db_operations.py`

**Description**:  
The scraper now filters documents to only include the 85 countries specified in the `countries` table. The workflow logs show this is working correctly (162 documents excluded in last run).

**Future Improvement**:  
- Add a configuration file or command-line argument to specify which countries to scrape
- Generate a report showing which countries have documents vs. which are in the filter list but have no documents

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

**Last Updated**: October 13, 2025  
**Maintained by**: Project Contributors


