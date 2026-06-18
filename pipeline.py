"""
Deal sourcing pipeline — main orchestrator.
Discovery: YC company API (5,800+ real startups, free, no key)
Enrichment: Companies House (UK companies only), NewsAPI, pytrends

Usage (CLI):
    python pipeline.py --sector "fintech" --limit 20

Usage (imported, e.g. from dashboard.py):
    from pipeline import run_pipeline
    results = run_pipeline(sector="fintech", limit=10)
"""

import os
import json
import time
import argparse
from datetime import datetime
from pathlib import Path

from scrapers.yc_discovery    import fetch_yc_companies, fetch_hiring_companies
from scrapers.companies_house import get_company_detail, get_officers, score_company_age
from scrapers.news_scraper    import get_press_score, get_hiring_score
from scrapers.market_timing   import get_market_timing_score
from scrapers.team_scorer     import score_team

OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)

WEIGHTS = {
    "team":              0.30,
    "product_traction":  0.20,
    "market_timing":     0.15,
    "hiring_momentum":   0.10,
    "funding_velocity":  0.10,
    "network_proximity": 0.10,
    "press_traction":    0.05,
}


def run_pipeline(sector: str, limit: int = 20,
                 region: str = None, hiring_only: bool = False) -> list[dict]:

    print(f"\n{'='*55}")
    print(f"  Deal sourcing pipeline  |  Source: YC API")
    print(f"  Sector: '{sector}'  |  Limit: {limit}")
    print(f"{'='*55}\n")

    # ── Step 1: Market timing ─────────────────────────────────────────────
    print(f"[1/4] Market timing for '{sector}'...")
    try:
        market = get_market_timing_score(sector)
    except Exception as e:
        print(f"      Market timing unavailable ({e}) — using neutral score")
        market = {"score": 7.5, "trend": "neutral"}
    print(f"      Trend: {market['trend']}  |  Score: {market['score']}/15")
    time.sleep(0.5)

    # ── Step 2: Discover via YC API ────────────────────────────────────────
    print(f"\n[2/4] Discovering companies via YC API...")
    if hiring_only:
        companies = fetch_hiring_companies(sector, max_results=limit)
    else:
        companies = fetch_yc_companies(sector, max_results=limit, region=region)

    if not companies:
        print("No companies found. Try a broader sector keyword.")
        return []

    # ── Step 3: Enrich & score ────────────────────────────────────────────
    print(f"\n[3/4] Enriching and scoring {len(companies)} companies...")
    results = []

    for i, company in enumerate(companies):
        name = company["name"]
        print(f"\n  [{i+1}/{len(companies)}] {name}  "
              f"({company.get('batch','?')}  {str(company.get('location',''))[:30]})")

        try:
            press  = get_press_score(name, days=90)
            time.sleep(0.3)
            hiring = get_hiring_score(name)
            time.sleep(0.3)

            ch_detail, ch_officers = {}, []
            if _is_uk_company(company):
                ch_result = _enrich_from_companies_house(name)
                if ch_result:
                    ch_detail, ch_officers = ch_result
                    print(f"      + Companies House data found")

            scoring = _compute_score(company, ch_detail, ch_officers, market, press, hiring)

            results.append({
                **company,
                "ch_directors":    [o["name"] for o in ch_officers[:4]],
                "ch_incorporated": ch_detail.get("incorporated_on", ""),
                "press_mentions":  press["total_mentions"],
                "top_articles":    press["top_articles"],
                "market_trend":    market["trend"],
                **scoring,
            })

            print(f"      Score: {scoring['total_score']}/100  →  {scoring['verdict']}")

        except Exception as e:
            print(f"      Error: {e} — skipping")
            continue

    # ── Step 4: Save ──────────────────────────────────────────────────────
    results.sort(key=lambda x: x.get("total_score", 0), reverse=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    safe_name = sector.replace(" ", "_").replace("/", "-")
    out_path  = OUTPUT_DIR / f"deals_{safe_name}_{timestamp}.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\n{'='*55}")
    print(f"  Done. {len(results)} companies scored.")
    print(f"  Saved → {out_path}")
    print(f"{'='*55}")

    return results


# ── Scoring ───────────────────────────────────────────────────────────────────

def _compute_score(company, ch_detail, ch_officers, market, press, hiring) -> dict:
    if ch_officers:
        team_result = score_team(ch_officers, ch_detail)
        team_raw = team_result["score"] / 3
    else:
        team_raw = _yc_team_score(company) / 3

    raw = {
        "team":              team_raw,
        "product_traction":  _product_score(company, ch_detail),
        "market_timing":     market["score"] / 1.5,
        "hiring_momentum":   min(hiring["score"], 10),
        "funding_velocity":  _funding_score(company),
        "network_proximity": _network_score(company),
        "press_traction":    min(press["score"] * 2, 10),
    }

    total = sum(raw[k] * WEIGHTS[k] * 10 for k in WEIGHTS)
    total = round(min(total, 100), 1)

    verdict = ("Strong — pursue" if total >= 70
               else "Watch list" if total >= 50
               else "Pass")

    return {
        "total_score": total,
        "verdict":     verdict,
        "breakdown":   {k: round(raw[k], 1) for k in raw},
    }


def _yc_team_score(company: dict) -> float:
    score = 12.0
    size = company.get("team_size") or 0
    if 10 <= size <= 50:    score += 10
    elif 51 <= size <= 150: score += 7
    elif size > 150:        score += 4
    elif 3 <= size <= 9:    score += 6
    elif size > 0:          score += 2
    if company.get("is_hiring"): score += 8
    return min(score, 30)


def _product_score(company: dict, ch_detail: dict) -> float:
    score = 5.0
    size = company.get("team_size") or 0
    if size >= 10: score += 3
    if size >= 25: score += 2
    inc = ch_detail.get("incorporated_on", "")
    if inc:
        age = score_company_age(inc)
        score = (score + age) / 2
    return min(score, 10)


def _funding_score(company: dict) -> float:
    batch = company.get("batch", "")
    if not batch:
        return 5.0
    try:
        year = int(batch.split()[-1])
        years_ago = datetime.now().year - year
        if years_ago <= 1:   return 10.0
        elif years_ago <= 2: return 8.0
        elif years_ago <= 3: return 6.0
        elif years_ago <= 4: return 4.0
        else:                return 2.0
    except (ValueError, IndexError):
        return 5.0


def _network_score(company: dict) -> float:
    score = 7.0
    if company.get("is_hiring"): score += 2
    if (company.get("team_size") or 0) > 20: score += 1
    return min(score, 10)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_uk_company(company: dict) -> bool:
    loc = str(company.get("location") or "").lower()
    return any(x in loc for x in
               ["uk", "united kingdom", "london", "manchester", "edinburgh", "bristol"])


def _enrich_from_companies_house(company_name: str):
    try:
        import requests as req_lib

        def get_secret(key):
            try:
                import streamlit as st
                if key in st.secrets:
                    return st.secrets[key]
            except Exception:
                pass
            return os.getenv(key, "")

        key = get_secret("COMPANIES_HOUSE_API_KEY")
        if not key:
            return None

        resp = req_lib.get(
            "https://api.company-information.service.gov.uk/search/companies",
            params={"q": company_name, "items_per_page": 3},
            auth=(key, ""),
            timeout=8,
        )
        if not resp.ok:
            return None

        items = resp.json().get("items", [])
        if not items:
            return None

        cid = items[0].get("company_number", "")
        if not cid:
            return None

        detail   = get_company_detail(cid)
        officers = get_officers(cid)
        return detail, officers

    except Exception:
        return None


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deal sourcing pipeline — YC edition")
    parser.add_argument("--sector",      type=str, default="fintech")
    parser.add_argument("--limit",       type=int, default=20)
    parser.add_argument("--region",      type=str, default=None)
    parser.add_argument("--hiring-only", action="store_true")
    args = parser.parse_args()

    run_pipeline(
        sector      = args.sector,
        limit       = args.limit,
        region      = args.region,
        hiring_only = args.hiring_only,
    )
