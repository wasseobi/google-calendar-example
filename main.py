import os, uuid, json
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from azure.cosmos import CosmosClient, PartitionKey
from openai import OpenAI
from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field

# ---------- 0. 환경 준비 ----------
load_dotenv()
SCOPES = ["https://www.googleapis.com/auth/calendar"]
TZ = pytz.timezone("Asia/Seoul")

# ---------- 1. Google Calendar 인증 ----------
def get_calendar_service():
    flow = InstalledAppFlow.from_client_config(
        {
            "installed": {
                "client_id": os.getenv("GOOGLE_OAUTH_CLIENT_ID"),
                "client_secret": os.getenv("GOOGLE_OAUTH_CLIENT_SECRET"),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost:8080/"],
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs"
            }
        },
        SCOPES
    )
    
    # OAuth 설정
    flow.redirect_uri = "http://localhost:8080"
    
    try:
        # 기존 토큰이 있는지 확인
        if os.path.exists('token.json'):
            from google.oauth2.credentials import Credentials
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
            if not creds.expired:
                print("✅ 기존 인증 토큰을 사용합니다.")
                return build("calendar", "v3", credentials=creds)
    except Exception as e:
        print(f"토큰 로드 중 오류 발생: {str(e)}")
    
    try:
        # 새로운 인증 진행
        print("🔑 Google Calendar 인증을 시작합니다...")
        creds = flow.run_local_server(port=8080)
        
        # 토큰 저장
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
        print("✅ 인증이 완료되었습니다.")
        
        return build("calendar", "v3", credentials=creds)
    except Exception as e:
        print(f"❌ 인증 중 오류가 발생했습니다: {str(e)}")
        raise

try:
    cal_service = get_calendar_service()
    USER_CAL_ID = os.getenv("USER_EMAIL")  # 기본 캘린더 ID
    print(f"✅ Calendar API 연결 성공 (사용자: {USER_CAL_ID})")
except Exception as e:
    print(f"❌ Calendar API 연결 실패: {str(e)}")
    raise

# ---------- 2. Cosmos DB(자기 성찰) ----------
client = CosmosClient(os.getenv("AZURE_COSMOS_ENDPOINT"),
                     credential=os.getenv("AZURE_COSMOS_KEY"))

# 데이터베이스 생성 또는 가져오기
try:
    db = client.create_database_if_not_exists(id="self_reflection_db")
    print("✅ 데이터베이스 생성/연결 성공")
except Exception as e:
    print(f"데이터베이스 생성 중 오류 발생: {str(e)}")
    db = client.get_database_client("self_reflection_db")

# 컨테이너 생성 또는 가져오기
try:
    # Vector Search를 위한 인덱싱 정책 정의
    indexing_policy = {
        "indexingMode": "consistent",
        "automatic": True,
        "includedPaths": [
            {
                "path": "/*"
            }
        ],
        "vectorIndexConfigs": [
            {
                "path": "/embedding",
                "kind": "vector-ivf",
                "dimension": 1536,
                "metric": "cosine"
            }
        ]
    }
    
    container = db.create_container_if_not_exists(
        id="self_reflections",
        partition_key=PartitionKey(path="/user_id"),
        indexing_policy=indexing_policy
    )
    print("✅ 컨테이너 생성/연결 성공")
except Exception as e:
    print(f"컨테이너 생성 중 오류 발생: {str(e)}")
    container = db.get_container_client("self_reflections")

# ---------- 3. 유틸 함수 ----------
def find_free_slots(busy, start, end, slot_min=30):
    """busy: [{'start':datetime,'end':datetime}, ...]"""
    busy_sorted = sorted(busy, key=lambda x: x["start"])
    free = []
    cur = start
    for b in busy_sorted:
        if b["start"] > cur:
            gap = (b["start"] - cur).total_seconds() / 60
            if gap >= slot_min:
                free.append({"start": cur, "end": b["start"]})
        cur = max(cur, b["end"])
    if (end - cur).total_seconds() / 60 >= slot_min:
        free.append({"start": cur, "end": end})
    return free

# 활동별 기본 시간 정의 (분 단위)
ACTIVITY_DURATIONS = {
    "산책": 30,
    "가벼운 산책": 20,
    "독서": 60,
    "운동": 45,
    "요가": 30,
    "명상": 15,
    "학습": 90,
    "휴식": 30,
    "스트레칭": 15,
    "기본 활동": 30
}

def get_activity_duration(activity_name: str) -> int:
    """활동 이름에 따른 적절한 시간(분)을 반환합니다."""
    for key, duration in ACTIVITY_DURATIONS.items():
        if key in activity_name:
            return duration
    return ACTIVITY_DURATIONS["기본 활동"]

def embed(text: str):
    openai_client = OpenAI()
    resp = openai_client.embeddings.create(
        model="text-embedding-3-small", input=text
    )
    return resp.data[0].embedding

# ---------- 4. LangGraph 상태 모델 ----------
class PAState(BaseModel):
    period_start: datetime
    period_end: datetime
    free_slots: list = Field(default_factory=list)
    interest_tags: list = Field(default_factory=list)
    suggestions: list = Field(default_factory=list)
    accepted: dict | None = None

# ---------- 5. 노드 구현 ----------
def node_get_freebusy(state: PAState):
    body = {
        "timeMin": state.period_start.isoformat(),
        "timeMax": state.period_end.isoformat(),
        "items": [{"id": USER_CAL_ID}],
        "timeZone": "Asia/Seoul",
    }
    fb = cal_service.freebusy().query(body=body).execute()
    busy_raw = fb["calendars"][USER_CAL_ID].get("busy", [])
    busy = [
        {
            "start": datetime.fromisoformat(b["start"]).astimezone(TZ),
            "end": datetime.fromisoformat(b["end"]).astimezone(TZ),
        }
        for b in busy_raw
    ]
    state.free_slots = find_free_slots(busy, state.period_start, state.period_end)
    return state

def node_query_interests(state: PAState):
    try:
        # 최근 14일 문서 벡터 검색 → 태그 추출
        query_vec = embed("recent interests summary")
        
        # 실제 데이터 쿼리
        query = """
        SELECT TOP 5 c.content, c.tags
        FROM c
        WHERE c.user_id = 'demo'
        ORDER BY c._ts DESC
        """
        
        results = list(container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))
        
        print("\n=== 최근 관심사 데이터 ===")
        for i, row in enumerate(results, 1):
            print(f"[{i}] {row['content']}")
        
        # 결과에서 태그 추출
        tags = {tag for row in results for tag in row.get("tags", [])}
        
        # 태그가 없는 경우 내용에서 키워드 추출
        if not tags:
            openai_client = OpenAI()
            contents = [row['content'] for row in results]
            prompt = f"""다음 내용들을 분석해서 주요 키워드나 관심사를 태그 형태로 추출해주세요:
            {chr(10).join(contents)}
            
            JSON 형식으로 응답해주세요:
            {{"tags": ["태그1", "태그2", "태그3"]}}
            """
            
            resp = openai_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            
            try:
                result = json.loads(resp.choices[0].message.content)
                tags = set(result.get("tags", []))
            except:
                tags = {"운동", "독서", "학습"}  # 기본 태그
        
        state.interest_tags = list(tags)
        print("\n✅ 관심사 검색 완료:", state.interest_tags)
        
    except Exception as e:
        print(f"⚠️ 관심사 검색 중 오류 발생: {str(e)}")
        state.interest_tags = ["운동", "독서", "학습"]  # 오류 시 기본 태그
    
    return state

def node_suggest(state: PAState):
    openai_client = OpenAI()
    
    # 시간대 정보를 더 명확하게 포맷팅
    time_slots = []
    for i, slot in enumerate(state.free_slots):
        start_time = slot['start'].strftime('%H:%M')
        end_time = slot['end'].strftime('%H:%M')
        duration = int((slot['end'] - slot['start']).total_seconds() / 60)
        time_slots.append(f"{i+1}. {start_time}~{end_time} ({duration}분)")
    
    # 프롬프트 수정
    prompt = f"""당신은 일정 추천 비서입니다. 다음 조건에 맞는 활동을 추천해주세요:

1. 사용자 관심사: {', '.join(state.interest_tags)}
2. 가능한 시간대:
{chr(10).join(time_slots)}

반드시 다음 JSON 형식으로만 응답해주세요. 다른 설명이나 텍스트는 포함하지 마세요:
[
    {{
        "slot": 0,
        "activity": "활동명",
        "reason": "추천 이유",
        "duration": 숫자
    }}
]

주의사항:
- slot은 0부터 시작하는 인덱스입니다
- duration은 분 단위의 숫자입니다 (예: 30)
- duration은 해당 시간대의 사용 가능한 시간을 초과할 수 없습니다
- 활동명은 구체적으로 작성해주세요 (예: "가벼운 산책", "집중 독서", "요가 스트레칭" 등)
- 반드시 유효한 JSON 형식이어야 합니다
- JSON 형식 외의 다른 텍스트는 포함하지 마세요"""

    try:
        resp = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "당신은 일정 추천 비서입니다. 반드시 JSON 형식으로만 응답해주세요. 다른 설명이나 텍스트는 포함하지 마세요."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        
        content = resp.choices[0].message.content.strip()
        try:
            suggestions = json.loads(content)
            if isinstance(suggestions, list):
                state.suggestions = suggestions
            else:
                raise ValueError("응답이 리스트 형식이 아닙니다.")
        except json.JSONDecodeError as e:
            print(f"⚠️ JSON 파싱 오류: {str(e)}")
            print(f"받은 응답: {content}")
            # 기본 제안 생성
            state.suggestions = [
                {
                    "slot": 0,
                    "activity": "가벼운 산책",
                    "reason": "기본 활동으로 추천",
                    "duration": 30
                }
            ]
    except Exception as e:
        print(f"⚠️ 추천 생성 중 오류 발생: {str(e)}")
        state.suggestions = [
            {
                "slot": 0,
                "activity": "휴식",
                "reason": "기본 활동으로 추천",
                "duration": 30
            }
        ]
    
    return state

def node_user_confirm(state: PAState):
    print("\n=== AI 제안 ===")
    for i, s in enumerate(state.suggestions):
        print(f"{i+1}. {s['activity']} ({s['duration']}분) – {s['reason']}")
    
    # 사용자 선택
    choice = int(input("추가할 번호(0=취소): "))
    if choice <= 0:
        return state
    
    selected_suggestion = state.suggestions[choice-1]
    duration = int(selected_suggestion["duration"])
    
    # 가능한 시간대 표시
    print("\n=== 가능한 시간대 ===")
    for i, slot in enumerate(state.free_slots):
        slot_duration = int((slot["end"] - slot["start"]).total_seconds() / 60)
        if slot_duration >= duration:
            print(f"{i+1}. {slot['start'].strftime('%H:%M')}~{slot['end'].strftime('%H:%M')} ({slot_duration}분)")
    
    # 시간대 선택
    slot_choice = int(input("\n원하는 시간대 번호를 선택하세요 (0=취소): "))
    if slot_choice <= 0:
        return state
    
    selected_slot = state.free_slots[slot_choice-1]
    slot_duration = int((selected_slot["end"] - selected_slot["start"]).total_seconds() / 60)
    
    # 시간 충돌 확인
    if slot_duration < duration:
        print(f"\n⚠️ 선택한 시간대({slot_duration}분)가 활동 시간({duration}분)보다 짧습니다.")
        print("다음 옵션 중 선택해주세요:")
        print("1. 더 짧은 시간으로 조정")
        print("2. 다른 시간대 선택")
        print("3. 취소")
        
        option = int(input("선택 (1-3): "))
        if option == 1:
            duration = slot_duration
        elif option == 2:
            return node_user_confirm(state)
        else:
            return state
    
    # 일정 생성
    state.accepted = {
        "start": selected_slot["start"],
        "end": selected_slot["start"] + timedelta(minutes=duration),
        "summary": selected_suggestion["activity"],
        "description": selected_suggestion["reason"],
    }
    
    return state

def node_create_event(state: PAState):
    if not state.accepted:
        return state
    
    evt = {
        "summary": state.accepted["summary"],
        "description": state.accepted["description"],
        "start": {"dateTime": state.accepted["start"].isoformat(), "timeZone": "Asia/Seoul"},
        "end": {"dateTime": state.accepted["end"].isoformat(), "timeZone": "Asia/Seoul"},
    }
    res = cal_service.events().insert(calendarId=USER_CAL_ID, body=evt).execute()
    print(f"✅ 일정 등록 완료: {res.get('htmlLink')}")
    return state

# ---------- 6. LangGraph 정의 ----------
graph = StateGraph(PAState)

# 노드 추가
graph.add_node("freebusy", node_get_freebusy)
graph.add_node("interests", node_query_interests)
graph.add_node("suggest", node_suggest)
graph.add_node("confirm", node_user_confirm)
graph.add_node("create", node_create_event)

# 엣지 추가 (START 노드 포함)
graph.set_entry_point("freebusy")  # freebusy를 시작점으로 설정
graph.add_edge("freebusy", "interests")
graph.add_edge("interests", "suggest")
graph.add_edge("suggest", "confirm")
graph.add_edge("confirm", "create")
graph.add_edge("create", END)

assistant = graph.compile()

# ---------- 7. 실행 ----------
if __name__ == "__main__":
    now = datetime.now(TZ)
    period_start = now + timedelta(hours=1)
    period_end = now + timedelta(days=1)

    init_state = PAState(period_start=period_start, period_end=period_end)
    assistant.invoke(init_state)
