#!/usr/bin/env python3
"""
Flexible Test Script for Retrieval with Improved Prompts

This script allows you to easily test retrieval with multiple questions and prompts.
Simply edit the TEST_QUESTIONS and TEST_COUNTRIES lists below to add more tests.

Usage:
    python tests/test_retrieval.py                    # Run all tests
    python tests/test_retrieval.py --question "Your question here" --country "Country Name"
    python tests/test_retrieval.py --single           # Test just the first question/country
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
    # Use improved prompts if available
    TEST_QUESTIONS = {
        "net_zero": IMPROVED_QUESTION_PROMPTS.get(9, "Does the country have a net-zero target?"),
        "emissions_targets": IMPROVED_QUESTION_PROMPTS.get(1, "What are the country's specific emissions reduction targets and commitments?"),
        "policies": IMPROVED_QUESTION_PROMPTS.get(4, "What specific policies, measures, and implementation strategies does the country propose?"),
        "adaptation": IMPROVED_QUESTION_PROMPTS.get(6, "What adaptation measures and climate resilience strategies does the country propose?"),
        "finance": IMPROVED_QUESTION_PROMPTS.get(7, "What are the country's climate finance needs and funding strategies?"),
    }
except ImportError:
    # Fallback to simple questions if improved_questions.py not available
    TEST_QUESTIONS = {
        "net_zero": "Does the country have a net-zero target?",
        "emissions_targets": "What are the country's emissions reduction targets?",
        "policies": "What policies does the country propose to meet its targets?",
        "adaptation": "What adaptation measures does the country propose?",
        "finance": "What are the country's climate finance needs?",
    }

# Test countries - EDIT THIS LIST TO ADD MORE COUNTRIES
TEST_COUNTRIES = [
    "Australia",
    "Brazil",
    "Barbados",
    "Sri Lanka",
    "Uruguay",
    "Costa Rica",
    "Dominican Republic",
    "Ecuador",
]

# ============================================================================
# TEST FUNCTIONS
# ============================================================================

def test_retrieval(question: str, country: str, use_hop: bool = False) -> Dict[str, Any]:
    """
    Test retrieval for a single question and country.
    
    Args:
        question: The question/prompt text
        country: Country name to filter by
        use_hop: Whether to use hop retrieval
        
    Returns:
        Dictionary with test results
    """
    print(f"  Testing: {country}")
    
    try:
        # Import retrieval functions using importlib (handles numeric module names)
        import importlib.util
        retrieve_path = project_root / "entrypoints" / "4_retrieve.py"
        spec = importlib.util.spec_from_file_location("retrieve_module", retrieve_path)
        retrieve_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(retrieve_module)
        
        # Run retrieval using the run_script function
        chunks = retrieve_module.run_script(
            question=question,
            country=country,
            use_hop_retrieval=use_hop
        )
        
        # Load results from JSON file
        retrieve_dir = project_root / "data" / "retrieve"
        country_file = retrieve_dir / f"{country}.json"
        
        if country_file.exists():
            with open(country_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Find the question in the results
            questions_data = data.get('questions', {})
            question_data = None
            
            # Try to find matching question
            for q_key, q_data in questions_data.items():
                q_text = q_data.get('question', '')
                # Check if question text matches (allowing for partial matches)
                if question[:50].lower() in q_text.lower() or q_text[:50].lower() in question.lower():
                    question_data = q_data
                    break
            
            # If not found, use first available
            if not question_data and questions_data:
                question_data = list(questions_data.values())[0]
            
            if question_data:
                chunks_retrieved = question_data.get('chunk_count', 0)
                top_chunks = question_data.get('top_k_chunks', [])
                
                # Calculate statistics (use combined_score if available, fallback to similarity_score)
                if top_chunks:
                    # Prefer combined_score as it includes all evaluation methods
                    top_similarity = top_chunks[0].get('combined_score') or top_chunks[0].get('similarity_score', 0)
                    avg_similarity = sum(
                        (c.get('combined_score') or c.get('similarity_score', 0)) 
                        for c in top_chunks
                    ) / len(top_chunks)
                else:
                    top_similarity = 0
                    avg_similarity = 0
                
                return {
                    "status": "success",
                    "country": country,
                    "question": question[:100] + "..." if len(question) > 100 else question,
                    "chunks_retrieved": chunks_retrieved,
                    "top_similarity": top_similarity,
                    "avg_similarity": avg_similarity,
                    "file_path": str(country_file),
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "status": "no_question_found",
                    "country": country,
                    "question": question[:100] + "..." if len(question) > 100 else question,
                    "chunks_retrieved": 0,
                    "error": "Question not found in results",
                    "timestamp": datetime.now().isoformat()
                }
        else:
            return {
                "status": "no_file",
                "country": country,
                "question": question[:100] + "..." if len(question) > 100 else question,
                "chunks_retrieved": 0,
                "error": f"File not found: {country_file}",
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        return {
            "status": "error",
            "country": country,
            "question": question[:100] + "..." if len(question) > 100 else question,
            "chunks_retrieved": 0,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


def run_retrieval_tests(
    questions: Dict[str, str] = None,
    countries: List[str] = None,
    use_hop: bool = False
) -> List[Dict[str, Any]]:
    """
    Run retrieval tests for all question-country combinations.
    
    Args:
        questions: Dictionary of question_name -> question_text
        countries: List of country names
        use_hop: Whether to use hop retrieval
        
    Returns:
        List of test results
    """
    if questions is None:
        questions = TEST_QUESTIONS
    if countries is None:
        countries = TEST_COUNTRIES
    
    print("=" * 70)
    print("RETRIEVAL TEST WITH IMPROVED PROMPTS")
    print("=" * 70)
    print(f"Questions: {len(questions)}")
    print(f"Countries: {len(countries)}")
    print(f"Total tests: {len(questions) * len(countries)}")
    print(f"Hop retrieval: {'Enabled' if use_hop else 'Disabled'}")
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
            
            result = test_retrieval(question_text, country, use_hop)
            result['question_name'] = question_name
            results.append(result)
            
            if result['status'] == 'success':
                print(f"  ✅ {result['chunks_retrieved']} chunks (top similarity: {result['top_similarity']:.3f})")
            else:
                print(f"  ❌ {result['status']}: {result.get('error', 'Unknown error')}")
    
    return results


def save_results(results: List[Dict[str, Any]], output_dir: Path = None):
    """Save test results to JSON and print summary."""
    if output_dir is None:
        output_dir = project_root / "test_data"
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Save full results
    json_file = output_dir / f"retrieval_test_results_{timestamp}.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
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
        avg_similarity = sum(r.get('top_similarity', 0) for r in successful) / len(successful)
        
        print(f"\nAverage chunks per test: {avg_chunks:.1f}")
        print(f"Average top similarity: {avg_similarity:.3f}")
        print(f"Total chunks retrieved: {total_chunks}")
    
    print(f"\n📁 Full results saved to: {json_file}")
    print("=" * 70)
    
    return json_file


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test retrieval with improved prompts"
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
        "--hop",
        action="store_true",
        help="Use hop retrieval"
    )
    parser.add_argument(
        "--single",
        action="store_true",
        help="Test just the first question and country"
    )
    
    args = parser.parse_args()
    
    # Determine questions and countries to test
    if args.question:
        questions = {"custom": args.question}
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
    results = run_retrieval_tests(questions, countries, use_hop=args.hop)
    
    # Save results
    save_results(results)


if __name__ == "__main__":
    main()

