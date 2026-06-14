import anthropic
import os
import re
import json
from datetime import datetime, timezone, timedelta

import gspread
from google.oauth2.service_account import Credentials

IST = timezone(timedelta(hours=5, minutes=30))
today = datetime.now(IST).strftime("%Y-%m-%d")

PROMPT = """Act as a Senior YouTube Content Strategist and Trend Research Analyst.

Your goal is NOT simply to find trending topics.

Your goal is to find topics that people are highly likely to click, watch, share, and discuss on YouTube.

Research the internet and identify topics with the highest potential for:

- High CTR (Click Through Rate)
- High Watch Time
- High Audience Retention
- High Shares
- High Comments
- Strong Search Demand
- Viral Growth Potential

---

## Research Sources

Analyze:

### Search Trends
- Google Trends
- Google Discover
- Exploding Topics

### Video Trends
- YouTube Trending
- YouTube Search Suggestions
- YouTube Shorts Trends

### Community Discussions
- Reddit
- Quora
- Hacker News

### News Sources
- TechCrunch
- VentureBeat
- Startup News
- Global News

### AI Sources
- OpenAI
- Anthropic
- Google AI
- Meta AI
- Hugging Face

### Social Sources
- X (Twitter)
- LinkedIn
- TikTok Trends

---

## Topic Evaluation Framework

For every topic calculate:

### Curiosity Score (0-100)
Does the topic make people say: "Wait... what?"

### Mass Appeal Score (0-100)
Can a non-expert understand it?

### Discussion Score (0-100)
Are people debating it?

### Search Demand Score (0-100)
Are people actively looking for it?

### Longevity Score (0-100)
Will people care in 30 days?

### YouTube Potential Score (0-100)
Would someone watch a 10-20 minute video on it?

---

## Viral Score Formula

Viral Score =
30% Curiosity +
25% Mass Appeal +
15% Search Demand +
15% Discussion +
15% Longevity

---

## Prioritize These Categories

### AI
- New AI breakthroughs
- AI replacing jobs
- AI startups
- AI tools
- Future predictions

### Technology
- Secret technologies
- Future inventions
- Billion-dollar startups
- Industry disruption

### Business
- Companies growing rapidly
- Startup success stories
- Business failures
- Market opportunities

### Science
- Space
- Longevity
- Health discoveries
- Physics breakthroughs

### Society
- Future of work
- Education changes
- Economic shifts
- Consumer behavior

---

## Output Format

Produce a markdown table with EXACTLY this format — one row per topic, pipe-delimited:

| Rank | Topic | Category | Why People Will Click | Viral Score | Search Demand | Competition | Suggested Title | Status |
|------|-------|----------|-----------------------|-------------|---------------|-------------|-----------------|--------|
| 1 | ... | ... | ... | 85 | High | Low | ... | PENDING |

Status must always be PENDING.

---

## Additional Requirement

After the table, for every selected topic generate:

### Suggested Titles (5)
### Thumbnail Hook (3)
### Video Angle
### Target Audience
### Estimated Longevity
### Monetization Potential

---

## Reject Topics If

- Pure celebrity gossip
- One-day news cycle
- Political drama
- Low information value
- No educational or curiosity component

---

## YouTube Opportunity Score Formula

YouTube Opportunity Score =
- 35% Curiosity Gap
- 25% Search Demand
- 20% Discussion Volume
- 10% Evergreen Potential
- 10% Monetization Potential

Target topics like:
- "AI agents replacing SaaS"
- "One-person billion-dollar companies"
- "The race to AGI"
- "Humanoid robots in factories"
- "Why Gen Z is abandoning traditional careers"

These outperform generic daily trending news because they combine trend + curiosity + long-term interest.

Today's date: """ + today + """

Research current trends as of today and produce the full ranked report."""

SHEET_HEADERS = [
    "Date", "Rank", "Topic", "Category",
    "Why People Will Click", "Viral Score",
    "Search Demand", "Competition", "Suggested Title", "Status",
]


def parse_table(text: str) -> list[list[str]]:
    """Extract data rows from the markdown table in the response."""
    rows = []
    in_table = False
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            if in_table:
                break
            continue
        # Skip header and separator rows
        if re.match(r"^\|\s*(Rank|---)", line, re.IGNORECASE):
            in_table = True
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) >= 8:
            rows.append(cells)
    return rows


def ensure_headers(sheet) -> None:
    """Add header row if the sheet is empty."""
    if sheet.row_count == 0 or not sheet.row_values(1):
        sheet.insert_row(SHEET_HEADERS, index=1)


def append_to_sheet(rows: list[list[str]]) -> None:
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    spreadsheet_id = os.environ.get("SPREADSHEET_ID")

    if not creds_json or not spreadsheet_id:
        print("GOOGLE_CREDENTIALS or SPREADSHEET_ID not set — skipping Sheets upload.")
        return

    creds_data = json.loads(creds_json)
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_data, scopes=scopes)
    gc = gspread.authorize(creds)

    sh = gc.open_by_key(spreadsheet_id)
    try:
        ws = sh.worksheet("Topics")
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title="Topics", rows=1000, cols=len(SHEET_HEADERS))

    ensure_headers(ws)

    sheet_rows = []
    for cells in rows:
        # Pad or trim to exactly 9 columns (without Date), then prepend date
        padded = (cells + [""] * 9)[:9]
        padded[-1] = "PENDING"   # enforce status
        sheet_rows.append([today] + padded)

    if sheet_rows:
        ws.append_rows(sheet_rows, value_input_option="USER_ENTERED")
        print(f"Appended {len(sheet_rows)} topics to Google Sheet.")


# ── Main ──────────────────────────────────────────────────────────────────────

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

print(f"Running YouTube research for {today}...")

response = client.messages.create(
    model="claude-opus-4-6",
    max_tokens=8000,
    tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 10}],
    messages=[{"role": "user", "content": PROMPT}],
)

# Extract text blocks
output_parts = [block.text for block in response.content if hasattr(block, "text")]
output = "\n\n".join(output_parts)

# Save markdown report
os.makedirs("outputs", exist_ok=True)
output_path = f"outputs/{today}.md"
with open(output_path, "w", encoding="utf-8") as f:
    f.write(f"# YouTube Research Report — {today}\n\n")
    f.write(output)
print(f"Saved: {output_path}")

# Parse table and push to Google Sheets
rows = parse_table(output)
print(f"Parsed {len(rows)} topics from table.")
append_to_sheet(rows)

print(f"Input tokens:  {response.usage.input_tokens}")
print(f"Output tokens: {response.usage.output_tokens}")
