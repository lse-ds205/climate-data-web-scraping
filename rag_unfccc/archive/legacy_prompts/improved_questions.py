#!/usr/bin/env python3
"""
Improved Predefined Questions for UNFCCC RAG System
Enhanced prompts for better retrieval and analysis.
"""

# Enhanced Question Prompts - More specific and actionable
IMPROVED_QUESTION_PROMPTS = {
    1: """What are the country's specific emissions reduction targets and commitments?

Please extract:
- Exact reduction percentage or absolute amount (e.g., "50% reduction", "1.2 GtCO2e")
- Target years (e.g., 2030, 2035, 2050)
- Whether targets are unconditional or conditional on international support
- Sector coverage (economy-wide vs. specific sectors like energy, transport, industry)
- Greenhouse gases covered (CO2, CH4, N2O, etc.)
- Baseline year or reference scenario used
- Any intermediate targets or milestones mentioned""",

    2: """What baseline year and reference scenarios does the country use for their targets?

Please identify:
- Specific baseline year (e.g., 2005, 2010, 2015)
- Business-as-usual (BAU) projections if used instead of baseline
- Reference scenario assumptions and methodologies
- Emissions levels in baseline year (if quantified)
- Sectors and gases included in baseline calculations
- Any adjustments or recalculations of historical emissions
- Comparison between baseline and projected BAU emissions""",

    3: """How has the country's NDC ambition changed from previous submissions?

Please analyze:
- Specific changes in reduction targets (increased/decreased ambition)
- New sectors or greenhouse gases added to scope
- Changes in baseline years or reference scenarios
- New conditional vs. unconditional commitments
- Additional policies or implementation measures
- Explicit comparisons to previous NDC versions
- Any commitments that were removed or modified""",

    4: """What specific policies, measures, and implementation strategies does the country propose?

Please extract:
- Detailed policy instruments (carbon pricing, regulations, subsidies, standards)
- Sector-specific action plans and roadmaps
- Technology deployment strategies (renewable energy, energy efficiency, EVs)
- Land use and forestry measures (REDD+, reforestation, sustainable agriculture)
- International cooperation mechanisms (carbon markets, technology transfer)
- Implementation timelines and milestones
- Expected emissions reductions from each major policy
- Institutional arrangements and governance structures""",

    5: """Which sectors present the greatest challenges for emissions reduction?

Please identify:
- Sectors explicitly mentioned as difficult to decarbonize
- Heavy industry sectors (cement, steel, chemicals, aluminum)
- Transport sectors requiring breakthrough technologies (aviation, shipping, freight)
- Sectors with limited mitigation potential or high costs
- Sectors requiring international support or technology transfer
- Quantitative analysis of sectoral challenges and costs
- Sectors with highest projected emissions growth
- Barriers and constraints mentioned for specific sectors""",

    6: """What adaptation measures and climate resilience strategies does the country propose?

Please extract:
- Priority adaptation sectors (water, agriculture, health, coastal, infrastructure)
- Specific adaptation projects, programs, and initiatives
- Climate risk assessments and vulnerability analyses
- Adaptation planning frameworks and institutional arrangements
- Estimated costs of adaptation measures (if quantified)
- Funding sources for adaptation (domestic vs. international)
- Integration with national development planning
- Community-based adaptation and indigenous knowledge approaches""",

    7: """What are the country's climate finance needs and funding strategies?

Please analyze:
- Total financial requirements for mitigation and adaptation (if quantified)
- Breakdown between domestic and international financing needs
- Specific funding mechanisms and instruments mentioned
- Project-level or program-level cost estimates
- Innovative financing approaches (green bonds, carbon markets, blended finance)
- Conditional commitments dependent on financial support
- Private sector engagement and investment mobilization
- International climate funds and multilateral development banks""",

    8: """How does the country address climate justice, equity, and fair share considerations?

Please identify:
- References to common but differentiated responsibilities (CBDR)
- Historical emissions and responsibility discussions
- Social justice, gender, and indigenous perspectives
- Just transition strategies for workers and communities
- Vulnerable groups and marginalized communities
- Intergenerational equity considerations
- Human rights and sustainable development integration
- Distributional impacts of climate policies
- Equity in burden-sharing among countries""",

    # NEW ADDITIONAL QUESTIONS
    9: """Does the country have a net-zero emissions or carbon neutrality target?

IMPORTANT: Provide a SHORT, CONCISE answer. Answer with "Yes" or "No" first, then provide a brief 2-3 sentence explanation.

If yes, briefly state:
- Target year (e.g., 2050, 2060)
- Scope (all GHGs or CO2 only)

Keep your response under 150 words total.""",

    10: """What role does the country assign to nature-based solutions and carbon sinks?

Please extract:
- Forest conservation, restoration, and sustainable management
- Agricultural practices and soil carbon sequestration
- Blue carbon and coastal ecosystem protection
- Biodiversity conservation and ecosystem restoration
- Quantified carbon removal potential from nature-based solutions
- Integration with emissions reduction targets
- Implementation strategies and governance
- International cooperation on nature-based solutions""",

    11: """How does the country plan to engage with international carbon markets?

Please analyze:
- Use of Article 6 mechanisms under the Paris Agreement
- International carbon credit trading or purchasing
- Quantified carbon credits needed or available for sale
- Domestic carbon pricing mechanisms (taxes, trading systems)
- Linkage with other countries' carbon markets
- Quality standards and environmental integrity requirements
- Revenue use from carbon market participation
- Capacity building needs for carbon market participation""",

    12: """What technology transfer and capacity building needs does the country identify?

Please identify:
- Specific technologies needed for mitigation and adaptation
- Capacity building requirements by sector
- Technical assistance needs and priorities
- Knowledge sharing and technology cooperation
- Innovation and research development priorities
- Barriers to technology deployment and adoption
- International partnerships for technology transfer
- Domestic technology development strategies"""
}

# Keywords for enhanced retrieval (matching the improved questions)
IMPROVED_HOP_KEYWORDS = {
    1: [
        "emissions reduction", "reduction target", "mitigation target", "climate target",
        "reduce emissions", "decrease emissions", "lower emissions", "cut emissions",
        "% reduction", "percent reduction", "percentage reduction", "reduction by",
        "unconditional", "conditional", "economy-wide", "sectoral", "absolute", "relative",
        "2030 target", "2035 target", "2050 target", "baseline", "reference year"
    ],
    
    2: [
        "baseline year", "reference year", "base year", "business as usual", "BAU",
        "reference scenario", "emissions in", "level in", "from the year", "since",
        "GHG inventory", "national inventory", "emissions inventory", "emissions level",
        "tonnes CO2", "tons CO2", "CO2 equivalent", "CO2eq", "MtCO2e", "GtCO2e"
    ],
    
    3: [
        "previous NDC", "initial NDC", "first NDC", "earlier submission", "prior submission",
        "updated NDC", "enhanced NDC", "revised NDC", "new NDC", "current NDC",
        "increased ambition", "enhanced ambition", "strengthened targets", "more ambitious",
        "compared to previous", "in contrast to", "differs from", "change from", "revision"
    ],
    
    4: [
        "policy measures", "mitigation actions", "mitigation measures", "policy instruments",
        "action plan", "strategy", "strategic plan", "roadmap", "framework", "program",
        "renewable energy", "energy efficiency", "clean energy", "sustainable transport",
        "carbon pricing", "carbon tax", "emissions trading", "cap and trade",
        "reforestation", "afforestation", "REDD+", "land use", "agriculture"
    ],
    
    5: [
        "challenging sectors", "difficult sectors", "hard to abate", "hard-to-abate",
        "barriers", "constraints", "challenges", "heavy industry", "cement", "steel",
        "chemicals", "industrial processes", "freight transport", "aviation", "shipping",
        "international support", "technology transfer", "capacity building"
    ],
    
    6: [
        "adaptation", "climate resilience", "climate-resilient", "resilient development",
        "vulnerability", "vulnerable sectors", "vulnerable communities", "climate risk",
        "water resources", "water management", "agriculture", "food security",
        "coastal protection", "disaster risk", "disaster management", "health impacts"
    ],
    
    7: [
        "climate finance", "financial resources", "financial support", "funding",
        "investment needs", "billion USD", "million USD", "cost estimate",
        "international support", "domestic resources", "private sector", "public finance",
        "green climate fund", "GCF", "adaptation fund", "financial mechanism"
    ],
    
    8: [
        "equity", "equitable", "fair share", "climate justice", "just transition",
        "social justice", "common but differentiated responsibilities", "CBDR",
        "historical responsibility", "historical emissions", "vulnerable groups",
        "indigenous", "gender", "women", "youth", "marginalized communities"
    ],
    
    9: [
        "net-zero", "net zero", "carbon neutrality", "carbon neutral", "zero emissions",
        "climate neutrality", "2050", "2060", "2070", "long-term", "negative emissions",
        "carbon removal", "carbon sinks", "net negative", "target", "ambition", "net zero emissions"
    ],
    
    10: [
        "nature-based solutions", "NbS", "forest conservation", "forest restoration",
        "reforestation", "afforestation", "sustainable forest management", "REDD+",
        "blue carbon", "coastal ecosystems", "biodiversity", "ecosystem restoration",
        "soil carbon", "agricultural practices", "carbon sinks", "natural climate solutions"
    ],
    
    11: [
        "carbon markets", "carbon trading", "carbon credits", "Article 6", "Paris Agreement",
        "international carbon", "carbon pricing", "carbon tax", "emissions trading",
        "cap and trade", "carbon offset", "voluntary carbon", "compliance carbon"
    ],
    
    12: [
        "technology transfer", "capacity building", "technical assistance", "knowledge sharing",
        "technology cooperation", "innovation", "research development", "technology deployment",
        "barriers to technology", "technology adoption", "international partnerships",
        "domestic technology", "technology needs", "technology priorities"
    ]
}

if __name__ == "__main__":
    print("Improved Question Prompts for UNFCCC RAG System")
    print("=" * 50)
    print(f"Total questions: {len(IMPROVED_QUESTION_PROMPTS)}")
    print(f"Enhanced keywords: {len(IMPROVED_HOP_KEYWORDS)}")
    
    print("\nQuestion Topics:")
    for i, prompt in IMPROVED_QUESTION_PROMPTS.items():
        topic = prompt.split('\n')[0].replace('?', '').strip()
        print(f"  {i}. {topic}")
    
    print("\nTo use these improved questions:")
    print("1. Copy the IMPROVED_QUESTION_PROMPTS to your prompts.py file")
    print("2. Update the QUESTION_PROMPTS dictionary in entrypoints/4_retrieve.py")
    print("3. Run tests with: python fixed_retrieval_test.py")



