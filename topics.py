"""
Topics for the weekly GTM / RevOps digest.

The digest no longer scrapes a 92-person Twitter list via web_search (X is not
reliably web-searchable and the batched calls hit rate limits). Instead each
topic below is researched with the last30days engine, which pulls real,
engagement-scored discussion from Reddit, Hacker News, GitHub, Polymarket, and
the web.

Phrase topics as discussion themes, not single nouns — the engine returns noise
on bare keywords like "SaaS" but rich signal on "product-led growth for SaaS".
"""

DIGEST_TITLE = "Weekly GTM & RevOps Digest"

# Each entry is researched independently, then all evidence is synthesized by
# theme into one email. Keep the list tight (4-6) — every topic is one engine
# run (~30-45s) plus its share of the synthesis prompt.
TOPICS = [
    "AI go-to-market (GTM) strategy for B2B SaaS",
    "RevOps and sales operations",
    "product-led growth for SaaS",
    "AI SDR and outbound sales automation",
    "B2B SaaS demand generation and marketing",
]
