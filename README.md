# twitter-digest

**Public repository.** Weekly GTM / RevOps digest: research real discussion with the [last30days](https://github.com/mvanhorn/last30days-skill) engine, synthesize by theme with Claude, and email an HTML digest via Resend.

Despite the historical name, this no longer scrapes a curated Twitter/X list. Each topic is researched across Reddit, Hacker News, GitHub, Polymarket, and the web, ranked by engagement, then written up by theme.

```bash
git clone https://github.com/tungjustin07/twitter-digest.git
cd twitter-digest
```

## What it does

1. For each topic in `topics.py`, run the last30days engine headless (`--emit=json`).
2. Keep the top ranked candidates per topic.
3. Ask Claude (default `claude-sonnet-4-6`) to group the evidence into 4–7 thematic sections.
4. Wrap the result in a styled HTML email and send it with Resend.

Default topics (edit `topics.py`):

- AI go-to-market (GTM) strategy for B2B SaaS
- RevOps and sales operations
- product-led growth for SaaS
- AI SDR and outbound sales automation
- B2B SaaS demand generation and marketing

## Layout

```
digest.py                         # research → synthesize → email
topics.py                         # DIGEST_TITLE + TOPICS list
requirements.txt
.env.example
.github/workflows/twitter-digest.yml   # Monday schedule + workflow_dispatch
```

## Setup

Requires Python 3.12+ (the last30days engine needs 3.12+).

```bash
pip install -r requirements.txt
cp .env.example .env
# fill in keys — never commit .env
```

### last30days engine

Locally, the script defaults to:

`~/.claude/skills/last30days/scripts/last30days.py`

Override with `LAST30DAYS_SCRIPT` if your install path differs. In GitHub Actions the workflow clones [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill) and points `LAST30DAYS_SCRIPT` at that checkout.

### Environment

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | yes | Claude API key |
| `RESEND_API_KEY` | yes (for send) | Resend API key |
| `EMAIL_FROM` | yes (for send) | From address |
| `EMAIL_TO` | yes (for send) | Recipient |
| `SYNTH_MODEL` | no | Override synthesis model (default `claude-sonnet-4-6`) |
| `LOOKBACK_DAYS` | no | Research window (default `7`) |
| `ITEMS_PER_TOPIC` | no | Ranked items kept per topic (default `8`) |
| `ENGINE_SOURCES` | no | Comma list (default `reddit,hackernews,github,polymarket`) |
| `LAST30DAYS_SCRIPT` | no | Path to `last30days.py` |

## Running

```bash
python digest.py             # full run + send email
python digest.py --dry-run   # print to terminal, no email
```

## GitHub Actions

Workflow: `.github/workflows/twitter-digest.yml`

- Schedule: Mondays `01:00` UTC (Sunday 6pm PT)
- Also runnable via **Actions → Weekly GTM & RevOps Digest → Run workflow**

Because this repo is **public**, configure these encrypted secrets only (Settings → Secrets and variables → Actions):

- `ANTHROPIC_API_KEY`
- `RESEND_API_KEY`
- `EMAIL_FROM`
- `EMAIL_TO`

## Security

- `.env` is gitignored — do not commit API keys
- Public forks will not receive your Actions secrets
- Logs under `logs/` are local-only and gitignored
