"""SIC code strategy for finding tech startups on Companies House."""

TECH_SICS = ["62012", "62020", "63110", "62090", "72190"]

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

NON_TECH_SIC_OVERRIDES = {
    "climate tech": ["35110", "35120", "38110", "71121", "72190", "62012"],
    "biotech":      ["72110", "21100", "72190", "86900"],
}


def get_sic_codes(sector: str) -> list[str]:
    key = sector.lower().strip()
    for k, codes in NON_TECH_SIC_OVERRIDES.items():
        if k in key or key in k:
            return codes
    return TECH_SICS


def get_sector_keywords(sector: str) -> list[str]:
    key = sector.lower().strip()
    if key in SECTOR_KEYWORDS:
        return SECTOR_KEYWORDS[key]
    for k, words in SECTOR_KEYWORDS.items():
        if k in key or key in k:
            return words
    return []
