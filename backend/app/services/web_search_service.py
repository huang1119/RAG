"""网络搜索服务：知识库无结果时自动搜索网络补充

使用 Bing 搜索引擎，支持代理配置。
"""

import logging
import re
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class WebSearchResult:
    title: str
    url: str
    snippet: str


class WebSearchService:
    """Bing 网络搜索"""

    def __init__(self):
        self.base_url = "https://www.bing.com/search"
        # 检测系统代理
        import os
        proxy = os.environ.get("https_proxy") or os.environ.get("HTTPS_PROXY") or ""
        self._proxy = proxy if proxy and "127.0.0.1" in proxy else None
        if self._proxy:
            logger.info(f"网络搜索使用代理: {self._proxy}")

    async def search(self, query: str, max_results: int = 5) -> list[WebSearchResult]:
        """搜索网络，返回结果列表

        Args:
            query: 搜索关键词
            max_results: 最大结果数

        Returns:
            WebSearchResult 列表
        """
        results: list[WebSearchResult] = []
        try:
            async with httpx.AsyncClient(
                timeout=15.0,
                proxy=self._proxy,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                },
            ) as client:
                resp = await client.get(
                    self.base_url,
                    params={"q": query, "count": max_results * 2, "setlang": "zh-CN"},
                )
                resp.raise_for_status()

                soup = BeautifulSoup(resp.text, "html.parser")
                # Bing 搜索结果在 <li class="b_algo"> 中
                items = soup.find_all("li", class_="b_algo")

                for item in items[:max_results]:
                    title_tag = item.find("h2")
                    link_tag = title_tag.find("a") if title_tag else None
                    snippet_tag = item.find("p") or item.find(class_="b_caption")

                    title = title_tag.get_text(strip=True) if title_tag else ""
                    url = link_tag.get("href", "") if link_tag else ""
                    snippet = ""
                    if snippet_tag:
                        snippet = snippet_tag.get_text(strip=True)[:300]

                    if title and url:
                        results.append(WebSearchResult(
                            title=title,
                            url=url,
                            snippet=snippet,
                        ))

                logger.info(f"Bing 搜索完成: '{query}' -> {len(results)} 条结果")

        except Exception as e:
            logger.error(f"网络搜索失败: {e}")

        return results


web_search_service = WebSearchService()
