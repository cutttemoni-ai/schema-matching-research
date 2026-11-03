# Product development results

Report UTC 2026-11-03T02:53:58.808189+00:00, frozen planfebc363253dbe422890ba7980ff32ec9b2587d38009273a55fdd1309e223ca2e. Strict Top1 includes reviews/API/output errors/unexecuted; same-source variants not independent. Auto-link eligibility is a matched/null-ID validated simulation before user edits, not actual automatic writes. Actual service exports require user confirmation. Natural no-match rate is unassessed if denominator0; generated-none is separate. Positive-only reference misses are unjudged, not invented negatives.

| condition | method | correct/planned | Top1 | auto-link precision lower bound | auto-link coverage | model review | categories |
|---|---|---:|---:|---:|---:|---:|---|
|original|A|2/6|33.3%|100.0%|33.3%|0.0%|{'semantic_error': 4, 'correct': 2}|
|original|C|5/6|83.3%|100.0%|83.3%|0.0%|{'semantic_error': 1, 'correct': 5}|
|original|C_no_categories|4/6|66.7%|100.0%|66.7%|33.3%|{'needs_review': 2, 'correct': 4}|
|original|D0|4/6|66.7%|100.0%|66.7%|33.3%|{'needs_review': 2, 'correct': 4}|
|original|D0_representatives|5/6|83.3%|100.0%|83.3%|0.0%|{'semantic_error': 1, 'correct': 5}|
|original|D1|5/6|83.3%|100.0%|83.3%|0.0%|{'semantic_error': 1, 'correct': 5}|
|opaque|A|0/6|0.0%|N/A|0.0%|0.0%|{'semantic_error': 6}|
|opaque|C|4/6|66.7%|100.0%|66.7%|33.3%|{'needs_review': 2, 'correct': 4}|
|opaque|C_no_categories|0/6|0.0%|N/A|0.0%|83.3%|{'needs_review': 5, 'semantic_error': 1}|
|opaque|D0|0/6|0.0%|N/A|0.0%|100.0%|{'needs_review': 6}|
|opaque|D0_representatives|4/6|66.7%|100.0%|66.7%|16.7%|{'semantic_error': 1, 'correct': 4, 'needs_review': 1}|
|opaque|D1|4/6|66.7%|100.0%|66.7%|16.7%|{'semantic_error': 1, 'correct': 4, 'needs_review': 1}|

All supplied usage/timing with observation/missing counts, generated/no-match false automatic links and type groups are in JSON; original usage nulls preserved. Costs use conservative1.5/7.5 perM, no cache/credit discounts, total-prompt outputs/thoughts once; current0.75/3.75 no-cache upper estimate is half. Actual bill/tax/credits unknown. Internal server time not supplied. No old Qwen/Gemini270 results merged.