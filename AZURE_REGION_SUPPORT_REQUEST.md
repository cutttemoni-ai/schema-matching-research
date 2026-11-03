# Azure 지원 요청 초안 — 전송하지 않음

제목: Azure for Students의 허용 리전과 Azure OpenAI GPT-4.1-mini 종량제 지원 리전 불일치

Azure for Students 구독 `f01f27b9-f573-4f0a-bfbc-4c1f883bcc5e`에서 학교 시제품 시연용으로 Azure OpenAI `gpt-4.1-mini` (2025-04-14), GlobalStandard 배포를 사용하려고 합니다. 학생 크레딧과 지출 제한을 유지하고자 하며 종량제 유료 구독 전환이나 예약 처리량은 원하지 않습니다.

East US 2의 모델 지원과 할당량은 확인했지만 리소스 생성 시 `RequestDisallowedByAzure`로 거부됩니다. 적용된 정책은 `sys.regionrestriction` / `Allowed resource deployment regions`이며, 허용 목록은 `indonesiacentral`, `indiasouthcentral`, `eastasia`, `malaysiawest`, `centralindia`입니다.

동아시아와 인도 중부에서 조회한 해당 모델은 GlobalProvisionedManaged SKU만 있고 종량제 할당량은 없습니다. 나머지 허용 리전 세 곳은 현재 Cognitive Services models/usages API의 지원 위치 목록에 없습니다. 이 구독에서 학생 크레딧으로 해당 모델의 GlobalStandard를 사용할 수 있는 공식 경로가 있는지 확인해 주세요. 가능하다면 East US 2 같은 지원 리전에 대한 승인된 허용 목록 조정 또는 공식 대안을 안내해 주세요.

대상 구성: 리소스 그룹 `schema-match-demo-rg`, 예정 리소스 `schema-match-demo-261102-a199b5`, 배포 이름 `schema-match-b`, capacity 10. 리소스 그룹만 생성되었으며 OpenAI 리소스·모델은 생성되지 않았습니다.

이 초안은 로컬 파일로만 준비했으며 Microsoft나 학교 관리자에게 전송하지 않았습니다. 구독 정책·권한·결제 설정도 변경하지 않았습니다.
