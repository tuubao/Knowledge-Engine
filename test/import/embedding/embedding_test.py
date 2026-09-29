#1. 创建嵌入模型对象
from pymilvus.model.hybrid import BGEM3EmbeddingFunction

bge_m3 = BGEM3EmbeddingFunction(
    model_name=r"D:\ai_models\modelscope_cache\models\BAAI\bge-m3",

    #如果安装的torch是gpu版本，这里就是"cuda:0"，如果安装的torch是cpu版本，这里就是"cpu"
    device="cuda:0",
    #如果安装的torch是gpu版本，这里就是True，如果安装的torch是cpu版本，这里就是False
    use_fp16=True,
)

#2. 嵌入向量
document_list = ["我是中国人","你是美国人"]

result = bge_m3.encode_documents(document_list)

#3. 解析出稠密向量和稀疏向量
#3.1 解析出稠密向量
dense = result.get("dense")
dense_vector_list = []
for item in dense:
    dense_vector = item.tolist()
    dense_vector_list.append(dense_vector)

#3.2 解析出稀疏向量
sparse_csr = result.get("sparse")

# indices: 表示稀疏向量的token_id,也就是不为0的维度
# data: 表示每个token_id的权重
# indptr: 每个稀疏向量的起始和终止(不包含)的下标
"""
我们最终要得到的稀疏向量应该是:
[{
    "token_id":"权重"
}]
"""
indptr = sparse_csr.indptr

sparse_vector_list = []

#1. 获取开始和结束的下标
for i in range(0,len(document_list)):
    start_index = indptr[i]
    end_index = indptr[i+1]

    # 获取indices
    indices = sparse_csr.indices[start_index:end_index].tolist()
    # data
    data = sparse_csr.data[start_index:end_index].tolist()

    sparse_vector = dict(zip(indices, data))

    sparse_vector_list.append(sparse_vector)

print(sparse_vector_list)






