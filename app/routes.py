"""
Flask API 路由
"""
import logging
from flask import Blueprint, request, jsonify, render_template
from app.models import (
    get_session, Wallet, Transaction, 
    get_config, set_config,
    CopyTradeConfig, CopyTradePosition, CopyTradeRecord
)
from app.services.monitor import get_monitor_service
from app.services.telegram import get_telegram_service
from app.services.blockchain import get_blockchain_service
from app.services.copytrade import get_copytrade_service
from web3 import Web3
from datetime import datetime

logger = logging.getLogger(__name__)

api = Blueprint('api', __name__, url_prefix='/api')


# ==================== 页面路由 ====================

@api.route('/')
def index():
    """主页"""
    return render_template('index.html')


# ==================== 状态 API ====================

@api.route('/status', methods=['GET'])
def get_status():
    """获取系统状态"""
    monitor = get_monitor_service()
    status = monitor.get_status()
    
    # 获取钱包数量
    session = get_session()
    try:
        total_wallets = session.query(Wallet).count()
        active_wallets = session.query(Wallet).filter(Wallet.is_active == True).count()
    finally:
        session.close()
    
    status["total_wallets"] = total_wallets
    status["active_wallets"] = active_wallets
    
    return jsonify(status)


# ==================== 钱包 API ====================

@api.route('/wallets', methods=['GET'])
def list_wallets():
    """获取所有钱包"""
    session = get_session()
    try:
        wallets = session.query(Wallet).order_by(Wallet.created_at.desc()).all()
        return jsonify([w.to_dict() for w in wallets])
    finally:
        session.close()


@api.route('/wallets', methods=['POST'])
def add_wallet():
    """添加钱包"""
    data = request.get_json()
    
    address = data.get('address', '').strip()
    name = data.get('name', '').strip()
    
    if not address:
        return jsonify({"error": "钱包地址不能为空"}), 400
    
    # 验证地址格式
    try:
        address = Web3.to_checksum_address(address)
    except:
        return jsonify({"error": "无效的钱包地址格式"}), 400
    
    if not name:
        name = f"Wallet_{address[:6]}"
    
    session = get_session()
    try:
        # 检查是否已存在
        existing = session.query(Wallet).filter(
            Wallet.address.ilike(address)
        ).first()
        
        if existing:
            return jsonify({"error": "该钱包已存在"}), 400
        
        wallet = Wallet(address=address, name=name, is_active=True)
        session.add(wallet)
        session.commit()
        session.refresh(wallet)
        
        logger.info(f"添加钱包: {name} ({address})")
        return jsonify(wallet.to_dict()), 201
        
    except Exception as e:
        session.rollback()
        logger.error(f"添加钱包失败: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@api.route('/wallets/<int:wallet_id>', methods=['PUT'])
def update_wallet(wallet_id):
    """更新钱包"""
    data = request.get_json()
    
    session = get_session()
    try:
        wallet = session.query(Wallet).filter(Wallet.id == wallet_id).first()
        
        if not wallet:
            return jsonify({"error": "钱包不存在"}), 404
        
        if 'name' in data:
            wallet.name = data['name'].strip()
        
        if 'is_active' in data:
            wallet.is_active = bool(data['is_active'])
        
        session.commit()
        session.refresh(wallet)
        
        return jsonify(wallet.to_dict())
        
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@api.route('/wallets/<int:wallet_id>', methods=['DELETE'])
def delete_wallet(wallet_id):
    """删除钱包"""
    session = get_session()
    try:
        wallet = session.query(Wallet).filter(Wallet.id == wallet_id).first()
        
        if not wallet:
            return jsonify({"error": "钱包不存在"}), 404
        
        address = wallet.address
        session.delete(wallet)
        session.commit()
        
        logger.info(f"删除钱包: {address}")
        return jsonify({"message": "删除成功"})
        
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@api.route('/wallets/<int:wallet_id>/toggle', methods=['POST'])
def toggle_wallet(wallet_id):
    """切换钱包监控状态"""
    session = get_session()
    try:
        wallet = session.query(Wallet).filter(Wallet.id == wallet_id).first()
        
        if not wallet:
            return jsonify({"error": "钱包不存在"}), 404
        
        wallet.is_active = not wallet.is_active
        session.commit()
        session.refresh(wallet)
        
        return jsonify(wallet.to_dict())
        
    finally:
        session.close()


# ==================== 交易 API ====================

@api.route('/transactions', methods=['GET'])
def list_transactions():
    """获取交易记录"""
    limit = request.args.get('limit', 50, type=int)
    wallet_address = request.args.get('wallet', '')
    
    session = get_session()
    try:
        query = session.query(Transaction).order_by(Transaction.timestamp.desc())
        
        if wallet_address:
            query = query.filter(Transaction.wallet_address.ilike(wallet_address))
        
        transactions = query.limit(limit).all()
        return jsonify([t.to_dict() for t in transactions])
        
    finally:
        session.close()


# ==================== 配置 API ====================

@api.route('/config', methods=['GET'])
def get_all_config():
    """获取配置"""
    return jsonify({
        "telegram_bot_token": get_config("telegram_bot_token", ""),
        "telegram_chat_id": get_config("telegram_chat_id", ""),
    })


@api.route('/config', methods=['POST'])
def save_config():
    """保存配置"""
    data = request.get_json()
    
    if 'telegram_bot_token' in data:
        set_config("telegram_bot_token", data['telegram_bot_token'])
    
    if 'telegram_chat_id' in data:
        set_config("telegram_chat_id", data['telegram_chat_id'])
    
    logger.info("配置已更新")
    return jsonify({"message": "配置保存成功"})


@api.route('/config/test-telegram', methods=['POST'])
def test_telegram():
    """测试 Telegram 连接"""
    telegram = get_telegram_service()
    success, message = telegram.test_connection()
    
    return jsonify({
        "success": success,
        "message": message
    })


# ==================== 监控控制 API ====================

@api.route('/monitor/start', methods=['POST'])
def start_monitor():
    """启动监控"""
    monitor = get_monitor_service()
    monitor.start()
    return jsonify({"message": "监控已启动", "running": True})


@api.route('/monitor/stop', methods=['POST'])
def stop_monitor():
    """停止监控"""
    monitor = get_monitor_service()
    monitor.stop()
    return jsonify({"message": "监控已停止", "running": False})


# ==================== 工具 API ====================

@api.route('/blockchain/status', methods=['GET'])
def blockchain_status():
    """获取区块链连接状态"""
    blockchain = get_blockchain_service()
    
    try:
        is_connected = blockchain.is_connected()
        latest_block = blockchain.get_latest_block() if is_connected else 0
        
        return jsonify({
            "connected": is_connected,
            "rpc_url": blockchain.rpc_url,
            "latest_block": latest_block,
        })
    except Exception as e:
        return jsonify({
            "connected": False,
            "error": str(e),
        })


# ==================== 跟单配置 API ====================

@api.route('/copytrade/config', methods=['GET'])
def get_copytrade_config():
    """获取跟单配置"""
    service = get_copytrade_service()
    config = service.get_config()
    return jsonify(config.to_dict())


@api.route('/copytrade/config', methods=['POST'])
def update_copytrade_config():
    """更新跟单配置"""
    data = request.get_json()
    service = get_copytrade_service()
    
    try:
        config = service.update_config(**data)
        logger.info(f"跟单配置已更新: {data}")
        return jsonify(config.to_dict())
    except Exception as e:
        logger.error(f"更新跟单配置失败: {e}")
        return jsonify({"error": str(e)}), 500


@api.route('/copytrade/toggle', methods=['POST'])
def toggle_copytrade():
    """切换跟单开关"""
    service = get_copytrade_service()
    config = service.get_config()
    new_state = not config.enabled
    service.update_config(enabled=new_state)
    
    logger.info(f"跟单已{'启用' if new_state else '停用'}")
    return jsonify({
        "enabled": new_state,
        "message": f"跟单已{'启用' if new_state else '停用'}"
    })


# ==================== 跟单持仓 API ====================

@api.route('/copytrade/positions', methods=['GET'])
def get_copytrade_positions():
    """获取模拟持仓"""
    service = get_copytrade_service()
    positions = service.get_positions()
    return jsonify(positions)


@api.route('/copytrade/positions/close-all', methods=['POST'])
def close_all_positions():
    """一键平仓所有持仓"""
    service = get_copytrade_service()
    result = service.close_all_positions()
    logger.info(f"一键平仓: 关闭 {result['closed_count']} 个持仓, 实现盈亏 ${result['total_realized_pnl']}")
    return jsonify(result)


# ==================== 跟单记录 API ====================

@api.route('/copytrade/records', methods=['GET'])
def get_copytrade_records():
    """获取跟单记录"""
    limit = request.args.get('limit', 50, type=int)
    service = get_copytrade_service()
    records = service.get_records(limit)
    return jsonify(records)


# ==================== 跟单统计 API ====================

@api.route('/copytrade/stats', methods=['GET'])
def get_copytrade_stats():
    """获取跟单统计"""
    service = get_copytrade_service()
    stats = service.get_stats_summary()
    return jsonify(stats)


# ==================== 跟单重置 API ====================

@api.route('/copytrade/reset', methods=['POST'])
def reset_copytrade():
    """重置模拟数据"""
    service = get_copytrade_service()
    success = service.reset_simulation()
    
    if success:
        return jsonify({"message": "模拟数据已重置"})
    else:
        return jsonify({"error": "重置失败"}), 500
