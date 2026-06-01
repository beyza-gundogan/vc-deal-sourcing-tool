"""
Team signal scorer.
Uses Companies House officer data as our data source.
Scores 0–30 matching the 30% weight in the framework.
"""

from datetime import date


def score_team(officers: list[dict], company_detail: dict) -> dict:
    """
    Score team signal 0–30 from Companies House officer data.

    officers: list from companies_house.get_officers()
    company_detail: dict from companies_house.get_company_detail()
    """
    score = 0
    signals = []

    active_directors = [o for o in officers if "director" in o.get("role", "").lower()]
    num_directors = len(active_directors)

    # 1. Team size signal (up to 8 pts)
    if num_directors == 2 or num_directors == 3:
        score += 8
        signals.append(f"Optimal founding team size ({num_directors} directors)")
    elif num_directors == 1:
        score += 4
        signals.append("Solo director (higher execution risk)")
    elif 4 <= num_directors <= 5:
        score += 6
        signals.append(f"Larger team ({num_directors} directors)")
    elif num_directors > 5:
        score += 3
        signals.append(f"Large board ({num_directors} directors) — may be established corp")

    # 2. Director tenure diversity (up to 7 pts)
    # Mix of long-tenured + recently added = active team-building
    tenures = []
    for d in active_directors:
        appointed = d.get("appointed_on", "")
        if appointed:
            try:
                years = (date.today() - date.fromisoformat(appointed)).days / 365
                tenures.append(years)
            except ValueError:
                pass

    if tenures:
        avg_tenure = sum(tenures) / len(tenures)
        if 1 <= avg_tenure <= 4:
            score += 7
            signals.append(f"Directors avg tenure {avg_tenure:.1f} yrs — healthy for VC stage")
        elif avg_tenure < 1:
            score += 4
            signals.append("Very recently appointed team")
        else:
            score += 3
            signals.append(f"Longer-tenured team ({avg_tenure:.1f} yrs avg)")

    # 3. International team signal (up to 5 pts)
    countries = set(
        d.get("country_of_residence", "").lower()
        for d in active_directors
        if d.get("country_of_residence")
    )
    if len(countries) > 1:
        score += 5
        signals.append(f"International team ({len(countries)} countries) — wider network")
    elif len(countries) == 1:
        score += 2

    # 4. Company health signals (up to 10 pts)
    if not company_detail.get("has_insolvency_history", False):
        score += 4
        signals.append("No insolvency history")

    sic_codes = company_detail.get("sic_codes", [])
    if sic_codes:
        score += 3
        signals.append(f"Registered SIC codes: {', '.join(sic_codes[:2])}")

    # Active filing = well-administered company
    if company_detail.get("last_accounts_date"):
        score += 3
        signals.append(f"Filed accounts to {company_detail['last_accounts_date']}")

    final_score = min(score, 30)

    return {
        "score": final_score,
        "signals": signals,
        "num_directors": num_directors,
        "director_names": [d["name"] for d in active_directors[:4]],
    }


if __name__ == "__main__":
    # Mock data test
    mock_officers = [
        {"name": "SMITH, Alice", "role": "director", "appointed_on": "2021-03-15", "country_of_residence": "England"},
        {"name": "JONES, Bob", "role": "director", "appointed_on": "2021-03-15", "country_of_residence": "Germany"},
        {"name": "LEE, Carol", "role": "director", "appointed_on": "2023-01-10", "country_of_residence": "England"},
    ]
    mock_detail = {
        "sic_codes": ["62012", "63110"],
        "has_insolvency_history": False,
        "last_accounts_date": "2024-12-31",
    }
    result = score_team(mock_officers, mock_detail)
    print(f"Team score: {result['score']}/30")
    for s in result["signals"]:
        print(f"  + {s}")
