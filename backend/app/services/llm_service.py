"""LLM 生成服务：支持流式输出，OpenAI 兼容 API"""

import logging
from typing import AsyncGenerator

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一个智能知识问答助手。请根据以下参考信息回答用户问题。

参考信息可能包含两种来源：
- [知识库] 标记的内容来自用户上传的文档
- [网络] 标记的内容来自网络搜索结果

规则：
1. 优先使用知识库中的信息回答
2. 如果知识库中没有相关内容，使用网络搜索结果回答
3. 如果两者都没有足够信息，可以基于自身知识回答，但需说明"以上信息来自模型自身知识，仅供参考"
4. 回答中引用来源时使用 [1] [2] 等标注，对应下方的引用列表
5. 回答简洁准确，使用 Markdown 格式

参考信息：
{context}

引用列表：
{citations}
"""


class LLMService:
    """LLM 推理服务，支持流式输出"""

    def __init__(self):
        self.api_base = settings.llm_api_base.rstrip("/")
        self.api_key = settings.llm_api_key
        self.model = settings.llm_model
        self._client = httpx.AsyncClient(
            base_url=self.api_base,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=120.0,
        )

    def build_prompt(self, question: str, context: str, citations: str) -> list[dict]:
        """构建消息列表"""
        system_content = SYSTEM_PROMPT.format(context=context, citations=citations)
        return [
            {"role": "system", "content": system_content},
            {"role": "user", "content": question},
        ]

    async def generate_stream(
        self,
        messages: list[dict],
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[str, None]:
        """流式生成，逐 token 返回"""
        try:
            async with self._client.stream(
                "POST",
                "/chat/completions",
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": True,
                },
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data.strip() == "[DONE]":
                            break
                        try:
                            import json
                            chunk = json.loads(data)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.error(f"LLM 流式生成失败: {e}")
            yield f"\n\n[生成错误: {e}]"

    async def generate(
        self,
        messages: list[dict],
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> str:
        """非流式生成，返回完整文本"""
        result = ""
        async for token in self.generate_stream(messages, temperature, max_tokens):
            result += token
        return result

    async def close(self):
        await self._client.aclose()


llm_service = LLMService()
