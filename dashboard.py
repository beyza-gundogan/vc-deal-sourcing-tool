"""
Deal sourcing dashboard
Run with: streamlit run dashboard.py

Reads all JSON files from outputs/ and displays a ranked,
filterable table of scored companies with score breakdowns,
press coverage, and generated investment briefs.
"""

import json
import glob
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path
from datetime import datetime

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Deal Sourcing Dashboard",
    page_icon="📊",
    layout="wide",
)

# ── Load data ─────────────────────────────────────────────────────────────────

@st.cache_data
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

    # Deduplicate by company name — keep highest score
    df = df.sort_values("total_score", ascending=False)
    df = df.drop_duplicates(subset=["name"], keep="first")

    # Extract breakdown scores into flat columns
    if "breakdown" in df.columns:
        breakdown_df = df["breakdown"].apply(
            lambda x: x if isinstance(x, dict) else {}
        ).apply(pd.Series)
        breakdown_df.columns = [f"score_{c}" for c in breakdown_df.columns]
        df = pd.concat([df, breakdown_df], axis=1)

    return df.reset_index(drop=True)


def load_briefs() -> dict:
    """Load any generated investment briefs from briefs/ folder."""
    briefs = {}
    for f in glob.glob("briefs/brief_*.md"):
        content = Path(f).read_text(encoding="utf-8")
        # Extract company name from filename
        name = Path(f).stem.replace("brief_", "").rsplit("_", 1)[0].replace("_", " ")
        briefs[name.lower()] = content
    return briefs


# ── Colour helpers ────────────────────────────────────────────────────────────

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
    df = load_all_companies()
    briefs = load_briefs()

    # ── Header ────────────────────────────────────────────────────────────────
    st.title("Deal sourcing dashboard")
    if df.empty:
        st.warning("No pipeline outputs found. Run the pipeline first:")
        st.code("python pipeline.py --sector fintech --limit 20")
        return

    st.caption(f"Last updated: {datetime.now().strftime('%d %b %Y, %H:%M')}  ·  "
               f"{len(df)} companies across {df['_sector'].nunique()} sectors")

    # ── Sidebar filters ────────────────────────────────────────────────────────
    with st.sidebar:
        st.header("Filters")

        sectors = ["All"] + sorted(df["_sector"].dropna().unique().tolist())
        selected_sector = st.selectbox("Sector", sectors)

        verdicts = ["All", "Strong — pursue", "Watch list", "Pass"]
        selected_verdict = st.selectbox("Verdict", verdicts)

        hiring_only = st.checkbox("Hiring companies only")

        if "batch" in df.columns:
            years = sorted(df["batch"].dropna().apply(batch_year).unique().tolist(), reverse=True)
            years = [y for y in years if y > 2000]
            if years:
                min_year = st.slider(
                    "Minimum batch year",
                    min_value=min(years),
                    max_value=max(years),
                    value=min(years),
                )
            else:
                min_year = 2000
        else:
            min_year = 2000

        score_min = st.slider("Minimum score", 0, 100, 0)

        st.divider()
        st.caption(f"{len(briefs)} brief(s) generated")

    # ── Apply filters ─────────────────────────────────────────────────────────
    filtered = df.copy()
    if selected_sector != "All":
        filtered = filtered[filtered["_sector"] == selected_sector]
    if selected_verdict != "All":
        filtered = filtered[filtered["verdict"] == selected_verdict]
    if hiring_only and "is_hiring" in filtered.columns:
        filtered = filtered[filtered["is_hiring"] == True]
    if "batch" in filtered.columns:
        filtered = filtered[filtered["batch"].apply(batch_year) >= min_year]
    filtered = filtered[filtered["total_score"] >= score_min]
    filtered = filtered.sort_values("total_score", ascending=False)

    # ── Summary metrics ───────────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)
    strong = len(filtered[filtered["verdict"] == "Strong — pursue"])
    watch  = len(filtered[filtered["verdict"] == "Watch list"])
    avg_score = filtered["total_score"].mean() if not filtered.empty else 0
    hiring_count = len(filtered[filtered.get("is_hiring", False) == True]) if "is_hiring" in filtered.columns else 0

    col1.metric("Companies", len(filtered))
    col2.metric("Strong — pursue", strong)
    col3.metric("Watch list", watch)
    col4.metric("Avg score", f"{avg_score:.1f}")

    st.divider()

    # ── Company table + detail panel ──────────────────────────────────────────
    if filtered.empty:
        st.info("No companies match the current filters.")
        return

    # Build display table
    display_cols = ["name", "batch", "location", "total_score", "verdict",
                    "is_hiring", "_sector"]
    display_cols = [c for c in display_cols if c in filtered.columns]
    table_df = filtered[display_cols].copy()

    # Format for display
    table_df["verdict"] = table_df["verdict"].apply(
        lambda v: f"{verdict_colour(v)} {v}"
    )
    if "is_hiring" in table_df.columns:
        table_df["is_hiring"] = table_df["is_hiring"].apply(
            lambda x: "Yes" if x else ""
        )
    table_df = table_df.rename(columns={
        "name": "Company", "batch": "Batch", "location": "Location",
        "total_score": "Score", "verdict": "Verdict",
        "is_hiring": "Hiring", "_sector": "Sector",
    })

    st.subheader(f"Companies ({len(filtered)})")

    # Company selector
    selected_name = st.selectbox(
        "Select a company to see full detail",
        options=filtered["name"].tolist(),
        index=0,
    )

    # Show table
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

    # ── Company detail panel ──────────────────────────────────────────────────
    if selected_name:
        st.divider()
        company = filtered[filtered["name"] == selected_name].iloc[0].to_dict()
        _render_company_detail(company, briefs)


def _render_company_detail(company: dict, briefs: dict):
    """Render the full detail panel for a selected company."""
    name    = company.get("name", "")
    verdict = company.get("verdict", "")
    score   = company.get("total_score", 0)

    # Header
    col_a, col_b = st.columns([3, 1])
    with col_a:
        st.subheader(f"{name}")
        st.caption(
            f"{company.get('batch','?')}  ·  "
            f"{company.get('location','?')[:40]}  ·  "
            f"{company.get('_sector','?').title()}"
        )
        if company.get("one_liner") or company.get("description"):
            st.write(
                (company.get("one_liner") or company.get("description",""))[:200]
            )
        if company.get("website"):
            st.link_button("Visit website", company["website"])

    with col_b:
        colour = score_colour(score)
        st.metric("Score", f"{score}/100")
        st.write(f"{verdict_colour(verdict)} {verdict}")
        if company.get("is_hiring"):
            st.success("Currently hiring")

    # Score breakdown chart
    breakdown = company.get("breakdown", {})
    if breakdown:
        st.subheader("Score breakdown")
        labels = [k.replace("_", " ").title() for k in breakdown.keys()]
        values = list(breakdown.values())
        colours = ["#3b82f6" if v >= 7 else "#f59e0b" if v >= 5 else "#ef4444"
                   for v in values]

        fig = go.Figure(go.Bar(
            x=values,
            y=labels,
            orientation="h",
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

    # Tags
    tags = company.get("tags", [])
    if tags:
        st.write(" ".join(f"`{t}`" for t in tags[:8]))

    # Press coverage
    articles = company.get("top_articles", [])
    if articles:
        st.subheader("Recent press")
        for a in articles[:3]:
            title   = a.get("title", "")
            source  = a.get("source", "")
            url     = a.get("url", "")
            if title and url:
                st.markdown(f"- [{title[:80]}]({url})  _({source})_")

    # Investment brief
    brief_key = name.lower()
    brief_content = briefs.get(brief_key)

    # Try fuzzy match if exact key not found
    if not brief_content:
        for k, v in briefs.items():
            if name.lower()[:8] in k:
                brief_content = v
                break

    if brief_content:
        st.subheader("Investment brief")
        st.markdown(brief_content)
    else:
        st.subheader("Investment brief")
        st.info(
            "No brief generated yet. Run:\n\n"
            f"```\npython brief_generator.py\n```"
        )


if __name__ == "__main__":
    main()
