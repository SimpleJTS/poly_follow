# 🐋 Polymarket 聪明钱监控系统

实时监控 Polymarket 上指定钱包（聪明钱）的交易行为，并通过 Telegram 发送通知。

## ✨ 功能特性

- 📊 **链上实时监听** - 监听 Polygon 链上的 Polymarket 交易事件
- 👛 **多钱包管理** - 支持添加多个钱包进行监控
- 📱 **Telegram 通知** - 交易发生时即时推送通知
- 🔗 **完整链接** - 通知包含交易详情、市场链接、钱包持仓链接
- 🖥️ **Web 管理界面** - 简洁美观的管理界面

## 🚀 快速开始

### Docker 部署（推荐）

```bash
# 1. 构建镜像
docker build -t polymarket-monitor .

# 2. 运行容器
docker run -d \
  --name polymarket-monitor \
  -p 5000:5000 \
  -v $(pwd)/data:/app/data \
  --restart unless-stopped \
  polymarket-monitor

# 3. 查看日志
docker logs -f polymarket-monitor
```

### 环境变量配置（可选）

```bash
docker run -d \
  --name polymarket-monitor \
  -p 5000:5000 \
  -v $(pwd)/data:/app/data \
  -e POLYGON_RPC_URL="https://polygon-rpc.com" \
  -e TELEGRAM_BOT_TOKEN="your_bot_token" \
  -e TELEGRAM_CHAT_ID="your_chat_id" \
  -e POLL_INTERVAL=5 \
  -e LOG_LEVEL=INFO \
  --restart unless-stopped \
  polymarket-monitor
```

### 本地运行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 运行
python run.py
```

## 📖 使用说明

### 1. 访问管理界面

启动后访问: `http://localhost:5000`

### 2. 配置 Telegram

1. 创建 Telegram Bot:
   - 在 Telegram 搜索 `@BotFather`
   - 发送 `/newbot` 创建新 Bot
   - 复制获得的 Bot Token

2. 获取 Chat ID:
   - **个人聊天**: 搜索 `@userinfobot`，发送任意消息获取你的 Chat ID
   - **群组**: 将 Bot 加入群组，访问 `https://api.telegram.org/bot<TOKEN>/getUpdates` 查看群组 ID（负数）

3. 在 Web 界面填入 Bot Token 和 Chat ID，点击"保存配置"

4. 点击"测试连接"验证配置是否正确

### 3. 添加监控钱包

1. 点击"添加钱包"
2. 输入钱包地址（0x 开头的 42 位地址）
3. 输入备注名称（方便识别）
4. 点击"确认"

### 4. 监控控制

- 系统启动后自动开始监控
- 可以在控制面板手动启动/停止监控
- 可以单独暂停某个钱包的监控

## 📝 通知示例

```
🚨 聪明钱交易提醒

👛 钱包: Whale_Alpha
📍 地址: 0x1234...5678

📊 交易详情:
• 类型: 🟢 买入
• 市场: Will Trump win the 2024 election?
• 结果: Yes
• 数量: 10,000.00 股
• 价格: $0.5200
• 总额: $5,200.00 USDC

⏰ 时间: 2024-01-15 14:30:25 UTC

🔗 快捷链接:
• 查看交易
• 查看市场
• 钱包持仓
```

## ⚙️ 配置说明

| 环境变量 | 说明 | 默认值 |
|---------|------|--------|
| `POLYGON_RPC_URL` | Polygon RPC 节点 URL | `https://polygon-rpc.com` |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token | - |
| `TELEGRAM_CHAT_ID` | Telegram Chat ID | - |
| `POLL_INTERVAL` | 轮询间隔（秒） | `5` |
| `BLOCKS_TO_CHECK` | 每次检查的区块数 | `10` |
| `WEB_HOST` | Web 服务监听地址 | `0.0.0.0` |
| `WEB_PORT` | Web 服务端口 | `5000` |
| `LOG_LEVEL` | 日志级别 | `INFO` |

## 🔧 RPC 节点

默认使用免费的公共 RPC 节点，如需更好的性能和稳定性，建议使用：

- [Alchemy](https://www.alchemy.com/) - 免费额度充足
- [Infura](https://infura.io/) - 稳定可靠
- [QuickNode](https://www.quicknode.com/) - 高性能

## 📁 数据存储

- 数据存储在 `data/monitor.db` (SQLite)
- 使用 Docker 时，建议挂载 `/app/data` 目录持久化数据

## 🛠️ 常用 Docker 命令

```bash
# 查看运行状态
docker ps

# 查看日志
docker logs -f polymarket-monitor

# 停止容器
docker stop polymarket-monitor

# 启动容器
docker start polymarket-monitor

# 删除容器
docker rm polymarket-monitor

# 重新构建并运行
docker stop polymarket-monitor && docker rm polymarket-monitor
docker build -t polymarket-monitor . && docker run -d --name polymarket-monitor -p 5000:5000 -v $(pwd)/data:/app/data --restart unless-stopped polymarket-monitor
```

## 📌 注意事项

1. **RPC 限流**: 免费 RPC 节点可能有请求限制，如遇到问题可更换节点
2. **数据延迟**: 链上事件通常在几秒内捕获，API 数据可能有几秒延迟
3. **市场信息**: 新创建的市场可能暂时无法获取详细信息

## 📄 License

MIT License
