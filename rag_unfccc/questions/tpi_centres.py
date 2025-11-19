"""
TPI Centre ID Mappings

Maps TPI Centre IDs to prompts and projects.
Multiple TPI Centre IDs can map to the same prompt (for different projects), 
but each TPI Centre ID maps to exactly one prompt.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class TPICentreMapping:
    """Mapping of TPI Centre ID to prompts and metadata"""
    tpi_centre_id: str
    project: str  # Primary project this TPI Centre belongs to
    prompt_ids: List[str]  # List of prompt IDs (references to prompts in registry)
    entity_types: List[str]  # Entity types this applies to
    description: str


# TPI Centre ID Mappings
TPI_CENTRE_MAPPINGS: Dict[str, TPICentreMapping] = {
    # ASCOR Project TPI Centres
    'EP4a': TPICentreMapping(
        tpi_centre_id='EP4a',
        project='ASCOR',
        prompt_ids=['net_zero_target'],  # Will be registered in prompt files
        entity_types=['countries'],
        description='Net zero target for countries (ASCOR)'
    ),
    
    'EP4ai': TPICentreMapping(
        tpi_centre_id='EP4ai',
        project='ASCOR',
        prompt_ids=['ep4ai'],
        entity_types=['countries'],
        description='Net zero CO₂ target year for countries (ASCOR)'
    ),
    
    # Banking Project TPI Centres
    'Banking_NetZero': TPICentreMapping(
        tpi_centre_id='Banking_NetZero',
        project='Banking',
        prompt_ids=['net_zero_target'],  # Same prompt, different project context
        entity_types=['banks'],
        description='Net zero target for banking sector'
    ),
    
    'Banking_Disclosure': TPICentreMapping(
        tpi_centre_id='Banking_Disclosure',
        project='Banking',
        prompt_ids=['climate_disclosure'],  # Example - to be defined
        entity_types=['banks'],
        description='Climate disclosure requirements for banks'
    ),
    
    # CP Project TPI Centres
    'CP_NetZero': TPICentreMapping(
        tpi_centre_id='CP_NetZero',
        project='CP',
        prompt_ids=['net_zero_target'],
        entity_types=['companies'],
        description='Net zero target for companies (CP)'
    ),
    
    # CA Project TPI Centres
    'CA_NetZero': TPICentreMapping(
        tpi_centre_id='CA_NetZero',
        project='CA',
        prompt_ids=['net_zero_target'],
        entity_types=['companies'],
        description='Net zero target for companies (CA)'
    ),
}


def get_tpi_centre_mapping(tpi_centre_id: str) -> Optional[TPICentreMapping]:
    """Get mapping for a TPI Centre ID"""
    return TPI_CENTRE_MAPPINGS.get(tpi_centre_id)


def get_prompts_for_tpi_centre(tpi_centre_id: str) -> List[str]:
    """Get prompt IDs for a TPI Centre ID"""
    mapping = get_tpi_centre_mapping(tpi_centre_id)
    return mapping.prompt_ids.copy() if mapping else []


def get_project_for_tpi_centre(tpi_centre_id: str) -> Optional[str]:
    """Get the project for a TPI Centre ID"""
    mapping = get_tpi_centre_mapping(tpi_centre_id)
    return mapping.project if mapping else None


def list_tpi_centres(project: Optional[str] = None) -> List[str]:
    """List TPI Centre IDs, optionally filtered by project"""
    if project:
        return [
            tpi_id for tpi_id, mapping in TPI_CENTRE_MAPPINGS.items()
            if mapping.project.upper() == project.upper()
        ]
    return list(TPI_CENTRE_MAPPINGS.keys())


def is_valid_tpi_centre(tpi_centre_id: str) -> bool:
    """Check if a TPI Centre ID is valid"""
    return tpi_centre_id in TPI_CENTRE_MAPPINGS


if __name__ == "__main__":
    print("TPI Centre ID Mappings")
    print("=" * 50)
    for tpi_id, mapping in TPI_CENTRE_MAPPINGS.items():
        print(f"\nTPI Centre ID: {tpi_id}")
        print(f"  Project: {mapping.project}")
        print(f"  Description: {mapping.description}")
        print(f"  Entity Types: {', '.join(mapping.entity_types)}")
        print(f"  Prompt IDs: {', '.join(mapping.prompt_ids)}")

