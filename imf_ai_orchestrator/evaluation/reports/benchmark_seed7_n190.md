# Planted-error benchmark (n=190, seed=7)

False positives on the clean draft: 0 flagged sentence(s).
Baseline register failures (planted defects in the sample case, excluded from scoring): C009: ['BELOW_THRESHOLD', 'OUTDATED:1674d>548d', 'RED-10', 'RED-3'], C010: ['BELOW_THRESHOLD', 'RED-3']

| Planted error | Trials | Caught by code (any) | Caught by code (blocking) | 
|---|---|---|---|
| appraisal_overreach | 5 | 5/5 (100%) | 5/5 (100%) |
| attribution_swap | 9 | 9/9 (100%) | 9/9 (100%) |
| causal_strengthening | 12 | 12/12 (100%) | 12/12 (100%) |
| data_mismatch | 12 | 12/12 (100%) | 12/12 (100%) |
| date_shift | 9 | 9/9 (100%) | 9/9 (100%) |
| fabricated_quote | 11 | 11/11 (100%) | 11/11 (100%) |
| fabricated_source | 9 | 9/9 (100%) | 9/9 (100%) |
| hedge_removal | 16 | 16/16 (100%) | 16/16 (100%) |
| inflation_term | 7 | 7/7 (100%) | 7/7 (100%) |
| missing_risk | 11 | 11/11 (100%) | 11/11 (100%) |
| negation_flip | 12 | 12/12 (100%) | 12/12 (100%) |
| number_change | 11 | 11/11 (100%) | 11/11 (100%) |
| number_not_in_evidence | 10 | 10/10 (100%) | 10/10 (100%) |
| outdated_source | 12 | 12/12 (100%) | 12/12 (100%) |
| probability_strengthening | 13 | 13/13 (100%) | 13/13 (100%) |
| scope_widening | 11 | 11/11 (100%) | 11/11 (100%) |
| tag_to_unapproved | 9 | 9/9 (100%) | 9/9 (100%) |
| untagged_new_claim | 11 | 11/11 (100%) | 11/11 (100%) |
| **All** | 190 | 190/190 (100%) | 190/190 (100%) |

Code checks are deterministic. Errors they miss are what model reviewers must be tested on: run with `--mode live --reviewers claude,gemini,...` to compare reviewers on the same planted errors.