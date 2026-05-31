# 작업 완료 검토 checklist

1. 테스트 전면 통과

```powershell
python -m unittest discover -s tests -v
```

- [ ] 모든 테스트 OK

## 2. 전용 md 동기화

[ ].py 에서,  [ ].md가 존재할경우, 그 md 파일은 python을 모르는 코드 및 국어 학자를 위한 파일이라고 생각해도 된다.

* [ ] 관련 md 업데이트

## 3. flow.md 동기화

flow.md는 코딩을 모르는 국어학자를 위한 md 파일이라고 생각해도 된다.

- [ ] 점수 공식 변경 시 `flow.md` 업데이트
- [ ] 지표 추가/제거 시 `flow.md` 업데이트
- [ ] 가중치 변경 시 `flow.md` 업데이트

## 4. html 수정

- [ ] index.html업데이트
- [ ] test_server.py 업데이트

## 5. 실제 데이터 무결성

- [ ] `saham_ai_data.xml` 등 실제 말뭉치로 파이프라인 실행 시 오류 없음
- [ ] score_0_1 범위 0.0~1.0 유지 (clamp 확인)
