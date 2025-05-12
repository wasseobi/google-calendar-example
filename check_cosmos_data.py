from azure.cosmos import CosmosClient
from dotenv import load_dotenv
import os

# 환경 변수 로드
load_dotenv()

# Cosmos DB 연결
client = CosmosClient(os.getenv("AZURE_COSMOS_ENDPOINT"),
                     credential=os.getenv("AZURE_COSMOS_KEY"))

# 데이터베이스와 컨테이너 연결
db = client.get_database_client("self_reflection_db")
container = db.get_container_client("self_reflections")

# 모든 데이터 조회
query = "SELECT * FROM c WHERE c.user_id = 'demo'"
items = list(container.query_items(query=query, enable_cross_partition_query=True))

print("\n=== Cosmos DB 데이터 확인 ===")
print(f"총 {len(items)}개의 데이터가 있습니다.\n")

# 각 데이터 출력
for i, item in enumerate(items, 1):
    print(f"[{i}] ID: {item['id']}")
    print(f"    내용: {item['content']}")
    print(f"    태그: {item.get('tags', [])}")
    print(f"    감정 점수: {item.get('sentiment', 0.0)}")
    print(f"    임베딩 벡터 크기: {len(item.get('embedding', []))}")
    print() 