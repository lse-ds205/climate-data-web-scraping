# Project Structure

This document describes the organization of the RAG-Fact-Sheet project.

**For system architecture and design principles, see [`SYSTEM_OVERVIEW.md`](SYSTEM_OVERVIEW.md) (in same directory).**

## Directory Structure

```
rag_unfccc/
├── entrypoints/          # Main pipeline scripts
│   ├── 1_scrape.py       # Download documents from UNFCCC - need to add new ways of adding documents to the system
│   ├── 2_chunk.py        # Extract and chunk text
│   ├── 3_embed.py        # Generate embeddings
│   ├── 4_retrieve.py     # Retrieve relevant chunks
│   ├── 5_llm_response.py # Generate LLM responses
│   ├── 6_output.py       # Generate CSV/Excel outputs - still contains legacy report generation code - to be cleaned
│   ├── 7_send_email.py   # Send email notifications - move or adapt to new needs - ie send email to projects when new data is scrapped 
│   └── batch_process.py  # Batch processing for multiple entities
│
├── tests/                # Test scripts
│   ├── test_llm_connection.py  # Test LLM API connection
│   ├── test_retrieval.py       # Test retrieval system
│   ├── test_llm_single.py      # Test full pipeline
│   └── README.md               # Testing guide
│
├── group4py/             # Core library code
│   └── src/
│       ├── chunk/        # Text chunking and extraction
│       ├── constants/    # Configuration, entities, prompts
│       ├── databases/    # Database operations and models
│       ├── embed/        # Embedding models (transformer, word2vec, hoprag)
│       ├── scrape/       # Web scraping and document processing
│       ├── schemas/       # Data models (Pydantic)
│       ├── helpers/      # Utility functions
│       ├── evaluator.py  # Retrieval evaluation
│       ├── query.py      # LLM client and processing
│       └── exceptions.py # Custom exceptions
│
├── questions/            # Prompt management system
│   ├── prompts.py        # Core PromptDefinition classes
│   ├── projects.py       # Project configurations (ASCOR, Banking, CP, CA)
│   ├── tpi_centres.py    # TPI Centre ID mappings
│   ├── filters.py        # Document metadata filtering
│   └── prompts/          # Prompt definitions
│       ├── shared/       # Prompts shared across projects
│       └── projects/     # Project-specific prompts
│           └── ascor/    # ASCOR project prompts
│
├── docs/                 # Documentation
│   ├── 1_scrape.md       # Scraping documentation
│   ├── 2_chunk.md        # Chunking documentation
│   ├── 3_embed.md        # Embedding documentation
│   ├── 4_retrieve.md     # Retrieval documentation
│   ├── 5_llm_response.md # LLM documentation
│   ├── 6_output.md       # Output documentation
│   ├── 7_send_email.md   # Email documentation
│   ├── db_schema.md      # Database schema
│   └── entity_management.md  # Entity management system
│
├── sql/                  # Database schema and setup
│   ├── setup_database.py # Database initialization script
│   ├── 1_countries.sql   # Countries table
│   ├── 2_questions.sql   # Questions table (legacy)
│   ├── 3_documents.sql   # Documents table
│   ├── 4_doc_chunks.sql  # Document chunks table
│   ├── 5_logical_relationships.sql  # Graph relationships
│   ├── 6_question_answers.sql  # Answers table
│   └── 7_citations.sql   # Citations table
│
├── data/                 # Data storage
│   ├── pdfs/             # Downloaded PDFs
│   ├── retrieve/         # Retrieval results (JSON)
│   ├── retrieve_hop/     # HopRAG retrieval results
│   └── entities/         # Entity definitions (JSON files)
│       ├── countries.json
│       ├── companies.json
│       ├── banks.json
│       ├── country_aliases.json
│       └── entity_config.json
│
├── outputs/              # Generated outputs
│   ├── csv/              # CSV/Excel exports
│   │   └── {entity_type}/{TPI_Centre_ID}/{date}/
│   └── failures/         # Failed batch processing runs (JSON)
│
├── archive/              # Archived/legacy code
│   └── legacy_prompts/   # Old prompt system files
│
├── Issues_tracking/      # Issue tracking and tools
│   ├── KNOWN_ISSUES.md   # Known issues and TODOs
│   └── tools/            # Utility scripts for debugging
│
├── logs/                 # Application logs
├── local_models/         # Local model files (Word2Vec)
├── manual/               # Manual utility scripts
├── scripts/              # Utility scripts
│   └── run_sql_in_docker.ps1  # Windows workaround for initial DB setup
└── requirements/         # Python dependencies
    ├── requirements.txt  # Main dependencies
    └── scrape.txt        # Scraping-specific dependencies
```

## Key Files

### Entry Points (Pipeline)

**Main Pipeline Scripts** (run in order for full pipeline):
1. **`entrypoints/1_scrape.py`** - Downloads documents from UNFCCC
2. **`entrypoints/2_chunk.py`** - Extracts text and creates chunks
3. **`entrypoints/3_embed.py`** - Generates embeddings for chunks
4. **`entrypoints/4_retrieve.py`** - Retrieves relevant chunks for questions
5. **`entrypoints/5_llm_response.py`** - Generates LLM responses
6. **`entrypoints/6_output.py`** - Generates CSV/Excel outputs
7. **`entrypoints/7_send_email.py`** - Sends email notifications

**Batch Processing**:
- **`entrypoints/batch_process.py`** - Process multiple entities with TPI Centre ID prompts, generates aggregated CSV/Excel outputs

### Test Scripts

Located in `tests/` directory:

- **`test_llm_connection.py`** - First step: verify LLM API is configured
- **`test_retrieval.py`** - Test retrieval with improved prompts
- **`test_llm_single.py`** - Test full pipeline (retrieval + LLM)

### Configuration

- **`.env`** - Environment variables (API keys, database URLs, etc.)
- **`env_format.txt`** - Template for environment variables
- **`requirements/requirements.txt`** - Python dependencies

### Documentation

- **`SYSTEM_OVERVIEW.md`** - **START HERE**: Complete system architecture and design
- **`README.md`** - Main project documentation and setup (root directory)
- **`PROJECT_STRUCTURE.md`** - This file (directory organization)
- **`BATCH_PROCESSING_GUIDE.md`** - Batch processing guide
- **Component docs** - Detailed documentation for each pipeline stage (1_scrape.md through 7_send_email.md)
- **`entity_management.md`** - Entity management system
- **`db_schema.md`** - Database schema documentation
- **`Issues_tracking/KNOWN_ISSUES.md`** - Known issues and TODOs (root directory)

## Workflow

### Initial Setup

1. Set up environment variables (`.env` file)
2. Set up database (`sql/setup_database.py`)
3. Download and process documents:
   ```bash
   python entrypoints/1_scrape.py
   python entrypoints/2_chunk.py
   python entrypoints/3_embed.py
   ```

### Testing

1. Test LLM connection:
   ```bash
   python tests/test_llm_connection.py
   ```

2. Test retrieval:
   ```bash
   python tests/test_retrieval.py --single
   ```

3. Test full pipeline:
   ```bash
   python tests/test_llm_single.py --single
   ```

### Running the Pipeline

After initial setup, run the pipeline:

```bash
python entrypoints/4_retrieve.py --question "Your question" --country "Country Name"
python entrypoints/5_llm_response.py
python entrypoints/6_output.py
python entrypoints/7_send_email.py
```

## File Organization Principles

1. **Entry points** - Main scripts users run (in `entrypoints/`)
2. **Core library** - Reusable code (in `group4py/src/`)
3. **Tests** - Test scripts (in `tests/`)
4. **Documentation** - All docs (in `docs/` and root)
5. **Data** - Generated data (in `data/`, `test_data/`, `logs/`)

## Adding New Features

- **New pipeline step**: Add to `entrypoints/` as `N_step_name.py`
- **New test**: Add to `tests/` as `test_feature_name.py`
- **New utility**: Add to `tools/` or `group4py/src/`
- **New documentation**: Add to `docs/` or root

## Key Directories

### `questions/` - Prompt Management System
The new prompt system organizes prompts by project with TPI Centre ID mapping:
- **`prompts.py`** - Core `PromptDefinition` and `PromptMetadata` classes
- **`projects.py`** - Project configurations (ASCOR, Banking, CP, CA)
- **`tpi_centres.py`** - Maps TPI Centre IDs (e.g., `EP4a`, `EP4ai`) to prompts
- **`prompts/projects/`** - Project-specific prompts organized by project
- **`prompts/shared/`** - Prompts shared across multiple projects

See [`SYSTEM_OVERVIEW.md`](SYSTEM_OVERVIEW.md#2-prompt-system) (in same directory) for detailed architecture.

### `data/entities/` - Entity Management
JSON-based entity definitions for countries, companies, and banks:
- Single source of truth for entity lists
- Metadata support (sectors, geography, document types)
- Alias matching for name variations

See [`docs/entity_management.md`](docs/entity_management.md) for details.

### `outputs/` - Generated Outputs
- **`csv/`** - Structured CSV/Excel exports organized by entity type, TPI Centre ID, and date
- **`failures/`** - JSON files tracking failed batch processing runs for easy re-runs

### `archive/` - Legacy Code
- **`legacy_prompts/`** - Old prompt system files (`improved_questions.py`, `tpi_centre_questions.py`)

---

## Test Files Status

✅ **All test files are properly organized in `tests/` directory**:
- `test_llm_connection.py` - LLM API connection testing
- `test_retrieval.py` - Retrieval system testing
- `test_llm_single.py` - Full pipeline testing

**Note**: The old test files mentioned in previous versions (`comprehensive_test.py`, `test_mvp.py`, `quick_test.py`, `simple_test.py`) have been removed. All testing is now done through the organized test suite in `tests/`.
