"""
监控服务 - 核心监听循环
"""
import logging
import threading
import time
from datetime import datetime
from typing import Optional, List, Dict, Any
from app.config import POLL_INTERVAL, BLOCKS_TO_CHECK
from app.models import (
    get_session, Wallet, Transaction, 
    get_config, set_config
)
from app.services.blockchain import get_blockchain_service
from app.services.polymarket import get_polymarket_api
from app.services.telegram import get_telegram_service
from app.services.copytrade import get_copytrade_service

logger = logging.getLogger(__name__)


class MonitorService:
    """交易监控服务"""
    
    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_block: int = 0
        self._poll_interval = POLL_INTERVAL
        self._blocks_to_check = BLOCKS_TO_CHECK
        
        # 服务依赖
        self._blockchain = get_blockchain_service()
        self._polymarket = get_polymarket_api()
        self._telegram = get_telegram_service()
        self._copytrade = get_copytrade_service()
    
    def is_running(self) -> bool:
        """检查监控是否运行中"""
        return self._running
    
    def start(self):
        """启动监控"""
        if self._running:
            logger.warning("监控服务已在运行")
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info("监控服务已启动")
    
    def stop(self):
        """停止监控"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("监控服务已停止")
    
    def _get_active_wallets(self) -> List[str]:
        """获取所有活跃的监控钱包地址"""
        session = get_session()
        try:
            wallets = session.query(Wallet).filter(Wallet.is_active == True).all()
            return [w.address for w in wallets]
        finally:
            session.close()
    
    def _get_wallet_name(self, address: str) -> str:
        """获取钱包备注名"""
        session = get_session()
        try:
            wallet = session.query(Wallet).filter(
                Wallet.address.ilike(address)
            ).first()
            return wallet.name if wallet else address[:8]
        finally:
            session.close()
    
    def _update_wallet_activity(self, address: str):
        """更新钱包最后活动时间"""
        session = get_session()
        try:
            wallet = session.query(Wallet).filter(
                Wallet.address.ilike(address)
            ).first()
            if wallet:
                wallet.last_activity = datetime.utcnow()
                session.commit()
        finally:
            session.close()
    
    def _is_tx_processed(self, tx_hash: str) -> bool:
        """检查交易是否已处理"""
        session = get_session()
        try:
            tx = session.query(Transaction).filter(
                Transaction.tx_hash == tx_hash
            ).first()
            return tx is not None
        finally:
            session.close()
    
    def _save_transaction(self, tx_data: Dict[str, Any]) -> Optional[Transaction]:
        """保存交易记录"""
        session = get_session()
        try:
            tx = Transaction(
                wallet_address=tx_data["wallet_address"],
                tx_hash=tx_data["tx_hash"],
                block_number=tx_data["block_number"],
                trade_type=tx_data["trade_type"],
                token_id=tx_data.get("token_id"),
                market_id=tx_data.get("market_id"),
                market_name=tx_data.get("market_name"),
                market_slug=tx_data.get("market_slug"),
                outcome=tx_data.get("outcome"),
                amount=tx_data.get("amount"),
                price=tx_data.get("price"),
                total_usdc=tx_data.get("total_usdc"),
                raw_data=tx_data.get("raw_data"),
                notified=False,
            )
            session.add(tx)
            session.commit()
            session.refresh(tx)
            return tx
        except Exception as e:
            session.rollback()
            logger.error(f"保存交易记录失败: {e}")
            return None
        finally:
            session.close()
    
    def _mark_tx_notified(self, tx_id: int):
        """标记交易已通知"""
        session = get_session()
        try:
            tx = session.query(Transaction).filter(Transaction.id == tx_id).first()
            if tx:
                tx.notified = True
                session.commit()
        finally:
            session.close()
    
    def _process_transaction(self, tx_data: Dict[str, Any]):
        """处理单个交易"""
        tx_hash = tx_data["tx_hash"]
        
        # 检查是否已处理
        if self._is_tx_processed(tx_hash):
            logger.debug(f"交易已处理: {tx_hash}")
            return
        
        logger.info(f"发现新交易: {tx_hash}")
        
        # 获取市场信息
        token_id = tx_data.get("token_id")
        if token_id:
            market_info = self._polymarket.get_market_by_token_id(token_id)
            if market_info:
                tx_data["market_id"] = market_info.get("market_id")
                tx_data["market_name"] = market_info.get("market_name", "Unknown Market")
                tx_data["market_slug"] = market_info.get("market_slug", "")
                tx_data["event_slug"] = market_info.get("event_slug", "")
                tx_data["outcome"] = market_info.get("outcome", "Yes")
            else:
                tx_data["market_name"] = f"Token ID: {token_id}"
                tx_data["outcome"] = "Unknown"
        
        # 保存交易
        tx = self._save_transaction(tx_data)
        if not tx:
            return
        
        # 更新钱包活动时间
        self._update_wallet_activity(tx_data["wallet_address"])
        
        # 获取钱包名称
        wallet_name = self._get_wallet_name(tx_data["wallet_address"])
        
        # 执行跟单逻辑
        try:
            copy_record = self._copytrade.execute_simulation_trade(tx_data, wallet_name)
            if copy_record:
                if copy_record.status == "success":
                    logger.info(f"模拟跟单成功: {copy_record.trade_type} {copy_record.copy_shares:.2f} 股")
                elif copy_record.status == "skipped":
                    logger.debug(f"跳过跟单: {copy_record.skip_reason}")
        except Exception as e:
            logger.error(f"跟单处理失败: {e}")
        
        # 发送通知
        if self._telegram.is_configured():
            success = self._telegram.send_trade_notification(
                wallet_name=wallet_name,
                wallet_address=tx_data["wallet_address"],
                trade_type=tx_data["trade_type"],
                market_name=tx_data.get("market_name", "Unknown"),
                outcome=tx_data.get("outcome", "Unknown"),
                amount=tx_data.get("amount", 0),
                price=tx_data.get("price", 0),
                total_usdc=tx_data.get("total_usdc", 0),
                tx_hash=tx_hash,
                event_slug=tx_data.get("event_slug", ""),
                market_slug=tx_data.get("market_slug", ""),
                timestamp=tx.timestamp,
            )
            
            if success:
                self._mark_tx_notified(tx.id)
                logger.info(f"交易通知已发送: {tx_hash}")
            else:
                logger.error(f"交易通知发送失败: {tx_hash}")
        else:
            logger.warning("Telegram 未配置，跳过通知")
    
    def _monitor_loop(self):
        """监控主循环"""
        logger.info("开始监控循环...")
        
        # 初始化最后处理的区块
        try:
            saved_block = get_config("last_processed_block", "0")
            self._last_block = int(saved_block) if saved_block else 0
        except:
            self._last_block = 0
        
        while self._running:
            try:
                self._check_new_transactions()
            except Exception as e:
                logger.error(f"监控循环错误: {e}")
            
            time.sleep(self._poll_interval)
    
    def _check_new_transactions(self):
        """检查新交易"""
        # 获取活跃钱包
        wallets = self._get_active_wallets()
        if not wallets:
            logger.debug("没有活跃的监控钱包")
            return
        
        # 获取最新区块
        try:
            latest_block = self._blockchain.get_latest_block()
        except Exception as e:
            logger.error(f"获取最新区块失败: {e}")
            return
        
        # 确定检查范围
        if self._last_block == 0:
            # 首次运行，从最新区块开始
            from_block = latest_block - 1
        else:
            from_block = self._last_block + 1
        
        # 限制单次检查的区块数
        if latest_block - from_block > self._blocks_to_check:
            from_block = latest_block - self._blocks_to_check
        
        if from_block > latest_block:
            return
        
        logger.debug(f"检查区块 {from_block} 到 {latest_block}")
        
        # 获取交易
        try:
            transactions = self._blockchain.get_transactions_for_wallets(
                wallets, from_block, latest_block
            )
        except Exception as e:
            logger.error(f"获取交易失败: {e}")
            return
        
        # 处理交易
        for tx_data in transactions:
            try:
                self._process_transaction(tx_data)
            except Exception as e:
                logger.error(f"处理交易失败: {e}")
        
        # 更新最后处理的区块
        self._last_block = latest_block
        set_config("last_processed_block", str(latest_block))
    
    def get_status(self) -> Dict[str, Any]:
        """获取监控状态"""
        is_connected = self._blockchain.is_connected()
        
        return {
            "running": self._running,
            "connected": is_connected,
            "last_block": self._last_block,
            "rpc_url": self._blockchain.rpc_url if is_connected else None,
            "poll_interval": self._poll_interval,
            "telegram_configured": self._telegram.is_configured(),
        }


# 单例实例
_monitor_service: Optional[MonitorService] = None


def get_monitor_service() -> MonitorService:
    """获取监控服务单例"""
    global _monitor_service
    if _monitor_service is None:
        _monitor_service = MonitorService()
    return _monitor_service
