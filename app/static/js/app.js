/**
 * Polymarket 聪明钱监控 - 前端应用
 */

// API 基础路径
const API_BASE = '/api';

// 状态
let isMonitorRunning = false;

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
    ]);
    
    // 定时刷新
    setInterval(loadStatus, 5000);
    setInterval(loadTransactions, 30000);
}

// 启动
document.addEventListener('DOMContentLoaded', init);

// 导出到全局（供 onclick 使用）
window.togglePassword = togglePassword;
window.toggleWallet = toggleWallet;
window.editWallet = editWallet;
window.deleteWallet = deleteWallet;
