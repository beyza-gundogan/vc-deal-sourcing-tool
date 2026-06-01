VC Deal Sourcing Tool
An AI-powered pipeline that discovers, scores, and writes investment briefs for YC-backed startups — built to streamline early-stage deal sourcing workflow.
Instead of a junior analyst spending hours manually researching companies, this tool fetches 5,900+ YC startups, scores each one across 7 signals, and generates a written investment brief in seconds.
Demo

📹 https://drive.google.com/file/d/1gOcG_ouKZ0QMuPpujVNFmz8a_Ra2c0I8/view?usp=sharing

What it does
1. Discovery — fetches all 5,900+ YC-backed companies via the yc-oss public API, filters by sector (fintech, AI, healthtech, B2B SaaS, climate tech and more), and narrows to VC-stage companies from recent batches.
2. Scoring — scores each company across 7 weighted signals using live data from Companies House, NewsAPI, and Google Trends. Outputs a score out of 100 with a verdict: Strong — pursue / Watch list / Pass.
3. Brief generation — calls the Anthropic Claude API to write a structured 1-page investment memo per company covering what they do, market opportunity, team signal, key risks, and an analyst note.
4. Dashboard — a Streamlit web app that lets you browse, filter, and compare all scored companies with interactive score breakdown charts and inline investment briefs.

Scoring framework
SignalWeightData sourceTeam signal30%YC batch data + Companies House officersProduct traction20%Team size + company age proxyMarket timing15%Google Trends (pytrends)Hiring momentum10%NewsAPI hiring mentionsFunding velocity10%YC batch recencyNetwork proximity10%YC network proxyPress traction5%NewsAPI + Google News RSS

Example output
## Mono — Investment Brief
Batch: Winter 2022  |  Score: 77.0/100  |  Verdict: Strong — pursue

### What they do
Mono provides an API-first platform enabling companies across Latin America
to embed financial services without building their own fintech infrastructure.
The offering includes wallets, real-time payouts, Visa card issuance, and
multi-rail bank transfers.

### Market opportunity
Latin America's fintech and embedded finance markets are experiencing rapid
growth as regional payment infrastructure modernizes and financial inclusion
expands. The B2B API-infrastructure play positions Mono to capture value
across multiple verticals rather than competing in consumer banking.

### Analyst note
Mono shows genuine product momentum in a structurally attractive market.
Next steps should focus on verifying CAC, churn rates, and competitive
differentiation versus other LatAm fintech infrastructure plays.

Tech stack

Python 3.12
Streamlit — dashboard UI
Plotly — score breakdown charts
Anthropic Claude API — investment brief generation
Companies House API — UK company enrichment (free)
NewsAPI — press and hiring signals (free tier)
pytrends — Google Trends market timing (no key needed)
yc-oss API — YC company discovery (free, no key needed)


Setup
1. Clone the repo
bashgit clone https://github.com/beyza-gundogan/vc-deal-sourcing-tool.git
cd vc-deal-sourcing-tool
2. Create a virtual environment
bashpython -m venv venv
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows
3. Install dependencies
bashpip install -r requirements.txt
4. Set up API keys
Copy the example env file and fill in your keys:
bashcp .env.example .env
KeyWhere to get itCostCOMPANIES_HOUSE_API_KEYdeveloper.company-information.service.gov.ukFreeNEWS_API_KEYnewsapi.org/registerFreeANTHROPIC_API_KEYconsole.anthropic.com~$0.002/brief

pytrends (Google Trends) requires no API key at all.

5. Run the pipeline
bash# Score 20 fintech startups
python pipeline.py --sector "fintech" --limit 20

# Score AI companies currently hiring
python pipeline.py --sector "ai" --limit 15 --hiring-only

# Filter to UK companies only
python pipeline.py --sector "fintech" --limit 20 --region "UK"
6. Generate investment briefs
bashpython brief_generator.py
Automatically generates briefs for all "Strong — pursue" companies from the latest pipeline run. Briefs are saved to briefs/ as Markdown files.
7. Launch the dashboard
bashstreamlit run dashboard.py
Opens at http://localhost:8501 in your browser.

Project structure
vc-deal-sourcing-tool/
├── pipeline.py              # Main orchestrator
├── brief_generator.py       # Investment brief generator
├── dashboard.py             # Streamlit dashboard
├── scrapers/
│   ├── yc_discovery.py      # YC API discovery layer
│   ├── companies_house.py   # UK company enrichment
│   ├── news_scraper.py      # Press & hiring signals
│   ├── market_timing.py     # Google Trends scoring
│   ├── team_scorer.py       # Team signal scoring
│   └── sic_codes.py         # SIC code mappings
├── .env.example             # API key template
├── requirements.txt
└── README.md

Supported sectors
fintech · ai · b2b saas · healthtech · climate tech · proptech · edtech · legaltech · insurtech · cybersecurity · devtools

Built as part of a VC/PE career development project. Data sources: YC OSS API, Companies House, NewsAPI, Google Trends.
