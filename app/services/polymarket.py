"""
Polymarket API 服务
用于获取市场信息、事件详情等
"""
import logging
import requests
from typing import Optional, Dict, Any
from functools import lru_cache
import time
from app.config import POLYMARKET_API_BASE, POLYMARKET_GAMMA_API

logger = logging.getLogger(__name__)

# 缓存过期时间（秒）
CACHE_TTL = 300  # 5分钟


class PolymarketAPI:
    """Polymarket API 客户端"""
    
    def __init__(self):
        self.clob_base = POLYMARKET_API_BASE
        self.gamma_base = POLYMARKET_GAMMA_API
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "PolymarketMonitor/1.0",
            "Accept": "application/json",
        })
        # token_id -> market_info 缓存
        self._market_cache: Dict[str, Dict] = {}
        self._cache_time: Dict[str, float] = {}
    
    def get_market_by_token_id(self, token_id: str) -> Optional[Dict[str, Any]]:
        """
        根据条件代币ID获取市场信息
        """
        # 检查缓存
        if token_id in self._market_cache:
            if time.time() - self._cache_time.get(token_id, 0) < CACHE_TTL:
                return self._market_cache[token_id]
        
        try:
            # 使用 CLOB API 获取市场信息
            url = f"{self.clob_base}/markets/{token_id}"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                market_info = self._parse_market_data(data, token_id)
                self._market_cache[token_id] = market_info
                self._cache_time[token_id] = time.time()
                return market_info
            
            # 如果 CLOB API 找不到，尝试 Gamma API
            return self._get_market_from_gamma(token_id)
            
        except Exception as e:
            logger.error(f"获取市场信息失败 (token_id: {token_id}): {e}")
            return None
    
    def _get_market_from_gamma(self, token_id: str) -> Optional[Dict[str, Any]]:
        """从 Gamma API 获取市场信息"""
        try:
            url = f"{self.gamma_base}/markets"
            params = {"clob_token_ids": token_id}
            response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    market = data[0]
                    market_info = {
                        "market_id": market.get("condition_id", ""),
                        "market_name": market.get("question", "Unknown Market"),
                        "market_slug": market.get("market_slug", ""),
                        "event_slug": market.get("event_slug", ""),
                        "outcome": self._determine_outcome(market, token_id),
                        "image": market.get("image", ""),
                        "end_date": market.get("end_date_iso", ""),
                    }
                    self._market_cache[token_id] = market_info
                    self._cache_time[token_id] = time.time()
                    return market_info
            
            return None
            
        except Exception as e:
            logger.error(f"从 Gamma API 获取市场信息失败: {e}")
            return None
    
    def _parse_market_data(self, data: Dict, token_id: str) -> Dict[str, Any]:
        """解析 CLOB API 返回的市场数据"""
        # CLOB API 返回的是单个 token 的信息
        return {
            "market_id": data.get("condition_id", ""),
            "market_name": data.get("question", "Unknown Market"),
            "market_slug": data.get("market_slug", ""),
            "event_slug": data.get("event_slug", ""),
            "outcome": data.get("outcome", "Yes"),  # Yes 或 No
            "image": data.get("icon", ""),
            "end_date": data.get("end_date_iso", ""),
            "tokens": data.get("tokens", []),
        }
    
    def _determine_outcome(self, market: Dict, token_id: str) -> str:
        """确定 token_id 对应的结果（Yes/No）"""
        tokens = market.get("tokens", [])
        for token in tokens:
            if str(token.get("token_id", "")) == str(token_id):
                return token.get("outcome", "Yes")
        
        # 如果找不到，根据 clob_token_ids 判断
        clob_ids = market.get("clob_token_ids", "").split(",")
        if len(clob_ids) >= 2:
            if str(token_id) == clob_ids[0].strip():
                return "Yes"
            elif str(token_id) == clob_ids[1].strip():
                return "No"
        
        return "Yes"
    
    def get_event_url(self, event_slug: str) -> str:
        """获取事件页面URL"""
        if event_slug:
            return f"https://polymarket.com/event/{event_slug}"
        return "https://polymarket.com"
    
    def get_market_url(self, market_slug: str, event_slug: str = "") -> str:
        """获取市场页面URL"""
        if event_slug and market_slug:
            return f"https://polymarket.com/event/{event_slug}/{market_slug}"
        elif event_slug:
            return f"https://polymarket.com/event/{event_slug}"
        return "https://polymarket.com"
    
    def get_profile_url(self, wallet_address: str) -> str:
        """获取钱包持仓页面URL"""
        return f"https://polymarket.com/profile/{wallet_address}"
    
    def get_tx_url(self, tx_hash: str) -> str:
        """获取交易详情URL (Polygonscan)"""
        return f"https://polygonscan.com/tx/{tx_hash}"
    
    def search_markets(self, query: str, limit: int = 10) -> list:
        """搜索市场"""
        try:
            url = f"{self.gamma_base}/markets"
            params = {
                "closed": "false",
                "limit": limit,
            }
            response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                markets = response.json()
                # 简单的文本匹配过滤
                if query:
                    query_lower = query.lower()
                    markets = [m for m in markets if query_lower in m.get("question", "").lower()]
                return markets[:limit]
            
            return []
            
        except Exception as e:
            logger.error(f"搜索市场失败: {e}")
            return []


# 单例实例
_polymarket_api: Optional[PolymarketAPI] = None


def get_polymarket_api() -> PolymarketAPI:
    """获取 Polymarket API 单例"""
    global _polymarket_api
    if _polymarket_api is None:
        _polymarket_api = PolymarketAPI()
    return _polymarket_api
