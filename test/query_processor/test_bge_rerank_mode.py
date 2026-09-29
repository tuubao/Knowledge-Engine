from modelscope import snapshot_download

local_dir = snapshot_download(model_id="BAAI/bge-reranker-large",
                              local_dir=r"D:\PythonCode\bge-reranker-large")

print(local_dir)