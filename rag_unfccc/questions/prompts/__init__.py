"""
Prompts Module - Subdirectory

This is a subdirectory for organizing prompts by project.
The actual PromptDefinition classes are in questions/prompts.py (parent directory).
"""

# Re-export from parent module for convenience
# Note: prompts.py is in questions/ (parent), not questions/prompts/
# We need to import from the parent module, not from ourselves
import sys
from pathlib import Path

# Add parent directory to path
parent_dir = Path(__file__).parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

# Import from the parent prompts.py module (not from this __init__.py)
# Use importlib to avoid circular import
import importlib.util
prompts_module_path = parent_dir / "prompts.py"
spec = importlib.util.spec_from_file_location("questions.prompts_module", prompts_module_path)
prompts_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prompts_module)

# Re-export the classes
PromptDefinition = prompts_module.PromptDefinition
PromptMetadata = prompts_module.PromptMetadata
PromptRegistry = prompts_module.PromptRegistry
get_prompt = prompts_module.get_prompt
list_prompts = prompts_module.list_prompts
get_registry = prompts_module.get_registry
register_prompt = prompts_module.register_prompt

# Import and register all prompts
# Shared prompts
from questions.prompts.shared import NET_ZERO_PROMPT

# Project-specific prompts
from questions.prompts.projects.ascor import EP4AI_PROMPT

__all__ = [
    'PromptDefinition',
    'PromptMetadata',
    'PromptRegistry',
    'get_prompt',
    'list_prompts',
    'get_registry',
    'register_prompt',
    'NET_ZERO_PROMPT',
    'EP4AI_PROMPT',
]

