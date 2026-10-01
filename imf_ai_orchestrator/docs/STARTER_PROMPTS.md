# Starter prompts: kicking off an analysis in each chatbot

These short prompts are for running the workflow by hand in the ordinary chat windows. You don't need the
software or any APIs. If you run `python main.py run --mode manual`, the system generates the full prompts for
you. These short versions carry the same essential rules.

**Before you start**
- Use only **public** material unless your institution has approved the tool for anything more sensitive.
- Open a **fresh chat** for every step. Old conversations leak earlier framing into the new one.
- Use the model's web or deep-research mode for steps 2–3 and 5.
- **Keep the blind steps blind.** In steps 2 and 3, paste only the question and the neutral subquestions:
  never ChatGPT's hypotheses, and never another model's answer.
- Replace `<QUESTION>`, `<SUBQUESTIONS>`, `<CLAIMS>` and the other placeholders. Keep each model's reply; you
  pass parts of it to the next step.

---

## Step 1 · ChatGPT: frame the question (do not answer it)

```
You are the research architect for an IMF-style analysis. Do NOT answer the question yet.
Question: <QUESTION>
1) List every premise the question assumes and say whether public evidence establishes it (yes/no/unclear).
2) Restate the question neutrally.
3) Give 4–6 neutral subquestions that do not presuppose any answer.
4) Give at least 3 rival hypotheses, including "boring" ones (base effects, one-offs, reclassification, data revision), each with a mechanism and a falsification test.
5) List the data series and primary sources needed, with the vintage required.
Never invent sources or numbers.
```

## Step 1b · DeepSeek: challenge the framing

```
Here is a research question and its framing: <QUESTION + STEP-1 OUTPUT>
Do not answer the question. Find what the framing gets wrong: (a) premises that are assumed but not established — mark RED if they could change the conclusion; (b) subquestions a sceptical IMF reviewer would add (data quality, definitions, timing, counterfactuals, fiscal/monetary/external/financial spillovers, distribution, political economy); (c) credible rival hypotheses that are missing.
```

## Step 2 · Gemini (Deep Research): blind evidence search

Paste only the question and the neutral subquestions.

```
Research question: <QUESTION>
Subquestions: <NEUTRAL SUBQUESTIONS>
Build the evidence base; do not argue a thesis. Prioritise primary sources (IMF, ministry, central bank, statistics office, legislation), then multilaterals, then peer-reviewed work.
For each finding give: the claim; source title, institution, date, data vintage and URL; a VERBATIM quote copied from the source with page or table; and unit, period and definition for any number.
Search actively for contradicting evidence and list it. List gaps you could not fill.
If you cannot open a source, write REFERENCE NOT CONFIRMED. Never quote from memory, and never treat search snippets as evidence.
```

## Step 3 · DeepSeek and Claude: blind independent analysis (separate chats)

Paste only the question and the neutral subquestions. Send the same prompt to both models.

```
Research question: <QUESTION>
Subquestions: <NEUTRAL SUBQUESTIONS>
Work independently from first principles. (1) What mechanisms could produce the outcome? (2) Which rival explanations produce the same outcome, and what evidence would distinguish them? (3) Check for reverse causality, omitted variables, timing confusions, measurement and reclassification effects, and policy endogeneity. (4) Consider general-equilibrium, distributional and implementation effects.
State each conclusion as a numbered claim at the strength you can defend, on this scale: coincided with < associated with < may have contributed < likely contributed < contributed < key driver < caused. Mark what would falsify it. Cite only sources you can quote verbatim; otherwise say what evidence is needed.
```

## Step 4 · You (or ChatGPT): build the claim register

Merge the outputs of steps 2–3 into a numbered list. For each claim record: C-number, claim, type (fact, data,
causal, recommendation, risk…), importance (critical, material, supporting), which model proposed it, and the
verbatim quote and source. Where models disagree, **keep both claims**; never pick by majority.
*Check every quote yourself (Ctrl-F in the source).* This single step removes most hallucinated citations.

## Step 5 · Perplexity: forensic claim audit

Send claims only, not the narrative.

```
Audit each claim below against primary sources. For each, return: status (VERIFIED / PARTIALLY_VERIFIED / NOT_VERIFIED / CONTRADICTED / OUTDATED / SOURCE_NOT_ACCESSIBLE); the strongest source with date and URL; a VERBATIM supporting quote with page or table; whether the wording is stronger than the source (and a corrected wording); and any contradicting or more recent evidence. Check period, country, units and definitions, and every number.
VERIFIED requires a verbatim quote. A citation is not evidence unless its text supports the claim.
<CLAIMS>
```

## Step 6 · Claude: adversarial review (fresh chat)

```
You are a demanding senior IMF reviewer who must defend this analysis under hostile questioning. Do not praise.
Below are the question, the claim register with audit results, and the competing analyses.
Attack: factual integrity (dates, definitions, vintages, staff estimates vs official data); causal logic (correlation vs causation, rival explanations, assumptions); macro logic (transmission, general-equilibrium and second-round effects); policy logic (does the instrument fit the mechanism? trade-offs, implementation); and institutional integrity (announced vs implemented, projections presented as outcomes, staff vs authorities' views).
For each problem give: the claim number, the issue, RED (could change the conclusion) or YELLOW, and what evidence or rewording would fix it. End with: "Would I sign off? Yes/No, because…".
<QUESTION + REGISTER + ANALYSES>
```

## Step 7 · Gemini: what is missing? (fresh chat)

```
Here is a claim register for <QUESTION> (document type: <SIP / policy note / Article IV section>).
Do not judge whether the claims are right; judge coverage only. Mark each item COVERED (cite claim numbers), NOT APPLICABLE (give a reason) or MISSING: premises tested; key facts with vintages; at least two rival explanations; transmission mechanism; data limitations and staff vs official data; risks; policy implications; political economy and implementation; distributional effects; spillovers.
Then list anything else a country-team economist would expect to see.
<REGISTER>
```

## Step 8 · ChatGPT: synthesis and response to every critique (fresh chat)

```
You are the chief analyst. Below are the verified claim register and the critiques from steps 5–7.
1) For EVERY critique, answer ACCEPTED / PARTIAL / REJECTED with an evidence-based reason. "I disagree" is not a reason.
2) Sort the claims into confirmed, qualified, competing, unresolved and rejected.
3) Write the strongest DEFENSIBLE thesis, citing claim numbers. It must be no stronger than its weakest critical claim. If the evidence does not settle the question, say so.
4) Give policy implications only after the diagnosis, each linked to claim numbers.
You may not upgrade any claim's wording or certainty.
```

If ChatGPT **rejects** a RED critique, paste its reason back to the critic (Claude or Perplexity) in that
model's chat: *"Your critique was rejected for this reason: <…>. Withdraw only if this cites evidence that
resolves your concern; otherwise uphold it and explain why."* If the critic upholds it, ask a third model to
rule (step 8b) or decide it yourself.

## Step 8b · Third model: adjudicate an upheld disagreement

```
Two analysts disagree. Critique: <…>. Rejection: <…>. Critic's reply: <…>. Relevant claims and sources: <…>.
Rule ONLY on the evidence cited, not on fluency, and not by counting votes: FOR_CRITIC, FOR_SYNTHESIZER, or ESCALATE (the evidence cannot settle it; a human must decide). Prefer ESCALATE to a guess.
```

## Step 9 · ChatGPT: draft from approved claims only (fresh chat)

```
Draft a <document type> using ONLY the approved claims below, at no more than their approved strength. After every sentence that states a fact, number, cause, forecast, risk or recommendation, add its claim tag, e.g. [C004]. Untagged sentences may only connect ideas.
Do not assert anything on the "do not assert" list. The staff appraisal may only use claims established earlier.
Use IMF style: message first; Point → Evidence → Interpretation → Qualification → Implication; authorities' views kept distinct from staff's; no rhetorical inflation.
<APPROVED CLAIMS> <DO-NOT-ASSERT LIST> <THESIS>
```

## Step 10 · Claude (substance) and Copilot (editorial): review the draft

**Claude:**
```
Compare every tagged sentence with the approved wording of its claim and flag ANY strengthening: causal, certainty, probability, scope, precision, numbers, dates, units, attribution. Also flag untagged sentences that carry facts or causal claims, and staff-appraisal conclusions not established in the body. Quote each sentence exactly.
<DRAFT> <APPROVED CLAIMS>
```

**Copilot (in Word):**
```
Edit this IMF draft for clarity, concision, headings that state messages, consistent terminology, acronyms, and table and number consistency. Do NOT add facts, numbers or causal claims, and do not strengthen any statement. Flag substantive concerns as comments instead of changing them. Rate each comment CRITICAL / HIGH / MEDIUM / LOW.
```

## Step 11 · You: final claim audit

Run `python main.py audit-draft --state <run>/state.json --draft final.md`. If you are working entirely by
hand, compare each tagged sentence with its approved wording. Any sentence stronger than its approved claim
goes back to step 9. Sign off only on what the register supports.
