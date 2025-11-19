# TPI RAG System: Architecture & Design Overview

## Executive Summary

The TPI RAG (Retrieval-Augmented Generation) system is a (hopefully) scalable, project-based framework for extracting structured information from climate policy documents. Designed for TPI Centre-wide deployment, the system enables analysts to query documents across multiple projects (ASCOR, Banking, CP, CA) using standardized prompts mapped to TPI Centre research codes.

**Core Philosophy**: Modular, extendible, and project-agnostic architecture that supports multiple entity types (countries, companies, banks), document types (NDCs, BTRs, sustainability reports), and research questions while maintaining a single unified codebase.

---

## System Architecture

### High-Level Flow

```
Document Ingestion → Chunking → Embedding → Storage
                                              ↓
Query (TPI Centre ID) → Entity Detection → Retrieval → LLM → Structured Output
```

### Key Components

1. **Entity Management System** - Centralized entity definitions and metadata
2. **Prompt System** - Project-based prompt organization with TPI Centre ID mapping
3. **Batch Processing** - Scalable processing of multiple entities with aggregated outputs
4. **Output System** - Structured CSV/Excel exports with source citations

---

## 1. Entity Management System

### Purpose

The Entity Management System provides a **single source of truth** for all entities (countries, companies, banks) used across the pipeline. This enables:
- Consistent entity recognition in queries
- Metadata-based filtering (by sector, geography, document type)
- Easy expansion to new entity types
- Project-specific entity configurations

### Architecture

**Location**: `data/entities/` and `group4py/src/constants/entities.py`

**Structure**:
```
data/entities/
├── entity_config.json      # Entity type configurations
├── countries.json          # Country list with metadata
├── companies.json          # Company list with metadata
├── banks.json              # Bank list with metadata
└── *_aliases.json          # Name variations for matching
```

**Key Features**:
- **JSON-based configuration**: Easy to edit, version control friendly
- **Metadata support**: Income groups, sectors, headquarters, document types
- **Alias matching**: Handles variations in entity names
- **Lazy loading**: Only loads entity types when needed (performance optimization)
- **Type-safe access**: Enum-based entity type system

### Usage Example

```python
from group4py.src.constants.entities import EntityManager, EntityType

# Load entities
manager = EntityManager()
countries = manager.get_entities_by_type(EntityType.COUNTRY)

# Use in batch processing
python entrypoints/batch_process.py --entity-type countries --tpi-centre-id EP4a
```

### Extension Points

- **Add new entity types**: Add JSON file + update `EntityType` enum
- **Add metadata fields**: Extend JSON schema, update `EntityConfig`
- **Custom matching logic**: Override `EntityManager` methods

**Goal for TPI Centre-wide**: Standardize entity metadata across all projects for overlapping fields, enabling cross-project analysis and consistent metadata.

---

## 2. Prompt System

### Purpose

The Prompt System organizes research questions by **project** and maps them to **TPI Centre IDs**, enabling:
- Project-specific prompt customization
- Shared prompts across projects to increase standardisation on similar questions
- TPI Centre ID-based querying (e.g., `EP4a`, `EP4ai`)
- Prompt versioning and evolution
- Metadata-based document filtering

### Architecture

**Location**: `questions/` module

**Structure**:
```
questions/
├── prompts.py              # Core PromptDefinition classes
├── projects.py             # Project configurations (ASCOR, Banking, CP, CA)
├── tpi_centres.py          # TPI Centre ID → Prompt mappings
├── filters.py              # Document metadata filtering
└── prompts/
    ├── shared/             # Prompts shared across projects
    └── projects/
        ├── ascor/          # ASCOR-specific prompts
        ├── banking/        # Banking-specific prompts
        └── ...
```

### Key Concepts

#### PromptDefinition
- **ID**: Unique identifier (e.g., `"ep4ai"`)
- **Text**: The actual prompt/question text
- **Metadata**: Entity types, projects, TPI Centre IDs, document types, keywords, `top_k`
- **Versioning**: Track prompt evolution over time

#### Project Organization
- **Primary dimension**: Projects (ASCOR, Banking, CP, CA)
- **Shared prompts**: Can be used across multiple projects
- **Project overrides**: Customize prompts per project without duplication

#### TPI Centre ID Mapping
- **TPI Centre IDs**: Research codes (e.g., `EP4a`, `EP4ai`, `Banking_NetZero`)
- **Many-to-one**: Multiple TPI Centre IDs can map to the same prompt (for different projects), but each TPI Centre ID maps to exactly one prompt
- **Entity type filtering**: Each mapping specifies applicable entity types

### Usage Example

```python
from questions import get_prompt, get_tpi_centre_mapping

# Get prompt by TPI Centre ID
mapping = get_tpi_centre_mapping('EP4ai')
prompts = mapping.prompt_ids  # ['ep4ai']

# Get prompt text for entity type
prompt = get_prompt('ep4ai')
text = prompt.get_text_for_entity('countries')
```

### Adding New Prompts

To add a new prompt to the system, follow these steps:

#### Step 1: Create Prompt File

Create a new file: `questions/prompts/projects/{project}/{prompt_id}.py`

**Example**: `questions/prompts/projects/ascor/ep4ai.py`

```python
"""
EP4ai Prompt for ASCOR Project

Asks: In what year is the net zero CO₂ target set?
"""

from questions.prompts import PromptDefinition, PromptMetadata, register_prompt

EP4AI_PROMPT = PromptDefinition(
    id="ep4ai",
    text="""Your prompt text here...""",
    metadata=PromptMetadata(
        entity_types=['countries'],  # ['countries', 'companies', 'banks']
        projects=['ASCOR'],  # ['ASCOR', 'Banking', 'CP', 'CA']
        tpi_centre_ids=['EP4ai'],  # TPI Centre ID(s) for this prompt
        document_types=None,  # None = all types, or ['NDC', 'BTR', etc.]
        created_by="Your Name",
        created_at="2025-11-18T00:00:00Z",
        version="1.0",
        description="Brief description of what this prompt asks",
        keywords=["keyword1", "keyword2", "keyword3"],  # For retrieval
        top_k=3  # Optional: number of chunks to retrieve (None = use system default)
    )
)

# Auto-register the prompt
register_prompt(EP4AI_PROMPT)
```

#### Step 2: Register in Project __init__.py

Import the prompt in `questions/prompts/projects/{project}/__init__.py`:

```python
# questions/prompts/projects/ascor/__init__.py
from questions.prompts.projects.ascor.ep4ai import EP4AI_PROMPT
```

#### Step 3: Map to TPI Centre ID

Add mapping in `questions/tpi_centres.py`:

```python
TPI_CENTRE_MAPPINGS: Dict[str, TPICentreMapping] = {
    # ... existing mappings ...
    
    'EP4ai': TPICentreMapping(
        tpi_centre_id='EP4ai',
        project='ASCOR',
        prompt_ids=['ep4ai'],  # Must match the prompt id above
        entity_types=['countries'],
        description='Net zero CO₂ target year for countries (ASCOR)'
    ),
}
```

#### Step 4: Add to Project Configuration (if new TPI Centre ID)

If you're adding a new TPI Centre ID, update `questions/projects.py`:

```python
PROJECTS: Dict[str, ProjectConfig] = {
    'ASCOR': ProjectConfig(
        # ... existing config ...
        tpi_centre_ids=['EP4a', 'EP4ai', 'EP4b'],  # Add your new TPI Centre ID here
        # ...
    ),
}
```

#### Step 5: Verify

Test that the prompt is accessible:

```python
from questions import get_prompt, get_tpi_centre_mapping

# Check prompt exists
prompt = get_prompt('ep4ai')
print(prompt.text)

# Check TPI Centre mapping
mapping = get_tpi_centre_mapping('EP4ai')
print(mapping.prompt_ids)  # Should show ['ep4ai']
```

#### Complete Example

See `questions/prompts/projects/ascor/ep4ai.py` for a complete working example.

**Note**: Currently, adding a prompt requires manual changes to multiple files. See Issue #14 in `KNOWN_ISSUES.md` for plans to simplify this process with auto-discovery.

**Goal for TPI Centre-wide**: Enable analysts to add prompts without code changes, with clear project organization and TPI Centre ID mapping for research tracking.

---

## 3. Batch Processing & Output System

### Purpose

The Batch Processing system enables **scalable analysis** of multiple entities with structured outputs:
- Process all entities of a type with one command
- Generate aggregated CSV/Excel files (one row per entity)
- Include source citations (page numbers, document titles, URLs) - this needs to be optimised and ideally made flexible to different questions that may want differnt strucutured outputs. 
- Support multiple output formats (CSV, Excel)
- Track failures for easy re-runs

### Architecture

**Location**: `entrypoints/batch_process.py` and `entrypoints/6_output.py`

**Flow**:
```
TPI Centre ID → Prompt IDs → Entities → Process Each → Aggregate → Export
```

### Key Features

#### Batch Processing (`batch_process.py`)
- **Entity filtering**: Process all entities or specific subset
- **Retry logic**: Automatic retry for LLM failures (up to 2 retries)
- **Failure tracking**: Saves failed runs to JSON for re-processing
- **Progress tracking**: Real-time status updates
- **Chunk metadata preservation**: Stores original chunks for citation lookup

#### Output System (`6_output.py`)
- **Structured exports**: Question, Question_text, Entity, Answer, Explanation, Sources
- **Source citations**: Chunk content, page numbers, document titles/URLs, metadata
- **Custom extraction**: Prompt-specific answer extraction (e.g., year extraction for EP4ai)
- **Directory organization**: `outputs/csv/{entity_type}/{TPI_Centre_ID}/{date}/`
- **Multiple formats**: CSV (UTF-8 with BOM) and Excel (with hyperlinks)

### Usage Example

```bash
# Process all countries with EP4ai prompt
python entrypoints/batch_process.py \
    --entity-type countries \
    --tpi-centre-id EP4ai \
    --output-format both

# Process specific countries only
python entrypoints/batch_process.py \
    --entity-type countries \
    --entities "Australia,Brazil,Barbados" \
    --tpi-centre-id EP4a
```

### Output Structure

**CSV/Excel Columns**:
- `Question`: TPI Centre ID (e.g., `EP4ai`)
- `Question_text`: First line of prompt
- `Entity`: Entity name
- `Answer`: Extracted answer (year, Yes/No, or custom format)
- `Explanation`: Full LLM explanation
- `Source_Chunk_1`, `Chunk_1_Page`, `Chunk_1_Document`, `Chunk_1_Metadata`: Citation details
- (Repeats for additional chunks)

**File Organization**: - output file organisation to be cleaned
```
outputs/csv/
└── countries/
    └── EP4ai/
        └── 20251118/
            ├── EP4ai_20251118_143022.csv
            └── EP4ai_20251118_143022.xlsx
```

### Extension Points

- **Custom output structures**: Add extraction logic in `export_batch_aggregated()` (see Issue #4 in KNOWN_ISSUES.md)
- **New output formats**: Extend `export_batch_aggregated()` to support additional formats
- **Metadata filtering**: Use `DocumentFilter` to filter by document type, date, etc.

**Goal for TPI Centre-wide**: Enable analysts to run batch analyses across all entities with standardized outputs that include full source citations for verification.

---

## 4. Design Principles & Extension Strategy

### Modularity

Each system component is **independent** and can be extended without affecting others:
- Entity Management: Add new entity types without changing prompts
- Prompt System: Add new prompts without changing entity definitions
- Batch Processing: Works with any entity type + prompt combination

### Project-Based Organization

**Primary dimension**: Projects (ASCOR, Banking, CP, CA)
- Each project has its own prompts and entity type
- Prompts can be shared across projects
- Project-specific customizations are isolated

### TPI Centre ID Mapping

**Research tracking**: TPI Centre IDs map to research questions
- Analysts query by TPI Centre ID (e.g., `EP4ai`)
- System automatically finds associated prompts
- Outputs are tagged with TPI Centre ID for tracking

### Metadata-Driven Filtering

**Flexible document selection**: Filter by:
- Entity type (countries, companies, banks)
- Document type (NDC, BTR, sustainability report)
- Publication date (year, date range)
- Custom metadata fields

### Scalability Considerations

- **Lazy loading**: Entity types loaded only when needed
- **Batch processing**: Process multiple entities efficiently
- **Retry logic**: Handle transient failures gracefully
- **Failure tracking**: Easy re-runs of failed analyses

---

## 5. Current State & Future Expansion

### Implemented Features

✅ **Entity Management**: Countries, companies, banks with metadata  
✅ **Prompt System**: Project-based organization with TPI Centre ID mapping  
✅ **Batch Processing**: Multi-entity processing with aggregated outputs  
✅ **Source Citations**: Page numbers, document titles, URLs in outputs  
✅ **Document Type Support**: NDC documents (extensible to other types)  
✅ **Custom Answer Extraction**: Year extraction for EP4ai (extensible)  

### Known Limitations (See KNOWN_ISSUES.md)

- **Issue #4**: Custom output structures require hardcoded extraction logic (EP4ai workaround)
- **Issue #15**: Legacy code in output module needs cleanup
- **Issue #12**: Database schema mismatch (legacy questions table vs new prompt system)

### Extension Roadmap

#### Short Term
1. **Auto-discovery for prompts**: Reduce manual steps when adding prompts (Issue #14)
2. **Custom output column definitions**: Move from hardcoded extraction to metadata-driven (Issue #4)
3. **Document type expansion**: Add BTRs, LTS, sustainability reports
4. **URL matching improvement**: Better document matching during chunking (Issue #10)

#### Medium Term
1. **Database schema migration**: Align database with new entity/prompt systems (Issue #13)
2. **Personal prompts**: Allow analysts to create project-specific prompts
3. **Prompt versioning UI**: Visual interface for prompt evolution
4. **Advanced filtering**: Date ranges, multiple document types, custom metadata

#### Long Term
1. **Multi-project analysis**: Cross-project queries and comparisons
2. **Prompt effectiveness tracking**: Metrics on prompt performance
3. **Automated prompt optimization**: A/B testing for prompt variations
4. **Web interface**: UI for prompt management and batch processing

---

## 6. Getting Started

### For Analysts

1. **Run batch analysis**:
   ```bash
   python entrypoints/batch_process.py --entity-type countries --tpi-centre-id EP4ai
   ```

2. **Review outputs**: Check `outputs/csv/countries/EP4ai/{date}/` for results

3. **Add new prompt**: See the "Adding New Prompts" section above in the Prompt System section, or refer to Issue #14 in `KNOWN_ISSUES.md` for future simplification plans

### For Developers

1. **Understand entity system**: Read [`entity_management.md`](entity_management.md) (in same directory)
2. **Understand prompt system**: Review `questions/` module structure (see "Adding New Prompts" section above)
3. **Extend batch processing**: Modify `entrypoints/batch_process.py` (see [`BATCH_PROCESSING_GUIDE.md`](BATCH_PROCESSING_GUIDE.md))
4. **Customize outputs**: Modify `entrypoints/6_output.py` (see Issue #4 in `Issues_tracking/KNOWN_ISSUES.md`)

### For Project Managers

1. **Review system architecture**: This document
2. **Check known issues**: `Issues_tracking/KNOWN_ISSUES.md`
3. **Plan extensions**: Use extension roadmap above
4. **Coordinate across projects**: Use project-based organization

---

## 7. Key Files Reference

| File | Purpose |
|------|---------|
| `data/entities/*.json` | Entity definitions and metadata |
| `group4py/src/constants/entities.py` | Entity management implementation |
| `questions/prompts.py` | Core prompt definition classes |
| `questions/projects.py` | Project configurations |
| `questions/tpi_centres.py` | TPI Centre ID mappings |
| `questions/prompts/projects/*/` | Project-specific prompts |
| `entrypoints/batch_process.py` | Batch processing orchestration |
| `entrypoints/6_output.py` | Export and output formatting |
| `Issues_tracking/KNOWN_ISSUES.md` | Known issues and TODOs (root directory) |
| [`BATCH_PROCESSING_GUIDE.md`](BATCH_PROCESSING_GUIDE.md) | Batch processing guide (same directory) |
| [`PROJECT_STRUCTURE.md`](PROJECT_STRUCTURE.md) | Directory structure (same directory) |

---

## 8. Design Goals for TPI Centre-Wide Application

### Standardization
- **Consistent entity definitions** across all projects
- **Standardized prompt format** with TPI Centre ID mapping
- **Unified output structure** for cross-project analysis

### Flexibility
- **Project-specific customizations** without code duplication
- **Easy prompt addition** by analysts (future: UI-based)
- **Extensible entity types** and metadata fields

### Scalability
- **Efficient batch processing** for large entity sets
- **Metadata-driven filtering** for targeted analysis
- **Modular architecture** for independent component updates

### Transparency
- **Source citations** in all outputs for verification
- **Prompt versioning** for reproducibility
- **Failure tracking** for quality assurance

### Collaboration
- **Shared prompts** across projects where applicable
- **Project isolation** for independent development
- **Clear extension points** for new features

---

**Last Updated**: November 18, 2025  
**Maintained by**: TPI Development Team  
**For Issues**: See `Issues_tracking/KNOWN_ISSUES.md`
