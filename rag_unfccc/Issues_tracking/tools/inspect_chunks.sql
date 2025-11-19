-- ============================================================================
-- SQL Queries to Inspect Chunks in Database
-- Run these in your PostgreSQL client or via docker exec
-- ============================================================================

-- 1. OVERVIEW: Total counts
-- ============================================================================
SELECT 
    COUNT(DISTINCT d.doc_id) as total_documents,
    COUNT(DISTINCT CASE WHEN d.processed_at IS NOT NULL THEN d.doc_id END) as processed_documents,
    COUNT(dc.id) as total_chunks,
    ROUND(AVG(LENGTH(dc.content)), 0) as avg_chunk_length,
    MIN(LENGTH(dc.content)) as min_chunk_length,
    MAX(LENGTH(dc.content)) as max_chunk_length
FROM documents d
LEFT JOIN doc_chunks dc ON d.doc_id = dc.doc_id;


-- 2. CHUNKS BY COUNTRY
-- ============================================================================
SELECT 
    d.country,
    COUNT(dc.id) as num_chunks,
    ROUND(AVG(LENGTH(dc.content)), 0) as avg_length,
    COUNT(DISTINCT d.doc_id) as num_documents
FROM documents d
LEFT JOIN doc_chunks dc ON d.doc_id = dc.doc_id
WHERE d.processed_at IS NOT NULL
GROUP BY d.country
ORDER BY num_chunks DESC;


-- 3. VIEW SAMPLE CHUNKS (First 5 from each document)
-- ============================================================================
SELECT 
    d.country,
    d.language,
    dc.chunk_index,
    dc.page,
    LEFT(dc.content, 100) || '...' as chunk_preview,
    LENGTH(dc.content) as chunk_length,
    dc.chunk_data->>'page_number' as metadata_page
FROM documents d
JOIN doc_chunks dc ON d.doc_id = dc.doc_id
WHERE dc.chunk_index < 5
ORDER BY d.country, dc.chunk_index
LIMIT 50;


-- 4. VIEW FULL CHUNKS from a specific country
-- ============================================================================
SELECT 
    d.country,
    d.title,
    dc.chunk_index,
    dc.page,
    dc.content,
    dc.chunk_data
FROM documents d
JOIN doc_chunks dc ON d.doc_id = dc.doc_id
WHERE d.country = 'USA'  -- Change country here
ORDER BY dc.chunk_index
LIMIT 10;


-- 5. SEARCH CHUNKS by content
-- ============================================================================
SELECT 
    d.country,
    d.title,
    dc.chunk_index,
    dc.page,
    dc.content,
    LENGTH(dc.content) as length
FROM documents d
JOIN doc_chunks dc ON d.doc_id = dc.doc_id
WHERE dc.content ILIKE '%emission%'  -- Search term here
   OR dc.content ILIKE '%climate%'
ORDER BY d.country, dc.chunk_index
LIMIT 20;


-- 6. CHUNKS WITH METADATA ANALYSIS
-- ============================================================================
SELECT 
    d.country,
    dc.page,
    dc.chunk_index,
    dc.chunk_data->>'page_number' as meta_page,
    dc.chunk_data->>'element_types' as element_types,
    dc.chunk_data->>'paragraph_numbers' as paragraphs,
    LEFT(dc.content, 80) || '...' as preview
FROM documents d
JOIN doc_chunks dc ON d.doc_id = dc.doc_id
ORDER BY d.country, dc.page, dc.chunk_index
LIMIT 30;


-- 7. DOCUMENTS WITHOUT CHUNKS (Processing failures)
-- ============================================================================
SELECT 
    d.country,
    d.title,
    d.file_path,
    d.processed_at,
    d.language
FROM documents d
WHERE d.processed_at IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM doc_chunks dc WHERE dc.doc_id = d.doc_id
  )
ORDER BY d.country;


-- 8. CHUNK DISTRIBUTION BY PAGE
-- ============================================================================
SELECT 
    d.country,
    dc.page,
    COUNT(dc.id) as chunks_on_page,
    ROUND(AVG(LENGTH(dc.content)), 0) as avg_chunk_length
FROM documents d
JOIN doc_chunks dc ON d.doc_id = dc.doc_id
WHERE d.country = 'China'  -- Change country here
GROUP BY d.country, dc.page
ORDER BY dc.page;


-- 9. LONGEST AND SHORTEST CHUNKS
-- ============================================================================
-- Longest chunks
SELECT 
    d.country,
    dc.chunk_index,
    dc.page,
    LENGTH(dc.content) as length,
    LEFT(dc.content, 100) || '...' as preview
FROM documents d
JOIN doc_chunks dc ON d.doc_id = dc.doc_id
ORDER BY LENGTH(dc.content) DESC
LIMIT 10;

-- Shortest chunks
SELECT 
    d.country,
    dc.chunk_index,
    dc.page,
    LENGTH(dc.content) as length,
    dc.content as full_content
FROM documents d
JOIN doc_chunks dc ON d.doc_id = dc.doc_id
ORDER BY LENGTH(dc.content) ASC
LIMIT 10;


-- 10. CHUNK QUALITY CHECKS
-- ============================================================================
-- Chunks that might be problematic (too short, repetitive, etc.)
SELECT 
    d.country,
    dc.chunk_index,
    LENGTH(dc.content) as length,
    dc.content,
    CASE 
        WHEN LENGTH(dc.content) < 50 THEN 'TOO_SHORT'
        WHEN LENGTH(dc.content) > 1000 THEN 'TOO_LONG'
        WHEN dc.content ~ '(.)\1{10,}' THEN 'REPETITIVE'
        ELSE 'OK'
    END as quality_flag
FROM documents d
JOIN doc_chunks dc ON d.doc_id = dc.doc_id
WHERE LENGTH(dc.content) < 50 
   OR LENGTH(dc.content) > 1000
   OR dc.content ~ '(.)\1{10,}'
ORDER BY quality_flag, LENGTH(dc.content)
LIMIT 30;


-- 11. EXPORT CHUNKS to CSV (for external analysis)
-- ============================================================================
-- Run this in psql:
-- \copy (SELECT d.country, d.title, dc.chunk_index, dc.page, dc.content, LENGTH(dc.content) as length FROM documents d JOIN doc_chunks dc ON d.doc_id = dc.doc_id ORDER BY d.country, dc.chunk_index) TO 'chunks_export.csv' WITH CSV HEADER;


-- 12. VIEW CHUNKS WITH THEIR CONTEXT (previous and next chunks)
-- ============================================================================
WITH chunk_context AS (
    SELECT 
        d.country,
        d.title,
        dc.chunk_index,
        dc.content as current_chunk,
        LAG(dc.content, 1) OVER (PARTITION BY d.doc_id ORDER BY dc.chunk_index) as previous_chunk,
        LEAD(dc.content, 1) OVER (PARTITION BY d.doc_id ORDER BY dc.chunk_index) as next_chunk
    FROM documents d
    JOIN doc_chunks dc ON d.doc_id = dc.doc_id
)
SELECT 
    country,
    chunk_index,
    LEFT(previous_chunk, 80) || '...' as prev,
    LEFT(current_chunk, 80) || '...' as current,
    LEFT(next_chunk, 80) || '...' as next
FROM chunk_context
WHERE country = 'USA'  -- Change country
  AND chunk_index BETWEEN 5 AND 10
ORDER BY chunk_index;

