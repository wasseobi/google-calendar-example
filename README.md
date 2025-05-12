# AI 일정 관리 비서

이 프로젝트는 Google Calendar API와 OpenAI를 활용한 AI 기반 일정 관리 비서입니다. 사용자의 관심사와 일정을 분석하여 적절한 활동을 추천하고 일정을 관리합니다.

## 주요 기능

- Google Calendar 연동
- Azure Cosmos DB를 활용한 자기 성찰 데이터 저장
- OpenAI GPT-4를 활용한 활동 추천
- LangGraph를 활용한 워크플로우 관리

## 설치 및 설정 가이드

아래 순서대로 진행하면 "키 발급 → DB → 로컬 환경 → 데모 실행"까지 차근차근 완료할 수 있습니다.

### 1. Google Cloud 프로젝트 & OAuth 자격 증명 설정 (~20분)

1. **Google Cloud Console** 접속 → 새 프로젝트 생성
2. **APIs & Services ▸ Library** 메뉴에서 **Google Calendar API** 활성화
3. **APIs & Services ▸ Credentials** → **Create Credentials ▸ OAuth client ID** 선택
   - 애플리케이션 유형: **Desktop** (로컬 테스트용)
4. 생성된 **Client ID**와 **Client Secret** 복사 → `.env` 파일에 저장

> 💡 **팁**: 배포 시에는 "Web" 클라이언트로 변경하고 Redirect URI를 서버 도메인으로 지정하세요.

### 2. Azure Cosmos DB 설정 (~25분)

1. Azure Portal에서 **Create resource ▸ Azure Cosmos DB for NoSQL** 선택
2. 계정 생성 후 **Settings ▸ Features** → **Vector Search** 활성화
3. **Keys** 메뉴에서 **URI**와 **PRIMARY KEY** 복사 → `.env` 파일에 저장

> ⚠️ **주의**: Vector Search는 프리뷰 기능이므로, 지원 리전(East US, West Europe 등)을 선택하세요.

### 3. 로컬 개발 환경 설정 (~10분)

```bash
# 저장소 클론
git clone [your-repository-url]
cd [repository-name]

# 가상환경 생성 및 활성화
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate

# 의존성 설치
pip install -r requirements.txt
```

### 4. 환경 변수 설정 (~5분)

`.env` 파일을 생성하고 다음 변수들을 설정하세요:
```env
GOOGLE_OAUTH_CLIENT_ID=your_client_id
GOOGLE_OAUTH_CLIENT_SECRET=your_client_secret
USER_EMAIL=your_email
AZURE_COSMOS_ENDPOINT=your_cosmos_endpoint
AZURE_COSMOS_KEY=your_cosmos_key
OPENAI_API_KEY=your_openai_api_key
```

### 5. 샘플 데이터 업로드 (~5분)

```bash
python send_reflection.py
```

### 6. 메인 프로그램 실행 (~2분)

```bash
python main.py
```

- 브라우저에서 Google 계정 권한 동의
- AI 제안 목록에서 원하는 활동 선택
- Google Calendar에서 일정 확인

## 문제 해결 가이드

| 증상 | 확인 포인트 |
|------|------------|
| `ERR_ACCESS_DENIED` (캘린더) | SCOPES에 `calendar` 포함 여부, OAuth 테스트 사용자 추가 여부 |
| `403 vector search not enabled` | Cosmos DB Vector Search 활성화 여부, 컨테이너 vectorPolicy 설정 |
| `quota exceeded` | OpenAI API 사용량 제한 확인, `text-embedding-3-small` 모델 사용 |

## 프로젝트 구조

- `main.py`: 메인 프로그램
- `send_reflection.py`: 샘플 데이터 업로드 스크립트
- `requirements.txt`: 의존성 목록
- `.env`: 환경 변수 설정 파일

## 다음 단계

1. LangGraph 노드 추가 및 커스터마이징
2. Gradio 또는 React 기반 UI 개발
3. 배포 환경 설정 (Web 클라이언트로 전환)

## 라이선스

이 프로젝트는 MIT 라이선스를 따릅니다.
