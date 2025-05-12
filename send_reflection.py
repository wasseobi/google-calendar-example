# seed_reflections.py (간단 스크립트)
from azure.cosmos import CosmosClient, PartitionKey
from openai import OpenAI
import os, uuid, datetime as dt
from dotenv import load_dotenv
import numpy as np

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
    emb = get_embedding(text)
    container.upsert_item({
        "id": str(uuid.uuid4()),
        "user_id": "demo",
        "content": text,
        "tags": [],
        "sentiment": 0.0,
        "embedding": emb
    })
print(f"🚀 샘플 {len(samples)}건 업로드 완료")
