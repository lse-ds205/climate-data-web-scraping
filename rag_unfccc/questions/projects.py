"""
Project Configuration

Defines all projects (ASCOR, Banking, CP, CA) and their configurations.
Projects are the PRIMARY organizational dimension.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class ProjectConfig:
    """Configuration for a project"""
    name: str
    entity_type: str  # 'countries', 'companies', 'banks'
    description: str
    tpi_centre_ids: List[str]  # TPI Centre IDs associated with this project
    document_types: List[str]  # Standard document types for this project
    # Examples: ['NDC', 'BTR', 'LTS'] for ASCOR, ['Sustainability Report', 'Annual Report'] for Banking


# Project Definitions
PROJECTS: Dict[str, ProjectConfig] = {
    'ASCOR': ProjectConfig(
        name='ASCOR Project',
        entity_type='countries',
        description='ASCOR research framework for country-level analysis',
        tpi_centre_ids=['EP4a', 'EP4ai', 'EP4b', 'EP4c'],  # Add more as needed
        document_types=['NDC', 'BTR', 'LTS', 'Law', 'Policy']  # Standard document types
    ),
    'Banking': ProjectConfig(
        name='Banking Project',
        entity_type='banks',
        description='Banking sector analysis and research',
        tpi_centre_ids=['Banking_NetZero', 'Banking_Disclosure', 'Banking_Financing'],
        document_types=['Sustainability Report', 'Annual Report', 'Climate Report', 'TCFD Report']
    ),
    'CP': ProjectConfig(
        name='CP Project',
        entity_type='companies',
        description='CP research framework for company-level analysis',
        tpi_centre_ids=['CP_NetZero', 'CP_Disclosure', 'CP_Transition'],
        document_types=['Sustainability Report', 'Annual Report', 'CDP Response', 'ESG Report']
    ),
    'CA': ProjectConfig(
        name='CA Project',
        entity_type='companies',
        description='CA research framework for company-level analysis',
        tpi_centre_ids=['CA_NetZero', 'CA_Disclosure', 'CA_Transition'],
        document_types=['Sustainability Report', 'Annual Report', 'CDP Response', 'ESG Report']
    ),
}


def get_project_config(project: str) -> Optional[ProjectConfig]:
    """Get configuration for a project"""
    return PROJECTS.get(project.upper())


def get_entity_type_for_project(project: str) -> Optional[str]:
    """Get the entity type for a project"""
    config = get_project_config(project)
    return config.entity_type if config else None


def list_projects() -> List[str]:
    """List all available projects"""
    return list(PROJECTS.keys())


def get_document_types_for_project(project: str) -> List[str]:
    """Get standard document types for a project"""
    config = get_project_config(project)
    return config.document_types.copy() if config else []


def is_valid_project(project: str) -> bool:
    """Check if a project name is valid"""
    return project.upper() in PROJECTS


def get_tpi_centres_for_project(project: str) -> List[str]:
    """Get TPI Centre IDs for a project"""
    config = get_project_config(project)
    return config.tpi_centre_ids.copy() if config else []


if __name__ == "__main__":
    print("Project Configuration")
    print("=" * 50)
    for project_id, config in PROJECTS.items():
        print(f"\nProject: {project_id}")
        print(f"  Name: {config.name}")
        print(f"  Entity Type: {config.entity_type}")
        print(f"  Description: {config.description}")
        print(f"  TPI Centre IDs: {', '.join(config.tpi_centre_ids)}")
        print(f"  Document Types: {', '.join(config.document_types)}")

