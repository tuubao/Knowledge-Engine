from utils.clients.ai_clients import AIClients

reranker = AIClients.get_bge_m3_rerank_client()

# 计算相关性得分
pairs = [
    # [question,document] -> Q-D
    ["什么是万用表？", "万用表是一种测量电压、电流、电阻的仪器"],
    ["什么是万用表？", "今天天气很好"]
]
scores = reranker.compute_score(pairs)
# 高分 = 高相关
print(scores)
