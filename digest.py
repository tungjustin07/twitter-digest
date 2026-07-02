"""
Weekly GTM / RevOps Digest — research with last30days, summarize by theme, email.

Rebuilt (2026-07) to run on the last30days engine instead of scraping a curated
Twitter list. For each topic in topics.py the engine returns real, engagement-
scored discussion from Reddit, Hacker News, GitHub, Polymarket, and the web.
Claude then synthesizes the pooled evidence into a themed HTML digest and it is
emailed via Resend.

Usage:
    python digest.py             # full run + send email
    python digest.py --dry-run   # print to terminal, no email
"""

import argparse
import json
import logging
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

from topics import DIGEST_TITLE, TOPICS

load_dotenv(override=True)

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

# Sonnet gives the polished themed writeup; override with SYNTH_MODEL if desired.
MODEL             = os.getenv("SYNTH_MODEL", "claude-sonnet-4-6")
LOOKBACK_DAYS     = int(os.getenv("LOOKBACK_DAYS", "7"))
ITEMS_PER_TOPIC   = int(os.getenv("ITEMS_PER_TOPIC", "8"))   # top ranked candidates kept per topic
ENGINE_SOURCES    = os.getenv("ENGINE_SOURCES", "reddit,hackernews,github,polymarket")
ENGINE_TIMEOUT    = int(os.getenv("ENGINE_TIMEOUT", "300"))  # seconds per topic run

# last30days engine location. Override with LAST30DAYS_SCRIPT (e.g. in CI).
DEFAULT_ENGINE = Path.home() / ".claude" / "skills" / "last30days" / "scripts" / "last30days.py"
ENGINE_SCRIPT  = os.getenv("LAST30DAYS_SCRIPT", str(DEFAULT_ENGINE))

# ─────────────────────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────────────────────

Path("logs").mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.FileHandler("logs/digest.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("gtm-digest")

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def _extract_text(response) -> str:
    """Pull plain text from an Anthropic response object."""
    return "".join(block.text for block in response.content if hasattr(block, "text"))


# ─────────────────────────────────────────────────────────────────────────────
# RESEARCH (last30days engine)
# ─────────────────────────────────────────────────────────────────────────────

def run_engine(topic: str) -> list[dict]:
    """Run the last30days engine headless for one topic; return top ranked candidates."""
    if not Path(ENGINE_SCRIPT).is_file():
        log.error(f"last30days engine not found at {ENGINE_SCRIPT} — set LAST30DAYS_SCRIPT")
        return []

    cmd = [
        sys.executable, ENGINE_SCRIPT, topic,
        "--emit=json",
        f"--days={LOOKBACK_DAYS}",
        f"--search={ENGINE_SOURCES}",
    ]
    log.info(f"Researching: {topic}")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=ENGINE_TIMEOUT)
    except subprocess.TimeoutExpired:
        log.error(f"Engine timed out ({ENGINE_TIMEOUT}s) on: {topic}")
        return []
    if proc.returncode != 0:
        log.error(f"Engine exited {proc.returncode} on '{topic}': {proc.stderr[-300:]}")
        return []

    out = proc.stdout
    try:
        data = json.loads(out[out.index("{"):])  # progress may precede the JSON
    except (ValueError, json.JSONDecodeError) as e:
        log.error(f"Could not parse engine JSON for '{topic}': {e}")
        return []

    cands = data.get("ranked_candidates", [])[:ITEMS_PER_TOPIC]
    log.info(f"  {len(cands)} ranked items")
    return cands


def format_evidence(topic: str, cands: list[dict]) -> str:
    """Render one topic's candidates as a compact evidence block for the summarizer."""
    lines = [f"### Topic: {topic}"]
    for c in cands:
        src   = c.get("source", "?")
        title = (c.get("title") or "").strip()
        eng   = c.get("engagement")
        url   = c.get("url") or ""
        snip  = re.sub(r"\s+", " ", (c.get("snippet") or "")).strip()
        eng_s = f" (engagement: {eng})" if eng is not None else ""
        lines.append(f"- [{src}] {title}{eng_s}")
        if snip:
            lines.append(f"  quote: {snip}")
        if url:
            lines.append(f"  url: {url}")
    return "\n".join(lines)


def gather_all(topics: list[str]) -> str:
    """Research every topic and concatenate the evidence blocks."""
    blocks = []
    for topic in topics:
        cands = run_engine(topic)
        if cands:
            blocks.append(format_evidence(topic, cands))
    return "\n\n".join(blocks)


# ─────────────────────────────────────────────────────────────────────────────
# SUMMARIZE
# ─────────────────────────────────────────────────────────────────────────────

def summarize_by_theme(evidence: str, since_date: str) -> str:
    """Turn pooled engine evidence into a themed HTML digest fragment."""
    prompt = f"""Below is real, engagement-scored discussion collected over the past week (since {since_date}) from Reddit, Hacker News, GitHub, Polymarket, and the web, across go-to-market, RevOps, and B2B SaaS topics. Each item shows its source, a title, an engagement number (upvotes / points / likes), and often a top quote with a URL.

<evidence>
{evidence}
</evidence>

Write a weekly digest organized by THEME. Group the most interesting content into 4-7 sections. Themes should emerge from the evidence — e.g. AI GTM / agentic sales, RevOps & data, product-led growth, demand gen & AEO/GEO, hiring & the GTM engineer role, contrarian takes.

For each theme:
1. A bold, punchy thematic title.
2. 3-5 standout items. Prefer the highest-engagement and most substantive ones.
   Format each as:
   <blockquote>"Exact quote or tight paraphrase"<br><em>— source label (e.g. r/SalesOperations, Hacker News), engagement</em></blockquote>
   Add ONE sentence of context after a blockquote only if it needs it.

Rules:
- Lead with what real people are actually saying, weighted by engagement — not generic advice.
- Quote real content from the evidence; keep source attribution accurate.
- Where an item has a URL, wrap the source label in a link: <a href="URL">label</a>.
- Total length 700-1100 words. Quality over quantity — drop weak items.
- Output clean HTML using ONLY: <h2>, <p>, <blockquote>, <br>, <em>, <strong>, <a>.
- No preamble and no "Here is the digest" opener — start directly with the first <h2>.
- Do not use em-dashes; use " - " (hyphen with spaces)."""

    log.info("Summarizing by theme...")
    response = client.messages.create(
        model=MODEL,
        max_tokens=6000,
        messages=[{"role": "user", "content": prompt}],
    )
    return _extract_text(response)


# ─────────────────────────────────────────────────────────────────────────────
# RENDER EMAIL
# ─────────────────────────────────────────────────────────────────────────────

def render_html(digest_body: str, week_label: str, topic_count: int) -> str:
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f4f4f4;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
  <div style="max-width:620px;margin:32px auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.08)">

    <!-- Header -->
    <div style="background:#1a1a1a;padding:28px 32px">
      <p style="margin:0;font-size:11px;color:#888;text-transform:uppercase;letter-spacing:.1em">{DIGEST_TITLE}</p>
      <h1 style="margin:4px 0 0;font-size:24px;font-weight:700;color:#fff">{week_label}</h1>
      <p style="margin:6px 0 0;font-size:13px;color:#aaa">What people are actually saying across {topic_count} GTM topics · by theme</p>
    </div>

    <!-- Body -->
    <div style="padding:32px;font-size:14px;line-height:1.75;color:#333">
      <style>
        h2 {{ font-size:17px;font-weight:700;color:#1a1a1a;margin:28px 0 12px;padding-bottom:6px;border-bottom:2px solid #f0f0f0 }}
        blockquote {{ margin:12px 0;padding:12px 16px;background:#f8f8f8;border-left:3px solid #4f6ef7;border-radius:0 6px 6px 0;font-size:14px;line-height:1.65;color:#222 }}
        blockquote em {{ font-style:normal;font-size:12px;color:#888 }}
        blockquote a {{ color:#888;text-decoration:none;border-bottom:1px dotted #bbb }}
        p {{ margin:8px 0 }}
      </style>
      {digest_body}
    </div>

    <!-- Footer -->
    <div style="padding:16px 32px 24px;border-top:1px solid #f0f0f0">
      <p style="margin:0;font-size:11px;color:#bbb;text-align:center">
        Sourced from Reddit, Hacker News, GitHub, Polymarket &amp; the web via
        <a href="https://github.com/mvanhorn/last30days-skill" style="color:#bbb">last30days</a> ·
        engagement-ranked · AI-synthesized
      </p>
    </div>

  </div>
</body>
</html>"""


def render_text(digest_body: str, week_label: str) -> str:
    """Strip HTML tags for plain-text fallback."""
    text = re.sub(r"<br\s*/?>", "\n", digest_body, flags=re.IGNORECASE)
    text = re.sub(r"<h2[^>]*>", "\n## ", text)
    text = re.sub(r"</h2>", "\n", text)
    text = re.sub(r"<blockquote[^>]*>", "\n  > ", text)
    text = re.sub(r"</blockquote>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return f"{DIGEST_TITLE.upper()} — {week_label}\n{'=' * 50}\n{text.strip()}"


# ─────────────────────────────────────────────────────────────────────────────
# SEND EMAIL
# ─────────────────────────────────────────────────────────────────────────────

def send_email(subject: str, html: str, text: str):
    key = os.getenv("RESEND_API_KEY")
    if not key:
        log.warning("RESEND_API_KEY not set — skipping email")
        return
    try:
        import resend
        resend.api_key = key
        resend.Emails.send({
            "from":    os.getenv("EMAIL_FROM"),
            "to":      [os.getenv("EMAIL_TO")],
            "subject": subject,
            "html":    html,
            "text":    text,
        })
        log.info(f"Email sent to {os.getenv('EMAIL_TO')}")
    except Exception as e:
        log.error(f"Email failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def run(dry_run: bool = False):
    since_date = (datetime.now() - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    week_label = datetime.now().strftime("Week of %B %-d, %Y")
    log.info(f"Starting {DIGEST_TITLE} for {week_label} (since {since_date})")

    # 1. Research every topic with the last30days engine
    evidence = gather_all(TOPICS)
    if not evidence.strip():
        log.warning("No evidence gathered across all topics — aborting")
        return
    log.info(f"Collected {len(evidence.splitlines())} lines of evidence")

    # 2. Synthesize by theme
    digest_html = summarize_by_theme(evidence, since_date)

    # 3. Render
    html    = render_html(digest_html, week_label, len(TOPICS))
    text    = render_text(digest_html, week_label)
    subject = f"{DIGEST_TITLE} — {week_label}"

    if dry_run:
        print(text)
        return

    # 4. Send + save local copy
    send_email(subject, html, text)
    out = Path("logs") / f"digest-{datetime.now().strftime('%Y%m%d')}.html"
    out.write_text(html)
    log.info(f"Saved to {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print output, skip email")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
