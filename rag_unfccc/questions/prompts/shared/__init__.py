"""
Shared Prompts

Prompts that are shared across multiple projects.
These can be used by any project, with project-specific overrides if needed.
"""

from questions.prompts import PromptDefinition, PromptMetadata, register_prompt

# Import shared prompts
from questions.prompts.shared.net_zero import NET_ZERO_PROMPT

# Register all shared prompts
__all__ = ['NET_ZERO_PROMPT']

# Auto-register on import
register_prompt(NET_ZERO_PROMPT)

