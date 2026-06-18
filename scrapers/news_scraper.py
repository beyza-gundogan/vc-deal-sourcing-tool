"""
News & hiring signal scraper using NewsAPI.
Works both locally (.env) and on Streamlit Cloud (st.secrets).
"""

import os
import time
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()


def get_secret(key: str) -> str:
    try:
        import streamlit as st
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.getenv(key, "")


TIER_1_SOURCES = {
    "techcrunch", "financial times", "bloomberg", "forbes",
    "wired", "reuters", "sifted", "business insider",
    "the guardian", "bbc", "city a.m.", "the times",
}


def get_press_score(company_name: str, days: int = 90) -> dict:
    articles = []
    articles += _newsapi_headlines(company_name)
    articles += _google_news_rss(company_name)

    seen, unique = set(), []
    for a in articles:
        t = a.get("title", "")[:60]
        if t and t not in seen:
            seen.add(t)
            unique.append(a)

    total = len(unique)
    tier1_count = sum(
        1 for a in unique
        if any(src in a.get("source", "").lower() for src in TIER_1_SOURCES)
    )

    base  = min(3.0, total / 3)
    bonus = min(2.0, tier1_count * 0.7)
    score = round(min(5.0, base + bonus), 2)

    return {
        "score": score,
        "total_mentions": total,
        "tier1_mentions": tier1_count,
        "top_articles": unique[:3],
    }


def get_hiring_score(company_name: str) -> dict:
    query = f"{company_name} hiring OR funding OR expansion OR growth"
    articles = _google_news_rss(query)
    count = len(articles)
    score = round(min(10.0, count * 1.5), 2)
    return {"score": score, "mentions": count}


def _newsapi_headlines(company_name: str) -> list[dict]:
    api_key = get_secret("NEWS_API_KEY")
    if not api_key:
        return []
    try:
        resp = requests.get(
            "https://newsapi.org/v2/top-headlines",
            params={"q": company_name, "language": "en", "pageSize": 10, "apiKey": api_key},
            timeout=8,
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        return [
            {
                "title":     a.get("title", ""),
                "source":    a.get("source", {}).get("name", ""),
                "url":       a.get("url", ""),
                "published": a.get("publishedAt", ""),
            }
            for a in data.get("articles", [])
        ]
    except Exception:
        return []


def _google_news_rss(query: str) -> list[dict]:
    try:
        url = (f"https://news.google.com/rss/search"
               f"?q={requests.utils.quote(query)}&hl=en-GB&gl=GB&ceid=GB:en")
        resp = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            return []

        root = ET.fromstring(resp.content)
        articles = []
        for item in root.findall(".//item")[:10]:
            title = item.findtext("title") or ""
            link  = item.findtext("link") or ""
            source_el = item.find("source")
            source = source_el.text if source_el is not None else ""
            pub = item.findtext("pubDate") or ""
            articles.append({"title": title, "source": source, "url": link, "published": pub})
        return articles
    except Exception:
        return []


if __name__ == "__main__":
    result = get_press_score("Monzo", days=90)
    print(f"Press score: {result['score']}/5")
    print(f"Mentions: {result['total_mentions']} total, {result['tier1_mentions']} tier-1")
