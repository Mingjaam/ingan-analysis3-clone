# Inner AI Lab Landing Clone

`ingan.ai` 인스타그램 심리 분석 랜딩의 전환 구조를 참고해 만든 원본 구현 클론입니다.

## 포함된 플로우

- 첫 화면: 고정 헤더, 8개 심리 카드, 인스타그램 ID 입력, 금색 CTA
- 긴 랜딩: 연구팀 소개, 후기, 리포트 미리보기, 분석 방식, FAQ, 하단 CTA
- 분석 시작 플로우: ID 입력 → 계정 소유 여부 선택 → 스페셜 질문 선택 → 성별/출생년도 입력 또는 건너뛰기 → 분석 중 상태

## 실행

```bash
cd /Users/mingjam/Development/ingan-analysis3-clone
python3 -m http.server 4174
```

브라우저에서 `http://127.0.0.1:4174`로 확인합니다.

## 메모

상표, 실제 이미지, 원문 후기, 실제 API 호출은 복제하지 않았습니다. 동일한 UX 흐름과 시각 톤을 재현하는 정적 프로토타입입니다.
