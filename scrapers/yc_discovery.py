"""
YC Company Discovery Layer using the yc-oss public API.
Free, no key needed, updated daily. Source: github.com/yc-oss/api
"""

import time
import requests

YC_API_BASE   = "https://yc-oss.github.io/api"
ALL_COMPANIES = f"{YC_API_BASE}/companies/all.json"
HIRING_NOW    = f"{YC_API_BASE}/companies/hiring.json"

RECENT_BATCHES = {
    "Spring 2026", "Winter 2026", "Fall 2025", "Summer 2025", "Spring 2025",
    "Winter 2025", "Fall 2024", "Summer 2024", "Winter 2024",
    "Summer 2023", "Winter 2023", "Summer 2022", "Winter 2022",
    "Summer 2021", "Winter 2021",
}

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
    all_companies = _fetch_all(ALL_COMPANIES)
    if not all_companies:
        return []

    tags = _get_tags_for_sector(sector)
    results = []

    for company in all_companies:
        if company.get("status") == "Inactive":
            continue

        batch = company.get("batch", "")
        if recent_only and batch and batch not in RECENT_BATCHES:
            continue

        match_score = _sector_match_score(company, tags, sector)
        if match_score == 0:
            continue

        if region and not _matches_region(company, region):
            continue

        normalised = _normalise(company)
        normalised["_match_score"] = match_score
        results.append(normalised)

    results.sort(key=lambda c: (
        -c.get("_match_score", 0),
        0 if c.get("is_hiring") else 1,
        _batch_sort_key(c.get("batch", "")),
    ))

    for r in results:
        r.pop("_match_score", None)

    return results[:max_results]


def fetch_hiring_companies(sector: str, max_results: int = 30) -> list[dict]:
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
    return results


def _fetch_all(url: str) -> list[dict]:
    headers = {"User-Agent": "Mozilla/5.0 deal-sourcing-tool/1.0"}
    for attempt in range(3):
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            if attempt < 2:
                time.sleep(2 ** attempt)
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
    company_tags = [t.lower() for t in (company.get("tags") or [])]
    industry     = (company.get("industry") or "").lower()
    description  = (company.get("long_description") or company.get("one_liner") or "").lower()
    score = 0

    for tag in tags:
        if tag in company_tags: score += 3
        if tag in industry:     score += 2
        if tag in description:  score += 1

    return score if score >= 2 else 0


def _matches_sector(company: dict, tags: list[str], sector: str) -> bool:
    return _sector_match_score(company, tags, sector) > 0


def _matches_region(company: dict, region: str) -> bool:
    location = (company.get("all_locations") or "").lower()
    return region.lower() in location


def _normalise(company: dict) -> dict:
    return {
        "id":              company.get("slug", ""),
        "name":            company.get("name", ""),
        "source":          "YC",
        "batch":           company.get("batch", ""),
        "website":         company.get("website", ""),
        "description":     company.get("long_description") or company.get("one_liner", ""),
        "one_liner":       company.get("one_liner", ""),
        "location":        company.get("all_locations", ""),
        "tags":            company.get("tags", []),
        "industry":        company.get("industry", ""),
        "is_hiring":       company.get("is_hiring", False),
        "team_size":       company.get("team_size"),
        "status":          company.get("status", "Active"),
        "incorporated_on": "",
        "directors":       [],
        "sic_codes":       [],
    }


def _batch_sort_key(batch: str) -> int:
    if not batch:
        return 9999
    try:
        parts = batch.lower().split()
        year = int(parts[-1])
        season_order = {"spring": 0, "summer": 1, "fall": 2, "winter": 3}
        season = season_order.get(parts[0], 2)
        return -(year * 10 + season)
    except (ValueError, IndexError):
        return 9999
