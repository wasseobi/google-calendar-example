# AI 일정 관리 비서

이 프로젝트는 Google Calendar API와 OpenAI를 활용한 AI 기반 일정 관리 비서입니다. 사용자의 관심사와 일정을 분석하여 적절한 활동을 추천하고 일정을 관리합니다.

## 주요 기능

- Google Calendar 연동
- Azure Cosmos DB를 활용한 자기 성찰 데이터 저장
- OpenAI GPT-4를 활용한 활동 추천
- LangGraph를 활용한 워크플로우 관리

## 설치 방법

1. 저장소 클론
```bash
git clone [your-repository-url]
cd [repository-name]
```

2. 가상환경 생성 및 활성화
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate
```

3. 의존성 설치
```bash
pip install -r requirements.txt
```

4. 환경 변수 설정
`.env` 파일을 생성하고 다음 변수들을 설정하세요:
```
GOOGLE_OAUTH_CLIENT_ID=your_client_id
GOOGLE_OAUTH_CLIENT_SECRET=your_client_secret
USER_EMAIL=your_email
AZURE_COSMOS_ENDPOINT=your_cosmos_endpoint
AZURE_COSMOS_KEY=your_cosmos_key
OPENAI_API_KEY=your_openai_api_key
```

## 사용 방법

1. 샘플 데이터 업로드
```bash
python send_reflection.py
```

2. 메인 프로그램 실행
```bash
python main.py
```

## 프로젝트 구조

- `main.py`: 메인 프로그램
- `send_reflection.py`: 샘플 데이터 업로드 스크립트
- `requirements.txt`: 의존성 목록
- `.env`: 환경 변수 설정 파일

## 라이선스

이 프로젝트는 MIT 라이선스를 따릅니다. 