"""
Companies House API client.
Works both locally (.env) and on Streamlit Cloud (st.secrets).
"""

import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api.company-information.service.gov.uk"


def get_secret(key: str) -> str:
    try:
        import streamlit as st
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.getenv(key, "")


def _get(endpoint: str, params: dict = {}) -> dict:
    api_key = get_secret("COMPANIES_HOUSE_API_KEY")
    if not api_key:
        return {}
    url = f"{BASE_URL}/{endpoint}"
    try:
        response = requests.get(url, params=params, auth=(api_key, ""), timeout=10)
        if response.status_code == 404:
            return {}
        if response.status_code == 429:
            time.sleep(3)
            response = requests.get(url, params=params, auth=(api_key, ""), timeout=10)
        if not response.ok:
            return {}
        return response.json()
    except Exception:
        return {}


def search_companies(keyword: str, max_results: int = 50) -> list[dict]:
    from scrapers.sic_codes import get_sic_codes
    from datetime import date

    sic_codes = get_sic_codes(keyword)
    today = date.today()
    date_from = date(today.year - 8, today.month, today.day).isoformat()
    date_to   = date(today.year - 1, today.month, today.day).isoformat()

    companies = []
    seen_ids  = set()

    def chunks(lst, n):
        for i in range(0, len(lst), n):
            yield lst[i:i + n]

    from scrapers.sic_codes import get_sector_keywords
    sector_keywords = get_sector_keywords(keyword)
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
            if _is_non_startup(name):
                continue

            sector_match = bool(not sector_keywords or _matches_sector(name, sector_keywords))

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

        time.sleep(0.3)

    companies.sort(key=lambda c: (0 if c.get("sector_match") else 1))
    return companies[:max_results]


def get_company_detail(company_number: str) -> dict:
    data = _get(f"company/{company_number}")
    if not data:
        return {}
    return {
        "id":                company_number,
        "name":              data.get("company_name", ""),
        "status":            data.get("company_status", ""),
        "company_type":      data.get("type", ""),
        "incorporated_on":   data.get("date_of_creation", ""),
        "address":           _extract_address(data.get("registered_office_address", {})),
        "sic_codes":         data.get("sic_codes", []),
        "last_accounts_date": data.get("accounts", {}).get("last_accounts", {}).get("made_up_to", ""),
        "next_accounts_due":  data.get("accounts", {}).get("next_due", ""),
        "jurisdiction":      data.get("jurisdiction", ""),
        "has_insolvency_history": data.get("has_insolvency_history", False),
    }


def get_officers(company_number: str) -> list[dict]:
    data = _get(f"company/{company_number}/officers")
    if not data:
        return []
    officers = []
    for item in data.get("items", []):
        if item.get("resigned_on"):
            continue
        officers.append({
            "name":                item.get("name", ""),
            "role":                item.get("officer_role", ""),
            "appointed_on":        item.get("appointed_on", ""),
            "nationality":         item.get("nationality", ""),
            "country_of_residence": item.get("country_of_residence", ""),
            "occupation":          item.get("occupation", ""),
        })
    return officers


def score_company_age(incorporated_on: str) -> float:
    if not incorporated_on:
        return 5.0
    from datetime import date
    try:
        inc = date.fromisoformat(incorporated_on)
        age_years = (date.today() - inc).days / 365
        if 1 <= age_years <= 3:   return 10.0
        elif 3 < age_years <= 5:  return 8.0
        elif age_years < 1:       return 5.0
        elif 5 < age_years <= 8:  return 5.0
        else:                     return 2.0
    except ValueError:
        return 5.0


_NON_STARTUP_KEYWORDS = {
    "accountant", "accounting", "accounts", "bookkeeping",
    "solicitor", "solicitors", "law firm",
    "consulting", "consultancy", "consultants",
    "recruitment", "recruiter", "staffing", "agency",
    "holding", "holdings", "acquisition", "acquisitions",
    "nominees", "trustee", "trustees", "pension",
    "dormant", "secretary", "management services",
    "mortgage funding", "bridging", "bridging loans",
    "motor finance", "vehicle finance", "asset finance",
    "funding no.", "funding no ", "spv", "special purpose",
    "commercials", "commercial finance",
    "cleaning", "property management", "lettings",
    "plumbing", "electrical", "construction", "builders",
}

def _is_non_startup(name: str) -> bool:
    lower = name.lower()
    return any(kw in lower for kw in _NON_STARTUP_KEYWORDS)


def _matches_sector(name: str, keywords: list[str]) -> bool:
    lower = name.lower()
    return any(kw in lower for kw in keywords)


def _extract_address(addr: dict) -> str:
    parts = [
        addr.get("address_line_1", ""),
        addr.get("locality", ""),
        addr.get("postal_code", ""),
    ]
    return ", ".join(p for p in parts if p)
