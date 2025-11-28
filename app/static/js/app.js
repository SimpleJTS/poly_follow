/**
 * Polymarket 聪明钱监控 - 前端应用
 */

// API 基础路径
const API_BASE = '/api';

// 状态
let isMonitorRunning = false;
let isCopyTradeEnabled = false;

// DOM 元素
const elements = {
    statusBadge: document.getElementById('status-badge'),
    statusText: document.querySelector('.status-text'),
    tgToken: document.getElementById('tg-token'),
    tgChatId: document.getElementById('tg-chat-id'),
    configStatus: document.getElementById('config-status'),
    walletList: document.getElementById('wallet-list'),
    transactionList: document.getElementById('transaction-list'),
    addWalletForm: document.getElementById('add-wallet-form'),
    newWalletAddress: document.getElementById('new-wallet-address'),
    newWalletName: document.getElementById('new-wallet-name'),
    latestBlock: document.getElementById('latest-block'),
    rpcUrl: document.getElementById('rpc-url'),
    btnToggleMonitor: document.getElementById('btn-toggle-monitor'),
    // 跟单相关
    copyTradeStatus: document.getElementById('copy-trade-status'),
    btnToggleCopy: document.getElementById('btn-toggle-copy'),
    copytradeSettings: document.getElementById('copytrade-settings'),
    positionList: document.getElementById('position-list'),
    recordList: document.getElementById('record-list'),
};

// ==================== 工具函数 ====================

/**
 * 显示 Toast 通知
 */
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

/**
 * 格式化地址
 */
function formatAddress(address) {
    if (!address) return '-';
    return `${address.slice(0, 8)}...${address.slice(-6)}`;
}

/**
 * 格式化时间
 */
function formatTime(isoString) {
    if (!isoString) return '-';
    const date = new Date(isoString);
    const now = new Date();
    const diff = (now - date) / 1000; // 秒
    
    if (diff < 60) return '刚刚';
    if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`;
    return date.toLocaleDateString('zh-CN');
}

/**
 * 切换密码显示
 */
function togglePassword(inputId) {
    const input = document.getElementById(inputId);
    input.type = input.type === 'password' ? 'text' : 'password';
}

// ==================== API 调用 ====================

/**
 * GET 请求
 */
async function apiGet(endpoint) {
    const response = await fetch(`${API_BASE}${endpoint}`);
    return response.json();
}

/**
 * POST 请求
 */
async function apiPost(endpoint, data = {}) {
    const response = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
    });
    return response.json();
}

/**
 * PUT 请求
 */
async function apiPut(endpoint, data = {}) {
    const response = await fetch(`${API_BASE}${endpoint}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
    });
    return response.json();
}

/**
 * DELETE 请求
 */
async function apiDelete(endpoint) {
    const response = await fetch(`${API_BASE}${endpoint}`, {
        method: 'DELETE',
    });
    return response.json();
}

// ==================== 状态管理 ====================

/**
 * 加载系统状态
 */
async function loadStatus() {
    try {
        const status = await apiGet('/status');
        
        isMonitorRunning = status.running;
        
        // 更新状态徽章
        elements.statusBadge.className = `status-badge ${status.running ? 'running' : 'stopped'}`;
        elements.statusText.textContent = status.running ? '运行中' : '已停止';
        
        // 更新控制面板
        elements.latestBlock.textContent = status.last_block || '-';
        elements.rpcUrl.textContent = status.rpc_url || '-';
        elements.rpcUrl.title = status.rpc_url || '';
        
        // 更新按钮
        elements.btnToggleMonitor.textContent = status.running ? '停止监控' : '启动监控';
        elements.btnToggleMonitor.className = `btn btn-toggle ${status.running ? 'active' : ''}`;
        
    } catch (error) {
        console.error('加载状态失败:', error);
    }
}

/**
 * 加载配置
 */
async function loadConfig() {
    try {
        const config = await apiGet('/config');
        elements.tgToken.value = config.telegram_bot_token || '';
        elements.tgChatId.value = config.telegram_chat_id || '';
    } catch (error) {
        console.error('加载配置失败:', error);
    }
}

/**
 * 保存配置
 */
async function saveConfig() {
    try {
        await apiPost('/config', {
            telegram_bot_token: elements.tgToken.value.trim(),
            telegram_chat_id: elements.tgChatId.value.trim(),
        });
        
        elements.configStatus.textContent = '✓ 已保存';
        elements.configStatus.className = 'config-status success';
        showToast('配置保存成功', 'success');
        
        setTimeout(() => {
            elements.configStatus.textContent = '';
        }, 3000);
        
    } catch (error) {
        elements.configStatus.textContent = '✗ 保存失败';
        elements.configStatus.className = 'config-status error';
        showToast('配置保存失败', 'error');
    }
}

/**
 * 测试 Telegram 连接
 */
async function testTelegram() {
    try {
        showToast('正在测试连接...', 'info');
        const result = await apiPost('/config/test-telegram');
        
        if (result.success) {
            showToast(result.message, 'success');
        } else {
            showToast(result.message, 'error');
        }
    } catch (error) {
        showToast('测试失败: ' + error.message, 'error');
    }
}

// ==================== 钱包管理 ====================

/**
 * 加载钱包列表
 */
async function loadWallets() {
    try {
        const wallets = await apiGet('/wallets');
        renderWallets(wallets);
    } catch (error) {
        console.error('加载钱包失败:', error);
        elements.walletList.innerHTML = '<div class="empty-state"><div class="icon">⚠️</div><p>加载失败</p></div>';
    }
}

/**
 * 渲染钱包列表
 */
function renderWallets(wallets) {
    if (wallets.length === 0) {
        elements.walletList.innerHTML = `
            <div class="empty-state">
                <div class="icon">👛</div>
                <p>暂无监控钱包，点击上方按钮添加</p>
            </div>
        `;
        return;
    }
    
    elements.walletList.innerHTML = wallets.map(wallet => `
        <div class="wallet-item ${wallet.is_active ? '' : 'inactive'}" data-id="${wallet.id}">
            <div class="wallet-info">
                <div class="wallet-toggle ${wallet.is_active ? 'active' : ''}" 
                     onclick="toggleWallet(${wallet.id})" 
                     title="${wallet.is_active ? '点击暂停' : '点击启用'}">
                </div>
                <div class="wallet-details">
                    <div class="wallet-name">${escapeHtml(wallet.name)}</div>
                    <div class="wallet-address">${wallet.address}</div>
                </div>
            </div>
            <div class="wallet-meta">
                最近活动: ${formatTime(wallet.last_activity)}
            </div>
            <div class="wallet-actions">
                <button class="btn-icon-only" onclick="editWallet(${wallet.id}, '${escapeHtml(wallet.name)}')" title="编辑">
                    ✏️
                </button>
                <button class="btn-icon-only btn-delete" onclick="deleteWallet(${wallet.id})" title="删除">
                    🗑️
                </button>
            </div>
        </div>
    `).join('');
}

/**
 * HTML 转义
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * 显示添加钱包表单
 */
function showAddWalletForm() {
    elements.addWalletForm.style.display = 'block';
    elements.newWalletAddress.focus();
}

/**
 * 隐藏添加钱包表单
 */
function hideAddWalletForm() {
    elements.addWalletForm.style.display = 'none';
    elements.newWalletAddress.value = '';
    elements.newWalletName.value = '';
}

/**
 * 添加钱包
 */
async function addWallet() {
    const address = elements.newWalletAddress.value.trim();
    const name = elements.newWalletName.value.trim();
    
    if (!address) {
        showToast('请输入钱包地址', 'error');
        return;
    }
    
    try {
        const result = await apiPost('/wallets', { address, name });
        
        if (result.error) {
            showToast(result.error, 'error');
            return;
        }
        
        showToast('钱包添加成功', 'success');
        hideAddWalletForm();
        loadWallets();
        
    } catch (error) {
        showToast('添加失败: ' + error.message, 'error');
    }
}

/**
 * 切换钱包状态
 */
async function toggleWallet(walletId) {
    try {
        await apiPost(`/wallets/${walletId}/toggle`);
        loadWallets();
    } catch (error) {
        showToast('操作失败', 'error');
    }
}

/**
 * 编辑钱包
 */
async function editWallet(walletId, currentName) {
    const newName = prompt('请输入新的备注名称:', currentName);
    
    if (newName === null || newName.trim() === '') {
        return;
    }
    
    try {
        await apiPut(`/wallets/${walletId}`, { name: newName.trim() });
        showToast('修改成功', 'success');
        loadWallets();
    } catch (error) {
        showToast('修改失败', 'error');
    }
}

/**
 * 删除钱包
 */
async function deleteWallet(walletId) {
    if (!confirm('确定要删除这个钱包吗？')) {
        return;
    }
    
    try {
        await apiDelete(`/wallets/${walletId}`);
        showToast('删除成功', 'success');
        loadWallets();
    } catch (error) {
        showToast('删除失败', 'error');
    }
}

// ==================== 交易记录 ====================

/**
 * 加载交易记录
 */
async function loadTransactions() {
    try {
        const transactions = await apiGet('/transactions?limit=20');
        renderTransactions(transactions);
    } catch (error) {
        console.error('加载交易失败:', error);
        elements.transactionList.innerHTML = '<div class="empty-state"><div class="icon">⚠️</div><p>加载失败</p></div>';
    }
}

/**
 * 渲染交易列表
 */
function renderTransactions(transactions) {
    if (transactions.length === 0) {
        elements.transactionList.innerHTML = `
            <div class="empty-state">
                <div class="icon">📜</div>
                <p>暂无交易记录</p>
            </div>
        `;
        return;
    }
    
    elements.transactionList.innerHTML = transactions.map(tx => {
        const isBuy = tx.trade_type === 'BUY';
        const typeEmoji = isBuy ? '🟢' : '🔴';
        const typeText = isBuy ? '买入' : '卖出';
        
        return `
            <div class="transaction-item">
                <div class="tx-type ${isBuy ? 'buy' : 'sell'}">
                    ${typeEmoji}
                </div>
                <div class="tx-details">
                    <div class="tx-market" title="${escapeHtml(tx.market_name || 'Unknown')}">
                        ${escapeHtml(tx.market_name || 'Unknown Market')}
                    </div>
                    <div class="tx-info">
                        <span><strong>${typeText}</strong></span>
                        <span class="${tx.outcome === 'Yes' ? 'outcome-yes' : 'outcome-no'}">${tx.outcome || '-'}</span>
                        <span>@ $${(tx.price || 0).toFixed(4)}</span>
                        <span>x ${(tx.amount || 0).toFixed(2)} 股</span>
                    </div>
                    <div class="tx-links">
                        <a href="https://polygonscan.com/tx/${tx.tx_hash}" target="_blank">查看交易</a>
                        ${tx.market_slug ? `<a href="https://polymarket.com/event/${tx.market_slug}" target="_blank">查看市场</a>` : ''}
                    </div>
                </div>
                <div class="tx-meta">
                    <div class="tx-amount ${isBuy ? 'buy' : 'sell'}">
                        ${isBuy ? '-' : '+'}$${(tx.total_usdc || 0).toFixed(2)}
                    </div>
                    <div>${formatTime(tx.timestamp)}</div>
                    <div>${formatAddress(tx.wallet_address)}</div>
                </div>
            </div>
        `;
    }).join('');
}

// ==================== 监控控制 ====================

/**
 * 切换监控状态
 */
async function toggleMonitor() {
    try {
        const endpoint = isMonitorRunning ? '/monitor/stop' : '/monitor/start';
        await apiPost(endpoint);
        showToast(isMonitorRunning ? '监控已停止' : '监控已启动', 'success');
        loadStatus();
    } catch (error) {
        showToast('操作失败', 'error');
    }
}

// ==================== 跟单功能 ====================

/**
 * 加载跟单配置
 */
async function loadCopyTradeConfig() {
    try {
        const config = await apiGet('/copytrade/config');
        
        isCopyTradeEnabled = config.enabled;
        updateCopyTradeUI(config);
        
        // 填充表单
        document.getElementById('copy-ratio').value = config.copy_ratio || 10;
        document.getElementById('min-amount').value = config.min_amount || 5;
        document.getElementById('max-amount').value = config.max_amount || 100;
        document.getElementById('max-position-market').value = config.max_position_per_market || 500;
        document.getElementById('max-total-position').value = config.max_total_position || 2000;
        document.getElementById('simulation-balance').value = config.simulation_balance || 10000;
        document.getElementById('min-price').value = config.min_price || 0.05;
        document.getElementById('max-price').value = config.max_price || 0.95;
        
        // 设置方向单选框
        const direction = config.copy_direction || 'all';
        document.querySelector(`input[name="copy-direction"][value="${direction}"]`).checked = true;
        
    } catch (error) {
        console.error('加载跟单配置失败:', error);
    }
}

/**
 * 更新跟单 UI 状态
 */
function updateCopyTradeUI(config) {
    const enabled = config.enabled;
    
    elements.copyTradeStatus.textContent = enabled ? '跟单运行中' : '跟单已停用';
    elements.copyTradeStatus.className = `copy-trade-status ${enabled ? 'active' : ''}`;
    
    elements.btnToggleCopy.textContent = enabled ? '停用跟单' : '启用跟单';
    elements.btnToggleCopy.className = `btn btn-toggle-copy ${enabled ? 'active' : ''}`;
}

/**
 * 切换跟单开关
 */
async function toggleCopyTrade() {
    try {
        const result = await apiPost('/copytrade/toggle');
        isCopyTradeEnabled = result.enabled;
        showToast(result.message, 'success');
        loadCopyTradeConfig();
        loadCopyTradeStats();
    } catch (error) {
        showToast('操作失败', 'error');
    }
}

/**
 * 保存跟单配置
 */
async function saveCopyTradeConfig() {
    try {
        const config = {
            copy_ratio: parseFloat(document.getElementById('copy-ratio').value),
            min_amount: parseFloat(document.getElementById('min-amount').value),
            max_amount: parseFloat(document.getElementById('max-amount').value),
            max_position_per_market: parseFloat(document.getElementById('max-position-market').value),
            max_total_position: parseFloat(document.getElementById('max-total-position').value),
            simulation_balance: parseFloat(document.getElementById('simulation-balance').value),
            min_price: parseFloat(document.getElementById('min-price').value),
            max_price: parseFloat(document.getElementById('max-price').value),
            copy_direction: document.querySelector('input[name="copy-direction"]:checked').value,
        };
        
        await apiPost('/copytrade/config', config);
        showToast('跟单设置已保存', 'success');
        loadCopyTradeStats();
    } catch (error) {
        showToast('保存失败: ' + error.message, 'error');
    }
}

/**
 * 加载跟单统计
 */
async function loadCopyTradeStats() {
    try {
        const stats = await apiGet('/copytrade/stats');
        
        // 更新统计显示
        document.getElementById('stat-balance').textContent = `$${formatNumber(stats.available_balance)}`;
        document.getElementById('stat-cost').textContent = `$${formatNumber(stats.total_cost)}`;
        document.getElementById('stat-value').textContent = `$${formatNumber(stats.total_value)}`;
        
        // 未实现盈亏
        const unrealizedEl = document.getElementById('stat-unrealized-pnl');
        const unrealizedPnl = stats.total_unrealized_pnl;
        const unrealizedPercent = stats.total_unrealized_pnl_percent;
        unrealizedEl.textContent = `${unrealizedPnl >= 0 ? '+' : ''}$${formatNumber(unrealizedPnl)} (${unrealizedPercent >= 0 ? '+' : ''}${unrealizedPercent.toFixed(1)}%)`;
        unrealizedEl.className = `stat-value pnl ${unrealizedPnl >= 0 ? 'positive' : 'negative'}`;
        
        // 已实现盈亏
        const realizedEl = document.getElementById('stat-realized-pnl');
        const realizedPnl = stats.total_realized_pnl;
        realizedEl.textContent = `${realizedPnl >= 0 ? '+' : ''}$${formatNumber(realizedPnl)}`;
        realizedEl.className = `stat-value pnl ${realizedPnl >= 0 ? 'positive' : 'negative'}`;
        
        // 总盈亏
        const totalEl = document.getElementById('stat-total-pnl');
        const totalPnl = stats.total_pnl;
        totalEl.textContent = `${totalPnl >= 0 ? '+' : ''}$${formatNumber(totalPnl)}`;
        totalEl.className = `stat-value pnl total ${totalPnl >= 0 ? 'positive' : 'negative'}`;
        
        // 底部统计
        document.getElementById('stat-trades').textContent = stats.total_trades;
        document.getElementById('stat-success').textContent = stats.successful_trades;
        document.getElementById('stat-positions').textContent = stats.position_count;
        
    } catch (error) {
        console.error('加载跟单统计失败:', error);
    }
}

/**
 * 格式化数字
 */
function formatNumber(num) {
    return num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/**
 * 加载持仓列表
 */
async function loadPositions() {
    try {
        const positions = await apiGet('/copytrade/positions');
        renderPositions(positions);
    } catch (error) {
        console.error('加载持仓失败:', error);
    }
}

/**
 * 渲染持仓列表
 */
function renderPositions(positions) {
    if (positions.length === 0) {
        elements.positionList.innerHTML = `
            <div class="empty-state">
                <div class="icon">💼</div>
                <p>暂无持仓</p>
            </div>
        `;
        return;
    }
    
    elements.positionList.innerHTML = positions.map(pos => {
        const isYes = pos.outcome === 'Yes';
        const pnlClass = pos.unrealized_pnl >= 0 ? 'positive' : 'negative';
        const pnlSign = pos.unrealized_pnl >= 0 ? '+' : '';
        
        return `
            <div class="position-item">
                <div class="position-info">
                    <div class="position-market">
                        ${escapeHtml(pos.market_name || 'Unknown Market')}
                        <span class="position-outcome ${isYes ? 'yes' : 'no'}">${pos.outcome || '-'}</span>
                    </div>
                    <div class="position-details">
                        <span>${pos.shares.toFixed(2)} 股</span>
                        <span>成本: $${pos.avg_price.toFixed(4)}</span>
                        <span>现价: $${pos.current_price.toFixed(4)}</span>
                    </div>
                </div>
                <div class="position-pnl">
                    <div class="position-value">$${formatNumber(pos.current_value)}</div>
                    <div class="position-change ${pnlClass}">
                        ${pnlSign}$${formatNumber(pos.unrealized_pnl)} (${pnlSign}${pos.unrealized_pnl_percent.toFixed(1)}%)
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

/**
 * 加载跟单记录
 */
async function loadCopyTradeRecords() {
    try {
        const records = await apiGet('/copytrade/records?limit=30');
        renderRecords(records);
    } catch (error) {
        console.error('加载跟单记录失败:', error);
    }
}

/**
 * 渲染跟单记录
 */
function renderRecords(records) {
    if (records.length === 0) {
        elements.recordList.innerHTML = `
            <div class="empty-state">
                <div class="icon">📝</div>
                <p>暂无跟单记录</p>
            </div>
        `;
        return;
    }
    
    elements.recordList.innerHTML = records.map(record => {
        const isBuy = record.trade_type === 'BUY';
        const statusEmoji = record.status === 'success' ? '✅' : (record.status === 'skipped' ? '⏭️' : '❌');
        const statusClass = record.status;
        
        return `
            <div class="record-item">
                <div class="record-status ${statusClass}">
                    ${statusEmoji}
                </div>
                <div class="record-info">
                    <div class="record-market" title="${escapeHtml(record.market_name || 'Unknown')}">
                        ${escapeHtml(record.market_name || 'Unknown Market')}
                    </div>
                    <div class="record-details">
                        <span>${isBuy ? '🟢 买入' : '🔴 卖出'}</span>
                        <span>${record.outcome || '-'}</span>
                        ${record.status === 'success' ? `<span>${(record.copy_shares || 0).toFixed(2)} 股 @ $${(record.copy_price || 0).toFixed(4)}</span>` : ''}
                    </div>
                    <div class="record-source">
                        跟单: ${escapeHtml(record.source_wallet_name || formatAddress(record.source_wallet_address))}
                        ${record.status === 'skipped' ? `<span class="record-reason">- ${record.skip_reason}</span>` : ''}
                    </div>
                </div>
                <div class="record-meta">
                    ${record.status === 'success' ? `
                        <div class="record-amount ${isBuy ? 'buy' : 'sell'}">
                            ${isBuy ? '-' : '+'}$${formatNumber(record.copy_amount || 0)}
                        </div>
                    ` : ''}
                    <div class="record-time">${formatTime(record.created_at)}</div>
                </div>
            </div>
        `;
    }).join('');
}

/**
 * 一键平仓
 */
async function closeAllPositions() {
    if (!confirm('确定要平仓所有持仓吗？这将卖出所有模拟持仓并结算盈亏。')) {
        return;
    }
    
    try {
        const result = await apiPost('/copytrade/positions/close-all');
        showToast(`已平仓 ${result.closed_count} 个持仓，实现盈亏: $${formatNumber(result.total_realized_pnl)}`, 'success');
        loadPositions();
        loadCopyTradeStats();
        loadCopyTradeRecords();
    } catch (error) {
        showToast('平仓失败', 'error');
    }
}

/**
 * 重置模拟数据
 */
async function resetSimulation() {
    if (!confirm('确定要重置所有模拟数据吗？这将清空所有持仓和跟单记录！')) {
        return;
    }
    
    try {
        await apiPost('/copytrade/reset');
        showToast('模拟数据已重置', 'success');
        loadPositions();
        loadCopyTradeStats();
        loadCopyTradeRecords();
    } catch (error) {
        showToast('重置失败', 'error');
    }
}

/**
 * 切换设置面板显示
 */
function toggleSettings() {
    const settings = elements.copytradeSettings;
    const btn = document.getElementById('btn-toggle-settings');
    
    if (settings.style.display === 'none') {
        settings.style.display = 'block';
        btn.textContent = '收起 ▲';
    } else {
        settings.style.display = 'none';
        btn.textContent = '展开 ▼';
    }
}

// ==================== 事件绑定 ====================

function bindEvents() {
    // 配置相关
    document.getElementById('btn-save-config').addEventListener('click', saveConfig);
    document.getElementById('btn-test-tg').addEventListener('click', testTelegram);
    
    // 钱包相关
    document.getElementById('btn-add-wallet').addEventListener('click', showAddWalletForm);
    document.getElementById('btn-confirm-add').addEventListener('click', addWallet);
    document.getElementById('btn-cancel-add').addEventListener('click', hideAddWalletForm);
    
    // 交易相关
    document.getElementById('btn-refresh-tx').addEventListener('click', loadTransactions);
    
    // 监控控制
    elements.btnToggleMonitor.addEventListener('click', toggleMonitor);
    
    // 跟单相关
    elements.btnToggleCopy.addEventListener('click', toggleCopyTrade);
    document.getElementById('btn-toggle-settings').addEventListener('click', toggleSettings);
    document.getElementById('btn-save-copytrade').addEventListener('click', saveCopyTradeConfig);
    document.getElementById('btn-reset-simulation').addEventListener('click', resetSimulation);
    document.getElementById('btn-close-all').addEventListener('click', closeAllPositions);
    document.getElementById('btn-refresh-records').addEventListener('click', loadCopyTradeRecords);
    
    // 回车提交
    elements.newWalletAddress.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') addWallet();
    });
    elements.newWalletName.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') addWallet();
    });
}

// ==================== 初始化 ====================

async function init() {
    bindEvents();
    
    // 加载数据
    await Promise.all([
        loadStatus(),
        loadConfig(),
        loadWallets(),
        loadTransactions(),
        loadCopyTradeConfig(),
        loadCopyTradeStats(),
        loadPositions(),
        loadCopyTradeRecords(),
    ]);
    
    // 定时刷新
    setInterval(loadStatus, 5000);
    setInterval(loadTransactions, 30000);
    setInterval(loadCopyTradeStats, 10000);
    setInterval(loadPositions, 15000);
    setInterval(loadCopyTradeRecords, 20000);
}

// 启动
document.addEventListener('DOMContentLoaded', init);

// 导出到全局（供 onclick 使用）
window.togglePassword = togglePassword;
window.toggleWallet = toggleWallet;
window.editWallet = editWallet;
window.deleteWallet = deleteWallet;
