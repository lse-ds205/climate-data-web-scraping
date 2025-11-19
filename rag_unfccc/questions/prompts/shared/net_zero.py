"""
Net Zero Target Prompt

Shared across multiple projects (ASCOR, Banking, CP, CA) with project-specific overrides.
"""

from questions.prompts import PromptDefinition, PromptMetadata

# Base net zero prompt - shared across all projects
NET_ZERO_PROMPT = PromptDefinition(
    id="net_zero_target",
    text="""Does the entity have a net-zero emissions or carbon neutrality target?

IMPORTANT: Provide a SHORT, CONCISE answer. Answer with "Yes" or "No" first, then provide a brief 2-3 sentence explanation.

If yes, briefly state:
- Target year (e.g., 2050, 2060)
- GHG scope (all GHGs or CO2 only)
- Economy scope (e.g., economy-wide, all sectors, specific sectors, etc.)

Keep your response under 150 words total.""",
    metadata=PromptMetadata(
        entity_types=['countries', 'companies', 'banks'],
        projects=['ASCOR', 'Banking', 'CP', 'CA'],
        tpi_centre_ids=['EP4a', 'Banking_NetZero', 'CP_NetZero', 'CA_NetZero'],
        document_types=None,  # Applies to all document types
        created_by="Sylvan",
        created_at="2025-11-17T00:00:00Z",
        version="1.0",
        description="Net zero target identification across all entity types",
        keywords=[
            "net-zero", "net zero", "carbon neutrality", "carbon neutral", "zero emissions",
            "climate neutrality", "2050", "2060", "2070", "long-term", "negative emissions",
            "carbon removal", "carbon sinks", "net negative", "target", "ambition", "net zero emissions"
        ],
        top_k=3  # Use 3 chunks for net zero questions (can be overridden per prompt)
    ),
    entity_specific_text={
        'companies': """Does the company have a net-zero emissions or carbon neutrality target?

IMPORTANT: Provide a SHORT, CONCISE answer. Answer with "Yes" or "No" first, then provide a brief 2-3 sentence explanation.

If yes, briefly state:
- Target year (e.g., 2050, 2060)
- Scope (all GHGs, CO2 only, or specific scopes 1, 2, 3)
- Whether it includes offsetting or only direct reductions

Keep your response under 150 words total.""",
        'banks': """Does the bank have a net-zero emissions or carbon neutrality target?

IMPORTANT: Provide a SHORT, CONCISE answer. Answer with "Yes" or "No" first, then provide a brief 2-3 sentence explanation.

If yes, briefly state:
- Target year (e.g., 2050, 2060)
- Scope (operational emissions, financed emissions, or both)
- Whether it includes portfolio alignment targets

Keep your response under 150 words total.""",
    },
    project_overrides={
        # Banking project might want different keywords
        'Banking': {
            'keywords': [
                "net-zero", "net zero", "carbon neutrality", "carbon neutral", "zero emissions",
                "financed emissions", "portfolio alignment", "operational emissions",
                "2050", "2060", "target", "ambition", "net zero emissions"
            ]
        },
        # CP project might want company-specific wording
        'CP': {
            'keywords': [
                "net-zero", "net zero", "carbon neutrality", "carbon neutral", "zero emissions",
                "scope 1", "scope 2", "scope 3", "GHG emissions", "carbon footprint",
                "2050", "2060", "target", "ambition", "net zero emissions"
            ]
        }
    }
)

