"""
EP4ai Prompt for ASCOR Project

Asks: In what year is the net zero CO₂ target set?
"""

from questions.prompts import PromptDefinition, PromptMetadata, register_prompt

EP4AI_PROMPT = PromptDefinition(
    id="ep4ai",
    text="""In what year is the net zero or net negative target set?

IMPORTANT: Your answer must be structured as follows:

FIRST LINE: Provide ONLY the year (e.g., "2050", "2060", "2070") or "No data" if no target is found.

THEN: Provide a brief 1-2 sentence explanation with context about the target.

Target types to consider:
- Net zero CO₂ targets
- Net zero GHG (all greenhouse gases) targets
- Net negative CO₂ or GHG targets
- Carbon neutrality targets

All of these are valid targets for this question, as they are inclusive of CO₂ targets.

Answer format example:
"2050
The country has committed to achieving net zero emissions of all greenhouse gases by 2050, which includes CO₂ and other GHGs."

Or if no target:
"No data
No net zero or net negative target was found in the available documents."

Keep your response under 150 words total.""",
    metadata=PromptMetadata(
        entity_types=['countries'],
        projects=['ASCOR'],
        tpi_centre_ids=['EP4ai'],
        document_types=None,  # Applies to all document types
        created_by="Sylvan",
        created_at="2025-11-18T00:00:00Z",
        version="1.0",
        description="Net zero or net negative target year identification for countries (CO₂ or GHG)",
        keywords=[
            "net zero", "net-zero", "net negative", "carbon neutrality", "zero emissions",
            "CO2", "CO₂", "carbon dioxide", "GHG", "greenhouse gas", "greenhouse gases",
            "target year", "2050", "2060", "2070", "long-term", "target", "ambition",
            "net zero CO2", "net zero CO₂", "net zero emissions", "carbon neutral"
        ],
        top_k=3
    )
)

# Auto-register the prompt
register_prompt(EP4AI_PROMPT)

