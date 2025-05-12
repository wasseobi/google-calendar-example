# seed_reflections.py (간단 스크립트)
from azure.cosmos import CosmosClient, PartitionKey
from openai import OpenAI
import os, uuid, datetime as dt
from dotenv import load_dotenv
import numpy as np
import json

# 환경 변수 로드
load_dotenv()

# 환경 변수 확인
if not os.getenv("AZURE_COSMOS_ENDPOINT") or not os.getenv("AZURE_COSMOS_KEY"):
    raise ValueError("Azure Cosmos DB 환경 변수가 설정되지 않았습니다. .env 파일을 확인해주세요.")

client = CosmosClient(os.getenv("AZURE_COSMOS_ENDPOINT"),
                      credential=os.getenv("AZURE_COSMOS_KEY"))

# 데이터베이스 연결
db = client.get_database_client("self_reflection_db")

# 컨테이너 연결
container = db.get_container_client("self_reflections")
print("✅ Azure Cosmos DB 연결 성공")

openai = OpenAI()

def get_embedding(text):
    try:
        emb = openai.embeddings.create(model="text-embedding-3-small",
                                     input=text).data[0].embedding
        return emb
    except Exception as e:
        print(f"임베딩 생성 중 오류 발생: {str(e)}")
        # 기본 임베딩 벡터 생성 (1536 차원)
        return np.zeros(1536).tolist()

def extract_tags(text):
    try:
        prompt = f"""다음 내용을 분석해서 주요 키워드나 관심사를 태그 형태로 추출해주세요:
        {text}
        
        JSON 형식으로 응답해주세요:
        {{"tags": ["태그1", "태그2", "태그3"]}}
        
        주의사항:
        - 태그는 2-4개 정도로 추출해주세요
        - 구체적인 수치나 시간은 제외해주세요 (예: "5 km" → "러닝")
        - 일반적인 카테고리나 활동 유형을 중심으로 추출해주세요
        - "오늘", "요즘" 같은 시간 표현은 제외해주세요
        """
        
        resp = openai.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        
        result = json.loads(resp.choices[0].message.content)
        return result.get("tags", [])
    except Exception as e:
        print(f"태그 추출 중 오류 발생: {str(e)}")
        return []

def analyze_sentiment(text):
    try:
        prompt = f"""다음 텍스트의 감정을 분석해서 -1.0(매우 부정적)부터 1.0(매우 긍정적) 사이의 점수를 부여해주세요:
        {text}
        
        JSON 형식으로 응답해주세요:
        {{"sentiment": 0.0}}
        
        감정 점수 기준:
        - 0.8 ~ 1.0: 매우 긍정적 (예: "정말 행복하다", "완벽했다")
        - 0.5 ~ 0.7: 긍정적 (예: "좋았다", "재미있다")
        - 0.2 ~ 0.4: 약간 긍정적 (예: "괜찮았다", "진도가 나간다")
        - -0.1 ~ 0.1: 중립 (예: "했다", "했다")
        - -0.4 ~ -0.2: 약간 부정적 (예: "힘들었다", "어렵다")
        - -0.7 ~ -0.5: 부정적 (예: "싫다", "안 좋다")
        - -1.0 ~ -0.8: 매우 부정적 (예: "최악이다", "실패했다")
        
        텍스트의 감정 강도에 따라 더 세밀하게 점수를 부여해주세요.
        """
        
        resp = openai.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        
        result = json.loads(resp.choices[0].message.content)
        return result.get("sentiment", 0.0)
    except Exception as e:
        print(f"감정 분석 중 오류 발생: {str(e)}")
        return 0.0

samples = [
    "오늘 러닝 5 km를 뛰었더니 기분이 상쾌했다.",
    "요즘 데이터 시각화 공부가 재밌다.",
    "새로운 SF 소설을 읽기 시작했는데 몰입감이 좋다.",
    "오늘 LangGraph 내용을 공부했는데 흥미로운 개념들이 많았다.",
    "자격증 공부를 했는데 진도가 잘 나가고 있다.",
    "LangGraph로 워크플로우를 구성하는 방법을 배웠다.",
    "자격증 시험 준비를 위해 실전 문제를 풀어봤다."
]

for text in samples:
    # 태그 추출
    tags = extract_tags(text)
    print(f"\n내용: {text}")
    print(f"추출된 태그: {tags}")
    
    # 감정 분석
    sentiment = analyze_sentiment(text)
    print(f"감정 점수: {sentiment:.2f}")
    
    # 임베딩 생성
    emb = get_embedding(text)
    
    # 데이터 저장
    container.upsert_item({
        "id": str(uuid.uuid4()),
        "user_id": "demo",
        "content": text,
        "tags": tags,
        "sentiment": sentiment,
        "embedding": emb
    })

print(f"\n🚀 샘플 {len(samples)}건 업로드 완료")
