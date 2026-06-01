"""
Market timing scorer using pytrends (Google Trends).
No API key needed — pytrends talks to Google Trends directly.
Scores how much search interest a sector/company keyword has right now
vs 12 months ago — a proxy for market tailwinds.
"""

import time
from pytrends.request import TrendReq


def get_market_timing_score(keyword: str) -> dict:
    """
    Compare Google Trends interest for a keyword:
    last 3 months vs same period last year.
    Score 0–15 (matching the 15% weight in our framework).
    """
    pytrends = TrendReq(hl="en-GB", tz=0)

    try:
        # Get trend over the last 12 months
        pytrends.build_payload([keyword], timeframe="today 12-m", geo="GB")
        interest_df = pytrends.interest_over_time()

        if interest_df.empty:
            print(f"    [pytrends] No data for '{keyword}' — using neutral score")
            return {"score": 7.5, "trend": "neutral", "recent_avg": 0, "year_avg": 0}

        values = interest_df[keyword].tolist()

        # Compare recent 3 months vs earlier 9 months
        recent_avg = sum(values[-13:]) / max(len(values[-13:]), 1)
        older_avg = sum(values[:-13]) / max(len(values[:-13]), 1)

        if older_avg == 0:
            ratio = 1.0
        else:
            ratio = recent_avg / older_avg

        # Score based on growth ratio
        if ratio >= 2.0:
            score = 15.0    # surging — strong tailwind
        elif ratio >= 1.5:
            score = 12.0    # growing fast
        elif ratio >= 1.1:
            score = 10.0    # steady growth
        elif ratio >= 0.9:
            score = 7.5     # flat — neutral
        elif ratio >= 0.7:
            score = 5.0     # declining interest
        else:
            score = 3.0     # significant decline

        trend = (
            "surging" if ratio >= 1.5
            else "growing" if ratio >= 1.1
            else "flat" if ratio >= 0.9
            else "declining"
        )

        return {
            "score": score,
            "trend": trend,
            "ratio": round(ratio, 2),
            "recent_avg": round(recent_avg, 1),
            "year_avg": round(sum(values) / len(values), 1),
        }

    except Exception as e:
        print(f"    [pytrends] Error for '{keyword}': {e} — using neutral score")
        return {"score": 7.5, "trend": "neutral", "recent_avg": 0, "year_avg": 0}


def get_related_topics(keyword: str) -> list[str]:
    """
    Get rising related topics — useful for spotting adjacent opportunities.
    """
    pytrends = TrendReq(hl="en-GB", tz=0)
    try:
        pytrends.build_payload([keyword], timeframe="today 3-m", geo="GB")
        related = pytrends.related_topics()
        rising = related.get(keyword, {}).get("rising")
        if rising is not None and not rising.empty:
            return rising["topic_title"].tolist()[:5]
    except Exception:
        pass
    return []


if __name__ == "__main__":
    for sector in ["fintech", "B2B SaaS", "climate tech", "AI healthcare"]:
        result = get_market_timing_score(sector)
        print(f"  {sector:<20} score={result['score']}/15  trend={result['trend']}  ratio={result.get('ratio', '—')}")
        time.sleep(1)  # be polite to Google
