# Batch Processing System Guide

## Overview

The batch processing system allows you to process **all entities of a type** (countries, companies, banks) with **multiple questions** and generate **aggregated CSV/Excel outputs** with one row per entity.

## Key Features

✅ **One file per entity type** - All answers for all entities in a single CSV/Excel  
✅ **One row per entity** - Easy comparison across entities  
✅ **Multiple columns per question** - Answer, Explanation, and Sources for each question  
✅ **Clickable source links** - Links to original documents with page numbers  
✅ **TPI Centre ID support** - Map questions to research centres  
✅ **Flexible question selection** - Use question IDs or TPI Centre IDs  

## File Structure

```
outputs/csv/
├── countries/
│   └── countries_aggregated_20251117_143022.csv
├── companies/
│   └── companies_aggregated_20251117_143022.csv
└── banks/
    └── banks_aggregated_20251117_143022.csv
```

## CSV Structure

Each aggregated file has:
- **Entity** column (entity name)
- **Q1_Answer**, **Q1_Explanation**, **Q1_Sources** (for question 1)
- **Q2_Answer**, **Q2_Explanation**, **Q2_Sources** (for question 2)
- ... and so on for each question

## Usage

### Basic Usage

```bash
# Process all countries with questions 1, 2, 3
python entrypoints/batch_process.py --entity-type countries --questions 1,2,3

# Process all countries with all questions
python entrypoints/batch_process.py --entity-type countries --questions all

# Process specific countries only
python entrypoints/batch_process.py --entity-type countries --entities "Australia,Brazil" --questions 9

# Process companies with questions 1-5, Excel only
python entrypoints/batch_process.py --entity-type companies --questions 1,2,3,4,5 --output-format excel
```

### Using TPI Centre IDs

```bash
# Process all countries with EP4a (net zero target question)
python entrypoints/batch_process.py --entity-type countries --tpi-centre-id EP4a

# Process all countries with EP4ai (net zero target year)
python entrypoints/batch_process.py --entity-type countries --tpi-centre-id EP4ai
```

### Available TPI Centre IDs

To see all available TPI Centre IDs:
```bash
python -c "from questions import list_tpi_centres; print(', '.join(list_tpi_centres()))"
```

Current TPI Centre IDs:
- **`EP4a`** - Net zero target question for countries
- **`EP4ai`** - Net zero target year for countries

**Note:** TPI Centre IDs are defined in `questions/tpi_centres.py` and map to prompts in the `questions/prompts/` directory. See [`SYSTEM_OVERVIEW.md`](SYSTEM_OVERVIEW.md) (in same directory) for details on the prompt system.

## Command Line Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--entity-type` | Yes | Type: `countries`, `companies`, or `banks` |
| `--questions` | No* | Comma-separated question IDs or `all` |
| `--tpi-centre-id` | No* | TPI Centre ID (overrides `--questions`) |
| `--entities` | No | Comma-separated list of specific entities |
| `--top-k` | No | Number of chunks to retrieve (default: 5) |
| `--min-similarity` | No | Minimum similarity threshold (default: 0.1) |
| `--output-format` | No | `csv`, `excel`, or `both` (default: both) |

*Either `--questions` or `--tpi-centre-id` must be provided.

## Source Links

The system automatically generates clickable source links in the Sources columns:

- **URL links** - Direct links to original documents (with page anchors for PDFs)
- **File links** - Local file paths as `file://` URLs
- **Page numbers** - Page references for PDF documents
- **Chunk indices** - Chunk positions within documents

Example source format:
```
1. URL: https://example.com/doc.pdf#page=5 | File: file:///path/to/doc.pdf | Page: 5 | Chunk: 42 (similarity: 0.95) - This chunk provided information about...
```

## Adding New Prompts

The system uses a project-based prompt organization. To add a new prompt:

1. **Create prompt file**: `questions/prompts/projects/{project}/{prompt_id}.py`
2. **Define prompt**: Use `PromptDefinition` with metadata including TPI Centre ID
3. **Register**: Import in `questions/prompts/projects/{project}/__init__.py`
4. **Map to TPI Centre ID**: Add to `questions/tpi_centres.py`
5. **Add to project**: Update `questions/projects.py` if needed

See [`SYSTEM_OVERVIEW.md`](SYSTEM_OVERVIEW.md#2-prompt-system) (in same directory) for detailed architecture and examples.

**Note**: The legacy question system (`improved_questions.py`) has been archived. All new prompts should use the new prompt system.

## Output Files

### CSV Format
- Location: `outputs/csv/{entity_type}/{entity_type}_aggregated_{timestamp}.csv`
- Encoding: UTF-8 with BOM (for Excel compatibility)
- Format: One row per entity, columns per question

### Excel Format
- Location: `outputs/csv/{entity_type}/{entity_type}_aggregated_{timestamp}.xlsx`
- Features: Hyperlink formatting for source columns
- Requires: `openpyxl` package (`pip install openpyxl`)

## Example Output

| Entity | Q1_Answer | Q1_Explanation | Q1_Sources | Q2_Answer | ... |
|--------|-----------|----------------|------------|-----------|-----|
| Australia | Yes, Australia has... | Detailed explanation... | 1. URL: ... | Baseline year is... | ... |
| Brazil | Yes, Brazil committed... | Detailed explanation... | 1. URL: ... | Uses 2005 as... | ... |

## Troubleshooting

### No chunks found
- Check that entities have documents in the database
- Lower `--min-similarity` threshold
- Increase `--top-k` value

### LLM errors
- Check API credentials in `.env` file
- Verify `AI_API_KEY` and `AI_BASE_URL` are set
- Check API rate limits

### Missing source links
- Verify documents have `url` or `file_path` in database
- Check that `doc_id` in citations matches database records

## Integration with Existing Pipeline

The batch processing system integrates with:
- ✅ **Retrieval system** (`4_retrieve.py`) - Uses same chunk retrieval
- ✅ **LLM system** (`5_llm_response.py`) - Uses same LLM calls
- ✅ **Entity management** (`group4py/src/constants/entities.py`) - Uses entity detection
- ✅ **Output system** (`6_output.py`) - Uses aggregated export functions

## Next Steps

1. **Test with a small subset**:
   ```bash
   python entrypoints/batch_process.py --entity-type countries --entities "Australia" --questions 9
   ```

2. **Process all countries with a TPI Centre ID**:
   ```bash
   python entrypoints/batch_process.py --entity-type countries --tpi-centre-id net_zero_centre
   ```

3. **Review the aggregated CSV** in `outputs/csv/countries/`

4. **Add custom TPI Centre IDs** in `tpi_centre_questions.py` as needed

