"""Team signal scorer using Companies House officer data. Scores 0-30."""

from datetime import date


def score_team(officers: list[dict], company_detail: dict) -> dict:
    score = 0
    signals = []

    active_directors = [o for o in officers if "director" in o.get("role", "").lower()]
    num_directors = len(active_directors)

    if num_directors in (2, 3):
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
        signals.append(f"Large board ({num_directors} directors)")

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
            signals.append(f"Directors avg tenure {avg_tenure:.1f} yrs")
        elif avg_tenure < 1:
            score += 4
        else:
            score += 3

    countries = set(
        d.get("country_of_residence", "").lower()
        for d in active_directors if d.get("country_of_residence")
    )
    if len(countries) > 1:
        score += 5
        signals.append(f"International team ({len(countries)} countries)")
    elif len(countries) == 1:
        score += 2

    if not company_detail.get("has_insolvency_history", False):
        score += 4
        signals.append("No insolvency history")

    if company_detail.get("sic_codes"):
        score += 3

    if company_detail.get("last_accounts_date"):
        score += 3
        signals.append(f"Filed accounts to {company_detail['last_accounts_date']}")

    return {
        "score": min(score, 30),
        "signals": signals,
        "num_directors": num_directors,
        "director_names": [d["name"] for d in active_directors[:4]],
    }
