#!/usr/bin/env python3
"""
Flexible Test Script for LLM Calls with Single/Multiple Questions

This script allows you to easily test LLM responses with multiple questions.
Simply edit the TEST_QUESTIONS and TEST_COUNTRIES lists below to add more tests.

Usage:
    python tests/test_llm_single.py                    # Run all tests
    python tests/test_llm_single.py --question "Your question" --country "Country Name"
    python tests/test_llm_single.py --single           # Test just the first question/country
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

# Add project root to path (go up one level from tests/ directory)
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# ============================================================================
# CONFIGURATION - EDIT THESE TO ADD MORE QUESTIONS/PROMPTS
# ============================================================================

# Import improved questions if available
try:
    from improved_questions import IMPROVED_QUESTION_PROMPTS
    # Use improved prompts if available - automatically uses all questions from improved_questions.py
    # You can customize this dict to test specific questions, or use all of them
    TEST_QUESTIONS = {
        "net_zero": IMPROVED_QUESTION_PROMPTS.get(9, "Does the country have a net-zero target?"),
        "emissions_targets": IMPROVED_QUESTION_PROMPTS.get(1, "What are the country's specific emissions reduction targets and commitments?"),
        "policies": IMPROVED_QUESTION_PROMPTS.get(4, "What specific policies, measures, and implementation strategies does the country propose?"),
        # Add more questions from improved_questions.py as needed:
        # "adaptation": IMPROVED_QUESTION_PROMPTS.get(6, "..."),
        # "finance": IMPROVED_QUESTION_PROMPTS.get(7, "..."),
    }
    print(f"✅ Loaded {len(TEST_QUESTIONS)} questions from improved_questions.py")
except ImportError:
    # Fallback to simple questions if improved_questions.py not available
    TEST_QUESTIONS = {
        "net_zero": "Does the country have a net-zero target?",
        "emissions_targets": "What are the country's emissions reduction targets?",
        "policies": "What policies does the country propose to meet its targets?",
    }
    print("⚠️  Using fallback questions (improved_questions.py not found)")

# Test countries - EDIT THIS LIST TO ADD MORE COUNTRIES
TEST_COUNTRIES = [
    "Australia",
    "Brazil",
    "Barbados",
]

# ============================================================================
# TEST FUNCTIONS
# ============================================================================

def test_llm_response(question: str, country: str) -> Dict[str, Any]:
    """
    Test LLM response for a single question and country.
    
    Args:
        question: The question/prompt text
        country: Country name to filter by
        
    Returns:
        Dictionary with test results including LLM response
    """
    print(f"  Testing: {country}")
    
    try:
        # Import retrieval functions using importlib (handles numeric module names)
        import importlib.util
        
        # Import 4_retrieve module
        retrieve_path = project_root / "entrypoints" / "4_retrieve.py"
        spec_retrieve = importlib.util.spec_from_file_location("retrieve_module", retrieve_path)
        retrieve_module = importlib.util.module_from_spec(spec_retrieve)
        spec_retrieve.loader.exec_module(retrieve_module)
        
        # Step 1: Retrieve chunks
        print(f"    📊 Retrieving chunks...")
        transformer_embedding, word2vec_embedding = retrieve_module.embed_prompt(question)
        
        chunks = retrieve_module.retrieve_chunks(
            embedded_prompts=(transformer_embedding, word2vec_embedding),
            prompt=question,
            top_k=10,
            country=country,
            min_similarity=0.1
        )
        
        if not chunks:
            return {
                "status": "no_chunks",
                "country": country,
                "question": question[:100] + "..." if len(question) > 100 else question,
                "chunks_retrieved": 0,
                "llm_response": None,
                "error": "No chunks found",
                "timestamp": datetime.now().isoformat()
            }
        
        print(f"    ✅ Retrieved {len(chunks)} chunks")
        
        # Step 2: Get LLM response
        print(f"    🤖 Generating LLM response...")
        # Import 5_llm_response module
        llm_path = project_root / "entrypoints" / "5_llm_response.py"
        spec_llm = importlib.util.spec_from_file_location("llm_module", llm_path)
        llm_module = importlib.util.module_from_spec(spec_llm)
        spec_llm.loader.exec_module(llm_module)
        
        setup_llm = llm_module.setup_llm
        get_llm_response = llm_module.get_llm_response
        process_response = llm_module.process_response
        
        try:
            llm_client = setup_llm()
        except Exception as e:
            return {
                "status": "llm_setup_error",
                "country": country,
                "question": question[:100] + "..." if len(question) > 100 else question,
                "chunks_retrieved": len(chunks),
                "llm_response": None,
                "error": f"Failed to setup LLM client: {str(e)}",
                "error_type": "setup_error",
                "timestamp": datetime.now().isoformat()
            }
        
        try:
            llm_response = get_llm_response(
                llm_client=llm_client,
                question=question,
                chunks=chunks
            )
        except Exception as e:
            error_str = str(e).lower()
            error_type = "connection_error" if "connection" in error_str else "api_error"
            
            return {
                "status": "llm_error",
                "country": country,
                "question": question[:100] + "..." if len(question) > 100 else question,
                "chunks_retrieved": len(chunks),
                "llm_response": None,
                "error": str(e),
                "error_type": error_type,
                "timestamp": datetime.now().isoformat()
            }
        
        if not llm_response:
            return {
                "status": "llm_error",
                "country": country,
                "question": question[:100] + "..." if len(question) > 100 else question,
                "chunks_retrieved": len(chunks),
                "llm_response": None,
                "error": "LLM returned no response",
                "error_type": "no_response",
                "timestamp": datetime.now().isoformat()
            }
        
        # Step 3: Process response
        processed_response = process_response(
            llm_response=llm_response,
            original_chunks=chunks,
            question=question
        )
        
        print(f"    ✅ LLM response generated")
        
        # Extract key information from response
        answer_text = ""
        confidence = 0.0
        citations_count = 0
        
        if isinstance(processed_response, dict):
            if 'answer' in processed_response:
                if isinstance(processed_response['answer'], dict):
                    answer_text = processed_response['answer'].get('summary', '')
                else:
                    answer_text = str(processed_response['answer'])
            confidence = processed_response.get('confidence', 0.0)
            citations = processed_response.get('citations', [])
            citations_count = len(citations) if citations else 0
        
        return {
            "status": "success",
            "country": country,
            "question": question[:100] + "..." if len(question) > 100 else question,
            "chunks_retrieved": len(chunks),
            "llm_response": processed_response,
            "answer_preview": answer_text[:200] + "..." if len(answer_text) > 200 else answer_text,
            "confidence": confidence,
            "citations_count": citations_count,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        return {
            "status": "error",
            "country": country,
            "question": question[:100] + "..." if len(question) > 100 else question,
            "chunks_retrieved": 0,
            "llm_response": None,
            "error": str(e),
            "error_details": error_details,
            "timestamp": datetime.now().isoformat()
        }


def run_llm_tests(
    questions: Dict[str, str] = None,
    countries: List[str] = None
) -> List[Dict[str, Any]]:
    """
    Run LLM tests for all question-country combinations.
    
    Args:
        questions: Dictionary of question_name -> question_text
        countries: List of country names
        
    Returns:
        List of test results
    """
    if questions is None:
        questions = TEST_QUESTIONS
    if countries is None:
        countries = TEST_COUNTRIES
    
    print("=" * 70)
    print("LLM RESPONSE TEST")
    print("=" * 70)
    print(f"Questions: {len(questions)}")
    print(f"Countries: {len(countries)}")
    print(f"Total tests: {len(questions) * len(countries)}")
    print("=" * 70)
    
    results = []
    total_tests = len(questions) * len(countries)
    current_test = 0
    
    for question_name, question_text in questions.items():
        print(f"\n📝 Question: {question_name}")
        print(f"   Text: {question_text[:80]}...")
        print("-" * 70)
        
        for country in countries:
            current_test += 1
            print(f"[{current_test}/{total_tests}] ", end="")
            
            result = test_llm_response(question_text, country)
            result['question_name'] = question_name
            results.append(result)
            
            if result['status'] == 'success':
                print(f"  ✅ {result['chunks_retrieved']} chunks, confidence: {result['confidence']:.2f}, citations: {result['citations_count']}")
            else:
                print(f"  ❌ {result['status']}: {result.get('error', 'Unknown error')}")
    
    return results


def save_results(results: List[Dict[str, Any]], output_dir: Path = None):
    """Save test results to JSON and print summary."""
    if output_dir is None:
        output_dir = project_root / "test_data"
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Save full results (including full LLM responses)
    json_file = output_dir / f"llm_test_results_{timestamp}.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    
    # Save summary (without full LLM responses for readability)
    summary = []
    for r in results:
        summary.append({
            "question_name": r.get('question_name'),
            "country": r.get('country'),
            "status": r.get('status'),
            "chunks_retrieved": r.get('chunks_retrieved', 0),
            "confidence": r.get('confidence', 0.0),
            "citations_count": r.get('citations_count', 0),
            "answer_preview": r.get('answer_preview', ''),
            "error": r.get('error'),
        })
    
    summary_file = output_dir / f"llm_test_summary_{timestamp}.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    # Print summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    successful = [r for r in results if r['status'] == 'success']
    print(f"Total tests: {len(results)}")
    print(f"Successful: {len(successful)} ({len(successful)/len(results)*100:.1f}%)")
    print(f"Failed: {len(results) - len(successful)}")
    
    if successful:
        total_chunks = sum(r['chunks_retrieved'] for r in successful)
        avg_chunks = total_chunks / len(successful)
        avg_confidence = sum(r.get('confidence', 0) for r in successful) / len(successful)
        total_citations = sum(r.get('citations_count', 0) for r in successful)
        
        print(f"\nAverage chunks per test: {avg_chunks:.1f}")
        print(f"Average confidence: {avg_confidence:.2f}")
        print(f"Total citations: {total_citations}")
        print(f"Total chunks retrieved: {total_chunks}")
    
    print(f"\n📁 Full results saved to: {json_file}")
    print(f"📁 Summary saved to: {summary_file}")
    print("=" * 70)
    
    return json_file, summary_file


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test LLM responses with single/multiple questions"
    )
    parser.add_argument(
        "--question",
        type=str,
        help="Custom question to test (overrides TEST_QUESTIONS)"
    )
    parser.add_argument(
        "--country",
        type=str,
        help="Single country to test (overrides TEST_COUNTRIES)"
    )
    parser.add_argument(
        "--single",
        action="store_true",
        help="Test just the first question and country"
    )
    
    args = parser.parse_args()
    
    # Determine questions and countries to test
    if args.question:
        # Check if the question is a key in TEST_QUESTIONS (e.g., "net_zero")
        if args.question in TEST_QUESTIONS:
            # Use the question from TEST_QUESTIONS
            questions = {args.question: TEST_QUESTIONS[args.question]}
            print(f"✅ Using question '{args.question}' from TEST_QUESTIONS")
        else:
            # Treat it as a custom question text
            questions = {"custom": args.question}
            print(f"📝 Using custom question text")
    elif args.single:
        questions = {list(TEST_QUESTIONS.keys())[0]: list(TEST_QUESTIONS.values())[0]}
    else:
        questions = TEST_QUESTIONS
    
    if args.country:
        countries = [args.country]
    elif args.single:
        countries = [TEST_COUNTRIES[0]]
    else:
        countries = TEST_COUNTRIES
    
    # Run tests
    results = run_llm_tests(questions, countries)
    
    # Save results
    save_results(results)


if __name__ == "__main__":
    main()

