"""
区块链交互服务
监听 Polygon 链上的 Polymarket 交易
"""
import json
import logging
from typing import Optional, List, Dict, Any
from web3 import Web3
from web3.exceptions import BlockNotFound
from app.config import POLYGON_RPC_URL, POLYGON_RPC_URLS, CONTRACTS

logger = logging.getLogger(__name__)

# CTF Exchange ABI - 只包含我们需要的事件
CTF_EXCHANGE_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "orderHash", "type": "bytes32"},
            {"indexed": True, "name": "maker", "type": "address"},
            {"indexed": True, "name": "taker", "type": "address"},
            {"indexed": False, "name": "makerAssetId", "type": "uint256"},
            {"indexed": False, "name": "takerAssetId", "type": "uint256"},
            {"indexed": False, "name": "makerAmountFilled", "type": "uint256"},
            {"indexed": False, "name": "takerAmountFilled", "type": "uint256"},
            {"indexed": False, "name": "fee", "type": "uint256"},
        ],
        "name": "OrderFilled",
        "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "takerOrderHash", "type": "bytes32"},
            {"indexed": True, "name": "takerOrderMaker", "type": "address"},
            {"indexed": False, "name": "makerAssetId", "type": "uint256"},
            {"indexed": False, "name": "takerAssetId", "type": "uint256"},
            {"indexed": False, "name": "makerAmountFilled", "type": "uint256"},
            {"indexed": False, "name": "takerAmountFilled", "type": "uint256"},
        ],
        "name": "OrdersMatched",
        "type": "event",
    },
]

# Conditional Tokens ABI - Transfer 事件
CONDITIONAL_TOKENS_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "operator", "type": "address"},
            {"indexed": True, "name": "from", "type": "address"},
            {"indexed": True, "name": "to", "type": "address"},
            {"indexed": False, "name": "id", "type": "uint256"},
            {"indexed": False, "name": "value", "type": "uint256"},
        ],
        "name": "TransferSingle",
        "type": "event",
    },
]


class BlockchainService:
    """区块链服务 - 监听Polymarket交易"""
    
    def __init__(self, rpc_url: str = None):
        self.rpc_url = rpc_url or POLYGON_RPC_URL
        self.w3: Optional[Web3] = None
        self.ctf_exchange = None
        self.neg_risk_ctf_exchange = None
        self.conditional_tokens = None
        self._connect()
    
    def _connect(self) -> bool:
        """连接到区块链节点"""
        # 尝试多个 RPC 节点
        urls_to_try = [self.rpc_url] + [u for u in POLYGON_RPC_URLS if u != self.rpc_url]
        
        for url in urls_to_try:
            try:
                self.w3 = Web3(Web3.HTTPProvider(url, request_kwargs={'timeout': 30}))
                if self.w3.is_connected():
                    logger.info(f"成功连接到 Polygon 节点: {url}")
                    self.rpc_url = url
                    self._init_contracts()
                    return True
            except Exception as e:
                logger.warning(f"连接到 {url} 失败: {e}")
                continue
        
        logger.error("无法连接到任何 Polygon RPC 节点")
        return False
    
    def _init_contracts(self):
        """初始化合约实例"""
        self.ctf_exchange = self.w3.eth.contract(
            address=Web3.to_checksum_address(CONTRACTS["CTF_EXCHANGE"]),
            abi=CTF_EXCHANGE_ABI
        )
        self.neg_risk_ctf_exchange = self.w3.eth.contract(
            address=Web3.to_checksum_address(CONTRACTS["NEG_RISK_CTF_EXCHANGE"]),
            abi=CTF_EXCHANGE_ABI
        )
        self.conditional_tokens = self.w3.eth.contract(
            address=Web3.to_checksum_address(CONTRACTS["CONDITIONAL_TOKENS"]),
            abi=CONDITIONAL_TOKENS_ABI
        )
    
    def is_connected(self) -> bool:
        """检查是否已连接"""
        try:
            return self.w3 is not None and self.w3.is_connected()
        except:
            return False
    
    def get_latest_block(self) -> int:
        """获取最新区块号"""
        if not self.is_connected():
            self._connect()
        return self.w3.eth.block_number
    
    def get_block_timestamp(self, block_number: int) -> int:
        """获取区块时间戳"""
        try:
            block = self.w3.eth.get_block(block_number)
            return block['timestamp']
        except BlockNotFound:
            return 0
    
    def get_transactions_for_wallets(
        self, 
        wallet_addresses: List[str], 
        from_block: int, 
        to_block: int
    ) -> List[Dict[str, Any]]:
        """
        获取指定钱包在区块范围内的 Polymarket 交易
        """
        if not self.is_connected():
            if not self._connect():
                return []
        
        transactions = []
        wallet_set = set(addr.lower() for addr in wallet_addresses)
        
        # 检查两个交易合约的 OrderFilled 事件
        for contract_name, contract in [
            ("CTF_EXCHANGE", self.ctf_exchange),
            ("NEG_RISK_CTF_EXCHANGE", self.neg_risk_ctf_exchange)
        ]:
            try:
                # 获取 OrderFilled 事件
                events = contract.events.OrderFilled.get_logs(
                    fromBlock=from_block,
                    toBlock=to_block
                )
                
                for event in events:
                    maker = event['args']['maker'].lower()
                    taker = event['args']['taker'].lower()
                    
                    # 检查是否是我们监控的钱包
                    if maker in wallet_set or taker in wallet_set:
                        tx_data = self._parse_order_filled_event(event, maker, taker, wallet_set, contract_name)
                        if tx_data:
                            transactions.append(tx_data)
                            
            except Exception as e:
                logger.error(f"获取 {contract_name} OrderFilled 事件失败: {e}")
        
        return transactions
    
    def _parse_order_filled_event(
        self, 
        event: Dict, 
        maker: str, 
        taker: str, 
        wallet_set: set,
        contract_name: str
    ) -> Optional[Dict[str, Any]]:
        """解析 OrderFilled 事件"""
        try:
            args = event['args']
            tx_hash = event['transactionHash'].hex()
            block_number = event['blockNumber']
            
            # 确定是哪个钱包的交易，以及是买还是卖
            # maker 是挂单方，taker 是吃单方
            # makerAssetId = 0 表示 maker 卖出 USDC，买入条件代币 (maker 是买方)
            # makerAssetId != 0 表示 maker 卖出条件代币，买入 USDC (maker 是卖方)
            
            maker_asset_id = args['makerAssetId']
            taker_asset_id = args['takerAssetId']
            maker_amount = args['makerAmountFilled']
            taker_amount = args['takerAmountFilled']
            
            # 判断我们监控的钱包的交易方向
            if maker in wallet_set:
                wallet_address = maker
                if maker_asset_id == 0:
                    # maker 用 USDC 买入条件代币
                    trade_type = "BUY"
                    token_id = str(taker_asset_id)
                    usdc_amount = maker_amount / 1e6  # USDC 6位小数
                    token_amount = taker_amount / 1e6  # 条件代币也是6位小数
                else:
                    # maker 卖出条件代币换取 USDC
                    trade_type = "SELL"
                    token_id = str(maker_asset_id)
                    token_amount = maker_amount / 1e6
                    usdc_amount = taker_amount / 1e6
            else:
                wallet_address = taker
                if taker_asset_id == 0:
                    # taker 用 USDC 买入条件代币
                    trade_type = "BUY"
                    token_id = str(maker_asset_id)
                    usdc_amount = taker_amount / 1e6
                    token_amount = maker_amount / 1e6
                else:
                    # taker 卖出条件代币换取 USDC
                    trade_type = "SELL"
                    token_id = str(taker_asset_id)
                    token_amount = taker_amount / 1e6
                    usdc_amount = maker_amount / 1e6
            
            # 计算价格
            price = usdc_amount / token_amount if token_amount > 0 else 0
            
            return {
                "wallet_address": Web3.to_checksum_address(wallet_address),
                "tx_hash": tx_hash,
                "block_number": block_number,
                "trade_type": trade_type,
                "token_id": token_id,
                "amount": token_amount,
                "price": round(price, 4),
                "total_usdc": round(usdc_amount, 2),
                "contract": contract_name,
                "raw_data": json.dumps({
                    "maker": maker,
                    "taker": taker,
                    "makerAssetId": str(maker_asset_id),
                    "takerAssetId": str(taker_asset_id),
                    "makerAmountFilled": str(maker_amount),
                    "takerAmountFilled": str(taker_amount),
                    "fee": str(args.get('fee', 0)),
                }),
            }
            
        except Exception as e:
            logger.error(f"解析 OrderFilled 事件失败: {e}")
            return None


# 单例实例
_blockchain_service: Optional[BlockchainService] = None


def get_blockchain_service() -> BlockchainService:
    """获取区块链服务单例"""
    global _blockchain_service
    if _blockchain_service is None:
        _blockchain_service = BlockchainService()
    return _blockchain_service
