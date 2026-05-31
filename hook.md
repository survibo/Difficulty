# 작업 완료 검토 checklist

python unittest는 항상 돌릴필요는 없고, 큰 변경사항이 생겼을 때에만 실행한다.

## 1. 전용 md 동기화

[ ].py 에서,  [ ].md가 존재할경우, 그 md 파일은 python 문법을 모르는 coder 및 국어 학자를 위한 파일이라고 생각해도 된다.

* [ ] 관련 md 업데이트

## 2. flow.md 동기화

flow.md는 코딩을 모르는 국어학자를 위한 md 파일이라고 생각해도 된다.

- [ ] 점수 공식 변경 시 `flow.md` 업데이트
- [ ] 지표 추가/제거 시 `flow.md` 업데이트
- [ ] 가중치 변경 시 `flow.md` 업데이트

## 3. html 수정

- [ ] index.html업데이트
- [ ] test_server.py 업데이트

## 4. test 수정

- [ ] 관련 테스트 업데이트

## 5. 실제 데이터 무결성

- [ ] `saham_ai_data.xml` 등 실제 말뭉치로 파이프라인 실행 시 오류 없음
- [ ] score_0_1 범위 0.0~1.0 유지 (clamp 확인)
