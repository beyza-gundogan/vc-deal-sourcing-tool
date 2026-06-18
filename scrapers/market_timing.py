"""Market timing scorer using pytrends (Google Trends). No API key needed."""

import time
from pytrends.request import TrendReq


def get_market_timing_score(keyword: str) -> dict:
    pytrends = TrendReq(hl="en-GB", tz=0)
    try:
        pytrends.build_payload([keyword], timeframe="today 12-m", geo="GB")
        interest_df = pytrends.interest_over_time()

        if interest_df.empty:
            return {"score": 7.5, "trend": "neutral", "recent_avg": 0, "year_avg": 0}

        values = interest_df[keyword].tolist()
        recent_avg = sum(values[-13:]) / max(len(values[-13:]), 1)
        older_avg  = sum(values[:-13]) / max(len(values[:-13]), 1)
        ratio = recent_avg / older_avg if older_avg else 1.0

        if ratio >= 2.0:    score = 15.0
        elif ratio >= 1.5:  score = 12.0
        elif ratio >= 1.1:  score = 10.0
        elif ratio >= 0.9:  score = 7.5
        elif ratio >= 0.7:  score = 5.0
        else:               score = 3.0

        trend = ("surging" if ratio >= 1.5 else
                 "growing" if ratio >= 1.1 else
                 "flat" if ratio >= 0.9 else "declining")

        return {
            "score": score, "trend": trend, "ratio": round(ratio, 2),
            "recent_avg": round(recent_avg, 1), "year_avg": round(sum(values)/len(values), 1),
        }
    except Exception:
        return {"score": 7.5, "trend": "neutral", "recent_avg": 0, "year_avg": 0}


if __name__ == "__main__":
    for sector in ["fintech", "B2B SaaS", "climate tech"]:
        result = get_market_timing_score(sector)
        print(f"  {sector:<20} score={result['score']}/15  trend={result['trend']}")
        time.sleep(1)
