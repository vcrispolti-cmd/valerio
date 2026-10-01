# IMF multi-model analytical orchestrator, v1.1

A Python orchestrator that makes several AI models scrutinise IMF-style analysis and drafting, and that uses
**code, not models, to verify evidence**.

- **Read first:** [`docs/GUIDE.md`](docs/GUIDE.md), the design, the controls, and how to operate and evaluate it.
- **Using chatbots by hand:** [`docs/STARTER_PROMPTS.md`](docs/STARTER_PROMPTS.md), short prompts for each
  model, in order.

## Quick start

```bash
pip install -r requirements.txt
python -m unittest discover -s tests

# dry run on the synthetic sample case (no model is contacted)
python main.py run --case evaluation/cases/sample_case --level 3 --mode mock \
  --question "What explains the decline in Country A's energy-sector arrears?" --as-of 2026-09-30
# then open runs/<id>/19_dashboard.md

# who checks whom under the current rules
python main.py roles --confidentiality PUBLIC

# planted-error benchmark
python main.py evaluate --n 190

# manual mode: paste generated prompts into the chatbots, no API needed
python main.py run --mode manual --confidentiality PUBLIC --question "..." --level 2
python main.py resume <run_id>
```

## Layout

| Path | Contents |
|---|---|
| `config/` | agents and model families, role constraints, confidentiality, exposure rules, gates, strength ladders, coverage maps, routing, taxonomy |
| `prompts/` | one prompt per **role**, plus `_common.md` (rules for all) and `drafting_standard.md` |
| `orchestrator/` | the pipeline, role solver, security gate, mechanical verification, strength audit, gate, adjudication, dashboard |
| `evaluation/` | planted-error harness and the synthetic sample case (fictional data, for testing only) |
| `schemas/` | JSON Schemas for claims, evidence, sources and issues |
| `tests/` | unit and end-to-end tests |
| `runs/` | run outputs (git-ignored) |

## Status and limits

- Mock and manual modes are tested end to end.
- Live API adapters are implemented but **not yet tested against live endpoints**.
- INTERNAL and higher material is blocked by default. Only an institutional decision recorded in
  `config/confidentiality.yaml` can open it.
- See GUIDE §15 for the remaining limitations.
