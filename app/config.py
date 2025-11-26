"""
配置管理模块
"""
import os
from pathlib import Path

# 基础路径
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# 数据库配置
DATABASE_PATH = DATA_DIR / "monitor.db"
SQLALCHEMY_DATABASE_URI = f"sqlite:///{DATABASE_PATH}"

# Polygon 网络配置
POLYGON_RPC_URLS = [
    "https://polygon-rpc.com",
    "https://rpc-mainnet.matic.network",
    "https://polygon-mainnet.public.blastapi.io",
]

# 可以通过环境变量覆盖，支持付费节点获得更好性能
POLYGON_RPC_URL = os.getenv("POLYGON_RPC_URL", POLYGON_RPC_URLS[0])

# Polymarket 合约地址 (Polygon Mainnet)
CONTRACTS = {
    # CTF Exchange - 主要交易合约
    "CTF_EXCHANGE": "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E",
    # Neg Risk CTF Exchange - 负风险交易合约
    "NEG_RISK_CTF_EXCHANGE": "0xC5d563A36AE78145C45a50134d48A1215220f80a",
    # Conditional Tokens - 条件代币合约
    "CONDITIONAL_TOKENS": "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045",
    # USDC 代币
    "USDC": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
}

# Polymarket API
POLYMARKET_API_BASE = "https://clob.polymarket.com"
POLYMARKET_GAMMA_API = "https://gamma-api.polymarket.com"

# 监听配置
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "5"))  # 轮询间隔(秒)
BLOCKS_TO_CHECK = int(os.getenv("BLOCKS_TO_CHECK", "10"))  # 每次检查的区块数

# Web 服务配置
WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.getenv("WEB_PORT", "5000"))

# Telegram 配置 (通过Web界面或环境变量设置)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# 日志配置
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
