"""Explicit rejection instead of clipping profiles, inputs or responses."""
import json


class InputLimitError(ValueError):
    def __init__(self,message,details):
        super().__init__(message)
        self.details=details


def check_request_limit(contents,instruction,schema,output_tokens,context_tokens=8192,reserve=512):
    content_bytes=len(contents.encode('utf-8'))
    system_bytes=len(instruction.encode('utf-8'))
    schema_bytes=len(json.dumps(schema,ensure_ascii=False,separators=(',',':')).encode('utf-8'))
    bound=content_bytes+system_bytes+schema_bytes+reserve+output_tokens
    result={'input_json_utf8_bytes':content_bytes,'system_utf8_bytes':system_bytes,
        'schema_utf8_bytes':schema_bytes,'framing_reserve_tokens':reserve,'output_token_limit':output_tokens,
        'conservative_context_bound':bound,'context_token_limit':context_tokens,
        'bound_is_actual_token_count':False,'truncate':False,'shift':False}
    if bound>context_tokens:
        raise InputLimitError('입력·출력 보수적 예산이 컨텍스트 8192를 초과합니다. 설명 또는 비교 열 범위를 줄여 새 비교를 시작하세요. 특징을 자동 삭제하지 않습니다.',result)
    return result
