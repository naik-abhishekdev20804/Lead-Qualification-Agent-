"""Parse Tavily/Serper results into structured research fields (no LLM)."""

import re
from urllib.parse import urlparse

# Common B2B technologies to detect in scraped text
TECH_KEYWORDS = (
    "Salesforce", "HubSpot", "AWS", "GCP", "Google Cloud", "Azure", "Kubernetes",
    "Snowflake", "Shopify", "Stripe", "React", "Python", "Java", "SAP", "Oracle",
    "Microsoft 365", "Epic", "Workday", "Slack", "Zoom", "Datadog", "Segment",
    "Marketo", "Intercom", "Zendesk", "Twilio", "MongoDB", "PostgreSQL", "Redis",
    "Docker", "Terraform", "Cloudflare", "Okta", "Auth0", "SOC 2", "HIPAA",
)

GROWTH_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(?:raised|closes?|closed|announces?)\s+\$[\d.]+\s*[MBKmbk]?(?:\s+(?:Series|seed|round))?", re.I), "Funding round reported"),
    (re.compile(r"\bSeries\s+[A-F]\b", re.I), "Venture funding (Series round)"),
    (re.compile(r"\b(?:hiring|open roles|job openings|careers|recruiting)\b", re.I), "Active hiring / open roles"),
    (re.compile(r"\b(?:acquired|acquisition|merger|M&A)\b", re.I), "M&A activity"),
    (re.compile(r"\b(?:expansion|expands?|new market|APAC|EMEA|international)\b", re.I), "Geographic or market expansion"),
    (re.compile(r"\b(?:launched|launch|new product|copilot|platform release)\b", re.I), "New product or feature launch"),
    (re.compile(r"\b(?:partnership|partnered|strategic alliance)\b", re.I), "Strategic partnership"),
    (re.compile(r"\b(?:IPO|went public|public offering)\b", re.I), "IPO / public markets activity"),
]

SKIP_DOMAINS = frozenset({
    "linkedin.com", "www.linkedin.com", "facebook.com", "twitter.com", "x.com",
    "instagram.com", "youtube.com", "wikipedia.org", "crunchbase.com",
    "glassdoor.com", "indeed.com", "zoominfo.com", "bloomberg.com",
    "google.com", "news.google.com",
})


def is_placeholder_url(url: str) -> bool:
    """True when CRM website is missing or a demo placeholder domain."""
    if not url or not url.strip():
        return True
    lower = url.lower()
    return "example.com" in lower or lower in ("http://", "https://", "n/a", "none")


def discover_official_website(company_name: str, search_results: list[dict]) -> str | None:
    """Pick the most likely official company homepage from search hits."""
    company_tokens = [t.lower() for t in re.split(r"\W+", company_name) if len(t) > 2]
    if not company_tokens:
        return None

    best_url: str | None = None
    best_score = 0

    for hit in search_results:
        url = hit.get("url") or ""
        if not url.startswith("http"):
            continue
        parsed = urlparse(url)
        domain = (parsed.netloc or "").lower().removeprefix("www.")
        if any(domain == d or domain.endswith("." + d) for d in SKIP_DOMAINS):
            continue
        if any(tok in domain for tok in company_tokens):
            score = 10
            path = parsed.path.strip("/")
            if not path or path in ("home", "index.html"):
                score += 5
            if score > best_score:
                best_score = score
                best_url = f"{parsed.scheme}://{parsed.netloc}"

    return best_url


def extract_tech_stack(*texts: str) -> list[str]:
    """Find known technologies mentioned across combined text."""
    combined = " ".join(t for t in texts if t)
    found: list[str] = []
    for tech in TECH_KEYWORDS:
        if re.search(re.escape(tech), combined, re.I) and tech not in found:
            found.append(tech)
    return found[:12]


def extract_growth_signals(*texts: str) -> list[str]:
    """Derive growth signals from news snippets and answers."""
    combined = " ".join(t for t in texts if t)
    signals: list[str] = []
    for pattern, label in GROWTH_PATTERNS:
        if pattern.search(combined) and label not in signals:
            signals.append(label)
    return signals[:8]


def build_company_overview(answer: str, results: list[dict], site_description: str) -> str:
    """Prefer Tavily synthesized answer, then site meta, then top snippets."""
    if answer and len(answer.strip()) > 80:
        return answer.strip()[:2000]
    if site_description and len(site_description.strip()) > 40:
        return site_description.strip()[:2000]

    snippets = [r.get("snippet", "") for r in results[:4] if r.get("snippet")]
    if snippets:
        return " ".join(snippets)[:2000]
    return "No detailed company overview found from web research."


def build_recent_news(results: list[dict], news_results: list[dict]) -> str:
    """Combine news-topic hits into a readable news block."""
    hits = news_results or results
    lines: list[str] = []
    for hit in hits[:5]:
        title = hit.get("title", "").strip()
        snippet = hit.get("snippet", "").strip()
        if title and snippet:
            lines.append(f"{title}: {snippet}")
        elif snippet:
            lines.append(snippet)
        elif title:
            lines.append(title)
    return " ".join(lines)[:2500] if lines else "No recent news found."


def collect_sources(*result_lists: list[dict]) -> list[str]:
    """Deduplicated source URLs from all search result sets."""
    seen: set[str] = set()
    sources: list[str] = []
    for results in result_lists:
        for hit in results:
            url = hit.get("url", "")
            if url and url not in seen:
                seen.add(url)
                sources.append(url)
    return sources[:10]


def build_detailed_summary(
    overview: str,
    news: str,
    growth_signals: list[str],
    tech_stack: list[str],
    headings: list[str],
    website_excerpt: str,
) -> str:
    """Single long-form block for reps who need more than CRM fields."""
    parts = [f"## Overview\n{overview}"]
    if news:
        parts.append(f"## Recent news\n{news}")
    if growth_signals:
        parts.append("## Growth signals\n" + "\n".join(f"- {s}" for s in growth_signals))
    if tech_stack:
        parts.append("## Tech stack signals\n" + ", ".join(tech_stack))
    if headings:
        parts.append("## Website sections\n" + ", ".join(headings[:8]))
    if website_excerpt:
        parts.append(f"## Website excerpt\n{website_excerpt[:1200]}")
    return "\n\n".join(parts)
