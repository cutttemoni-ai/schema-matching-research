"""Pinned Ollama completion budget: prompt bytes upper bound != actual tokens.

JSON Schema is a decoder grammar, not prompt text in Ollama0.40.13's
llama-server completion path. Keep its size separately; no feature clipping.
Legacy limits and frozen campaigns are deliberately untouched.
"""
import json
from .limits import InputLimitError

VERSION='prompt-byte-upper-bound-v3-grammar-separated'
SOURCE='https://github.com/ollama/ollama/blob/v0.40.13/llm/llama_server.go'


def check_payload(payload):
    if payload['model']!='qwen3:4b' or payload['options']['num_ctx']!=8192 or payload['options']['num_predict']!=160:
        raise ValueError('This budget is pinned to unchanged qwen3:4b /8192/160')
    if [m['role'] for m in payload['messages']]!=['system','user']:
        raise ValueError('Two-message text-only protocol required')
    if payload.get('truncate') is not False or payload.get('shift') is not False:
        raise ValueError('Truncation/context shift must remain disabled')
    system=len(payload['messages'][0]['content'].encode('utf-8'))
    user=len(payload['messages'][1]['content'].encode('utf-8'))
    schema=len(json.dumps(payload['format'],ensure_ascii=False,separators=(',',':')).encode('utf-8'))
    bound=system+user+512+160
    result={'version':VERSION,'system_utf8_bytes':system,'user_utf8_bytes':user,
            'grammar_schema_utf8_bytes':schema,'schema_counted_in_prompt':False,
            'template_reserve_tokens':512,'output_token_limit':160,'prompt_context_upper_bound':bound,
            'context_token_limit':8192,'is_actual_token_count':False,'truncate':False,'shift':False,
            'legacy_v2_bound_with_schema':bound+schema,'source':SOURCE}
    if bound>8192:raise InputLimitError('Conservative prompt bound exceeds unchanged8192; no clipping',result)
    return result
