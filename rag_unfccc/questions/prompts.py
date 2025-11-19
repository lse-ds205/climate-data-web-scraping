"""
Prompt Definitions and Registry

This module defines the PromptDefinition structure and manages the prompt registry.
Supports versioning, project-specific overrides, and entity-specific customizations.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
import json
from pathlib import Path


@dataclass
class PromptMetadata:
    """Metadata for prompt filtering and organization"""
    entity_types: List[str]  # ['countries', 'companies', 'banks']
    projects: List[str]  # ['ASCOR', 'Banking', 'CP', 'CA']
    tpi_centre_ids: List[str]  # ['EP4a', 'Banking_NetZero', etc.]
    document_types: Optional[List[str]] = None  # ['NDC', 'BTR', 'LTS'] or None for all
    created_by: Optional[str] = None
    created_at: Optional[str] = None
    version: str = "1.0"
    description: str = ""
    keywords: List[str] = field(default_factory=list)  # Keywords for retrieval
    top_k: Optional[int] = None  # Number of chunks to retrieve (None = use system default)
    output_columns: Optional[List[Dict[str, Any]]] = None  # Custom output column definitions
    # Example: [
    #   {'name': 'Year', 'extract': 'year', 'source': 'answer'},
    #   {'name': 'Target_Type', 'extract': 'target_type', 'source': 'answer'},
    #   {'name': 'Scope', 'extract': 'scope', 'source': 'answer'}
    # ]
    # If None, uses default: ['Question', 'Question_text', 'Entity', 'Answer', 'Explanation']


@dataclass
class PromptDefinition:
    """
    Complete prompt definition with support for:
    - Versioning
    - Project-specific overrides
    - Entity-specific customizations
    """
    id: str  # Unique ID: "net_zero_target" or "EP4a_001"
    text: str  # Base prompt text
    metadata: PromptMetadata
    entity_specific_text: Optional[Dict[str, str]] = None  # Entity-specific wording
    # Example: {'companies': 'Does the company have...', 'banks': 'Does the bank have...'}
    project_overrides: Optional[Dict[str, Dict[str, Any]]] = None
    # Example: {'Banking': {'text': 'Banking-specific wording', 'keywords': [...]}}
    version_history: Optional[List[Dict[str, Any]]] = None  # Previous versions
    
    def get_text_for_entity(self, entity_type: str) -> str:
        """Get prompt text customized for specific entity type"""
        if self.entity_specific_text and entity_type in self.entity_specific_text:
            return self.entity_specific_text[entity_type]
        return self.text
    
    def get_text_for_project(self, project: str, entity_type: str) -> str:
        """Get prompt text with project-specific override"""
        if self.project_overrides and project in self.project_overrides:
            override = self.project_overrides[project]
            if 'text' in override:
                # Check for entity-specific override in project
                if isinstance(override['text'], dict) and entity_type in override['text']:
                    return override['text'][entity_type]
                elif isinstance(override['text'], str):
                    return override['text']
        
        # Fall back to entity-specific or base text
        return self.get_text_for_entity(entity_type)
    
    def get_keywords_for_project(self, project: str) -> List[str]:
        """Get keywords with project-specific overrides"""
        if self.project_overrides and project in self.project_overrides:
            override = self.project_overrides[project]
            if 'keywords' in override:
                return override['keywords']
        return self.metadata.keywords
    
    def create_version(self, new_text: Optional[str] = None, 
                      new_keywords: Optional[List[str]] = None,
                      new_metadata: Optional[Dict[str, Any]] = None) -> 'PromptDefinition':
        """Create a new version of this prompt, preserving history"""
        # Save current version to history
        if self.version_history is None:
            self.version_history = []
        
        version_entry = {
            'version': self.metadata.version,
            'text': self.text,
            'keywords': self.metadata.keywords.copy(),
            'metadata': {
                'created_at': self.metadata.created_at,
                'created_by': self.metadata.created_by,
            },
            'archived_at': datetime.now().isoformat()
        }
        self.version_history.append(version_entry)
        
        # Create new version
        new_version = PromptDefinition(
            id=self.id,
            text=new_text if new_text else self.text,
            metadata=PromptMetadata(
                entity_types=self.metadata.entity_types.copy(),
                projects=self.metadata.projects.copy(),
                tpi_centre_ids=self.metadata.tpi_centre_ids.copy(),
                document_types=self.metadata.document_types.copy() if self.metadata.document_types else None,
                created_by=self.metadata.created_by,
                created_at=datetime.now().isoformat(),
                version=self._increment_version(self.metadata.version),
                description=self.metadata.description,
                keywords=new_keywords if new_keywords else self.metadata.keywords.copy()
            ),
            entity_specific_text=self.entity_specific_text.copy() if self.entity_specific_text else None,
            project_overrides=self.project_overrides.copy() if self.project_overrides else None,
            version_history=self.version_history.copy()
        )
        
        # Update metadata if provided
        if new_metadata:
            for key, value in new_metadata.items():
                if hasattr(new_version.metadata, key):
                    setattr(new_version.metadata, key, value)
        
        return new_version
    
    @staticmethod
    def _increment_version(version: str) -> str:
        """Increment version number (e.g., '1.0' -> '1.1', '1.9' -> '2.0')"""
        try:
            parts = version.split('.')
            major = int(parts[0])
            minor = int(parts[1]) if len(parts) > 1 else 0
            
            minor += 1
            if minor >= 10:
                major += 1
                minor = 0
            
            return f"{major}.{minor}"
        except (ValueError, IndexError):
            return "1.0"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'id': self.id,
            'text': self.text,
            'metadata': {
                'entity_types': self.metadata.entity_types,
                'projects': self.metadata.projects,
                'tpi_centre_ids': self.metadata.tpi_centre_ids,
                'document_types': self.metadata.document_types,
                'created_by': self.metadata.created_by,
                'created_at': self.metadata.created_at,
                'version': self.metadata.version,
                'description': self.metadata.description,
                'keywords': self.metadata.keywords,
            },
            'entity_specific_text': self.entity_specific_text,
            'project_overrides': self.project_overrides,
            'version_history': self.version_history,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PromptDefinition':
        """Create from dictionary"""
        metadata = PromptMetadata(**data['metadata'])
        return cls(
            id=data['id'],
            text=data['text'],
            metadata=metadata,
            entity_specific_text=data.get('entity_specific_text'),
            project_overrides=data.get('project_overrides'),
            version_history=data.get('version_history'),
        )


class PromptRegistry:
    """
    Central registry for all prompts.
    Manages prompt lookup, versioning, and project-specific overrides.
    """
    
    def __init__(self):
        self._prompts: Dict[str, PromptDefinition] = {}
        self._prompts_by_project: Dict[str, List[str]] = {}  # project -> [prompt_ids]
        self._prompts_by_tpi_centre: Dict[str, List[str]] = {}  # tpi_centre_id -> [prompt_ids]
    
    def register(self, prompt: PromptDefinition):
        """Register a prompt in the registry"""
        self._prompts[prompt.id] = prompt
        
        # Index by project
        for project in prompt.metadata.projects:
            if project not in self._prompts_by_project:
                self._prompts_by_project[project] = []
            if prompt.id not in self._prompts_by_project[project]:
                self._prompts_by_project[project].append(prompt.id)
        
        # Index by TPI Centre ID
        for tpi_centre_id in prompt.metadata.tpi_centre_ids:
            if tpi_centre_id not in self._prompts_by_tpi_centre:
                self._prompts_by_tpi_centre[tpi_centre_id] = []
            if prompt.id not in self._prompts_by_tpi_centre[tpi_centre_id]:
                self._prompts_by_tpi_centre[tpi_centre_id].append(prompt.id)
    
    def get(self, prompt_id: str, version: Optional[str] = None) -> Optional[PromptDefinition]:
        """Get a prompt by ID, optionally by version"""
        prompt = self._prompts.get(prompt_id)
        if not prompt:
            return None
        
        if version and prompt.metadata.version != version:
            # Look in version history
            if prompt.version_history:
                for hist_entry in prompt.version_history:
                    if hist_entry['version'] == version:
                        # Reconstruct old version
                        old_metadata = PromptMetadata(**hist_entry['metadata'])
                        old_metadata.version = version
                        old_metadata.keywords = hist_entry['keywords']
                        return PromptDefinition(
                            id=prompt.id,
                            text=hist_entry['text'],
                            metadata=old_metadata,
                            entity_specific_text=prompt.entity_specific_text,
                            project_overrides=prompt.project_overrides,
                            version_history=prompt.version_history
                        )
        
        return prompt
    
    def get_by_project(self, project: str) -> List[PromptDefinition]:
        """Get all prompts for a project"""
        prompt_ids = self._prompts_by_project.get(project, [])
        return [self._prompts[pid] for pid in prompt_ids if pid in self._prompts]
    
    def get_by_tpi_centre(self, tpi_centre_id: str) -> List[PromptDefinition]:
        """Get all prompts for a TPI Centre ID"""
        prompt_ids = self._prompts_by_tpi_centre.get(tpi_centre_id, [])
        return [self._prompts[pid] for pid in prompt_ids if pid in self._prompts]
    
    def list_all(self) -> List[PromptDefinition]:
        """List all registered prompts"""
        return list(self._prompts.values())
    
    def update_prompt(self, prompt_id: str, **updates) -> Optional[PromptDefinition]:
        """Update a prompt (creates new version)"""
        prompt = self.get(prompt_id)
        if not prompt:
            return None
        
        new_prompt = prompt.create_version(
            new_text=updates.get('text'),
            new_keywords=updates.get('keywords'),
            new_metadata=updates.get('metadata')
        )
        
        self.register(new_prompt)
        return new_prompt


# Global registry instance
_registry = PromptRegistry()


def register_prompt(prompt: PromptDefinition):
    """Register a prompt in the global registry"""
    _registry.register(prompt)


def get_prompt(prompt_id: str, version: Optional[str] = None) -> Optional[PromptDefinition]:
    """Get a prompt by ID"""
    return _registry.get(prompt_id, version)


def list_prompts(project: Optional[str] = None, 
                tpi_centre_id: Optional[str] = None) -> List[PromptDefinition]:
    """List prompts, optionally filtered by project or TPI Centre ID"""
    if project:
        return _registry.get_by_project(project)
    elif tpi_centre_id:
        return _registry.get_by_tpi_centre(tpi_centre_id)
    else:
        return _registry.list_all()


def get_registry() -> PromptRegistry:
    """Get the global registry instance"""
    return _registry

