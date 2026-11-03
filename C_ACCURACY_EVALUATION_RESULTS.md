# C accuracy evaluation results

2026-11-03T04:37:16.723712+00:00. Original families5,2source-header conditions; variants are not independent. First recommendations only; no user corrections. Top1 includes review/errors/unexecuted. No old270/D scores merged.

|condition|method|correct/planned|Top1|review|semantic error|output error|API failure|unexecuted/uncertain|auto correct/links|coverage|
|---|---|---|---:|---:|---:|---:|---:|---|---|---:|
|original|A|5/5|100.0%|0|0|0|0|0/0|3/3|60.0%|
|original|C|5/5|100.0%|0|0|0|0|0/0|3/3|60.0%|
|original|product-matcher-v1|5/5|100.0%|0|0|0|0|0/0|3/3|60.0%|
|opaque|A|2/5|40.0%|0|3|0|0|0/0|0/0|0.0%|
|opaque|C|3/5|60.0%|2|0|0|0|0/0|2/2|40.0%|
|opaque|product-matcher-v1|4/5|80.0%|1|0|0|0|0/0|3/3|60.0%|

## Paired observations

{
  "planned": 10,
  "observed": 10,
  "missing": 0,
  "C_input": 84166,
  "v1_input": 150188,
  "input_change_ratio": 0.7844260152555664,
  "C_standard_cost": 0.133899,
  "v1_standard_cost": 0.231057,
  "cost_change_ratio": 0.7256066139403583
}

Improved 1, worsened 0. Promotion gate descriptive pass: True; production remains C. Same count does not establish equivalence. Token/cost difference is not VM cost savings. Cache/thinking components missing in API remain missing; paired usage includes only both-side observations and reports exclusions.

## Profile coverage

{
  "source": {
    "unique_columns": 5,
    "types": {
      "string": 3,
      "integer": 2
    },
    "numeric_aggregate_columns": 2,
    "date_range_columns": 0,
    "partial_numeric_columns": 4,
    "unit_label_columns": 4
  },
  "target": {
    "unique_columns": 56,
    "types": {
      "integer": 26,
      "string": 24,
      "number": 4,
      "unknown": 2
    },
    "numeric_aggregate_columns": 30,
    "date_range_columns": 0,
    "partial_numeric_columns": 33,
    "unit_label_columns": 33
  }
}

## Cases

|source|condition|C correct/status/target|v1 correct/status/target|change|
|---|---|---|---|---|
|Capital City|original|True/matched/capital|True/matched/capital|same|
|Capital City|opaque|True/matched/capital|True/matched/capital|same|
|Participatory development and good governance|original|True/no_match/None|True/no_match/None|same|
|Participatory development and good governance|opaque|False/needs_review/None|False/needs_review/None|same|
|AgencyID|original|True/matched/AgID|True/matched/AgID|same|
|AgencyID|opaque|False/needs_review/AgID|True/matched/AgID|improved|
|doc_id|original|True/no_match/None|True/no_match/None|same|
|doc_id|opaque|True/no_match/None|True/no_match/None|same|
|Population|original|True/matched/populationTotal|True/matched/populationTotal|same|
|Population|opaque|True/matched/populationTotal|True/matched/populationTotal|same|

## Scope and limits

Development8 families are reused/known-exposed; not independent evaluation. Final5families were never submitted before this campaign,3positive+2verified generated-lineage none. No natural none condition is evaluated. T2D annotated candidates are not the full target schema; external generated vertical partitions have lineage-audited complete matches. Same family variants remain together. Only small known-family separation, not proof against every partial/source/pretraining overlap. Official test-derived development families remain excluded thereafter.

Candidate retains all C categories and adds representative/partial-parse/format evidence jointly. Any outcome is a bundled-engine observation, not an isolated causal effect of one feature. Short model explanations do not reveal internal reasoning. No inference confidence probabilities or forced status repair. Real exports still require user confirmation. Explanation omission/mixed Korean-English/domestic enterprise data/production six-candidate accuracy and unit transformations are not validated here.

## Cumulative budget

{
  "at": "2026-11-03T04:37:17.108963+00:00",
  "categories": {
    "valid_output": 52
  },
  "C_actual_POSTs": 52,
  "C_reserved_slots": 52,
  "previous_D_experiment_POSTs": 366,
  "deployment_POSTs": 2,
  "global_actual_POSTs": 420,
  "C_reference_cost_usd": 0.6576525,
  "global_reference_commitment_usd": 2.4534494999999996,
  "remaining_global_calls": 30,
  "remaining_reference_usd": 7.5465504999999995,
  "recorded_C_seconds": 356.82432349996816,
  "automatic_inference_retries": 0
}