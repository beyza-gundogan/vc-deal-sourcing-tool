"""
SIC code strategy for finding tech startups on Companies House.

Key insight: Real tech startups almost always register under software/tech
SIC codes (62012, 62020, 63110) regardless of their sector. A fintech
startup registers as a software company, not as a bank. A healthtech
startup registers as software, not as a hospital.

So the strategy is:
  1. Always search the core tech SIC codes
  2. Use sector keywords to filter results by name/description
  3. Use sector-specific SIC codes ONLY for non-tech sectors (e.g. climate)

This gives clean startup results instead of traditional industry incumbents.
"""

# Core tech SIC codes — used for ALL tech startup sectors
TECH_SICS = [
    "62012",  # Business and domestic software development
    "62020",  # Information technology consultancy
    "63110",  # Data processing and hosting
    "62090",  # Other IT service activities
    "72190",  # R&D on natural sciences and engineering
]

# Sector keyword filters — used to narrow results by name after SIC search
# These are words we WANT to see in a company name/description
SECTOR_KEYWORDS = {
    "fintech":      ["pay", "payment", "finance", "financial", "bank", "invest",
                     "lending", "loan", "credit", "money", "wallet", "crypto",
                     "trading", "wealth", "insurance", "mortgage", "capital"],
    "saas":         ["software", "platform", "cloud", "data", "tech", "digital",
                     "app", "system", "solutions", "services", "api"],
    "b2b saas":     ["software", "platform", "cloud", "enterprise", "business",
                     "analytics", "automation", "workflow", "dashboard"],
    "ai":           ["ai", "artificial intelligence", "machine learning", "ml",
                     "data", "automation", "intelligence", "neural", "predict"],
    "healthtech":   ["health", "medical", "clinical", "patient", "care",
                     "pharma", "bio", "diagnostic", "therapy", "wellness"],
    "climate tech": ["energy", "solar", "wind", "carbon", "green", "sustainable",
                     "climate", "renewable", "battery", "electric", "clean"],
    "proptech":     ["property", "real estate", "rental", "letting", "housing",
                     "home", "building", "estate", "resi", "prop"],
    "edtech":       ["education", "learning", "school", "tutor", "student",
                     "training", "course", "teach", "academy", "skills"],
    "legaltech":    ["legal", "law", "contract", "compliance", "regulatory",
                     "governance", "risk", "audit"],
    "insurtech":    ["insurance", "insure", "cover", "risk", "claims",
                     "underwrite", "policy", "protect"],
    "cybersecurity":["security", "cyber", "protect", "threat", "fraud",
                     "identity", "authentication", "privacy", "encrypt"],
}

# Non-tech sectors where sector-specific SIC codes genuinely work better
NON_TECH_SIC_OVERRIDES = {
    "climate tech": [
        "35110",  # Production of electricity
        "35120",  # Transmission of electricity
        "38110",  # Collection of non-hazardous waste
        "71121",  # Engineering design
        "72190",  # R&D natural sciences
        "62012",  # Software (still include)
    ],
    "biotech": [
        "72110",  # R&D on biotechnology
        "21100",  # Manufacture of pharmaceutical products
        "72190",  # Other R&D
        "86900",  # Other human health
    ],
}


def get_sic_codes(sector: str) -> list[str]:
    """Return the best SIC codes to search for a given sector."""
    key = sector.lower().strip()

    # Check non-tech overrides first
    for k, codes in NON_TECH_SIC_OVERRIDES.items():
        if k in key or key in k:
            return codes

    # All other tech sectors: use core tech SICs
    return TECH_SICS


def get_sector_keywords(sector: str) -> list[str]:
    """
    Return name-filter keywords for a sector.
    Used to check if a company name is relevant after SIC search.
    If no keywords defined, no name filtering is applied.
    """
    key = sector.lower().strip()
    if key in SECTOR_KEYWORDS:
        return SECTOR_KEYWORDS[key]
    for k, words in SECTOR_KEYWORDS.items():
        if k in key or key in k:
            return words
    return []  # no filter — return all tech companies
