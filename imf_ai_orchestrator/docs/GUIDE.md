# Orchestrating multiple AI models for IMF analytical work

**A guide to the design and operation of the multi-model orchestrator, version 1.1**

---

## Executive summary

**The aim.** Use several AI models so that the final product has faced the **highest level of scrutiny**,
has been **genuinely improved**, has **no unexamined blind spots**, and contains **no hallucinated facts,
numbers or citations**.

**The central insight.** Adding chatbots does not add scrutiny. Large language models are trained on
overlapping data and share the same misconceptions. They defer to whatever framing they are given, and they
tend to concede when another model pushes back. Five models agreeing is evidence that they converge, not that
they are right.

Scrutiny comes from **structure**:

1. **Code verifies; models argue.** Whether a quote exists, whether a number matches the data, whether a source
   is current, and whether a draft sentence says more than its approved claim are all checked by software,
   never by a model's say-so.
2. **No model family checks its own work.** Roles are assigned by a constraint solver. A family never grades,
   audits, reviews or adjudicates claims that the same family produced. If that cannot be guaranteed, the run
   stops.
3. **Independence is designed into what each model sees.** The researchers and analysts work blind on the raw
   question. The auditor sees claims, not prose. The drafter sees only approved claims.
4. **Every critique gets a recorded disposition.** The drafter cannot quietly dismiss criticism. A rejected
   critique goes back to its author, then to a third-family adjudicator, then to you. Nothing is decided by vote.
5. **Blind spots are found with a coverage map, not more reviewers.** There is a framing challenge, a
   checklist by document type, and an omission audit.
6. **The claim register is the database; the draft is a view of it.** Every material sentence carries a claim
   tag and is checked against the approved wording.
7. **Measure, don't assume.** A planted-error harness measures what each control actually catches, so that
   models, roles and prompts are chosen on evidence.
8. **You remain accountable.** The system's endpoint is a dashboard and a sign-off box, not a published
   document.

**Status.** Version 1.1 implements all of the above, with 23 passing tests and an end-to-end dry run on a
synthetic case. It runs in three modes:
- `mock`: no models, for testing;
- `manual`: it writes each prompt, you paste it into the chatbot and save the reply. No APIs are needed;
- `live`: API calls. The adapters are written but have **not been tested against live endpoints**.

---

## 1. Objectives, failure modes and controls

| Objective | How multi-model work typically fails | Control in v1.1 |
|---|---|---|
| **Highest scrutiny** | Reviewers anchor on the drafter's framing; the drafter judges critiques of its own work; models concede under pushback | Blind independent tracks; role constraints; disposition, rebuttal and adjudication flow; anti-sycophancy rules in every prompt |
| **Most effective improvements** | Critiques are vague; fixes re-run everything; nobody checks the fix landed | Every issue names claim IDs and a resolution path; targeted routing of only the affected claims; re-verification after each fix; at most 3 cycles, then stop and report |
| **No blind spots** | Everyone answers the question as posed; nobody asks what is missing | Premise check and framing challenge; coverage maps per document type; an omission auditor; a second red team at level 4; human dashboard |
| **Minimal hallucination** | Invented citations, altered quotes, wrong numbers, stale sources, and "verified" stamped by another LLM | Verbatim excerpts checked against retrieved sources; numbers checked against data; number provenance; vintage rules; an auditor's "VERIFIED" checked against its own quote; claim-strength audit of the draft |

---

## 2. Why more chatbots do not, by themselves, mean more scrutiny

- **Correlated errors.** The models learn from largely the same public text. A misconception common in the
  literature or the press is likely to be shared. Agreement is weak evidence.
- **Brand independence is partly illusory.** Microsoft Copilot runs largely on OpenAI models, so it is not
  independent of ChatGPT. Perplexity's answer engine can run on models from several labs. The system tracks a
  model **family** for each agent and enforces independence between families, not brands.
- **Anchoring.** A model shown a thesis tends to evaluate that thesis rather than the problem. If the first
  model frames the question and everyone else sees the framing, you have one analysis with several editors.
- **Sycophancy.** Told "the reviewer disagrees", models often reverse a correct position. Told "the author
  rejected your critique", they often withdraw it. Every prompt instructs models to change position only for
  evidence, and the disposition flow records who conceded and why.
- **A model checking a model is still a model.** An AI "source auditor" can report a passage as verified when
  the passage does not exist. Verification has to end in something a model cannot fake: the text of the source
  and the data series.

---

## 3. Architecture

### 3.1 Three layers that never collapse into one

| Layer | Question | Object |
|---|---|---|
| **Evidence** | What do we know? | Sources (retrieved, hashed, dated) and verbatim excerpts |
| **Analysis** | What do we infer? | The claim register: type, importance, S/E/C grades, status, approved wording |
| **Draft** | How do we say it? | Tagged prose, generated from approved claims and audited against them |

The most common failure of AI-assisted analysis is a plausible narrative that several models repeat until it
is treated as fact. The three-layer separation, plus the rule that only code can mark evidence as found, is
what prevents that.

### 3.2 The pipeline (level 3–4)

```
 QUESTION
   │  classify (rules; can escalate, never downgrade)        → level 0–4
   │  confidentiality gate (before EVERY transmission)
   ▼
 FRAME ─────────► FRAMING CHALLENGE          (different family from the framer)
   │  neutral subquestions only ↓
   ▼
 ┌──────────── BLIND, INDEPENDENT ───────────┐
 │ RESEARCHER        ANALYST A     ANALYST B  │  (three families; none sees the others or any thesis)
 └───────────────────────┬────────────────────┘
                         ▼
                   CLAIM REGISTER  (registrar: may weaken wording, never strengthen; author kept per claim)
                         ▼
         ┌───── MECHANICAL VERIFICATION (code) ─────┐
         │ fetch + hash sources · quote matching     │
         │ data checks · derived numbers · vintages  │
         │ number provenance · contradictions        │
         └───────────────────┬───────────────────────┘
                             ▼
           SOURCE AUDIT (per claim, never the author's family; its quotes are re-checked by code)
                             ▼
           GRADING (two graders of different families, neither the author's; minimum grade used)
                             ▼
           ADVERSARIAL REVIEW (+ a second, independent one at level 4)  ·  OMISSION AUDIT (coverage map)
                             ▼
           SYNTHESIS + a disposition for every issue
                             ▼
           ADJUDICATION: rejected critique → critic's rebuttal → third-family ruling → or human
                             ▼
           QUALITY GATE (code) ── not GREEN ──► targeted fixes on affected claims only (≤ 3 cycles)
                             │ RED blocks drafting
                             ▼
           DRAFT from approved claims only (every material sentence tagged [C###])
                             ▼
           SUBSTANCE review (≠ drafter family) · STRUCTURE review (≠ drafter family) · EDITORIAL review
                             ▼
           REVISION with dispositions
                             ▼
           FINAL CLAIM AUDIT (code): every sentence against approved wording
                             ▼
           FINAL GATE ──► DASHBOARD + HUMAN SIGN-OFF
```

### 3.3 Stage reference

| Stage | Role | Sees | Produces | Checked by code |
|---|---|---|---|---|
| Classify | code | question, document type | level and basis | keyword and document-type floors |
| Frame | framer | question, context | premises, neutral subquestions, rival hypotheses, falsification tests | premises "no"/"unclear" become issues |
| Challenge framing | framing challenger | question + framing | loaded premises, missing subquestions and hypotheses | logged as issues |
| Research | researcher (blind) | question, neutral subquestions | sources, candidate claims with verbatim excerpts | sources registered and deduplicated |
| Analysis | 2 analysts (blind) | question, neutral subquestions | mechanisms, rivals, candidate claims | author attached to each claim |
| Register | registrar | candidate claims, sources | merged register, approved wording | strengthening reverted; untraceable claims flagged |
| Verify | code | register, sources, data | quote, data, provenance, vintage and contradiction results | (is the check) |
| Audit | source auditor (per claim) | claims and evidence, no narrative | status plus verbatim excerpt | the auditor's excerpt must exist in the source |
| Grade | 2 graders (per claim) | claims, evidence, check results | S/E/C grades | minimum used; a spread ≥ 2 notches is flagged |
| Review | adversarial reviewer | register, tracks, issues | RED/YELLOW issues | — |
| Omissions | omission auditor | register, coverage map | coverage status, extra omissions | required claim types present |
| Synthesize | synthesizer | register, issues | thesis, findings, dispositions | relying on an unapproved claim → RED |
| Adjudicate | critic, then third family | disputed issue, claims | UPHELD/WITHDRAWN; ruling | unresolved → human |
| Gate | code | everything | GREEN / YELLOW / RED | (is the check) |
| Draft / revise | drafter | approved claims, do-not-assert list | tagged draft | — |
| Draft reviews | substance, structure, editorial | draft, approved claims | issues, scores | — |
| Final audit | code | draft, register | sentence-by-sentence findings | (is the check) |

---

## 4. Roles, not brands

Roles are allocated by `orchestrator/roles.py` from preference lists in `config/roles.yaml`. The default
allocation with all six models permitted for PUBLIC material:

| Role | Default | Constraint |
|---|---|---|
| Synthesizer, drafter, framer | ChatGPT | — |
| Framing challenger | DeepSeek | ≠ framer's family |
| Researcher | Gemini | — |
| Analysts (2) | DeepSeek, Claude | two different families, ≠ framer, ≠ researcher |
| Registrar | Gemini | ≠ synthesizer and drafter |
| Source auditor | Perplexity | per claim: ≠ the claim author's family |
| Graders (2) | Claude, Gemini | different families; per claim ≠ the author's family |
| Adversarial reviewer | Claude | ≠ synthesizer, drafter, registrar |
| Omission auditor, adjudicator | Gemini | ≠ synthesizer |
| Substance and structure reviewers | Claude, Gemini | ≠ drafter |
| Editorial reviewer | Copilot | editorial only; may not change substance |

**What changed from v1.**
- ChatGPT no longer classifies the task, owns the claim register, writes approved wording, or reviews the
  structure of its own draft.
- It still frames, synthesizes and drafts, which matches your stated preference. But every one of those
  outputs is checked by another family or by code.

**These defaults are a starting hypothesis.** Nothing in the evidence base says Claude is the best adversary or
Perplexity the best auditor, and model versions change every few months. Use the benchmark (§11) and
`rotation_seed` to test other allocations. A `rotate: true` flag on a role shuffles its preferences per run.

**Disclosure.** This guide and v1.1 were written by Claude, which is one of the six models assigned roles here.
The constraint solver, not the author's preference, decides who checks whom. The benchmark exists precisely so
that role assignments can be judged on measured performance.

---

## 5. Information-isolation rules (`config/exposure.yaml`)

| Role | Sees | Never sees |
|---|---|---|
| Researcher, analysts | question, neutral subquestions, context, documents | framing hypotheses, other tracks, any thesis, the register |
| Source auditor | individual claims, their evidence, source metadata | narrative, synthesis, draft |
| Graders | claims, evidence and its check results, the grading scale | other graders' grades, thesis |
| Drafter | approved claims, the do-not-assert list, synthesis, drafting standard | rejected/unresolved claims (except as do-not-assert), critiques |
| Critic (rebuttal), adjudicator | the disputed issue, relevant claims, sources | the rest of the debate |

The exposure builder refuses to run if a configuration edit would let a blind role see a forbidden field. The
fields each call actually received are recorded in `audit_log.jsonl`.

---

## 6. The claim register

**Claim types:** FCT, DAT, DEF, POL, REL, CAU, INT, FOR, RSK, CMP, REC, QUO, UNR.
**Importance:** CRITICAL, MATERIAL, SUPPORTING, MINOR.

**Three separate grades.** They are never collapsed into one confidence score, because an authoritative
source can still give weak support to a causal proposition.
- **S, source authority (S0–S5):** from unusable up to primary official sources.
- **E, evidence support for the approved wording (E0–E5):** from no support up to "directly establishes".
- **C, causal strength (C0–C5):** from an unsupported assertion up to strong identification.

**Conservative consensus.** Each claim is graded by two graders from different families, neither of them the
author's. The system uses the **lower** grade, and flags a disagreement of two or more notches for you.

**Pass rules** (`config/quality_gates.yaml`):

| Requirement | Applies to | Minimum |
|---|---|---|
| Source authority and evidence support | CRITICAL claims | S4 and E4 |
| Source authority and evidence support | MATERIAL claims | S3 and E3 |
| Causal grade required by the wording | causal, interpretive, relationship and recommendation claims | see below |

The causal grade required depends on the strongest causal phrase in the approved wording:

| Phrase | Minimum causal grade |
|---|---|
| "may/appears to have contributed" | C2 |
| "likely contributed" or "contributed to" | C3 |
| "key driver" | C4 |
| "caused" | C5 |

**Status is computed, never declared.** A claim is VERIFIED or QUALIFIED only if:
- its evidence was found in a retrieved source, or, for a recommendation, interpretation, risk or forecast,
  the claims it depends on are all approved;
- its grades pass the rules above; and
- no automatic-RED condition applies to it.

Otherwise it is UNRESOLVED, and the drafter may not assert it.

**Recommendations** must record `depends_on`, the diagnostic claims they rest on, and the chain: diagnosis →
mechanism → objective → instrument → implementation → trade-off.

---

## 7. Defences against hallucination, in layers

| Layer | What it catches | How |
|---|---|---|
| 1. Verbatim excerpts | paraphrased or invented quotations | Every evidence item must quote the source; the prompts say this will be checked |
| 2. Source retrieval | non-existent or inaccessible sources | Each source is opened (local file or URL), its text hashed and its retrieval date recorded |
| 3. Quote matching | altered or fabricated quotes | Token-level match against the source. Near-matches are tolerated only for extraction noise such as hyphenation, ligatures or articles; a changed content word or number fails |
| 4. Data checks | wrong numbers | Values compared with data connectors (CSV extracts of WEO/IFS/GFS or authorities' data; the World Bank API when live); derived numbers recomputed from their formula |
| 5. Number provenance | numbers that appear in wording but in no evidence | Every number in a claim must appear in a verified excerpt or a matching data point |
| 6. Vintage | stale sources presented as current | Maximum source age by claim type (default: 18 months for data claims) |
| 7. Auditor's own quote | an auditor that "verifies" what isn't there | Its quote is re-checked; failure downgrades the status, opens an issue and counts against that model in the reliability table |
| 8. Final claim audit | drift during drafting | Every tagged sentence compared with its approved wording; untagged material sentences flagged |

**What this cannot catch**, and therefore what models and you still own:
- a quote that exists but does not support the claim (the graders and the auditor judge this);
- a misreading of a correct table;
- missing context;
- a source that is authoritative but wrong.

---

## 8. Scrutiny: how critiques are handled

```
issue raised (by a reviewer, the auditor, or code)
   │
   ▼  synthesizer: ACCEPTED / PARTIAL / REJECTED + evidence-based rationale (mandatory)
   ├── ACCEPTED/PARTIAL → targeted fix → re-verify → resolved only if the claims now pass
   └── REJECTED → critic sees the rationale: WITHDRAWN (only if evidence resolves it) or UPHELD
                     └── UPHELD → adjudicator from a third family: FOR_CRITIC / FOR_SYNTHESIZER / ESCALATE
                                                                         └── ESCALATE → HUMAN_REQUIRED
```

- **Issues raised by code** (e.g. "quote not found") cannot be argued away. Rejecting one sends it straight
  to you.
- **Any RED issue that is not resolved** blocks the gate (RED-11).

---

## 9. Blind spots

1. **Premise check.** The framer must test the question's own assumptions ("why did X fail?" assumes X failed).
2. **Framing challenge.** A different family looks for loaded premises, missing subquestions and missing
   rival hypotheses before any research starts.
3. **Independent tracks.** Three families attack the raw question without seeing each other.
4. **Coverage maps** (`config/coverage.yaml`). Each document type has a checklist: analytical question, SIP,
   staff report, policy note.
   - The omission auditor must mark every item COVERED (with claim IDs), NOT APPLICABLE (with a reason) or
     MISSING.
   - Code adds a check: "Risks" counts as covered only if an approved RSK claim exists, and "Recommendations"
     only if an approved REC claim exists.
   - A missing mandatory item is RED-13.
5. **Second red team** at level 4, from a fourth family where available.
6. **You and the country team.** The dashboard lists what the system could not settle. Tacit knowledge
   (a recent mission finding, an unpublished data revision) enters as documents or as a reply to an issue.
   Tailor the coverage maps to your department's templates; they are the cheapest blind-spot control.

---

## 10. The quality gate

**Principle: the product may not rely on a failing claim.**
- A failing CRITICAL claim makes the gate RED.
- So does any failing claim that the thesis or the draft relies on.
- A failing MATERIAL claim that nothing relies on is kept as UNRESOLVED and makes the gate at most YELLOW.

**Automatic RED conditions:**

| Code | Condition |
|---|---|
| RED-1 | Critical claim with E0/E1 evidence, or a relied-upon claim below threshold |
| RED-2 | A number not verified against data or a matching excerpt, or a data mismatch |
| RED-3 | Material citation not confirmed (source missing/unreadable, or quote not found) |
| RED-4 | Causal wording stronger than the causal grade allows |
| RED-5 | A recommendation or judgment depends on an unapproved claim |
| RED-6 | Unexplained contradiction between authoritative (S4+) sources |
| RED-7 | Draft content not mapped to an approved claim, or tagged to an unapproved one |
| RED-8 | Draft strengthens wording, or changes a number, date, unit, scope, attribution or negation, or adds intensifiers |
| RED-9 | Staff appraisal introduces claims not established in the body |
| RED-10 | Outdated source for a claim presented as current |
| RED-11 | RED issue not resolved |
| RED-12 | Self-certification unavoidable (no independent family available for a claim) |
| RED-13 | Mandatory coverage item missing |

**Score.** Seven weighted dimensions sum to 100. Six are **deterministic**, computed from the register and the
draft audit. One, IMF drafting quality, is **model-judged** and is labelled as such on the dashboard so it
cannot hide a weak register.

**Status:**
- **GREEN:** score ≥ 85, no RED, no open YELLOW items.
- **YELLOW:** score 70–84, or open YELLOW items.
- **RED:** any automatic RED, or score < 70.

A RED analytical gate blocks drafting. Human sign-off is required from level 2.

---

## 11. Measuring what works: the planted-error benchmark

The right orchestration is an empirical question. `python main.py evaluate` takes a clean, approved case and
plants one known error per trial across 18 error types: changed numbers, shifted dates, causal strengthening,
dropped hedges, "could → will", scope widening, attribution swaps, untagged new claims, tags to unapproved
claims, appraisal overreach, intensifiers, negation flips, fabricated quotes, fabricated sources, numbers not
in the evidence, data mismatches, outdated sources, and a missing risk section. It then records which controls
caught each one.

**Results on the synthetic sample case (n = 190, seed 7).**
- **Code checks alone caught 190/190 planted errors** (all as blocking), with **0 false positives** on the
  clean draft.
- The first run of the benchmark caught only 9% of fabricated quotes and 0% of negation flips. Both checks were
  fixed. This is the harness doing its job.

**Read these results with care.** The same author wrote the checks and the error generators, and the case is
synthetic, so this is an in-sample result, a floor on what is mechanically catchable rather than a claim about
real-world accuracy. Real errors are subtler.

**How to use the benchmark to choose your setup:**
1. **Build 3–5 real cases** from past products with known errata (published corrigenda, review comments that
   caught real errors) and their sources.
2. **Run live reviewers on the same planted errors:**
   `python main.py evaluate --mode live --reviewers claude,gemini,deepseek,chatgpt`.
   Each reviewer's catch rate per error type appears as its own column.
3. **Compare designs on the same cases.** Examples:
   - code checks plus one reviewer, against code checks plus two;
   - reviewer A against reviewer B in a given role;
   - a single strong model with the full checklist, against the six-model pipeline.
4. **Track cost and time per run**, and the **reliability counters** on each dashboard (e.g. an auditor's
   "excerpt not found" count).
5. **Re-run whenever a model version or a prompt changes.**

---

## 12. Task levels

| Level | Use | Stages |
|---|---|---|
| 0 | factual retrieval | frame, research, register, verify, audit, grade, gate |
| 1 | factual/forensic | + framing challenge, review, synthesis |
| 2 | analytical question | + blind analysts, omission audit, adjudication |
| 3 | major product (SIP, policy note) | + drafting, three draft reviews, revision, final claim audit, final gate |
| 4 | high-stakes (DSA, conditionality, disputed data, legal/tax) | + second independent red team |

The level is the maximum of your request and a rule-based floor set by keywords and document type. Edit the
floors in `config/routing.yaml`.

---

## 13. Confidentiality and institutional constraints

- **The gate runs before every transmission,** including manual mode, because pasting into a chatbot is a
  transmission. Only mock mode sends nothing anywhere.
- **Defaults:** PUBLIC material is open to the listed providers. INTERNAL, CONFIDENTIAL and RESTRICTED are
  **closed**. Opening them requires an institutional approval reference and an explicit list of approved
  providers in `config/confidentiality.yaml`.
- **DeepSeek.** Its hosted service raises data-governance questions even for public material, because the
  queries reveal staff research interests. It is listed for PUBLIC with a warning comment; delete it if your
  institution's policy requires. The role solver will then reassign its roles.
- **Consumer subscriptions do not give API access.** Manual mode exists so the workflow can be run with
  ordinary chat accounts where policy allows.

---

## 14. Operating the system

### Install

```bash
pip install -r requirements.txt        # PyYAML; pypdf optional, for PDF sources
python -m unittest discover -s tests   # 23 tests
```

### Dry run on the synthetic case

```bash
python main.py run --case evaluation/cases/sample_case --level 3 --mode mock \
  --question "What explains the decline in Country A's energy-sector arrears?" --as-of 2026-09-30
```

The dry run demonstrates every control:
- a fabricated quote and an outdated source are caught (C009);
- a fabricated claim is rejected (C010);
- an overstated causal proposal ("drove") is held at its hedged wording, and the targeted fix adds rival
  explanations (C005);
- the auditor that rubber-stamped a fabricated quote is recorded against it;
- draft v1's "drove" and "unprecedented" are flagged and removed in revision.

The run ends **YELLOW** with honest open items.

### Manual mode (no APIs)

```bash
python main.py run --mode manual --confidentiality PUBLIC --document-type policy_note --level 3 \
  --question "<your question>" --documents-dir <folder with your PDFs/texts> --data-csv <extract.csv>
```

Each pending step writes `runs/<id>/manual/<step>.prompt.md`. Paste it into the named chatbot, save the full
reply as the matching `.reply.md` file, and run `python main.py resume <id>`. Parallel steps are issued
together. For quick, unstructured use without the software, see **`docs/STARTER_PROMPTS.md`**.

### Live mode

1. Set the `model` fields in `config/agents.yaml` to approved model identifiers.
2. Export the API keys.
3. Run with `--mode live`.

For research roles, use models with web access; for Gemini, set `web_search: true` on the agent. The adapters
use plain HTTPS (OpenAI-compatible, Anthropic and Gemini formats) and **have not yet been tested against live
endpoints**: run a level-0 PUBLIC question first.

### Outputs (`runs/<id>/`)

| File | Contents |
|---|---|
| `00_input.json` | run inputs |
| `01_classification.json` | task level and basis |
| `02_security.json` | gate result and role assignments |
| `03_framing*.json` | framing and challenge |
| `04_independent_tracks/` | blind track outputs |
| `05_claim_register_initial.json` | initial register |
| `06_source_register.json` | sources with hashes |
| `07_mechanical_verification_it*.json` | code checks per iteration |
| `08_source_audit_it*.json` | auditor results per iteration |
| `09_grades_it*.json` | grades per iteration |
| `10_review_*.json`, `10c_coverage.json` | adversarial reviews, coverage map |
| `11_synthesis.json` | thesis, findings, dispositions |
| `12_issues.json` | every issue, with disposition, rebuttal and ruling |
| `13_gate_*.json` | gate results |
| `14_draft_v1.md`, `15_draft_reviews/`, `16_draft_final.md` | drafts and reviews |
| `17_final_claim_audit_it*.json` | sentence-level audit |
| `18_final_audit.json` | consolidated result |
| **`19_dashboard.md`** | **what you sign off** |
| `audit_log.jsonl` | every call: model, settings, input fields, request hash |
| `calls/` | cached replies, which make runs reproducible and resumable |

### Checking any draft

```bash
python main.py audit-draft --state runs/<id>/state.json --draft my_revised_draft.md
```

---

## 15. Limitations and residual risks

- **Live adapters are untested.** Expect first-run fixes to request formats and model names.
- **Lexical strength detection.** The claim audit uses phrase ladders. It catches the common forms of
  overstatement, but a skilled paraphrase ("the waterfall was decisive") can evade it until the phrase is
  added to `config/strength.yaml`. The substance reviewer is the second line of defence. Extend the ladders
  with your house vocabulary.
- **Grades remain model judgments.** Mitigations: dual grading, the minimum rule, disagreement flags. Add human
  spot-checks of a sample of grades.
- **Data connectors.** The local CSV and World Bank connectors work. An IMF data connector must be configured
  against whichever endpoint your institution approves; it is intentionally not hard-coded.
- **Source retrieval.** Paywalled or scanned documents need to be supplied as files. Image-only PDFs need OCR
  first.
- **The benchmark result is in-sample** (§11). Real-case benchmarking is the most important next step.
- **The system supports judgment; it does not supply it.** The dashboard ends in a human decision by design.

---

## 16. Roadmap

1. **Real-case benchmark set:** 3–5 past products with known errata, and live reviewer comparison.
2. **First live run** at level 0–1 on PUBLIC material, to validate adapters.
3. **IMF data connector** against an approved endpoint, plus WEO/IFS extract templates.
4. **Coverage maps** aligned with the current Article IV and SIP guidance used by your department.
5. **Semantic strength check:** a second, model-based comparison of tagged sentences, scored separately from the
   lexical check and benchmarked against it.
6. **Word export** of the final draft with claim tags as comments, plus an Excel claim register.

---

## Appendix A: changes from v1.0

| v1.0 gap | v1.1 |
|---|---|
| No model calls; `agents/` empty | Adapters for mock, manual (paste into chatbots) and live (HTTPS) modes |
| YAML configs never read; pipelines duplicated in code | `config.py` loads and cross-validates every config file; nothing is hard-coded |
| Security gate passed INTERNAL with external AI off; advisory only | Gate checked before every transmission; INTERNAL+ closed without an approval reference |
| ChatGPT frames, owns the register, synthesizes, drafts, reviews its own structure, decides critiques | Constraint solver: no family grades, audits or reviews its own work; registrar ≠ drafter; disposition, rebuttal and adjudication flow |
| Independence stated but not enforced | Exposure whitelist per role; blind tracks; fields logged per call |
| Verification by one LLM (Perplexity) | Code verifies quotes, data, provenance and vintage; the auditor's own quote is re-checked |
| `exceeds_evidence()`: 4 phrases, never called | Strength ladders across 7 dimensions plus numbers, dates, units, negation, attribution and intensifiers; draft audit enforced in the gate |
| Automatic RED conditions were labels | 13 RED conditions computed from state |
| Quality score had no defined inputs | 6 deterministic dimensions plus 1 labelled model-judged |
| No iteration loop | Targeted routing by issue category; re-verification; at most 3 cycles, then stop and report |
| No blind-spot mechanism | Premise check, framing challenge, coverage maps, omission auditor, second red team |
| No way to tell which design is best | Planted-error benchmark with per-control and per-model detection rates |
| No audit trail | `audit_log.jsonl`, cached calls, numbered outputs, dashboard with sign-off |
| 3 trivial tests | 23 tests, including an end-to-end run and the benchmark |

## Appendix B: glossary of codes

**Draft-audit findings:**

| Finding | Meaning |
|---|---|
| `CAUSAL_STRENGTHENED` | causal language stronger than approved, a dropped hedge, or causal language added to a fact |
| `EPISTEMIC_STRENGTHENED` | e.g. "suggests" → "shows" |
| `PROBABILITY_STRENGTHENED` | e.g. "could" → "will" |
| `SCOPE_WIDENED` | e.g. "some" → "all" |
| `PRECISION_INFLATED` | an approximation removed |
| `NUMBER_CHANGED`, `DATE_CHANGED`, `UNIT_CHANGED` | a number, date or unit differs from the approved wording |
| `ATTRIBUTION_CHANGED` | e.g. authorities ↔ staff |
| `NEGATION_CHANGED` | a negation added or removed |
| `INFLATION_TERM_ADDED` | an intensifier or novelty word added |
| `UNMAPPED_MATERIAL` | untagged material sentence |
| `TAG_TO_UNAPPROVED` | sentence tagged to an unapproved claim |
| `APPRAISAL_NEW_CLAIM` | claim first appearing in the staff appraisal |
| `REWORDED` | large rewording (review, not blocking) |

**Mechanical flags:**

| Flag | Meaning |
|---|---|
| `QUOTE_NOT_FOUND` | excerpt not in the source |
| `UNKNOWN_SOURCE` | evidence cites a source not in the register |
| `NUMBER_NOT_IN_EVIDENCE` | a number in the wording appears in no verified excerpt or data point |
| `DATA_MISMATCH` | value differs from the data connector |
| `OUTDATED` | source too old for a current claim |
| `UNRESOLVED_CONTRADICTION` | S4+ source contradicts the claim |
| `SELF_CERT_UNAVOIDABLE` | no independent family available for a claim |
