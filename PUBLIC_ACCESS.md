# 공개 접속 전환 기록

2026-11-03 Asia/Seoul. 사용자가 Cloud Run과 GitHub의 공개 전환을 명시적으로 지시했다.

- 웹앱: https://schema-c-web-392692577987.asia-northeast3.run.app
- GitHub: https://github.com/cutttemoni-ai/schema-matching-research (PUBLIC)
- Cloud Run 서비스 schema-c-web / 프로젝트 schema-match-gemini-261103 / 리전 asia-northeast3에만 allUsers→roles/run.invoker를 추가했다. 인증 없는 HTTP GET200을 확인했다. 프록시·Google 로그인이 필요하지 않다.
- GitHub 현재 파일301개와 변경 전 전체 이력303개 blob에서 비밀 패턴이 발견되지 않았다. 실제 .env·ADC·키·raw runs·다운로드 원본은 계속 Git 제외다.
- 세션별 사용자 업로드·검토·결과 버킷은 비공개(public access prevention enforced)이며 버킷 IAM을 공개하지 않았다. 공개 방문자 전체 합계 일일20생성, 단일 유료 추론 동시 실행, 입력 한도·중복 제출 차단·보관 정책을 유지했다.
- 서비스 리비전 schema-c-web-00003-kcm과 모델/생성 설정은 변경하지 않았다. 모델 추론·평가 재실행0, 이미지 빌드·재배포0이다. 기존 연구 점수·원 기록을 변경하지 않았다.

실행한 변경 명령:

```powershell
gcloud --configuration=schema-research-gemini run services add-iam-policy-binding schema-c-web --project=schema-match-gemini-261103 --region=asia-northeast3 --member=allUsers --role=roles/run.invoker --quiet
gh repo edit cutttemoni-ai/schema-matching-research --visibility public --accept-visibility-change-consequences
```

이전 시점의 비공개 배포/저장소 언급은 해당 당시 기록이며 현재 접속 상태는 이 문서와 최신 README가 우선한다. 공개 웹앱의 Gemini 호출은 기존 서비스 계정으로 수행되므로 방문자의 ADC는 필요하지 않다. 로컬 개발에서 Vertex를 직접 호출하는 권한과 GitHub 쓰기 권한은 별개다.
