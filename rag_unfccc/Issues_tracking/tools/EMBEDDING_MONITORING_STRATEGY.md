# Embedding Monitoring Strategy

## Overview
This document outlines the strategy for monitoring and verifying that embeddings are being created correctly during the embedding process.

## 📊 Monitoring Strategy

### 1. Real-Time Progress Monitoring

#### **Option A: Live Monitoring Script**
```bash
# Monitor embedding progress every 30 seconds
python Issues_tracking/tools/monitor_embeddings.py --monitor --interval 30
```

#### **Option B: Manual Progress Checks**
```bash
# Check current embedding status
python Issues_tracking/tools/monitor_embeddings.py

# Verify sample embeddings
python Issues_tracking/tools/monitor_embeddings.py --verify --sample 10
```

### 2. Database Verification Queries

#### **Check Embedding Progress**
```sql
-- Total chunks vs embedded chunks
SELECT 
    COUNT(*) as total_chunks,
    COUNT(transformer_embedding) as transformer_embedded,
    COUNT(word2vec_embedding) as word2vec_embedded,
    COUNT(CASE WHEN transformer_embedding IS NOT NULL AND word2vec_embedding IS NOT NULL THEN 1 END) as both_embedded
FROM doc_chunks;
```

#### **Verify Embedding Dimensions**
```sql
-- Check embedding dimensions
SELECT 
    array_length(transformer_embedding, 1) as transformer_dims,
    array_length(word2vec_embedding, 1) as word2vec_dims,
    COUNT(*) as count
FROM doc_chunks 
WHERE transformer_embedding IS NOT NULL 
AND word2vec_embedding IS NOT NULL
GROUP BY 1, 2;
```

#### **Sample Embedding Values**
```sql
-- Check sample embedding values
SELECT 
    id,
    content,
    transformer_embedding[1:3] as transformer_sample,
    word2vec_embedding[1:3] as word2vec_sample
FROM doc_chunks 
WHERE transformer_embedding IS NOT NULL 
AND word2vec_embedding IS NOT NULL
LIMIT 5;
```

### 3. Log Analysis Strategy

#### **Key Log Messages to Watch For**
```
[3_EMBED] Processing chunk X/18333: <chunk_id>
[3_EMBED] Transformer embedding: 384 dimensions, first 3 values: [0.1, 0.2, 0.3]
[3_EMBED] Vector format: [0.1,0.2,0.3,0.4,0.5...
[3_EMBED] Word2Vec embedding: 100 dimensions, first 3 values: [0.1, 0.2, 0.3]
[3_EMBED] VERIFICATION - Chunk <chunk_id>:
[3_EMBED]   Transformer: YES (384 dims)
[3_EMBED]   Word2Vec: YES (100 dims)
```

#### **Error Messages to Watch For**
```
ERROR: Vector contents must start with "["
ERROR: null value in column "confidence"
ERROR: DockerProxySession does not support ORM queries
```

### 4. Expected Embedding Specifications

#### **Transformer Embeddings**
- **Model**: `all-MiniLM-L6-v2`
- **Dimensions**: 384
- **Format**: `[0.1,0.2,0.3,...]` (384 values)
- **Database Column**: `transformer_embedding`

#### **Word2Vec Embeddings**
- **Model**: Custom Word2Vec trained on all chunks
- **Dimensions**: 100
- **Format**: `[0.1,0.2,0.3,...]` (100 values)
- **Database Column**: `word2vec_embedding`

### 5. Progress Tracking

#### **Expected Progress Pattern**
```
Chunk 1/18333: Processing...
Chunk 100/18333: VERIFICATION - Both embeddings stored
Chunk 500/18333: Committed batch at 500 chunks
Chunk 1000/18333: VERIFICATION - Both embeddings stored
...
Chunk 18333/18333: Successfully generated embeddings for 18333 chunks
```

#### **Success Indicators**
- ✅ No "Vector contents must start with" errors
- ✅ Both transformer and Word2Vec embeddings for each chunk
- ✅ Correct dimensions (384 for transformer, 100 for Word2Vec)
- ✅ Proper vector formatting with square brackets
- ✅ Progress continues without infinite loops

## 🚀 Running the Embedding Process

### 1. Start the Embedding Process
```bash
# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Run embedding script
python entrypoints/3_embed.py
```

### 2. Monitor Progress (Separate Terminal)
```bash
# Option A: Live monitoring
python Issues_tracking/tools/monitor_embeddings.py --monitor

# Option B: Periodic checks
python Issues_tracking/tools/monitor_embeddings.py
```

### 3. Verify Results
```bash
# Check final status
python Issues_tracking/tools/monitor_embeddings.py

# Verify sample embeddings
python Issues_tracking/tools/monitor_embeddings.py --verify --sample 10
```

## 🔍 Troubleshooting

### If Embedding Fails
1. **Check vector formatting**: Ensure square brackets `[]` not curly braces `{}`
2. **Check database connection**: Verify Docker container is running
3. **Check chunk data**: Ensure chunks exist and have content
4. **Check memory**: Large embedding processes may need more RAM

### If Progress Stops
1. **Check logs**: Look for error messages
2. **Check database**: Verify chunks are being processed
3. **Restart process**: May need to restart if stuck
4. **Check disk space**: Embeddings require significant storage

### If Embeddings Are Wrong
1. **Check dimensions**: Should be 384 (transformer) and 100 (Word2Vec)
2. **Check format**: Should be square brackets `[]`
3. **Check values**: Should be reasonable float values
4. **Re-run if needed**: May need to clear and restart

## 📈 Expected Timeline

- **18,333 chunks** to process
- **~2-3 seconds per chunk** (with both embeddings)
- **Total time**: ~10-15 hours for complete embedding
- **Progress**: ~100-200 chunks per hour

## ✅ Success Criteria

The embedding process is successful when:
1. All 18,333 chunks have both transformer and Word2Vec embeddings
2. No vector formatting errors in logs
3. Correct dimensions for both embedding types
4. No infinite loops or repeated processing
5. Database contains valid embedding data for retrieval

