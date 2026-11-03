# C accuracy development results

2026-11-03T04:30:41.266868+00:00. Original families8,2source-header conditions; variants are not independent. First recommendations only; no user corrections. Top1 includes review/errors/unexecuted. No old270/D scores merged.

|condition|method|correct/planned|Top1|review|semantic error|output error|API failure|unexecuted/uncertain|auto correct/links|coverage|
|---|---|---|---:|---:|---:|---:|---:|---|---|---:|
|original|A|3/8|37.5%|0|5|0|0|0/0|3/3|37.5%|
|original|C|7/8|87.5%|0|1|0|0|0/0|7/7|87.5%|
|original|product-matcher-v1|7/8|87.5%|0|1|0|0|0/0|7/7|87.5%|
|opaque|A|0/8|0.0%|0|8|0|0|0/0|0/0|0.0%|
|opaque|C|5/8|62.5%|3|0|0|0|0/0|5/5|62.5%|
|opaque|product-matcher-v1|4/8|50.0%|3|1|0|0|0/0|4/4|50.0%|

## Paired observations

{
  "planned": 16,
  "observed": 16,
  "missing": 0,
  "C_input": 66447,
  "v1_input": 111589,
  "input_change_ratio": 0.679368519270998,
  "C_standard_cost": 0.1123905,
  "v1_standard_cost": 0.180306,
  "cost_change_ratio": 0.604281500660643
}

Improved 0, worsened 1. Promotion gate descriptive pass: False; production remains C. Same count does not establish equivalence. Token/cost difference is not VM cost savings. Cache/thinking components missing in API remain missing; paired usage includes only both-side observations and reports exclusions.

## Profile coverage

{
  "source": {
    "unique_columns": 8,
    "types": {
      "string": 6,
      "integer": 2
    },
    "numeric_aggregate_columns": 2,
    "date_range_columns": 0,
    "partial_numeric_columns": 2,
    "unit_label_columns": 2
  },
  "target": {
    "unique_columns": 37,
    "types": {
      "string": 34,
      "integer": 3
    },
    "numeric_aggregate_columns": 3,
    "date_range_columns": 0,
    "partial_numeric_columns": 8,
    "unit_label_columns": 8
  }
}

## Cases

|source|condition|C correct/status/target|v1 correct/status/target|change|
|---|---|---|---|---|
|Latin name|original|False/no_match/None|False/no_match/None|same|
|Latin name|opaque|False/needs_review/rdf-schema#label|False/no_match/None|same|
|Vespasian|original|True/matched/rdf-schema#label|True/matched/rdf-schema#label|same|
|Vespasian|opaque|True/matched/rdf-schema#label|True/matched/rdf-schema#label|same|
|Sub Currency|original|True/matched/subunitName|True/matched/subunitName|same|
|Sub Currency|opaque|False/needs_review/subunitName|False/needs_review/subunitName|same|
|System|original|True/matched/computingPlatform|True/matched/computingPlatform|same|
|System|opaque|True/matched/computingPlatform|True/matched/computingPlatform|same|
|Industry|original|True/matched/industry|True/matched/industry|same|
|Industry|opaque|True/matched/industry|True/matched/industry|same|
|phone|original|True/matched/phone|True/matched/phone|same|
|phone|opaque|True/matched/phone|True/matched/phone|same|
|Met|original|True/matched/elevation|True/matched/elevation|same|
|Met|opaque|True/matched/elevation|False/needs_review/elevation|worsened|
|Elevation (metres)|original|True/matched/elevation|True/matched/elevation|same|
|Elevation (metres)|opaque|False/needs_review/elevation|False/needs_review/elevation|same|

## Scope and limits

Development8 families are reused/known-exposed; not independent evaluation. Final5families were never submitted before this campaign,3positive+2verified generated-lineage none. No natural none condition is evaluated. T2D annotated candidates are not the full target schema; external generated vertical partitions have lineage-audited complete matches. Same family variants remain together. Only small known-family separation, not proof against every partial/source/pretraining overlap. Official test-derived development families remain excluded thereafter.

Candidate retains all C categories and adds representative/partial-parse/format evidence jointly. Any outcome is a bundled-engine observation, not an isolated causal effect of one feature. Short model explanations do not reveal internal reasoning. No inference confidence probabilities or forced status repair. Real exports still require user confirmation. Explanation omission/mixed Korean-English/domestic enterprise data/production six-candidate accuracy and unit transformations are not validated here.

## Cumulative budget

{
  "at": "2026-11-03T04:30:41.544924+00:00",
  "categories": {
    "valid_output": 32
  },
  "C_actual_POSTs": 32,
  "C_reserved_slots": 32,
  "previous_D_experiment_POSTs": 366,
  "deployment_POSTs": 2,
  "global_actual_POSTs": 400,
  "C_reference_cost_usd": 0.2926965,
  "global_reference_commitment_usd": 2.0884935,
  "remaining_global_calls": 50,
  "remaining_reference_usd": 7.9115065,
  "recorded_C_seconds": 141.58436379994964,
  "automatic_inference_retries": 0
}