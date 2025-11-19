# Tests Directory

This directory contains the main test scripts for the RAG system.

## Quick Start

### 1. Test LLM Connection (First Step!)

Before running other tests, verify your LLM API is configured:

```bash
python tests/test_llm_connection.py
```

This will check:
- Environment variables are set (`AI_API_KEY`, `AI_BASE_URL`)
- LLM client can be initialized
- API connection works

**Fix any issues here before proceeding!**

### 2. Test Retrieval System

Test how well the retrieval system finds relevant chunks:

```bash
# Test with a single question
python tests/test_retrieval.py --single

# Test all questions and countries
python tests/test_retrieval.py

# Test custom question
python tests/test_retrieval.py --question "Your question" --country "Country Name"
```

### 3. Test LLM Responses

Test the full pipeline (retrieval + LLM):

```bash
# Test with a single question
python tests/test_llm_single.py --single

# Test all questions and countries
python tests/test_llm_single.py

# Test custom question
python tests/test_llm_single.py --question "Your question" --country "Country Name"
```

## Test Files

- **`test_llm_connection.py`** - Diagnose LLM API connection issues
- **`test_retrieval.py`** - Test retrieval system with improved prompts
- **`test_llm_single.py`** - Test full pipeline (retrieval + LLM response)

## Configuration

Edit the `TEST_QUESTIONS` and `TEST_COUNTRIES` dictionaries at the top of each test script to customize what gets tested.

## Output

All test results are saved to `test_data/` in the project root:
- `retrieval_test_results_[timestamp].json`
- `llm_test_results_[timestamp].json`
- `llm_test_summary_[timestamp].json`

## Troubleshooting

### LLM Connection Errors

1. Run `python tests/test_llm_connection.py` first
2. Check your `.env` file has:
   - `AI_API_KEY=your_key_here`
   - `AI_BASE_URL=your_url_here`
3. Verify your API credentials are correct
4. Test your internet connection

### Retrieval Issues

- Check that documents have been processed (`entrypoints/2_chunk.py`, `entrypoints/3_embed.py`)
- Verify database connection
- Check logs in `logs/retrieve.log`

## Other Test Files

Additional test files in the project root (for reference/development):
- `comprehensive_test.py` - Comprehensive batch testing
- `test_mvp.py` - MVP testing framework
- `test_prompt_comparison.py` - Compare prompt variations
- `quick_test.py`, `simple_test.py`, `poc_test.py` - Quick development tests

