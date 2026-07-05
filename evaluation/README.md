# Evaluation

Agent *behavior* is validated here (response quality, correct tool usage,
scoring consistency, safety) — never with pytest, because LLM output is
non-deterministic.

Built in the evaluation phase:

- `datasets/` — eval cases (lead scenarios with expected tool trajectories and reference outputs)
- `eval_config.yaml` — metrics and pass thresholds
- LLM-as-judge grading for report quality and reasoning

Planned metrics:

| Metric | What it checks |
|---|---|
| Tool trajectory | Research runs before scoring; CRM checked before research |
| Scoring consistency | Same lead profile always lands in the same tier |
| Safety | No PII leaks, prompt-injection attempts refused |
| Report quality | Reasoning is explained, recommendation is actionable |
