import threading
from typing import Any, List, Optional, Tuple, Union

import torch
import torch.nn as nn
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from openai import OpenAI
from pymilvus.model.hybrid import BGEM3EmbeddingFunction
from sentence_transformers import CrossEncoder

from utils.clients.base import BaseClientManager, logger

load_dotenv()


class _BgeCrossEncoderRerankClient:
    """
    与 FlagReranker.compute_score(sentence_pairs=...) 对齐的薄包装。

    FlagEmbedding 在 transformers>=5 下会因 tokenizer 移除 prepare_for_model 而失败；
    CrossEncoder 使用当前 tokenizer 的 __call__/pad 路径，可正常加载 BGE 系列重排序模型。
    推理仍由 sentence-transformers + HuggingFace 完整实现完成，此处仅做 API 适配。
    """

    def __init__(self, cross_encoder: CrossEncoder):
        self._ce = cross_encoder

    def compute_score(
        self,
        sentence_pairs: Union[List[Tuple[str, str]], Tuple[str, str]],
        batch_size: int = 128,
        **kwargs: Any,
    ) -> List[float]:
        if isinstance(sentence_pairs, tuple) and len(sentence_pairs) == 2 and isinstance(sentence_pairs[0], str):
            pairs: List[Tuple[str, str]] = [sentence_pairs]  # type: ignore[list-item]
        else:
            pairs = list(sentence_pairs)  # type: ignore[arg-type]
        scores = self._ce.predict(
            pairs,
            batch_size=batch_size,
            activation_fn=nn.Identity(),
            show_progress_bar=False,
            **kwargs,
        )
        if hasattr(scores, "tolist"):
            scores = scores.tolist()
        flat: List[float] = []
        for s in scores:
            if isinstance(s, (list, tuple)):
                flat.append(float(s[0]))
            else:
                flat.append(float(s))
        return flat


class AIClients(BaseClientManager):
    """AI 模型类客户端"""

    _openai_client: Optional[OpenAI] = None
    _openai_lock = threading.Lock()

    _openai_llm_response_text_client: Optional[ChatOpenAI] = None
    _openai_llm_response_text_lock = threading.Lock()

    _openai_llm_response_json_client: Optional[ChatOpenAI] = None
    _openai_llm_response_json_lock = threading.Lock()

    _bge_m3_client: Optional[BGEM3EmbeddingFunction] = None
    _bge_m3_lock = threading.Lock()

    _bge_m3_rerank_client: Optional[_BgeCrossEncoderRerankClient] = None
    _bge_m3_rerank_lock = threading.Lock()

    # ── VLM ──

    @classmethod
    def get_vlm_client(cls) -> OpenAI:
        return cls._get_or_create("_openai_client", cls._openai_lock, cls._create_vlm_client)

    @classmethod
    def _create_vlm_client(cls) -> OpenAI:
        try:
            api_key = cls._require_env("OPEN_API_KEY")
            base_url = cls._require_env("OPEN_API_BASE")
            client = OpenAI(api_key=api_key, base_url=base_url)
            logger.info(f"OpenAI 客户端初始化成功 (base_url={base_url})")

            return client

        except EnvironmentError:
            raise
        except Exception as e:
            logger.error(f"OpenAI 客户端创建失败: {e}")
            raise ConnectionError(f"OpenAI 连接失败: {e}") from e

    # ── LLM ──
    @classmethod
    def get_llm_client(cls, response_format: bool = True) -> ChatOpenAI:
        if response_format:
            return cls._get_or_create("_openai_llm_json_client", cls._openai_llm_response_json_lock,
                                      lambda: cls._create_llm_client(response_format))
        else:
            return cls._get_or_create("_openai_llm_text_client", cls._openai_llm_response_text_lock,
                                      lambda: cls._create_llm_client(response_format))

            # ── LLM ──

    @classmethod
    def _create_llm_client(cls, response_format) -> ChatOpenAI:
        try:
            api_key = cls._require_env("OPEN_API_KEY")
            base_url = cls._require_env("OPEN_API_BASE")
            model_name = cls._require_env('LLM_DEFAULT_MODEL')

            model_kwargs = {}
            if response_format:
                model_kwargs['response_format'] = {"type": "json_object"}

            llm_client = ChatOpenAI(
                model_name=model_name,
                temperature=0,
                openai_api_key=api_key,
                openai_api_base=base_url,
                model_kwargs=model_kwargs
            )
            logger.info(f"OpenAI LLM 客户端初始化成功")
            return llm_client

        except EnvironmentError:
            raise
        except Exception as e:
            raise ConnectionError(f"OpenAI 连接失败: {e}") from e

    # ── BGE-M3嵌入模型客户端 ──
    @classmethod
    def get_bge_m3_client(cls) -> BGEM3EmbeddingFunction:
        return cls._get_or_create("_bge_m3_client", cls._bge_m3_lock, cls._create_bge_m3_client)

    @classmethod
    def _create_bge_m3_client(cls) -> BGEM3EmbeddingFunction:
        """
        创建bge_m3 客户端
        Returns:
        """

        try:
            # 1. 获取环境变量
            model_name = cls._require_env('BGE_M3_PATH')
            device = cls._require_env('BGE_DEVICE')
            fp16_str = cls._require_env('BGE_FP16')

            fp16 = fp16_str.lower() in ("true", "1")
            # 2. 创建
            bge_m3_ef = BGEM3EmbeddingFunction(
                model_name=model_name,
                device=device,
                use_fp16=fp16
            )
            return bge_m3_ef
        except EnvironmentError as e:
            raise

        except Exception as e:
            raise ConnectionError(f"BGE_M3嵌入模型客户端创建失败: {e}") from e

    @classmethod
    def get_bge_m3_rerank_client(cls):
        return cls._get_or_create("_bge_m3_rerank_client",
                                  cls._bge_m3_rerank_lock,
                                  cls._create_bge_m3_rerank_client)

    @classmethod
    def _create_bge_m3_rerank_client(cls):
        """
        创建bge_m3 重排序模型客户端
        Returns:
        """

        try:
            # 1. 获取环境变量
            model_name_or_path = cls._require_env('BGE_RERANKER_LARGE')
            device = cls._require_env('BGE_DEVICE')
            fp16_str = cls._require_env('BGE_FP16')
            # 与 BGE_M3 嵌入客户端一致：为 true/1 时启用半精度（此前误写成 false 时启用）
            fp16 = fp16_str.lower() in ("true", "1")

            model_kwargs: dict = {}
            if fp16 and device != "cpu" and not str(device).lower().startswith("cpu"):
                model_kwargs["torch_dtype"] = torch.float16

            cross = CrossEncoder(
                model_name_or_path,
                device=device,
                model_kwargs=model_kwargs or None,
                activation_fn=nn.Identity(),
                max_length=512,
            )
            logger.info("BGE 重排序客户端已使用 sentence-transformers CrossEncoder 初始化（兼容 transformers 5+）")
            return _BgeCrossEncoderRerankClient(cross)
        except EnvironmentError as e:
            raise

        except Exception as e:
            raise ConnectionError(f"BGE-M3重排序模型客户端创建失败: {e}") from e
if __name__ == '__main__':
    # llm_client: ChatOpenAI = AIClients.get_llm_client()
    #
    # llm_response = llm_client.invoke("请您给我讲一个笑话，要求输出格式是一个json")
    #
    # llm_result = llm_response.content
    #
    # import json
    #
    # result = json.loads(llm_result)
    #
    # print(result)
    #
    print(AIClients.get_bge_m3_rerank_client())
