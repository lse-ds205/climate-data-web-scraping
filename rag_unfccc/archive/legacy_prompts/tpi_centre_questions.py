#!/usr/bin/env python3
"""
TPI Centre ID Question Mapping System
Maps TPI Centre IDs to questions and applicable entity types.

This allows flexible question management based on TPI Centre research needs.
"""

from typing import Dict, List, Optional
from improved_questions import IMPROVED_QUESTION_PROMPTS

# TPI Centre ID to Question Mapping
# Format: TPI_CENTRE_ID: {
#     'question_ids': [list of question IDs from improved_questions.py],
#     'entity_types': ['countries', 'companies', 'banks'],  # Which entity types this applies to
#     'description': 'Description of the research focus'
# }
#
# Note: Question IDs map to improved_questions.py
# Question 9 = "Does the country have a net-zero or carbon neutrality target?"

TPI_CENTRE_QUESTIONS = {
    # EP4a: Net Zero Target for Countries
    'EP4a': {
        'question_ids': [9],  # Net zero question (question 9)
        'entity_types': ['countries'],
        'description': 'Does the entity have a net zero target? (Countries only)'
    },
    
    # Example: Net Zero Research Centre (legacy name, kept for compatibility)
    'net_zero_centre': {
        'question_ids': [9, 1, 2],  # Net zero, emissions targets, baseline
        'entity_types': ['countries', 'companies'],
        'description': 'Net zero commitments and emissions targets'
    },
    
    # Example: Adaptation Research Centre
    'adaptation_centre': {
        'question_ids': [6, 7],  # Adaptation measures, climate finance
        'entity_types': ['countries'],
        'description': 'Adaptation and climate resilience strategies'
    },
    
    # Example: Carbon Markets Research Centre
    'carbon_markets_centre': {
        'question_ids': [11, 1, 2],  # Carbon markets, emissions targets
        'entity_types': ['countries', 'companies'],
        'description': 'Carbon market engagement and emissions trading'
    },
    
    # Example: Nature-Based Solutions Centre
    'nature_solutions_centre': {
        'question_ids': [10, 9],  # Nature-based solutions, net zero
        'entity_types': ['countries'],
        'description': 'Nature-based solutions and carbon sinks'
    },
    
    # Example: Technology Transfer Centre
    'technology_centre': {
        'question_ids': [12, 4],  # Technology transfer, policies
        'entity_types': ['countries'],
        'description': 'Technology transfer and capacity building'
    },
    
    # Example: Climate Justice Centre
    'justice_centre': {
        'question_ids': [8, 6],  # Climate justice, adaptation
        'entity_types': ['countries'],
        'description': 'Climate justice and equity considerations'
    },
    
    # Default: All questions for all entity types
    'all': {
        'question_ids': list(IMPROVED_QUESTION_PROMPTS.keys()),
        'entity_types': ['countries', 'companies', 'banks'],
        'description': 'All questions for comprehensive analysis'
    }
}


def get_questions_for_centre(centre_id: str) -> Dict[str, any]:
    """
    Get question configuration for a TPI Centre ID.
    
    Args:
        centre_id: TPI Centre ID (e.g., 'net_zero_centre')
        
    Returns:
        Dictionary with 'question_ids', 'entity_types', 'description'
        
    Raises:
        ValueError: If centre_id is not found
    """
    if centre_id not in TPI_CENTRE_QUESTIONS:
        available = ', '.join(TPI_CENTRE_QUESTIONS.keys())
        raise ValueError(
            f"TPI Centre ID '{centre_id}' not found. "
            f"Available IDs: {available}"
        )
    
    return TPI_CENTRE_QUESTIONS[centre_id]


def list_available_centres() -> List[str]:
    """List all available TPI Centre IDs."""
    return list(TPI_CENTRE_QUESTIONS.keys())


def get_question_texts_for_centre(centre_id: str) -> Dict[int, str]:
    """
    Get question texts for a TPI Centre ID.
    
    Args:
        centre_id: TPI Centre ID
        
    Returns:
        Dictionary mapping question IDs to question texts
    """
    config = get_questions_for_centre(centre_id)
    question_ids = config['question_ids']
    
    return {
        qid: IMPROVED_QUESTION_PROMPTS[qid]
        for qid in question_ids
        if qid in IMPROVED_QUESTION_PROMPTS
    }


if __name__ == "__main__":
    print("TPI Centre Question Mapping System")
    print("=" * 50)
    print(f"Available Centres: {len(TPI_CENTRE_QUESTIONS)}")
    print()
    
    for centre_id, config in TPI_CENTRE_QUESTIONS.items():
        print(f"Centre ID: {centre_id}")
        print(f"  Description: {config['description']}")
        print(f"  Questions: {len(config['question_ids'])} questions")
        print(f"  Entity Types: {', '.join(config['entity_types'])}")
        print()

