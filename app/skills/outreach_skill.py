"""Outreach playbook — email drafting guidelines for the outreach agent.

The actual template logic lives in outreach_tool.py (deterministic, no LLM).
This skill supplies the agent with tone, structure, and human-approval rules.
"""

OUTREACH_PLAYBOOK = """
## Outreach principles

1. **Personalize** — reference something specific from CRM notes or research (never generic blasts).
2. **Match tier to urgency:**
   - **Hot** → direct CTA (schedule demo, send docs, book technical call)
   - **Warm** → qualifying question or light-touch value offer
   - **Cold** → no outbound email; recommend nurture only
3. **Keep emails short** — 3–5 sentences max. One clear ask.
4. **Never send without approval** — all drafts have status `pending_approval`.
5. **No PII in subject lines** — use company name, not personal email/phone.

## Email structure

```
Hi {first_name},

{personalized opener referencing their specific signal}

{one sentence of value prop tied to their situation}

{single clear CTA — question or meeting offer}

Best,
[Your name]
```

## Talking points rules

- Pull from CRM engagement notes first, then research growth signals.
- Hot leads: max 3 actionable points a rep can use on a call.
- Cold leads: focus on re-qualification triggers, not pitch points.
"""

EMAIL_OUTREACH_THRESHOLD = 55  # Warm and Hot get emails; Cold does not
