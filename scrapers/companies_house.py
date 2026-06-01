"""
Companies House API client
Docs: https://developer.company-information.service.gov.uk
Free, no rate limit issues for reasonable use.
Authentication: HTTP Basic Auth — API key as username, password left blank.
"""

import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("COMPANIES_HOUSE_API_KEY")
BASE_URL = "https://api.company-information.service.gov.uk"


def _get(endpoint: str, params: dict = {}) -> dict:
    """Base authenticated GET request."""
    url = f"{BASE_URL}/{endpoint}"
    # Companies House uses HTTP Basic Auth: API key as username, blank password
    response = requests.get(url, params=params, auth=(API_KEY, ""), timeout=10)
    if response.status_code == 404:
        return {}
    if response.status_code == 429:
        print("Rate limited by Companies House — waiting 5s...")
        time.sleep(5)
        response = requests.get(url, params=params, auth=(API_KEY, ""), timeout=10)
    response.raise_for_status()
    return response.json()


def search_companies(keyword: str, max_results: int = 50) -> list[dict]:
    """
    Search Companies House using the advanced search endpoint with proper
    SIC code filtering. This returns genuine sector companies rather than
    anything with the keyword in its name.

    Uses /advanced-search/companies which supports:
    - sic_codes: filter by industry classification
    - incorporated_from/to: VC-stage date range (1–8 years old)
    - company_status: active only
    """
    from scrapers.sic_codes import get_sic_codes
    from datetime import date

    sic_codes = get_sic_codes(keyword)
    today = date.today()
    date_from = date(today.year - 8, today.month, today.day).isoformat()
    date_to   = date(today.year - 1, today.month, today.day).isoformat()

    companies = []
    seen_ids  = set()

    # Advanced search supports comma-separated SIC codes — batch them
    # in groups of 3 to stay within URL length limits
    def chunks(lst, n):
        for i in range(0, len(lst), n):
            yield lst[i:i + n]

    from scrapers.sic_codes import get_sector_keywords
    sector_keywords = get_sector_keywords(keyword)

    # Fetch more than we need so filtering doesn't leave us short
    fetch_size = min(100, max_results * 5)

    for sic_batch in chunks(sic_codes, 3):
        if len(companies) >= max_results:
            break

        params = {
            "sic_codes":         ",".join(sic_batch),
            "incorporated_from": date_from,
            "incorporated_to":   date_to,
            "company_status":    "active",
            "size":              min(fetch_size, 100),
        }

        data = _get("advanced-search/companies", params)

        for item in data.get("items", []):
            if len(companies) >= max_results:
                break

            cid = item.get("company_number", "")
            if cid in seen_ids:
                continue

            name = item.get("company_name", "") or item.get("title", "")

            # Filter 1: remove obvious non-startups (hard gate)
            if _is_non_startup(name):
                continue

            # Filter 2: sector relevance — soft scoring, not a hard gate
            # We tag the company with whether it matches, for later use
            sector_match = bool(
                not sector_keywords or _matches_sector(name, sector_keywords)
            )

            seen_ids.add(cid)
            companies.append({
                "id":              cid,
                "name":            name,
                "status":          item.get("company_status", "active"),
                "company_type":    item.get("company_type", ""),
                "incorporated_on": item.get("date_of_creation", ""),
                "address":         _extract_address(
                                       item.get("registered_office_address")
                                       or item.get("address", {})
                                   ),
                "sic_codes":       item.get("sic_codes", []),
                "sector_match":    sector_match,
            })

        time.sleep(0.4)

    # Prioritise sector-matching companies but keep all
    companies.sort(key=lambda c: (0 if c.get("sector_match") else 1))
    print(f"[Companies House] Found {len(companies)} active VC-stage companies for '{keyword}'")
    return companies[:max_results]


# ── Non-startup filter ────────────────────────────────────────────────────────

# Words that strongly suggest a company is NOT a VC-backable startup
_NON_STARTUP_KEYWORDS = {
    # Professional services
    "accountant", "accounting", "accounts", "bookkeeping",
    "solicitor", "solicitors", "law firm",
    "consulting", "consultancy", "consultants",
    "recruitment", "recruiter", "staffing", "agency",
    # Corporate structures
    "holding", "holdings", "acquisition", "acquisitions",
    "nominees", "trustee", "trustees", "pension",
    "dormant", "secretary", "management services",
    # Traditional finance (not fintech)
    "mortgage funding", "bridging", "bridging loans",
    "motor finance", "vehicle finance", "asset finance",
    "funding no.", "funding no ", "spv", "special purpose",
    "commercials", "commercial finance",
    # Non-tech services
    "cleaning", "property management", "lettings",
    "plumbing", "electrical", "construction", "builders",
}

def _is_non_startup(name: str) -> bool:
    """Return True if the company name suggests it is not a startup."""
    lower = name.lower()
    return any(kw in lower for kw in _NON_STARTUP_KEYWORDS)


def _matches_sector(name: str, keywords: list[str]) -> bool:
    """Return True if the company name contains at least one sector keyword."""
    lower = name.lower()
    return any(kw in lower for kw in keywords)


def get_company_detail(company_number: str) -> dict:
    """
    Fetch full profile for a single company.
    Includes SIC codes (industry), accounts filing dates, registered address.
    """
    data = _get(f"company/{company_number}")
    if not data:
        return {}

    return {
        "id": company_number,
        "name": data.get("company_name", ""),
        "status": data.get("company_status", ""),
        "company_type": data.get("type", ""),
        "incorporated_on": data.get("date_of_creation", ""),
        "address": _extract_address(data.get("registered_office_address", {})),
        "sic_codes": data.get("sic_codes", []),
        "last_accounts_date": data.get("accounts", {}).get("last_accounts", {}).get("made_up_to", ""),
        "next_accounts_due": data.get("accounts", {}).get("next_due", ""),
        "jurisdiction": data.get("jurisdiction", ""),
        "has_insolvency_history": data.get("has_insolvency_history", False),
    }


def get_officers(company_number: str) -> list[dict]:
    """
    Fetch directors and officers — our proxy for team signal.
    Returns name, role, and appointment date per officer.
    """
    data = _get(f"company/{company_number}/officers")
    if not data:
        return []

    officers = []
    for item in data.get("items", []):
        # Skip resigned officers
        if item.get("resigned_on"):
            continue
        officers.append({
            "name": item.get("name", ""),
            "role": item.get("officer_role", ""),
            "appointed_on": item.get("appointed_on", ""),
            "nationality": item.get("nationality", ""),
            "country_of_residence": item.get("country_of_residence", ""),
            "occupation": item.get("occupation", ""),
        })

    return officers


def get_filing_history(company_number: str) -> list[dict]:
    """
    Recent filings — active filing history signals a healthy, compliant company.
    """
    data = _get(f"company/{company_number}/filing-history", {"items_per_page": 10})
    if not data:
        return []

    filings = []
    for item in data.get("items", []):
        filings.append({
            "date": item.get("date", ""),
            "description": item.get("description", ""),
            "type": item.get("type", ""),
        })
    return filings


def score_company_age(incorporated_on: str) -> float:
    """
    Score 0–10 based on company age.
    VC sweet spot: 1–5 years old. Too new = risky, too old = missed the window.
    """
    if not incorporated_on:
        return 5.0
    from datetime import date
    try:
        inc = date.fromisoformat(incorporated_on)
        age_years = (date.today() - inc).days / 365
        if 1 <= age_years <= 3:
            return 10.0   # sweet spot — early but proven
        elif 3 < age_years <= 5:
            return 8.0
        elif age_years < 1:
            return 5.0    # very new — higher risk
        elif 5 < age_years <= 8:
            return 5.0
        else:
            return 2.0    # older — likely not VC-stage
    except ValueError:
        return 5.0


# ── helpers ──────────────────────────────────────────────────────────────────

def _extract_address(addr: dict) -> str:
    parts = [
        addr.get("address_line_1", ""),
        addr.get("locality", ""),
        addr.get("postal_code", ""),
    ]
    return ", ".join(p for p in parts if p)


if __name__ == "__main__":
    # Quick smoke test — make sure your .env has COMPANIES_HOUSE_API_KEY set
    results = search_companies("fintech", max_results=5)
    for c in results:
        print(f"  {c['name']} | {c['incorporated_on']} | {c['address']}")
        officers = get_officers(c["id"])
        print(f"    Directors: {[o['name'] for o in officers[:3]]}")
