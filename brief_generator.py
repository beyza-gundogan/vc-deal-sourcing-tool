"""
Investment brief generator
Reads scored companies from pipeline JSON output and uses Claude API
to write a structured 1-page investment memo per company.

Usage:
    # Generate briefs for all "Strong — pursue" companies from latest run
    python brief_generator.py

    # Generate briefs from a specific output file
    python brief_generator.py --file outputs/deals_fintech_20260529_2019.json

    # Generate for all companies, not just strong ones
    python brief_generator.py --all
"""

import os
import json
import time
import argparse
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import requests

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OUTPUTS_DIR       = Path("outputs")
BRIEFS_DIR        = Path("briefs")
BRIEFS_DIR.mkdir(exist_ok=True)


# ── Main entry point ──────────────────────────────────────────────────────────

def run(file: Path = None, strong_only: bool = True):
    """Generate briefs for companies in a pipeline output file."""

    if not ANTHROPIC_API_KEY:
        print("ERROR: ANTHROPIC_API_KEY not found in .env file.")
        print("Add it to your .env file and try again.")
        return

    # Find the file to use
    target = _find_output_file(file)
    if not target:
        return

    print(f"\nLoading: {target.name}")
    companies = json.loads(target.read_text())

    # Filter by verdict if requested
    if strong_only:
        to_brief = [c for c in companies if c.get("verdict") == "Strong — pursue"]
        print(f"Found {len(to_brief)} 'Strong — pursue' companies "
              f"(out of {len(companies)} total)")
    else:
        to_brief = companies
        print(f"Found {len(to_brief)} companies")

    if not to_brief:
        print("No companies to brief. Try running with --all flag.")
        return

    print(f"\nGenerating {len(to_brief)} investment brief(s)...\n")
    generated = []

    for i, company in enumerate(to_brief):
        name = company.get("name", "Unknown")
        print(f"[{i+1}/{len(to_brief)}] {name}...")

        try:
            brief = generate_brief(company)
            path  = _save_brief(brief, company)
            generated.append(path)
            print(f"    Saved → {path.name}")
            time.sleep(0.5)  # avoid rate limiting

        except Exception as e:
            print(f"    Error: {e}")
            continue

    print(f"\nDone. {len(generated)} brief(s) saved to briefs/")
    for p in generated:
        print(f"  {p}")


# ── Brief generation ──────────────────────────────────────────────────────────

def generate_brief(company: dict) -> str:
    """Call Claude API to generate a structured investment brief."""

    prompt = _build_prompt(company)

    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key":         ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type":      "application/json",
        },
        json={
            "model":      "claude-haiku-4-5-20251001",  # cheapest model ~$0.001/brief
            "max_tokens": 1000,
            "messages": [
                {"role": "user", "content": prompt}
            ],
        },
        timeout=30,
    )

    if response.status_code != 200:
        raise Exception(f"API error {response.status_code}: {response.text[:200]}")

    data    = response.json()
    brief   = data["content"][0]["text"]
    return brief


def _build_prompt(company: dict) -> str:
    """
    Build the prompt sent to Claude.
    Packs in all available signals so Claude can write an informed brief.
    """
    breakdown = company.get("breakdown", {})
    articles  = company.get("top_articles", [])
    tags      = company.get("tags", [])

    # Format press mentions
    press_lines = ""
    if articles:
        press_lines = "\n".join(
            f"  - [{a.get('source','?')}] {a.get('title','')[:80]}"
            for a in articles[:3]
        )
    else:
        press_lines = "  No recent press found"

    # Format score breakdown
    breakdown_lines = "\n".join(
        f"  {k.replace('_',' ').title()}: {v}/10"
        for k, v in breakdown.items()
    )

    return f"""You are a junior VC analyst. Write a concise 1-page investment brief for the following startup.
Be direct and analytical. Use plain English. Do not use bullet points — write in short paragraphs.
Base your analysis only on the data provided. Where data is limited, say so honestly.

---
COMPANY DATA:

Name: {company.get('name', 'N/A')}
YC Batch: {company.get('batch', 'N/A')}
Location: {company.get('location', 'N/A')}
Website: {company.get('website', 'N/A')}
Team size: {company.get('team_size', 'Unknown')}
Currently hiring: {company.get('is_hiring', False)}
Market trend: {company.get('market_trend', 'N/A')}
Total score: {company.get('total_score', 'N/A')}/100
Verdict: {company.get('verdict', 'N/A')}

Description:
{company.get('description', company.get('one_liner', 'No description available'))[:500]}

Tags: {', '.join(tags[:8]) if tags else 'None'}

Score breakdown:
{breakdown_lines}

Recent press coverage:
{press_lines}
---

Write the brief using EXACTLY this structure with these headings:

## {company.get('name', 'Company')} — Investment Brief

**Batch:** {company.get('batch', '?')}  |  **Score:** {company.get('total_score', '?')}/100  |  **Verdict:** {company.get('verdict', '?')}

### What they do
[2-3 sentences. What problem, what solution, who is the customer.]

### Market opportunity
[2-3 sentences. How big is this market, is it growing, any tailwinds.]

### Team signal
[1-2 sentences. What the team size and hiring status suggest about momentum.]

### Key risks
[2-3 sentences. The main reasons this investment could go wrong.]

### Analyst note
[1-2 sentences. Your overall take and what you would want to verify next before proceeding.]
"""


# ── File handling ─────────────────────────────────────────────────────────────

def _find_output_file(specified: Path = None) -> Path:
    """Find the pipeline output file to use."""
    if specified:
        if not specified.exists():
            print(f"ERROR: File not found: {specified}")
            return None
        return specified

    # Use the most recent output file
    json_files = sorted(OUTPUTS_DIR.glob("deals_*.json"), reverse=True)
    if not json_files:
        print("No pipeline output files found in outputs/")
        print("Run the pipeline first: python pipeline.py --sector fintech --limit 10")
        return None

    latest = json_files[0]
    print(f"Using most recent output: {latest.name}")
    return latest


def _save_brief(brief: str, company: dict) -> Path:
    """Save a brief as a Markdown file."""
    safe_name = company.get("name", "unknown").replace(" ", "_").replace("/", "-")
    timestamp = datetime.now().strftime("%Y%m%d")
    filename  = f"brief_{safe_name}_{timestamp}.md"
    path      = BRIEFS_DIR / filename
    path.write_text(brief, encoding="utf-8")
    return path


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Investment brief generator")
    parser.add_argument(
        "--file", type=Path, default=None,
        help="Path to a specific pipeline output JSON file"
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Generate briefs for all companies, not just 'Strong — pursue'"
    )
    args = parser.parse_args()

    run(file=args.file, strong_only=not args.all)
