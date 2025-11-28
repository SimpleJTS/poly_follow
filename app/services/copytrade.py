"""
跟单交易服务
处理模拟跟单逻辑、持仓管理、盈亏计算
"""
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy import func
from app.models import (
    get_session, 
    CopyTradeConfig, 
    CopyTradePosition, 
    CopyTradeRecord,
    CopyTradeStats,
    Wallet
)
from app.services.polymarket import get_polymarket_api

logger = logging.getLogger(__name__)


class CopyTradeService:
    """跟单交易服务"""
    
    def __init__(self):
        self._polymarket = get_polymarket_api()
    
    def get_config(self) -> CopyTradeConfig:
        """获取跟单配置，不存在则创建默认配置"""
        session = get_session()
        try:
            config = session.query(CopyTradeConfig).first()
            if not config:
                config = CopyTradeConfig()
                session.add(config)
                session.commit()
                session.refresh(config)
            return config
        finally:
            session.close()
    
    def update_config(self, **kwargs) -> CopyTradeConfig:
        """更新跟单配置"""
        session = get_session()
        try:
            config = session.query(CopyTradeConfig).first()
            if not config:
                config = CopyTradeConfig()
                session.add(config)
            
            for key, value in kwargs.items():
                if hasattr(config, key):
                    setattr(config, key, value)
            
            session.commit()
            session.refresh(config)
            
            # 返回一个可序列化的副本
            return self.get_config()
        finally:
            session.close()
    
    def should_copy_trade(self, tx_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        判断是否应该跟单
        返回: (是否跟单, 原因)
        """
        config = self.get_config()
        
        # 检查是否启用跟单
        if not config.enabled:
            return False, "跟单未启用"
        
        trade_type = tx_data.get("trade_type", "")
        price = tx_data.get("price", 0)
        total_usdc = tx_data.get("total_usdc", 0)
        
        # 检查跟单方向
        if config.copy_direction == "buy_only" and trade_type != "BUY":
            return False, "只跟单买入，跳过卖出"
        if config.copy_direction == "sell_only" and trade_type != "SELL":
            return False, "只跟单卖出，跳过买入"
        
        # 检查价格范围
        if price < config.min_price:
            return False, f"价格 {price} 低于最低限制 {config.min_price}"
        if price > config.max_price:
            return False, f"价格 {price} 高于最高限制 {config.max_price}"
        
        # 计算跟单金额
        copy_amount = total_usdc * (config.copy_ratio / 100)
        
        # 检查最小金额
        if copy_amount < config.min_amount:
            return False, f"跟单金额 {copy_amount:.2f} 低于最小限制 {config.min_amount}"
        
        # 检查单笔最大金额
        if copy_amount > config.max_amount:
            copy_amount = config.max_amount
        
        # 检查总持仓上限
        total_position = self.get_total_position_value()
        if trade_type == "BUY" and total_position + copy_amount > config.max_total_position:
            return False, f"总持仓将超过上限 {config.max_total_position}"
        
        # 检查单市场持仓上限
        token_id = tx_data.get("token_id", "")
        if token_id and trade_type == "BUY":
            market_position = self.get_position_value_by_token(token_id)
            if market_position + copy_amount > config.max_position_per_market:
                return False, f"市场持仓将超过上限 {config.max_position_per_market}"
        
        return True, "符合跟单条件"
    
    def calculate_copy_amount(self, tx_data: Dict[str, Any]) -> Dict[str, float]:
        """计算跟单金额和股数"""
        config = self.get_config()
        
        total_usdc = tx_data.get("total_usdc", 0)
        price = tx_data.get("price", 0)
        
        # 按比例计算
        copy_amount = total_usdc * (config.copy_ratio / 100)
        
        # 限制在最大金额内
        if copy_amount > config.max_amount:
            copy_amount = config.max_amount
        
        # 计算股数
        copy_shares = copy_amount / price if price > 0 else 0
        
        return {
            "copy_amount": round(copy_amount, 2),
            "copy_shares": round(copy_shares, 2),
            "copy_price": price
        }
    
    def execute_simulation_trade(self, tx_data: Dict[str, Any], wallet_name: str) -> Optional[CopyTradeRecord]:
        """
        执行模拟跟单
        """
        session = get_session()
        try:
            # 检查是否应该跟单
            should_copy, reason = self.should_copy_trade(tx_data)
            
            # 创建跟单记录
            record = CopyTradeRecord(
                source_tx_hash=tx_data.get("tx_hash", ""),
                source_wallet_address=tx_data.get("wallet_address", ""),
                source_wallet_name=wallet_name,
                token_id=tx_data.get("token_id"),
                market_id=tx_data.get("market_id"),
                market_name=tx_data.get("market_name"),
                market_slug=tx_data.get("market_slug"),
                event_slug=tx_data.get("event_slug"),
                outcome=tx_data.get("outcome"),
                trade_type=tx_data.get("trade_type", ""),
                source_amount=tx_data.get("total_usdc"),
                source_shares=tx_data.get("amount"),
                source_price=tx_data.get("price"),
                is_simulation=True
            )
            
            if not should_copy:
                record.status = "skipped"
                record.skip_reason = reason
                session.add(record)
                session.commit()
                logger.info(f"跳过跟单: {reason}")
                return record
            
            # 计算跟单金额
            copy_info = self.calculate_copy_amount(tx_data)
            record.copy_amount = copy_info["copy_amount"]
            record.copy_shares = copy_info["copy_shares"]
            record.copy_price = copy_info["copy_price"]
            
            # 执行模拟交易
            trade_type = tx_data.get("trade_type", "")
            if trade_type == "BUY":
                realized_pnl = self._simulate_buy(tx_data, copy_info, session)
            else:
                realized_pnl = self._simulate_sell(tx_data, copy_info, session)
            
            record.status = "success"
            record.realized_pnl = realized_pnl
            session.add(record)
            
            # 更新每日统计
            self._update_daily_stats(record, session)
            
            session.commit()
            logger.info(f"模拟跟单成功: {trade_type} {copy_info['copy_shares']:.2f} 股 @ ${copy_info['copy_price']:.4f}")
            
            return record
            
        except Exception as e:
            session.rollback()
            logger.error(f"模拟跟单失败: {e}")
            return None
        finally:
            session.close()
    
    def _simulate_buy(self, tx_data: Dict, copy_info: Dict, session) -> float:
        """模拟买入"""
        token_id = tx_data.get("token_id", "")
        
        # 查找或创建持仓
        position = session.query(CopyTradePosition).filter(
            CopyTradePosition.token_id == token_id
        ).first()
        
        if position:
            # 更新现有持仓
            old_cost = position.total_cost
            old_shares = position.shares
            new_shares = copy_info["copy_shares"]
            new_cost = copy_info["copy_amount"]
            
            position.shares = old_shares + new_shares
            position.total_cost = old_cost + new_cost
            position.avg_price = position.total_cost / position.shares if position.shares > 0 else 0
        else:
            # 创建新持仓
            position = CopyTradePosition(
                token_id=token_id,
                market_id=tx_data.get("market_id"),
                market_name=tx_data.get("market_name"),
                market_slug=tx_data.get("market_slug"),
                event_slug=tx_data.get("event_slug"),
                outcome=tx_data.get("outcome"),
                shares=copy_info["copy_shares"],
                avg_price=copy_info["copy_price"],
                total_cost=copy_info["copy_amount"],
                current_price=copy_info["copy_price"]
            )
            session.add(position)
        
        # 更新当前价值
        position.current_price = copy_info["copy_price"]
        position.current_value = position.shares * position.current_price
        position.unrealized_pnl = position.current_value - position.total_cost
        position.unrealized_pnl_percent = (position.unrealized_pnl / position.total_cost * 100) if position.total_cost > 0 else 0
        
        return 0  # 买入不产生已实现盈亏
    
    def _simulate_sell(self, tx_data: Dict, copy_info: Dict, session) -> float:
        """模拟卖出"""
        token_id = tx_data.get("token_id", "")
        
        position = session.query(CopyTradePosition).filter(
            CopyTradePosition.token_id == token_id
        ).first()
        
        if not position or position.shares <= 0:
            logger.warning(f"没有持仓可卖出: {token_id}")
            return 0
        
        # 计算卖出股数（不能超过持仓）
        sell_shares = min(copy_info["copy_shares"], position.shares)
        sell_value = sell_shares * copy_info["copy_price"]
        
        # 计算已实现盈亏
        cost_basis = sell_shares * position.avg_price
        realized_pnl = sell_value - cost_basis
        
        # 更新持仓
        position.shares -= sell_shares
        position.total_cost -= cost_basis
        
        if position.shares <= 0.001:  # 清仓
            session.delete(position)
        else:
            position.current_value = position.shares * position.current_price
            position.unrealized_pnl = position.current_value - position.total_cost
            position.unrealized_pnl_percent = (position.unrealized_pnl / position.total_cost * 100) if position.total_cost > 0 else 0
        
        return realized_pnl
    
    def _update_daily_stats(self, record: CopyTradeRecord, session):
        """更新每日统计"""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        
        stats = session.query(CopyTradeStats).filter(
            CopyTradeStats.date == today
        ).first()
        
        if not stats:
            stats = CopyTradeStats(date=today)
            session.add(stats)
        
        stats.total_trades += 1
        
        if record.status == "success":
            stats.successful_trades += 1
            if record.trade_type == "BUY":
                stats.total_buy_amount += record.copy_amount or 0
            else:
                stats.total_sell_amount += record.copy_amount or 0
            if record.realized_pnl:
                stats.realized_pnl += record.realized_pnl
        elif record.status == "skipped":
            stats.skipped_trades += 1
        else:
            stats.failed_trades += 1
    
    def get_positions(self) -> List[Dict]:
        """获取所有持仓"""
        session = get_session()
        try:
            positions = session.query(CopyTradePosition).filter(
                CopyTradePosition.shares > 0.001
            ).order_by(CopyTradePosition.updated_at.desc()).all()
            return [p.to_dict() for p in positions]
        finally:
            session.close()
    
    def get_total_position_value(self) -> float:
        """获取总持仓价值"""
        session = get_session()
        try:
            result = session.query(func.sum(CopyTradePosition.current_value)).filter(
                CopyTradePosition.shares > 0.001
            ).scalar()
            return result or 0
        finally:
            session.close()
    
    def get_position_value_by_token(self, token_id: str) -> float:
        """获取某个代币的持仓价值"""
        session = get_session()
        try:
            position = session.query(CopyTradePosition).filter(
                CopyTradePosition.token_id == token_id
            ).first()
            return position.current_value if position else 0
        finally:
            session.close()
    
    def get_records(self, limit: int = 50) -> List[Dict]:
        """获取跟单记录"""
        session = get_session()
        try:
            records = session.query(CopyTradeRecord).order_by(
                CopyTradeRecord.created_at.desc()
            ).limit(limit).all()
            return [r.to_dict() for r in records]
        finally:
            session.close()
    
    def get_stats_summary(self) -> Dict[str, Any]:
        """获取统计摘要"""
        session = get_session()
        try:
            # 总持仓信息
            positions = session.query(CopyTradePosition).filter(
                CopyTradePosition.shares > 0.001
            ).all()
            
            total_cost = sum(p.total_cost for p in positions)
            total_value = sum(p.current_value for p in positions)
            total_unrealized_pnl = sum(p.unrealized_pnl for p in positions)
            
            # 总已实现盈亏
            total_realized_pnl = session.query(func.sum(CopyTradeRecord.realized_pnl)).filter(
                CopyTradeRecord.status == "success"
            ).scalar() or 0
            
            # 交易统计
            total_trades = session.query(CopyTradeRecord).count()
            successful_trades = session.query(CopyTradeRecord).filter(
                CopyTradeRecord.status == "success"
            ).count()
            
            # 获取配置
            config = self.get_config()
            
            return {
                "total_cost": round(total_cost, 2),
                "total_value": round(total_value, 2),
                "total_unrealized_pnl": round(total_unrealized_pnl, 2),
                "total_unrealized_pnl_percent": round(total_unrealized_pnl / total_cost * 100, 2) if total_cost > 0 else 0,
                "total_realized_pnl": round(total_realized_pnl, 2),
                "total_pnl": round(total_unrealized_pnl + total_realized_pnl, 2),
                "total_trades": total_trades,
                "successful_trades": successful_trades,
                "position_count": len(positions),
                "simulation_balance": config.simulation_balance,
                "available_balance": round(config.simulation_balance - total_cost + total_realized_pnl, 2)
            }
        finally:
            session.close()
    
    def update_positions_prices(self):
        """更新所有持仓的当前价格（从API获取）"""
        session = get_session()
        try:
            positions = session.query(CopyTradePosition).filter(
                CopyTradePosition.shares > 0.001
            ).all()
            
            for position in positions:
                market_info = self._polymarket.get_market_by_token_id(position.token_id)
                if market_info:
                    # 这里需要获取当前价格，暂时保持不变
                    # 实际实现需要调用 Polymarket API 获取实时价格
                    pass
                
                # 更新计算值
                position.current_value = position.shares * position.current_price
                position.unrealized_pnl = position.current_value - position.total_cost
                position.unrealized_pnl_percent = (position.unrealized_pnl / position.total_cost * 100) if position.total_cost > 0 else 0
            
            session.commit()
        finally:
            session.close()
    
    def close_all_positions(self) -> Dict[str, Any]:
        """一键平仓所有持仓（模拟）"""
        session = get_session()
        try:
            positions = session.query(CopyTradePosition).filter(
                CopyTradePosition.shares > 0.001
            ).all()
            
            total_realized_pnl = 0
            closed_count = 0
            
            for position in positions:
                # 计算已实现盈亏
                realized_pnl = position.current_value - position.total_cost
                total_realized_pnl += realized_pnl
                
                # 创建平仓记录
                record = CopyTradeRecord(
                    source_tx_hash=f"manual_close_{datetime.utcnow().timestamp()}",
                    source_wallet_address="manual",
                    source_wallet_name="手动平仓",
                    token_id=position.token_id,
                    market_id=position.market_id,
                    market_name=position.market_name,
                    market_slug=position.market_slug,
                    event_slug=position.event_slug,
                    outcome=position.outcome,
                    trade_type="SELL",
                    source_amount=position.current_value,
                    source_shares=position.shares,
                    source_price=position.current_price,
                    copy_shares=position.shares,
                    copy_price=position.current_price,
                    copy_amount=position.current_value,
                    status="success",
                    is_simulation=True,
                    realized_pnl=realized_pnl
                )
                session.add(record)
                
                # 删除持仓
                session.delete(position)
                closed_count += 1
            
            session.commit()
            
            return {
                "closed_count": closed_count,
                "total_realized_pnl": round(total_realized_pnl, 2)
            }
        finally:
            session.close()
    
    def reset_simulation(self) -> bool:
        """重置模拟（清空所有持仓和记录）"""
        session = get_session()
        try:
            session.query(CopyTradePosition).delete()
            session.query(CopyTradeRecord).delete()
            session.query(CopyTradeStats).delete()
            session.commit()
            logger.info("模拟数据已重置")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"重置模拟失败: {e}")
            return False
        finally:
            session.close()


# 单例实例
_copytrade_service: Optional[CopyTradeService] = None


def get_copytrade_service() -> CopyTradeService:
    """获取跟单服务单例"""
    global _copytrade_service
    if _copytrade_service is None:
        _copytrade_service = CopyTradeService()
    return _copytrade_service
