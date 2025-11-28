"""
数据模型定义
"""
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Float, DateTime, Text, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import SQLALCHEMY_DATABASE_URI
import enum

# 创建引擎和基类
engine = create_engine(SQLALCHEMY_DATABASE_URI, echo=False)
Base = declarative_base()
SessionLocal = sessionmaker(bind=engine)


class CopyTradeDirection(enum.Enum):
    """跟单方向"""
    ALL = "all"  # 买卖都跟
    BUY_ONLY = "buy_only"  # 只跟买入
    SELL_ONLY = "sell_only"  # 只跟卖出


class Wallet(Base):
    """监控钱包表"""
    __tablename__ = "wallets"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    address = Column(String(42), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)  # 备注名称
    is_active = Column(Boolean, default=True)  # 是否启用监控
    created_at = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, nullable=True)  # 最后活动时间
    
    def to_dict(self):
        return {
            "id": self.id,
            "address": self.address,
            "name": self.name,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
        }


class Transaction(Base):
    """交易记录表"""
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    wallet_address = Column(String(42), nullable=False, index=True)
    tx_hash = Column(String(66), unique=True, nullable=False, index=True)
    block_number = Column(Integer, nullable=False)
    
    # 交易信息
    trade_type = Column(String(10), nullable=False)  # BUY / SELL
    token_id = Column(String(100), nullable=True)  # 条件代币ID
    market_id = Column(String(100), nullable=True)  # 市场ID
    market_name = Column(String(500), nullable=True)  # 市场名称
    market_slug = Column(String(200), nullable=True)  # 市场slug用于链接
    outcome = Column(String(10), nullable=True)  # Yes / No
    
    # 金额信息
    amount = Column(Float, nullable=True)  # 股数
    price = Column(Float, nullable=True)  # 价格
    total_usdc = Column(Float, nullable=True)  # 总金额
    
    # 时间和状态
    timestamp = Column(DateTime, default=datetime.utcnow)
    notified = Column(Boolean, default=False)  # 是否已通知
    raw_data = Column(Text, nullable=True)  # 原始数据JSON
    
    def to_dict(self):
        return {
            "id": self.id,
            "wallet_address": self.wallet_address,
            "tx_hash": self.tx_hash,
            "block_number": self.block_number,
            "trade_type": self.trade_type,
            "token_id": self.token_id,
            "market_id": self.market_id,
            "market_name": self.market_name,
            "market_slug": self.market_slug,
            "outcome": self.outcome,
            "amount": self.amount,
            "price": self.price,
            "total_usdc": self.total_usdc,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "notified": self.notified,
        }


class Config(Base):
    """配置表"""
    __tablename__ = "configs"
    
    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CopyTradeConfig(Base):
    """跟单配置表"""
    __tablename__ = "copy_trade_config"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    enabled = Column(Boolean, default=False)  # 是否启用跟单
    simulation_mode = Column(Boolean, default=True)  # 模拟模式（不实际执行）
    
    # 跟单金额设置
    copy_ratio = Column(Float, default=10.0)  # 跟单比例 (%)
    min_amount = Column(Float, default=5.0)  # 单笔最小金额 (USDC)
    max_amount = Column(Float, default=100.0)  # 单笔最大金额 (USDC)
    max_position_per_market = Column(Float, default=500.0)  # 单市场最大持仓 (USDC)
    max_total_position = Column(Float, default=2000.0)  # 总持仓上限 (USDC)
    
    # 跟单方向
    copy_direction = Column(String(20), default="all")  # all, buy_only, sell_only
    
    # 高级设置
    slippage_tolerance = Column(Float, default=2.0)  # 滑点容忍 (%)
    min_price = Column(Float, default=0.05)  # 最低价格过滤
    max_price = Column(Float, default=0.95)  # 最高价格过滤
    
    # 模拟账户
    simulation_balance = Column(Float, default=10000.0)  # 模拟初始余额
    
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": self.id,
            "enabled": self.enabled,
            "simulation_mode": self.simulation_mode,
            "copy_ratio": self.copy_ratio,
            "min_amount": self.min_amount,
            "max_amount": self.max_amount,
            "max_position_per_market": self.max_position_per_market,
            "max_total_position": self.max_total_position,
            "copy_direction": self.copy_direction,
            "slippage_tolerance": self.slippage_tolerance,
            "min_price": self.min_price,
            "max_price": self.max_price,
            "simulation_balance": self.simulation_balance,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class CopyTradePosition(Base):
    """模拟持仓表"""
    __tablename__ = "copy_trade_positions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    token_id = Column(String(100), nullable=False, index=True)  # 条件代币ID
    market_id = Column(String(100), nullable=True)  # 市场ID
    market_name = Column(String(500), nullable=True)  # 市场名称
    market_slug = Column(String(200), nullable=True)
    event_slug = Column(String(200), nullable=True)
    outcome = Column(String(10), nullable=True)  # Yes / No
    
    # 持仓信息
    shares = Column(Float, default=0)  # 持有股数
    avg_price = Column(Float, default=0)  # 平均成本价
    total_cost = Column(Float, default=0)  # 总成本 (USDC)
    current_price = Column(Float, default=0)  # 当前价格
    current_value = Column(Float, default=0)  # 当前价值
    unrealized_pnl = Column(Float, default=0)  # 未实现盈亏
    unrealized_pnl_percent = Column(Float, default=0)  # 未实现盈亏百分比
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": self.id,
            "token_id": self.token_id,
            "market_id": self.market_id,
            "market_name": self.market_name,
            "market_slug": self.market_slug,
            "event_slug": self.event_slug,
            "outcome": self.outcome,
            "shares": self.shares,
            "avg_price": self.avg_price,
            "total_cost": self.total_cost,
            "current_price": self.current_price,
            "current_value": self.current_value,
            "unrealized_pnl": self.unrealized_pnl,
            "unrealized_pnl_percent": self.unrealized_pnl_percent,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class CopyTradeRecord(Base):
    """跟单记录表"""
    __tablename__ = "copy_trade_records"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 来源交易信息
    source_tx_hash = Column(String(66), nullable=False, index=True)  # 聪明钱的交易hash
    source_wallet_address = Column(String(42), nullable=False)  # 聪明钱地址
    source_wallet_name = Column(String(100), nullable=True)  # 聪明钱备注名
    
    # 市场信息
    token_id = Column(String(100), nullable=True)
    market_id = Column(String(100), nullable=True)
    market_name = Column(String(500), nullable=True)
    market_slug = Column(String(200), nullable=True)
    event_slug = Column(String(200), nullable=True)
    outcome = Column(String(10), nullable=True)
    
    # 跟单信息
    trade_type = Column(String(10), nullable=False)  # BUY / SELL
    source_amount = Column(Float, nullable=True)  # 聪明钱交易金额
    source_shares = Column(Float, nullable=True)  # 聪明钱交易股数
    source_price = Column(Float, nullable=True)  # 聪明钱交易价格
    
    copy_shares = Column(Float, nullable=True)  # 跟单股数
    copy_price = Column(Float, nullable=True)  # 跟单执行价格
    copy_amount = Column(Float, nullable=True)  # 跟单金额 (USDC)
    
    # 状态
    status = Column(String(20), default="pending")  # pending, success, failed, skipped
    skip_reason = Column(String(200), nullable=True)  # 跳过原因
    is_simulation = Column(Boolean, default=True)  # 是否为模拟交易
    
    # 盈亏（平仓时计算）
    realized_pnl = Column(Float, nullable=True)  # 已实现盈亏
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": self.id,
            "source_tx_hash": self.source_tx_hash,
            "source_wallet_address": self.source_wallet_address,
            "source_wallet_name": self.source_wallet_name,
            "token_id": self.token_id,
            "market_id": self.market_id,
            "market_name": self.market_name,
            "market_slug": self.market_slug,
            "event_slug": self.event_slug,
            "outcome": self.outcome,
            "trade_type": self.trade_type,
            "source_amount": self.source_amount,
            "source_shares": self.source_shares,
            "source_price": self.source_price,
            "copy_shares": self.copy_shares,
            "copy_price": self.copy_price,
            "copy_amount": self.copy_amount,
            "status": self.status,
            "skip_reason": self.skip_reason,
            "is_simulation": self.is_simulation,
            "realized_pnl": self.realized_pnl,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class CopyTradeStats(Base):
    """跟单统计表（每日统计）"""
    __tablename__ = "copy_trade_stats"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String(10), unique=True, nullable=False, index=True)  # YYYY-MM-DD
    
    total_trades = Column(Integer, default=0)  # 总交易次数
    successful_trades = Column(Integer, default=0)  # 成功次数
    failed_trades = Column(Integer, default=0)  # 失败次数
    skipped_trades = Column(Integer, default=0)  # 跳过次数
    
    total_buy_amount = Column(Float, default=0)  # 总买入金额
    total_sell_amount = Column(Float, default=0)  # 总卖出金额
    realized_pnl = Column(Float, default=0)  # 当日已实现盈亏
    
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": self.id,
            "date": self.date,
            "total_trades": self.total_trades,
            "successful_trades": self.successful_trades,
            "failed_trades": self.failed_trades,
            "skipped_trades": self.skipped_trades,
            "total_buy_amount": self.total_buy_amount,
            "total_sell_amount": self.total_sell_amount,
            "realized_pnl": self.realized_pnl,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


def init_db():
    """初始化数据库"""
    Base.metadata.create_all(engine)


def get_session():
    """获取数据库会话"""
    return SessionLocal()


def get_config(key: str, default: str = "") -> str:
    """获取配置值"""
    session = get_session()
    try:
        config = session.query(Config).filter(Config.key == key).first()
        return config.value if config else default
    finally:
        session.close()


def set_config(key: str, value: str):
    """设置配置值"""
    session = get_session()
    try:
        config = session.query(Config).filter(Config.key == key).first()
        if config:
            config.value = value
        else:
            config = Config(key=key, value=value)
            session.add(config)
        session.commit()
    finally:
        session.close()
