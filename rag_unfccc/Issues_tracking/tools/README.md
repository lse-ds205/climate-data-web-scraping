# Tools Directory

This directory contains development and inspection utilities that are **not part of the core pipeline**.

---

## 📁 What's Here

### `inspect_chunks.py`
Interactive Python tool to inspect chunks in the database with pretty formatting.

**Usage:**
```powershell
# Interactive mode
python tools/inspect_chunks.py

# Quick overview
python tools/inspect_chunks.py --overview --by-country

# View samples
python tools/inspect_chunks.py --sample 10

# Search content
python tools/inspect_chunks.py --search "emission"
```

### `check_embeddings.py`
Verify that embeddings exist and are working correctly in the database.

**Usage:**
```powershell
# Check embedding status
python tools/check_embeddings.py
```

Shows:
- Total chunks and embedding coverage
- Top countries by chunk count
- Embedding dimensions (transformer: 768, word2vec: 300)
- Country-specific statistics

### `inspect_chunks.sql`
Collection of SQL queries for direct database inspection.

**Usage:**
```powershell
# Open psql in Docker
docker exec -it NDC_rag psql -U climate -d climate

# Then copy/paste any query from inspect_chunks.sql
```

Contains 12 pre-written queries for:
- Overview statistics
- Chunks by country
- Content search
- Quality checks
- Data export

**Full documentation:** See [HOW_TO_INSPECT_CHUNKS.md](../HOW_TO_INSPECT_CHUNKS.md)

---

## 🎯 Purpose

Tools in this directory are for:
- ✅ Development and debugging
- ✅ Data inspection and quality checks
- ✅ Analysis and experimentation
- ✅ Reporting and exports

**NOT for:**
- ❌ Core pipeline execution (use `entrypoints/` instead)
- ❌ Production automation
- ❌ Required dependencies

---

## 🔧 Core Pipeline vs Tools

| Core Pipeline (`entrypoints/`) | Development Tools (`tools/`) |
|-------------------------------|------------------------------|
| `1_scrape.py` | `inspect_chunks.py` |
| `2_chunk.py` | Future: evaluation scripts |
| `3_embed.py` | Future: benchmark scripts |
| `4_retrieve.py` | Future: analysis tools |

---

## 📦 Dependencies

Tools may have additional dependencies not required for the core pipeline.

**For inspect_chunks.py:**
```powershell
pip install rich
```

---

## 🚀 Future Tools

Planned tools to add here:
- `evaluate_embeddings.py` - Compare embedding models
- `evaluate_chunking.py` - Test chunking strategies
- `benchmark_retrieval.py` - Measure retrieval performance
- `analyze_coverage.py` - Check document/country coverage
- `export_data.py` - Export chunks/embeddings for analysis
- `test_queries.py` - Interactive query testing

---

**Note**: If you're running the pipeline, you don't need anything in this folder. These are optional utilities for development and analysis.

