# Inner AI Lab Instagram Analysis Clone

`ingan.ai` 스타일의 인스타그램 심리 분석 랜딩과 분석 시작 플로우를 참고해 만든 구현체입니다. 이제 정적 클론뿐 아니라 Python 백엔드로 Instagram Login OAuth를 받고, 실제 Instagram Professional 계정 데이터를 가져와 결과 화면을 생성하는 구조를 포함합니다.

## 포함된 플로우

- 랜딩: 고정 헤더, 8개 심리 카드, 후기, 리포트 미리보기, FAQ, 하단 CTA
- 시작 플로우: ID 입력 → 계정 소유 여부 → 스페셜 질문 → 성별/출생년도 → Instagram Login
- 백엔드: OAuth callback → token 교환 → profile/media/comments/insights 수집 → 분석 결과 JSON 저장
- 결과 화면: 유형 카드, 요약, 분석 근거 수치, 무의식 지표, 챕터형 리포트, 잠금형 전체 리포트 CTA

## 중요한 제한

- 실제 데이터 분석은 GitHub Pages 같은 정적 배포만으로는 불가능합니다. `IG_APP_SECRET`을 브라우저에 둘 수 없기 때문에 Python 서버가 필요합니다.
- 공식 Instagram API는 Professional 계정(Business/Creator) 중심입니다. 개인 계정은 공식 API 접근이 제한됩니다.
- 앱이 Development mode일 때는 Meta App 역할/테스터에 등록된 계정만 로그인할 수 있습니다. 외부 사용자에게 열려면 Meta App Review가 필요합니다.
- 이 리포트는 자기이해/엔터테인먼트용이며 의학적 진단이 아닙니다.

## 설정

```bash
cd /Users/mingjam/Development/ingan-analysis3-clone
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

`.env`에 Meta Developers의 Instagram 앱 값을 넣습니다.

```bash
IG_APP_ID=...
IG_APP_SECRET=...
IG_REDIRECT_URI=http://127.0.0.1:5000/auth/instagram/callback
```

Meta App 설정의 Valid OAuth Redirect URIs에도 위 Redirect URI를 정확히 추가해야 합니다.

## 실행

```bash
python app.py
```

브라우저에서 `http://127.0.0.1:5000`을 엽니다.

## 테스트

```bash
python -m unittest discover -s tests
```

## API 구조

- `POST /api/analysis/start`: 분석 시작 payload를 받고 Instagram OAuth URL 반환
- `GET /auth/instagram/callback`: OAuth code 교환, 실제 Instagram 데이터 수집, 분석 결과 생성
- `GET /api/result/<result_id>`: 결과 화면용 분석 JSON 반환
- `GET /health`: 서버 상태와 Instagram 앱 설정 여부 확인
