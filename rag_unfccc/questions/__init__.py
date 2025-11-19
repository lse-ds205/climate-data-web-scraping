"""
Questions Module - Prompt Management System

This module provides a flexible prompt system organized by project, with support for:
- Project-based organization (primary dimension)
- Shared prompts across projects
- Project-specific overrides
- Prompt versioning
- TPI Centre ID mappings
- Metadata filtering
"""

from typing import Dict, List, Optional, Any
from pathlib import Path

# Import project configurations
from questions.projects import PROJECTS, get_project_config, get_entity_type_for_project
from questions.tpi_centres import (
    TPI_CENTRE_MAPPINGS, 
    get_prompts_for_tpi_centre,
    get_tpi_centre_mapping,
    get_project_for_tpi_centre,
    list_tpi_centres,
    is_valid_tpi_centre
)

# Import from prompts.py directly (the file, not the directory)
# This avoids circular import with questions/prompts/__init__.py
import questions.prompts as prompts_module
PromptDefinition = prompts_module.PromptDefinition
PromptMetadata = prompts_module.PromptMetadata
PromptRegistry = prompts_module.PromptRegistry
get_prompt = prompts_module.get_prompt
list_prompts = prompts_module.list_prompts
get_registry = prompts_module.get_registry
register_prompt = prompts_module.register_prompt

from questions.filters import DocumentFilter, apply_filters

# Import and register prompts (this will trigger registration)
try:
    from questions.prompts.shared import NET_ZERO_PROMPT
except ImportError:
    pass  # Prompts will be registered when imported

__all__ = [
    'PROJECTS',
    'TPI_CENTRE_MAPPINGS',
    'PromptDefinition',
    'PromptMetadata',
    'PromptRegistry',
    'get_project_config',
    'get_entity_type_for_project',
    'get_tpi_centre_mapping',
    'get_prompts_for_tpi_centre',
    'get_project_for_tpi_centre',
    'list_tpi_centres',
    'is_valid_tpi_centre',
    'get_prompt',
    'list_prompts',
    'get_registry',
    'register_prompt',
    'DocumentFilter',
    'apply_filters',
]

# Module version
__version__ = "1.0.0"

