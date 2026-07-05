"""CRM lookup tool — reads the local sample CRM (zero API cost).

CRM stores minimum fields for demo: company name, industry, and notes.
Detailed company intel is fetched at runtime via Tavily + Firecrawl.
"""

import csv

from app.security import sanitize_crm_lead
from config import DATA_DIR

_LEADS_FILE = DATA_DIR / "sample_leads.csv"


def crm_lookup(query: str) -> dict:
    """Look up leads in the CRM by lead ID, name, or company name.

    Args:
        query: A lead ID (e.g. "L-001"), a person's name, or a company name.
               Pass "all" to list every lead in the CRM.

    Returns:
        dict with 'status' and 'leads' (list of matching lead records).
    """
    if not _LEADS_FILE.exists():
        return {"status": "error", "message": "CRM data file not found.", "leads": []}

    with open(_LEADS_FILE, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    q = query.strip().lower()
    if q == "all":
        matches = rows
    else:
        matches = [
            r for r in rows
            if q in r.get("lead_id", "").lower()
            or q in r.get("company", "").lower()
            or q in r.get("name", "").lower()
            or q in r.get("notes", "").lower()
        ]

    if not matches:
        return {"status": "not_found", "message": f"No lead matched '{query}'.", "leads": []}
    return {"status": "success", "leads": [sanitize_crm_lead(row) for row in matches]}
