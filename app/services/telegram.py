"""
Telegram 通知服务
"""
import logging
import asyncio
from typing import Optional
from datetime import datetime
import telegram
from telegram.constants import ParseMode
from app.models import get_config

logger = logging.getLogger(__name__)


class TelegramService:
    """Telegram 通知服务"""
    
    def __init__(self):
        self._bot: Optional[telegram.Bot] = None
        self._bot_token: str = ""
        self._chat_id: str = ""
    
    def _load_config(self):
        """从数据库加载配置"""
        self._bot_token = get_config("telegram_bot_token", "")
        self._chat_id = get_config("telegram_chat_id", "")
    
    def _get_bot(self) -> Optional[telegram.Bot]:
        """获取 Bot 实例"""
        self._load_config()
        
        if not self._bot_token:
            logger.warning("Telegram Bot Token 未配置")
            return None
        
        if self._bot is None or self._bot.token != self._bot_token:
            self._bot = telegram.Bot(token=self._bot_token)
        
        return self._bot
    
    def is_configured(self) -> bool:
        """检查是否已配置"""
        self._load_config()
        return bool(self._bot_token and self._chat_id)
    
    async def _send_message_async(self, text: str, parse_mode: str = ParseMode.HTML) -> bool:
        """异步发送消息"""
        bot = self._get_bot()
        if not bot or not self._chat_id:
            return False
        
        try:
            await bot.send_message(
                chat_id=self._chat_id,
                text=text,
                parse_mode=parse_mode,
                disable_web_page_preview=True,
            )
            logger.info("Telegram 消息发送成功")
            return True
        except Exception as e:
            logger.error(f"Telegram 消息发送失败: {e}")
            return False
    
    def send_message(self, text: str, parse_mode: str = ParseMode.HTML) -> bool:
        """同步发送消息"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self._send_message_async(text, parse_mode))
    
    def send_trade_notification(
        self,
        wallet_name: str,
        wallet_address: str,
        trade_type: str,
        market_name: str,
        outcome: str,
        amount: float,
        price: float,
        total_usdc: float,
        tx_hash: str,
        event_slug: str = "",
        market_slug: str = "",
        timestamp: datetime = None,
    ) -> bool:
        """发送交易通知"""
        
        # 生成链接
        tx_url = f"https://polygonscan.com/tx/{tx_hash}"
        profile_url = f"https://polymarket.com/profile/{wallet_address}"
        
        if event_slug:
            if market_slug:
                market_url = f"https://polymarket.com/event/{event_slug}/{market_slug}"
            else:
                market_url = f"https://polymarket.com/event/{event_slug}"
        else:
            market_url = "https://polymarket.com"
        
        # 交易类型 emoji
        type_emoji = "🟢" if trade_type == "BUY" else "🔴"
        type_text = "买入" if trade_type == "BUY" else "卖出"
        
        # 格式化时间
        time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S UTC") if timestamp else datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        
        # 构建消息
        message = f"""🚨 <b>聪明钱交易提醒</b>

👛 <b>钱包:</b> {wallet_name}
📍 <b>地址:</b> <code>{wallet_address[:8]}...{wallet_address[-6:]}</code>

📊 <b>交易详情:</b>
• 类型: {type_emoji} <b>{type_text}</b>
• 市场: {market_name[:80]}{'...' if len(market_name) > 80 else ''}
• 结果: <b>{outcome}</b>
• 数量: <b>{amount:,.2f}</b> 股
• 价格: <b>${price:.4f}</b>
• 总额: <b>${total_usdc:,.2f}</b> USDC

⏰ <b>时间:</b> {time_str}

🔗 <b>快捷链接:</b>
• <a href="{tx_url}">查看交易</a>
• <a href="{market_url}">查看市场</a>
• <a href="{profile_url}">钱包持仓</a>"""

        return self.send_message(message)
    
    async def test_connection_async(self) -> tuple:
        """异步测试连接"""
        bot = self._get_bot()
        if not bot:
            return False, "Bot Token 未配置"
        
        try:
            me = await bot.get_me()
            
            if self._chat_id:
                # 尝试发送测试消息
                await bot.send_message(
                    chat_id=self._chat_id,
                    text="✅ Polymarket 监控系统连接测试成功！",
                    parse_mode=ParseMode.HTML,
                )
                return True, f"连接成功！Bot: @{me.username}"
            else:
                return True, f"Bot 验证成功: @{me.username}，但 Chat ID 未配置"
                
        except telegram.error.InvalidToken:
            return False, "无效的 Bot Token"
        except telegram.error.Forbidden:
            return False, "Bot 无权发送消息到该 Chat，请确认 Bot 已加入群组或开始对话"
        except telegram.error.BadRequest as e:
            return False, f"请求错误: {e}"
        except Exception as e:
            return False, f"连接失败: {e}"
    
    def test_connection(self) -> tuple:
        """同步测试连接"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self.test_connection_async())


# 单例实例
_telegram_service: Optional[TelegramService] = None


def get_telegram_service() -> TelegramService:
    """获取 Telegram 服务单例"""
    global _telegram_service
    if _telegram_service is None:
        _telegram_service = TelegramService()
    return _telegram_service
