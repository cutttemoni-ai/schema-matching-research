# v2 실제 출력 계약 호환성 검증

보고 2026-11-02T15:37:44.917103+00:00. 기존 동결 train/validation 캠페인의 같은3 ID만 실행했다. 자동 추론 재시도0. 본 평가와 합산하지 않는다.

문제: train / 32051842_5_1757891723986774036 / source_index0 / RANG / natural_none. 원격에서 처음3개 ID 모두not_found·active=null 확인후실행했다. 기존진단차단슬롯은보존했다.

| 방법 | 실행·회수·출력검증 | 의미 정답 | 상태/대상 | 근거 길이 | 입력/출력/캐시 | 서버 초 |
|---|---|---|---|---:|---|---:|
|B|True|False|matched/t_1b7ece62a8119932|[20]|242/78/0|51.77999334999993|
|C|True|False|matched/t_1b7ece62a8119932|[20]|1672/78/134|147.71476281899993|
|D|True|False|matched/t_1b7ece62a8119932|[20]|955/77/134|79.78913699700013|

strict gate 통과=True. 의미 정답 여부를 gate에 사용하지 않았다. 전체 압축 조각/응답SHA·요청/설정hash·ID·스키마·상태/대상·근거1~20자·완결성검증을통과한경우만True다. 새로운문제로교체하거나성공할때까지재호출하지않았다.

## B 원 응답

request `958bdaf3e591eeb29aeaf021df588d53`

```json
{
  "mappings": [
    {
      "source_id": "s_48bfd4039b4ca7fd",
      "target_id": "t_1b7ece62a8119932",
      "status": "matched",
      "reason": "RANG is likely a non"
    }
  ]
}
```

## C 원 응답

request `0d9802512896eb8309771d5d834b24f0`

```json
{
  "mappings": [
    {
      "source_id": "s_48bfd4039b4ca7fd",
      "target_id": "t_1b7ece62a8119932",
      "status": "matched",
      "reason": "RANG is a numeric ID"
    }
  ]
}
```

## D 원 응답

request `272aa552120f4844cab371d7022ffef9`

```json
{
  "mappings": [
    {
      "source_id": "s_48bfd4039b4ca7fd",
      "target_id": "t_1b7ece62a8119932",
      "status": "matched",
      "reason": "RANG is integer with"
    }
  ]
}
```
