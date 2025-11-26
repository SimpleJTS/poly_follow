"""
数据模型定义
"""
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Float, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import SQLALCHEMY_DATABASE_URI

# 创建引擎和基类
engine = create_engine(SQLALCHEMY_DATABASE_URI, echo=False)
Base = declarative_base()
SessionLocal = sessionmaker(bind=engine)


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
