# Next Steps & Future Improvements

**Last Updated**: October 13, 2025  
**Status**: Planning & Experimentation Phase

---

## 🧪 Priority 1: Chunking Strategy Evaluation

### Motivation

The current **semantic sentence-based chunking** (512 chars, 2-sentence overlap) works well for general text but may not be optimal for:
- Multi-column policy documents
- Documents with tables and figures
- Documents with complex hierarchical structure
- Non-English documents with different sentence patterns

**Goal**: Systematically evaluate different chunking strategies to optimize retrieval quality and answer accuracy.

---

### Chunking Strategies to Test

#### 1. **Docling (Layout-Aware Chunking)** 🆕

**What it is**:
- IBM's document understanding library
- Uses vision-language models to understand document layout
- Preserves visual structure (columns, tables, figures)
- Maintains hierarchical relationships

**Key Features**:
```python
from docling import DocumentConverter

# Docling automatically detects:
# - Page regions (headers, footers, columns)
# - Tables (extracts as structured data)
# - Figures and captions
# - Reading order
# - Document hierarchy (sections, subsections)

converter = DocumentConverter()
result = converter.convert("document.pdf")

# Returns structured chunks with:
# - Layout preservation
# - Table extraction as markdown/JSON
# - Hierarchical structure
# - Visual reading order
```

**Advantages**:
- ✅ Preserves multi-column layouts
- ✅ Keeps tables intact
- ✅ Maintains visual reading order
- ✅ Extracts figures and captions
- ✅ Better for complex policy documents

**Implementation**:
```python
# entrypoints/2_chunk_docling.py (new file)
from docling.document_converter import DocumentConverter

converter = DocumentConverter()
doc_result = converter.convert(pdf_path)

# Iterate through structured chunks
for chunk in doc_result.document.chunks:
    db_chunk = DocChunkORM(
        content=chunk.text,
        chunk_data={
            'layout_type': chunk.type,  # 'text', 'table', 'figure'
            'bbox': chunk.bbox,  # Bounding box coordinates
            'page': chunk.page,
            'reading_order': chunk.order
        }
    )
```

**Dependencies**:
```bash
pip install docling docling-core
# May require additional dependencies for vision models
```

**Resources**:
- GitHub: https://github.com/DS4SD/docling
- Docs: https://ds4sd.github.io/docling/

---

#### 2. **Unstructured (Layout Mode)** 🔧

**What it is**:
- Enhanced mode of the `unstructured` library (already in use)
- Uses `hi_res` strategy with layout detection
- Identifies document structure via coordinates

**Current Implementation**:
```python
# Currently using basic extraction
from unstructured.partition.pdf import partition_pdf

elements = partition_pdf(
    filename=pdf_path,
    strategy='fast'  # ← Current approach
)
```

**Enhanced Implementation**:
```python
elements = partition_pdf(
    filename=pdf_path,
    strategy='hi_res',  # Use layout analysis
    infer_table_structure=True,  # Extract tables
    include_page_breaks=True,
    extract_images_in_pdf=True,  # For figures
    languages=['eng', 'spa', 'chi_sim'],  # Multi-language support
)

# Group elements by layout region
from unstructured.chunking.title import chunk_by_title

chunks = chunk_by_title(
    elements,
    max_characters=512,
    combine_text_under_n_chars=50,
    new_after_n_chars=480,
)
```

**Advantages**:
- ✅ Already integrated (minimal code changes)
- ✅ Better table extraction
- ✅ Layout-aware chunking
- ✅ Multi-language support

**Implementation Effort**: Low (already using `unstructured`)

---

#### 3. **LangChain Recursive Character Splitter**

**What it is**:
- Hierarchical splitting approach
- Tries to split by sections → paragraphs → sentences → characters
- Preserves semantic boundaries when possible

**Implementation**:
```python
from langchain.text_splitter import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=512,
    chunk_overlap=100,  # Character overlap
    length_function=len,
    separators=[
        "\n\n\n",  # Section breaks
        "\n\n",    # Paragraph breaks
        "\n",      # Line breaks
        ". ",      # Sentence breaks
        " ",       # Word breaks
        ""         # Character breaks
    ]
)

chunks = splitter.create_documents([document_text])
```

**Advantages**:
- ✅ Simple to implement
- ✅ Respects natural boundaries
- ✅ Configurable separators
- ✅ Good for plain text

**Disadvantages**:
- ⚠️ Doesn't understand layout
- ⚠️ May split tables awkwardly
- ⚠️ No visual structure preservation

---

#### 4. **LlamaIndex Sentence Window Retrieval**

**What it is**:
- Stores small chunks (1-2 sentences) but retrieves with surrounding context
- Embeds individual sentences but returns windows

**Implementation**:
```python
from llama_index.node_parser import SentenceWindowNodeParser
from llama_index.indices.postprocessor import MetadataReplacementPostProcessor

# Create small chunks with context window
node_parser = SentenceWindowNodeParser.from_defaults(
    window_size=3,  # 3 sentences before and after
    window_metadata_key="window",
    original_text_metadata_key="original_text",
)

# At retrieval time
postprocessor = MetadataReplacementPostProcessor(
    target_metadata_key="window"  # Replace with full window
)
```

**Advantages**:
- ✅ Precise embedding (single sentences)
- ✅ Rich context at retrieval (windows)
- ✅ Best of both worlds

**Disadvantages**:
- ⚠️ More complex implementation
- ⚠️ Higher storage requirements

---

#### 5. **Semantic Chunking (Embedding-Based)**

**What it is**:
- Uses embeddings to determine semantic similarity
- Splits when semantic shift is detected
- Groups semantically similar sentences

**Implementation**:
```python
from langchain.text_splitter import SemanticChunker
from langchain.embeddings import HuggingFaceEmbeddings

embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

splitter = SemanticChunker(
    embeddings=embeddings,
    breakpoint_threshold_type="percentile",  # or "standard_deviation"
    breakpoint_threshold_amount=95,
)

chunks = splitter.create_documents([document_text])
```

**Advantages**:
- ✅ Semantic coherence guaranteed
- ✅ Adaptive chunk sizes
- ✅ Better topic boundaries

**Disadvantages**:
- ⚠️ Computationally expensive
- ⚠️ Slower processing
- ⚠️ Variable chunk sizes (harder to tune)

---

#### 6. **Proposition-Based Chunking** 🆕

**What it is**:
- Splits text into atomic propositions (facts)
- Each chunk = one or more related facts
- Uses LLM to extract propositions

**Example**:
```
Original: "The United States commits to reducing emissions by 50% by 2030 and 
           achieving net-zero by 2050 through renewable energy investment."

Propositions:
1. "The United States commits to reducing emissions by 50% by 2030"
2. "The United States commits to achieving net-zero by 2050"
3. "Net-zero will be achieved through renewable energy investment"
```

**Implementation**:
```python
from langchain.chains import create_extraction_chain_pydantic
from pydantic import BaseModel

class Proposition(BaseModel):
    fact: str
    entities: list[str]
    
# Use LLM to extract propositions
llm = ChatOpenAI(model="gpt-4")
chain = create_extraction_chain_pydantic(Proposition, llm)

propositions = chain.run(document_text)
```

**Advantages**:
- ✅ Maximum precision
- ✅ Fact-level retrieval
- ✅ Better for complex reasoning

**Disadvantages**:
- ⚠️ Very expensive (LLM calls for all text)
- ⚠️ Slower processing
- ⚠️ Loses surrounding context

---

#### 7. **Late Chunking** 🆕

**What it is**:
- Embed entire document or large sections first
- Then split into chunks while preserving full-context embeddings
- Uses token-level embeddings from full context

**Implementation**:
```python
# Embed full document
full_embedding = embed_model.encode(full_document)

# Then split into chunks, but retain context-aware embeddings
chunks = split_document(full_document, chunk_size=512)

# Each chunk gets embedding from full context position
for chunk in chunks:
    chunk.embedding = extract_contextual_embedding(
        full_embedding,
        chunk.start_pos,
        chunk.end_pos
    )
```

**Advantages**:
- ✅ Embeddings have full document context
- ✅ Better semantic understanding
- ✅ Improves retrieval accuracy

**Disadvantages**:
- ⚠️ Requires models that support token-level embeddings
- ⚠️ More complex implementation
- ⚠️ Higher memory requirements

**Resources**:
- Paper: "Contextual Document Embeddings" (2024)
- Blog: https://jina.ai/news/late-chunking-in-long-context-embedding-models

---

### Evaluation Framework

#### Metrics to Track

1. **Retrieval Metrics**:
   ```python
   # For each chunking strategy, measure:
   - Precision@k (k=1,3,5,10)
   - Recall@k
   - Mean Reciprocal Rank (MRR)
   - NDCG (Normalized Discounted Cumulative Gain)
   ```

2. **Quality Metrics**:
   ```python
   - Answer accuracy (vs. ground truth)
   - Answer completeness (coverage of relevant info)
   - Context relevance (are retrieved chunks useful?)
   - Hallucination rate (incorrect info in answers)
   ```

3. **Efficiency Metrics**:
   ```python
   - Chunking time per document
   - Storage requirements (# of chunks, total size)
   - Embedding time
   - Retrieval latency
   ```

4. **Structural Metrics**:
   ```python
   - Table preservation (% tables kept intact)
   - Multi-column handling (% correctly separated)
   - Figure-caption association (% maintained)
   - Reading order accuracy
   ```

#### Test Dataset

Create a **gold standard evaluation set**:
```python
test_cases = [
    {
        "document": "USA_English_20220601.pdf",
        "query": "What are the USA's emission reduction targets for 2030?",
        "ground_truth_answer": "50% reduction by 2030",
        "ground_truth_chunks": [chunk_ids],  # Known relevant chunks
        "expected_page": 5
    },
    # ... 50-100 test cases covering:
    # - Simple facts
    # - Complex reasoning
    # - Table lookups
    # - Multi-country comparisons
    # - Temporal reasoning
]
```

#### Evaluation Script

```python
# entrypoints/evaluate_chunking.py

def evaluate_chunking_strategy(strategy_name, chunker, test_cases):
    """
    Evaluate a chunking strategy on test cases.
    
    Args:
        strategy_name: Name of the strategy (e.g., "docling", "unstructured_hi_res")
        chunker: Chunking function to evaluate
        test_cases: List of test cases with queries and ground truth
        
    Returns:
        Dictionary of metrics
    """
    results = {
        'strategy': strategy_name,
        'precision_at_3': [],
        'recall_at_3': [],
        'mrr': [],
        'answer_accuracy': [],
        'chunking_time': [],
        'total_chunks': 0,
        'avg_chunk_size': 0
    }
    
    for test_case in test_cases:
        # 1. Chunk the document
        start_time = time.time()
        chunks = chunker(test_case['document'])
        chunking_time = time.time() - start_time
        
        # 2. Embed chunks
        embed_chunks(chunks)
        
        # 3. Retrieve for query
        retrieved = retrieve_similar_chunks(
            query=test_case['query'],
            top_k=5
        )
        
        # 4. Calculate metrics
        precision = calculate_precision(
            retrieved_ids=[c.id for c in retrieved],
            relevant_ids=test_case['ground_truth_chunks']
        )
        
        recall = calculate_recall(
            retrieved_ids=[c.id for c in retrieved],
            relevant_ids=test_case['ground_truth_chunks']
        )
        
        # 5. Generate answer and check accuracy
        answer = generate_answer(test_case['query'], retrieved)
        accuracy = compare_answer(answer, test_case['ground_truth_answer'])
        
        # 6. Store results
        results['precision_at_3'].append(precision)
        results['recall_at_3'].append(recall)
        results['answer_accuracy'].append(accuracy)
        results['chunking_time'].append(chunking_time)
    
    # Aggregate results
    results['avg_precision'] = np.mean(results['precision_at_3'])
    results['avg_recall'] = np.mean(results['recall_at_3'])
    results['avg_accuracy'] = np.mean(results['answer_accuracy'])
    results['avg_chunking_time'] = np.mean(results['chunking_time'])
    
    return results


# Run evaluation
strategies = {
    'current_semantic': semantic_chunker,
    'docling_layout': docling_chunker,
    'unstructured_hi_res': unstructured_hi_res_chunker,
    'langchain_recursive': langchain_recursive_chunker,
    'llamaindex_sentence_window': llamaindex_window_chunker,
    'semantic_embeddings': semantic_embedding_chunker,
}

all_results = {}
for name, chunker in strategies.items():
    print(f"Evaluating {name}...")
    all_results[name] = evaluate_chunking_strategy(name, chunker, test_cases)

# Compare results
create_comparison_table(all_results)
create_performance_plots(all_results)
```

---

### Implementation Plan

#### Phase 1: Setup (Week 1)
- [ ] Create evaluation framework (`entrypoints/evaluate_chunking.py`)
- [ ] Build test dataset (50 query-answer pairs with ground truth)
- [ ] Implement baseline metrics (precision, recall, MRR)
- [ ] Document current performance (semantic sentence-based)

#### Phase 2: Implementation (Weeks 2-3)
- [ ] **Docling**: Implement layout-aware chunking
  - Install dependencies
  - Create `2_chunk_docling.py`
  - Test on 10 documents
  - Measure table/column preservation
  
- [ ] **Unstructured Hi-Res**: Enhance current implementation
  - Switch from `fast` to `hi_res` strategy
  - Enable table structure inference
  - Add layout-based grouping
  
- [ ] **LangChain Recursive**: Implement as alternative
  - Create `2_chunk_langchain.py`
  - Configure separators for policy documents
  - Test on 10 documents
  
- [ ] **LlamaIndex Sentence Window**: Implement if time permits
  - Create `2_chunk_llamaindex.py`
  - Configure window sizes
  - Modify retrieval to use windows

#### Phase 3: Evaluation (Week 4)
- [ ] Run all strategies on full test dataset
- [ ] Collect metrics for each strategy
- [ ] Analyze results:
  - Which strategy has best retrieval accuracy?
  - Which preserves tables/structure best?
  - Which is fastest/most efficient?
  - Are there trade-offs (accuracy vs. speed)?

#### Phase 4: Analysis & Selection (Week 5)
- [ ] Compare results across strategies
- [ ] Consider production requirements:
  - Processing speed
  - Storage costs
  - Maintenance complexity
  - Multi-language support
  - Table/structure handling
- [ ] Select optimal strategy (or hybrid approach)
- [ ] Document decision and rationale

#### Phase 5: Production Implementation (Week 6)
- [ ] Implement chosen strategy
- [ ] Re-process document corpus
- [ ] Validate retrieval improvements
- [ ] Update documentation
- [ ] Deploy to production

---

### Expected Outcomes

#### Success Criteria

1. **Retrieval Improvement**:
   - ≥10% improvement in Precision@3
   - ≥15% improvement in answer accuracy
   - Better handling of table-based queries

2. **Structure Preservation**:
   - >90% of tables kept intact
   - Multi-column documents correctly processed
   - Reading order maintained

3. **Efficiency**:
   - Chunking time <2x current implementation
   - Storage increase <50%

#### Hypothesis

**Expected Best Performers**:
1. **Docling** - For complex policy documents with tables/columns
2. **Unstructured Hi-Res** - Balance of quality and ease of implementation
3. **Current Semantic** - For simple narrative documents

**Likely Trade-offs**:
- Layout-aware strategies will be slower but more accurate
- Semantic strategies will be faster but may miss structural info
- Hybrid approach may be optimal (layout-aware + semantic)

---

### Alternative: Hybrid Approach

Instead of choosing one strategy, consider a **document-type-aware hybrid**:

```python
def chunk_document_hybrid(pdf_path, metadata):
    """
    Choose chunking strategy based on document characteristics.
    """
    # Analyze document
    has_tables = detect_tables(pdf_path)
    is_multi_column = detect_columns(pdf_path)
    language = detect_language(pdf_path)
    
    # Select strategy
    if has_tables or is_multi_column:
        return chunk_with_docling(pdf_path)  # Layout-aware
    elif language not in ['en', 'es', 'fr']:
        return chunk_with_unstructured_multilang(pdf_path)  # Multi-language
    else:
        return chunk_with_semantic(pdf_path)  # Fast semantic
```

---

## 🌍 Priority 2: Multi-Language Support

### Current Issue
The gibberish detector rejects non-Latin scripts (Chinese, Arabic, etc.) as "corrupted".

### Solution Options

#### Option 1: Language Detection + Skip Validation
```python
def is_severely_corrupted(text: str) -> bool:
    # Detect language first
    import langdetect
    try:
        lang = langdetect.detect(text)
        if lang in ['zh-cn', 'zh-tw', 'ar', 'ru', 'ja', 'ko']:
            # For non-Latin scripts, only check for genuine corruption
            return has_cid_corruption(text) or has_unicode_errors(text)
    except:
        pass
    
    # For Latin scripts, use current validation
    return is_latin_text_corrupted(text)
```

#### Option 2: Universal Character Pattern
```python
# Add Unicode ranges for all supported languages
legit_char_pattern = r'[
    a-zA-Z0-9                    # Latin
    \u4e00-\u9fff                # Chinese
    \u0600-\u06ff                # Arabic
    \u0400-\u04ff                # Cyrillic
    \u3040-\u309f\u30a0-\u30ff   # Japanese
    \uac00-\ud7af                # Korean
    àáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ  # European
    \s.,;:!?()\-\'"
]'
```

#### Option 3: Disable for All Languages
Remove gibberish detection entirely and rely on:
- Sentence tokenization (NLTK supports 17 languages)
- Minimum length thresholds
- CID corruption detection only

### Implementation
- [ ] Choose approach (recommend Option 1)
- [ ] Test on Chinese/Arabic documents
- [ ] Verify chunks are preserved
- [ ] Update documentation

---

## 🔧 Priority 3: Technical Improvements

### 3.1 Replace Windows Docker Proxy with Proper Solution

**Current**: `DockerProxyConnection` uses `docker exec` (workaround)

**Options**:
1. Fix PostgreSQL authentication in `pg_hba.conf`
2. Use `host.docker.internal` (Windows Docker Desktop feature)
3. Migrate to cloud database (AWS RDS, Supabase, etc.)

**Recommended**: Option 3 for production readiness

---

### 3.2 Add Embeddings Evaluation

Compare embedding models:
- Current: (check which one is used)
- Alternatives:
  - `all-MiniLM-L6-v2` (fast, 384 dims)
  - `all-mpnet-base-v2` (better quality, 768 dims)
  - `e5-large` (state-of-the-art, 1024 dims)
  - `multilingual-e5-large` (multi-language support)

**Evaluation**:
```python
models = {
    'minilm': 'sentence-transformers/all-MiniLM-L6-v2',
    'mpnet': 'sentence-transformers/all-mpnet-base-v2',
    'e5': 'intfloat/e5-large-v2',
    'multilingual_e5': 'intfloat/multilingual-e5-large'
}

for name, model_name in models.items():
    evaluate_retrieval_with_model(model_name, test_cases)
```

---

### 3.3 Query Rewriting & Expansion

Improve retrieval with query enhancement:

```python
from langchain.chains import LLMChain

# Query rewriting
rewriter = LLMChain(
    llm=ChatOpenAI(),
    prompt="Rewrite this query to be more specific: {query}"
)

# Multi-query expansion
expander = LLMChain(
    llm=ChatOpenAI(),
    prompt="Generate 3 alternative phrasings of: {query}"
)

# Use all queries for retrieval, merge results
original_results = retrieve(original_query)
expanded_results = [retrieve(q) for q in expanded_queries]
merged = merge_and_rerank(original_results + expanded_results)
```

---

### 3.4 Re-ranking Pipeline

Add re-ranker after initial retrieval:

```python
from sentence_transformers import CrossEncoder

# Initial retrieval (fast, gets top 20)
candidates = retrieve_similar_chunks(query, top_k=20)

# Re-ranking (slower but more accurate)
reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
scores = reranker.predict([
    (query, chunk.content) for chunk in candidates
])

# Return top 5 after re-ranking
top_chunks = sorted(
    zip(candidates, scores),
    key=lambda x: x[1],
    reverse=True
)[:5]
```

---

## 📊 Priority 4: Monitoring & Analytics

### 4.1 Query Analytics Dashboard

Track:
- Most common queries
- Failed queries (no good results)
- Retrieval latency
- Answer quality ratings
- User feedback

### 4.2 Document Coverage Analysis

```sql
-- Which countries have the most/least chunks?
SELECT d.country, COUNT(dc.id) as num_chunks
FROM documents d
LEFT JOIN doc_chunks dc ON d.doc_id = dc.doc_id
GROUP BY d.country
ORDER BY num_chunks DESC;

-- Which documents have no chunks? (processing failures)
SELECT country, title, file_path
FROM documents
WHERE processed_at IS NOT NULL
AND doc_id NOT IN (SELECT DISTINCT doc_id FROM doc_chunks);
```

---

## 🎯 Recommended Priority Order

1. **Chunking Evaluation** (4-6 weeks) - Biggest potential impact
2. **Multi-Language Support** (1-2 weeks) - Required for Chinese documents
3. **Docling Implementation** (2 weeks) - Likely best strategy
4. **Embedding Model Comparison** (1 week) - Easy wins
5. **Re-ranking Pipeline** (1 week) - Proven improvement
6. **Production Database** (1 week) - Remove Docker proxy hack

---

**Total Estimated Timeline**: 10-13 weeks for all improvements

**Quick Wins** (can start immediately):
- Multi-language support fix (1 day)
- Unstructured hi_res mode (1 day)
- Add re-ranking (2 days)

---

**Next Action**: Create evaluation test dataset with ground truth queries and answers.

