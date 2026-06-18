"""
Deal sourcing dashboard — with live pipeline trigger
Run with: streamlit run dashboard.py

Lets the user type a sector and run the discovery + scoring pipeline
live in the browser, then browse results in a filterable table with
score breakdown charts.
"""

import os
import json
import glob
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path
from datetime import datetime

st.set_page_config(
    page_title="Deal Sourcing Dashboard",
    page_icon="📊",
    layout="wide",
)

OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)


# ── Secrets helper (works locally via .env AND on Streamlit Cloud) ───────────

def get_secret(key: str) -> str:
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.getenv(key, "")


# ── Load data ─────────────────────────────────────────────────────────────────

def load_all_companies():
    """Load and merge all pipeline output JSON files."""
    files = sorted(glob.glob("outputs/deals_*.json"), reverse=True)
    if not files:
        return pd.DataFrame()

    all_companies = []
    for f in files:
        try:
            data = json.loads(Path(f).read_text())
            sector = Path(f).stem.split("_")[1]
            for c in data:
                c["_sector"] = sector.replace("-", " ")
                c["_source_file"] = Path(f).name
            all_companies.extend(data)
        except Exception:
            continue

    if not all_companies:
        return pd.DataFrame()

    df = pd.DataFrame(all_companies)
    df = df.sort_values("total_score", ascending=False)
    df = df.drop_duplicates(subset=["name"], keep="first")

    if "breakdown" in df.columns:
        breakdown_df = df["breakdown"].apply(
            lambda x: x if isinstance(x, dict) else {}
        ).apply(pd.Series)
        breakdown_df.columns = [f"score_{c}" for c in breakdown_df.columns]
        df = pd.concat([df, breakdown_df], axis=1)

    return df.reset_index(drop=True)


def load_briefs() -> dict:
    briefs = {}
    for f in glob.glob("briefs/brief_*.md"):
        content = Path(f).read_text(encoding="utf-8")
        name = Path(f).stem.replace("brief_", "").rsplit("_", 1)[0].replace("_", " ")
        briefs[name.lower()] = content
    return briefs


def verdict_colour(verdict: str) -> str:
    return {"Strong — pursue": "🟢", "Watch list": "🟡", "Pass": "🔴"}.get(verdict, "⚪")


def score_colour(score: float) -> str:
    if score >= 70: return "green"
    if score >= 50: return "orange"
    return "red"


def batch_year(batch: str) -> int:
    try:
        return int(str(batch).split()[-1])
    except Exception:
        return 0


# ── Main app ──────────────────────────────────────────────────────────────────

def main():
    st.title("📊 Deal sourcing dashboard")
    st.caption(
        "Type a sector below to live-search 5,900+ YC-backed startups, "
        "score them across 7 signals, and browse the results."
    )

    # ── Live pipeline trigger ────────────────────────────────────────────────
    with st.container(border=True):
        st.subheader("Run a new search")
        col1, col2, col3 = st.columns([2, 1, 1])

        with col1:
            sector_input = st.text_input(
                "Sector",
                placeholder="e.g. fintech, ai, healthtech, b2b saas, climate tech",
                label_visibility="collapsed",
            )
        with col2:
            limit_input = st.slider("How many companies", 5, 30, 10, label_visibility="visible")
        with col3:
            run_btn = st.button("🔍 Run pipeline", type="primary", use_container_width=True)

        hiring_only = st.checkbox("Hiring companies only")

        if run_btn and sector_input:
            with st.status(f"Running pipeline for '{sector_input}'...", expanded=True) as status:
                try:
                    from pipeline import run_pipeline
                    st.write("📡 Fetching market timing data...")
                    st.write("🔎 Discovering companies via YC API (5,900+ companies)...")
                    st.write("⚖️ Scoring companies across 7 signals...")

                    results = run_pipeline(
                        sector=sector_input,
                        limit=limit_input,
                        hiring_only=hiring_only,
                    )

                    if results:
                        status.update(
                            label=f"✅ Found and scored {len(results)} companies!",
                            state="complete"
                        )
                        st.cache_data.clear()
                    else:
                        status.update(label="⚠️ No companies found — try a different sector", state="error")

                except Exception as e:
                    status.update(label="❌ Pipeline error", state="error")
                    st.error(f"Error: {e}")
                    st.exception(e)

    st.divider()

    # ── Load and display data ────────────────────────────────────────────────
    df = load_all_companies()
    briefs = load_briefs()

    if df.empty:
        st.info(
            "No data yet — run a search above to get started. "
            "Try sectors like **fintech**, **ai**, **healthtech**, **b2b saas**, or **climate tech**."
        )
        return

    st.caption(
        f"Showing {len(df)} companies across {df['_sector'].nunique()} sector(s) "
        f"· Last updated {datetime.now().strftime('%d %b %Y, %H:%M')}"
    )

    # ── Sidebar filters ────────────────────────────────────────────────────────
    with st.sidebar:
        st.header("Filters")

        sectors = ["All"] + sorted(df["_sector"].dropna().unique().tolist())
        selected_sector = st.selectbox("Sector", sectors)

        verdicts = ["All", "Strong — pursue", "Watch list", "Pass"]
        selected_verdict = st.selectbox("Verdict", verdicts)

        filter_hiring = st.checkbox("Hiring companies only", key="filter_hiring")

        score_min = st.slider("Minimum score", 0, 100, 0)

        st.divider()
        st.caption(f"{len(briefs)} brief(s) generated")

    # ── Apply filters ─────────────────────────────────────────────────────────
    filtered = df.copy()
    if selected_sector != "All":
        filtered = filtered[filtered["_sector"] == selected_sector]
    if selected_verdict != "All":
        filtered = filtered[filtered["verdict"] == selected_verdict]
    if filter_hiring and "is_hiring" in filtered.columns:
        filtered = filtered[filtered["is_hiring"] == True]
    filtered = filtered[filtered["total_score"] >= score_min]
    filtered = filtered.sort_values("total_score", ascending=False)

    # ── Summary metrics ───────────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)
    strong = len(filtered[filtered["verdict"] == "Strong — pursue"])
    watch  = len(filtered[filtered["verdict"] == "Watch list"])
    avg_score = filtered["total_score"].mean() if not filtered.empty else 0

    col1.metric("Companies", len(filtered))
    col2.metric("Strong — pursue", strong)
    col3.metric("Watch list", watch)
    col4.metric("Avg score", f"{avg_score:.1f}")

    st.divider()

    if filtered.empty:
        st.info("No companies match the current filters.")
        return

    # ── Table ─────────────────────────────────────────────────────────────────
    display_cols = ["name", "batch", "location", "total_score", "verdict",
                    "is_hiring", "_sector"]
    display_cols = [c for c in display_cols if c in filtered.columns]
    table_df = filtered[display_cols].copy()

    table_df["verdict"] = table_df["verdict"].apply(lambda v: f"{verdict_colour(v)} {v}")
    if "is_hiring" in table_df.columns:
        table_df["is_hiring"] = table_df["is_hiring"].apply(lambda x: "Yes" if x else "")
    table_df = table_df.rename(columns={
        "name": "Company", "batch": "Batch", "location": "Location",
        "total_score": "Score", "verdict": "Verdict",
        "is_hiring": "Hiring", "_sector": "Sector",
    })

    st.subheader(f"Companies ({len(filtered)})")

    selected_name = st.selectbox(
        "Select a company to see full detail",
        options=filtered["name"].tolist(),
        index=0,
    )

    st.dataframe(
        table_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Score": st.column_config.ProgressColumn(
                "Score", min_value=0, max_value=100, format="%.1f"
            )
        }
    )

    if selected_name:
        st.divider()
        company = filtered[filtered["name"] == selected_name].iloc[0].to_dict()
        _render_company_detail(company, briefs)


def _render_company_detail(company: dict, briefs: dict):
    name    = company.get("name", "")
    verdict = company.get("verdict", "")
    score   = company.get("total_score", 0)

    col_a, col_b = st.columns([3, 1])
    with col_a:
        st.subheader(f"{name}")
        st.caption(
            f"{company.get('batch','?')}  ·  "
            f"{str(company.get('location','?'))[:40]}  ·  "
            f"{str(company.get('_sector','?')).title()}"
        )
        desc = company.get("one_liner") or company.get("description", "")
        if desc:
            st.write(str(desc)[:200])
        if company.get("website"):
            st.link_button("Visit website", company["website"])

    with col_b:
        st.metric("Score", f"{score}/100")
        st.write(f"{verdict_colour(verdict)} {verdict}")
        if company.get("is_hiring"):
            st.success("Currently hiring")

    breakdown = company.get("breakdown", {})
    if breakdown and isinstance(breakdown, dict):
        st.subheader("Score breakdown")
        labels = [k.replace("_", " ").title() for k in breakdown.keys()]
        values = list(breakdown.values())
        colours = ["#3b82f6" if v >= 7 else "#f59e0b" if v >= 5 else "#ef4444" for v in values]

        fig = go.Figure(go.Bar(
            x=values, y=labels, orientation="h",
            marker_color=colours,
            text=[f"{v:.1f}" for v in values],
            textposition="outside",
        ))
        fig.update_layout(
            xaxis=dict(range=[0, 10], title="Score (out of 10)"),
            yaxis=dict(autorange="reversed"),
            height=280,
            margin=dict(l=10, r=40, t=10, b=10),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, use_container_width=True)

    tags = company.get("tags", [])
    if tags:
        st.write(" ".join(f"`{t}`" for t in tags[:8]))

    articles = company.get("top_articles", [])
    if articles:
        st.subheader("Recent press")
        for a in articles[:3]:
            title  = a.get("title", "")
            source = a.get("source", "")
            url    = a.get("url", "")
            if title and url:
                st.markdown(f"- [{title[:80]}]({url})  _({source})_")

    brief_key = name.lower()
    brief_content = briefs.get(brief_key)
    if not brief_content:
        for k, v in briefs.items():
            if name.lower()[:8] in k:
                brief_content = v
                break

    if brief_content:
        st.subheader("Investment brief")
        st.markdown(brief_content)


if __name__ == "__main__":
    main()
