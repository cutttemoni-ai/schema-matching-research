"""Constrain generated IDs as well as validating them after inference."""
import json
from .models import MatchResponse


def json_schema_for_request(contents, reason_max_chars=None):
    payload=json.loads(contents)
    schema=MatchResponse.model_json_schema()
    properties=schema["$defs"]["Recommendation"]["properties"]
    properties["source_id"]={"type":"string","enum":[c["id"] for c in payload["source_columns"]]}
    properties["target_id"]={"anyOf":[{"type":"string","enum":[c["id"] for c in payload["target_fields"]]},{"type":"null"}]}
    if reason_max_chars is not None:
        properties['reason']['maxLength']=reason_max_chars
    schema["properties"]["mappings"].update(minItems=len(payload["source_columns"]),maxItems=len(payload["source_columns"]))
    return schema
