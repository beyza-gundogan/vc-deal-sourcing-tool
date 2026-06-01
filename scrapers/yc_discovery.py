"""
YC Company Discovery Layer
Uses the yc-oss public API — free, no key, updated daily.
Source: https://github.com/yc-oss/api

Fetches all 5,800+ YC companies and filters by:
- Sector / tag / keyword
- Batch recency (recent batches = earlier stage)
- Active status
- Region (optional)

This replaces Companies House as the DISCOVERY layer.
Companies House is still used for ENRICHMENT of UK companies.
"""

import json
import time
import requests
from datetime import datetime

# API endpoints — all free, no key needed
YC_API_BASE   = "https://yc-oss.github.io/api"
ALL_COMPANIES = f"{YC_API_BASE}/companies/all.json"
HIRING_NOW    = f"{YC_API_BASE}/companies/hiring.json"
TOP_COMPANIES = f"{YC_API_BASE}/companies/top.json"

# Recent batches — companies still at VC-stage (last ~4 years)
# The API uses full batch names e.g. "Winter 2025", "Spring 2026"
RECENT_BATCHES = {
    "Spring 2026", "Winter 2026", "Fall 2025", "Summer 2025", "Spring 2025",
    "Winter 2025", "Fall 2024", "Summer 2024", "Winter 2024",
    "Summer 2023", "Winter 2023", "Summer 2022", "Winter 2022",
    "Summer 2021", "Winter 2021",
}

# YC tag → sector keyword mapping
SECTOR_TAG_MAP = {
    "fintech":      ["fintech", "finance", "payments", "banking", "insurance",
                     "crypto", "defi", "lending", "wealth management", "neobank"],
    "b2b saas":     ["b2b", "saas", "enterprise software", "productivity",
                     "workflow", "analytics", "crm", "erp", "devtools"],
    "ai":           ["ai", "machine learning", "generative ai", "llm",
                     "computer vision", "nlp", "ai assistant", "ml"],
    "healthtech":   ["health tech", "healthcare", "medical", "biotech",
                     "mental health", "diagnostics", "clinical", "pharma"],
    "climate tech": ["climate", "clean energy", "sustainability", "carbon",
                     "renewable energy", "electric vehicles", "green tech"],
    "proptech":     ["real estate", "proptech", "construction", "housing"],
    "edtech":       ["education", "edtech", "learning", "upskilling"],
    "cybersecurity":["security", "cybersecurity", "privacy", "identity"],
    "legaltech":    ["legal", "legaltech", "compliance", "regtech"],
    "insurtech":    ["insurance", "insurtech"],
    "devtools":     ["developer tools", "devtools", "api", "infrastructure",
                     "open source", "developer productivity"],
}


def fetch_yc_companies(sector: str, max_results: int = 50,
                       recent_only: bool = True, region: str = None) -> list[dict]:
    """
    Main discovery function. Fetches YC companies filtered by sector.
    Collects ALL matches first, then sorts and truncates — ensures
    batch diversity and best results surface to the top.
    """
    print(f"[YC API] Fetching company list...")
    all_companies = _fetch_all(ALL_COMPANIES)
    if not all_companies:
        print("[YC API] Failed to fetch — check internet connection")
        return []

    print(f"[YC API] Loaded {len(all_companies)} companies — filtering for '{sector}'...")

    tags = _get_tags_for_sector(sector)
    results = []

    for company in all_companies:
        # Filter 1: active companies only
        if company.get("status") == "Inactive":
            continue

        # Filter 2: recent batches only (if requested)
        batch = company.get("batch", "")
        if recent_only and batch and batch not in RECENT_BATCHES:
            continue

        # Filter 3: sector match — must match via tags (strict), not just description
        match_score = _sector_match_score(company, tags, sector)
        if match_score == 0:
            continue

        # Filter 4: region (optional)
        if region and not _matches_region(company, region):
            continue

        normalised = _normalise(company)
        normalised["_match_score"] = match_score  # used for sorting
        results.append(normalised)

    # Sort: tag match strength first, then hiring, then batch recency
    results.sort(key=lambda c: (
        -c.get("_match_score", 0),          # higher match score first
        0 if c.get("is_hiring") else 1,     # hiring companies next
        _batch_sort_key(c.get("batch", "")),# most recent batch
    ))

    # Remove internal sort key before returning
    for r in results:
        r.pop("_match_score", None)

    print(f"[YC API] Found {len(results)} matching companies — returning top {min(len(results), max_results)}")
    return results[:max_results]


def fetch_hiring_companies(sector: str, max_results: int = 30) -> list[dict]:
    """
    Fetch only YC companies currently hiring — strong momentum signal.
    """
    print(f"[YC API] Fetching hiring companies for '{sector}'...")
    hiring = _fetch_all(HIRING_NOW)
    if not hiring:
        return []

    tags = _get_tags_for_sector(sector)
    results = []

    for company in hiring:
        if _matches_sector(company, tags, sector):
            results.append(_normalise(company))
        if len(results) >= max_results:
            break

    print(f"[YC API] Found {len(results)} hiring companies in '{sector}'")
    return results


# ── Internal helpers ──────────────────────────────────────────────────────────

def _fetch_all(url: str) -> list[dict]:
    """Fetch a YC API endpoint with retry."""
    headers = {"User-Agent": "Mozilla/5.0 deal-sourcing-tool/1.0"}
    for attempt in range(3):
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
            else:
                print(f"  [YC API] Error fetching {url}: {e}")
    return []


def _get_tags_for_sector(sector: str) -> list[str]:
    key = sector.lower().strip()
    if key in SECTOR_TAG_MAP:
        return SECTOR_TAG_MAP[key]
    for k, tags in SECTOR_TAG_MAP.items():
        if k in key or key in k:
            return tags
    return [sector.lower()]


def _sector_match_score(company: dict, tags: list[str], sector: str) -> int:
    """
    Return a match strength score (0 = no match, higher = stronger match).
    Tag matches score higher than description matches.
    Requires at least one tag match for non-obvious sector names
    to prevent false positives like "Nourish" matching fintech.
    """
    company_tags = [t.lower() for t in (company.get("tags") or [])]
    industry     = (company.get("industry") or "").lower()
    description  = (company.get("long_description") or
                    company.get("one_liner") or "").lower()
    score = 0

    for tag in tags:
        # Strong signal: exact tag match
        if tag in company_tags:
            score += 3
        # Strong signal: tag appears in industry field
        if tag in industry:
            score += 2
        # Weak signal: tag appears in description
        if tag in description:
            score += 1

    # Require at least a tag or industry match (score >= 2)
    # to avoid description false positives
    if score < 2:
        return 0

    return score


def _matches_sector(company: dict, tags: list[str], sector: str) -> bool:
    """Backward-compatible wrapper."""
    return _sector_match_score(company, tags, sector) > 0


def _matches_region(company: dict, region: str) -> bool:
    location = (company.get("all_locations") or "").lower()
    return region.lower() in location


def _normalise(company: dict) -> dict:
    """Flatten YC company object to our standard format."""
    return {
        "id":           company.get("slug", ""),
        "name":         company.get("name", ""),
        "source":       "YC",
        "batch":        company.get("batch", ""),
        "website":      company.get("website", ""),
        "description":  company.get("long_description") or company.get("one_liner", ""),
        "one_liner":    company.get("one_liner", ""),
        "location":     company.get("all_locations", ""),
        "tags":         company.get("tags", []),
        "industry":     company.get("industry", ""),
        "is_hiring":    company.get("is_hiring", False),
        "team_size":    company.get("team_size"),
        "status":       company.get("status", "Active"),
        # These come from Companies House enrichment later
        "incorporated_on": "",
        "directors":    [],
        "sic_codes":    [],
    }


def _batch_sort_key(batch: str) -> int:
    """Convert batch string like 'Winter 2025' to sortable int (lower = more recent)."""
    if not batch:
        return 9999
    try:
        parts = batch.lower().split()
        year = int(parts[-1])
        season_order = {"spring": 0, "summer": 1, "fall": 2, "winter": 3}
        season = season_order.get(parts[0], 2)
        return -(year * 10 + season)  # negative = more recent first
    except (ValueError, IndexError):
        return 9999


if __name__ == "__main__":
    # Quick test
    companies = fetch_yc_companies("fintech", max_results=10, recent_only=True)
    for c in companies:
        hiring = "hiring" if c["is_hiring"] else "      "
        print(f"  {hiring}  {c['batch']:<4}  {c['name']:<35}  {c['one_liner'][:50]}")
