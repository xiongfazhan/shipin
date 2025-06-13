// 公共工具函数和全局变量
let streams = [];
let frameConfig = {
    highRiskInterval: 0.5,
    mediumRiskInterval: 1.0,
    lowRiskInterval: 2.0
};
let activeStreams = new Set();
let currentCleanup = null;            // 当前页面的清理函数
const loadedScripts = new Set();      // 已加载外链脚本缓存

// 风险等级映射
const riskLevelMapping = {
    '高': 'highRiskInterval',
    '中': 'mediumRiskInterval', 
    '低': 'lowRiskInterval',
    'high': 'highRiskInterval',
    'medium': 'mediumRiskInterval',
    'low': 'lowRiskInterval'
};

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    initializeCommon();
});

// 公共初始化
function initializeCommon() {
    console.log('初始化公共模块...');
    
    // 初始化导航栏状态
    updateSystemStatus();
    
        // 加载公共配置
        loadFrameConfig();
    
        // 设置定时更新
        startCommonUpdaters();
        // 初始化 WebSocket（接收 pusher-service 推送）
        initWebSocket();
     }
     
     // 启动公共更新器
     function startCommonUpdaters() 
    {
    // 每30秒更新系统状态
    setInterval(updateSystemStatus, 30000);
    
    // 每10秒更新统计信息
    setInterval(updateGlobalStats, 10000);
}

// 更新系统状态
async function updateSystemStatus() {
    try {
        const response = await fetch('/api/system_status');
        const status = await response.json();
        
        const statusElement = document.getElementById('systemStatus');
        if (statusElement) {
            const indicator = statusElement.querySelector('.status-indicator');
            const text = statusElement.querySelector('.status-text');
            
            if (status.success && status.status === 'running') {
                if (indicator) indicator.className = 'status-indicator status-running me-2';
                if (text) text.textContent = '系统正常';
            } else {
                if (indicator) indicator.className = 'status-indicator status-stopped me-2';
                if (text) text.textContent = '系统异常';
            }
        }
    } catch (error) {
        console.error('更新系统状态失败:', error);
    }
}

// 更新全局统计信息
async function updateGlobalStats() {
    try {
        const [streamsRes, statsRes] = await Promise.all([
            fetch('/api/streams?offset=0&limit=200'),
            fetch('/api/stats')
        ]);
        
        const streamsData = await streamsRes.json();
        const statsData = await statsRes.json();
        
        if (streamsData.success) {
            streams = streamsData.streams;
            
            // 从后端数据获取真实的活跃流数量
            const activeCount = streams.filter(s => s.is_running).length;
            updateStatElement('totalStreams', streams.length);
            updateStatElement('activeStreams', activeCount);
            
            // 更新本地activeStreams Set以保持兼容性
            activeStreams.clear();
            streams.forEach(s => {
                if (s.is_running) {
                    activeStreams.add(s.stream_id || s.name);
                }
            });
        }
        
        if (statsData.success) {
            updateStatElement('totalDetections', statsData.total_detections || 0);
            updateStatElement('avgProcessTime', (statsData.average_processing_time || 0).toFixed(0) + 'ms');
        }
    } catch (error) {
        console.error('更新统计信息失败:', error);
    }
}

// 更新统计元素
function updateStatElement(elementId, value) {
    const element = document.getElementById(elementId);
    if (element) {
        const currentValue = parseInt(element.textContent) || 0;
        if (typeof value === 'number' && currentValue !== value) {
            animateNumber(elementId, value);
        } else if (typeof value === 'string') {
            element.textContent = value;
        }
    }
}

// 数字动画
function animateNumber(elementId, targetValue) {
    const element = document.getElementById(elementId);
    if (!element) return;
    
    const currentValue = parseInt(element.textContent) || 0;
    if (currentValue === targetValue) return;
    
    const step = targetValue > currentValue ? 1 : -1;
    let current = currentValue;
    
    const timer = setInterval(() => {
        current += step;
        element.textContent = current;
        
        if (current === targetValue) {
            clearInterval(timer);
        }
    }, 50);
}

// 显示Toast通知
function showToast(message, type = 'info') {
    const toastContainer = document.getElementById('toastContainer');
    if (!toastContainer) return;
    
    const toastId = 'toast_' + Date.now();
    
    const typeClasses = {
        'success': 'text-bg-success',
        'error': 'text-bg-danger', 
        'warning': 'text-bg-warning',
        'info': 'text-bg-primary'
    };
    
    const iconClasses = {
        'success': 'bi-check-circle-fill',
        'error': 'bi-x-circle-fill',
        'warning': 'bi-exclamation-triangle-fill',
        'info': 'bi-info-circle-fill'
    };
    
    const toastHtml = `
        <div id="${toastId}" class="toast ${typeClasses[type] || 'text-bg-primary'}" role="alert">
            <div class="toast-body">
                <i class="bi ${iconClasses[type] || 'bi-info-circle-fill'} me-2"></i>
                ${message}
            </div>
        </div>
    `;
    
    toastContainer.insertAdjacentHTML('beforeend', toastHtml);
    
    const toastElement = document.getElementById(toastId);
    const toast = new bootstrap.Toast(toastElement, {
        autohide: true,
        delay: 4000
    });
    
    // 入场动画
    toastElement.style.transform = 'translateX(100%)';
    setTimeout(() => {
        toastElement.style.transform = 'translateX(0)';
        toastElement.style.transition = 'transform 0.3s ease-out';
    }, 10);
    
    toast.show();
    
    // 清理已隐藏的toast
    toastElement.addEventListener('hidden.bs.toast', () => {
        toastElement.remove();
    });
}

// 显示全屏加载状态
function showLoading(show) {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) {
        if (show) {
            overlay.classList.add('show');
        } else {
            overlay.classList.remove('show');
        }
    }
}

// 加载抽帧配置
function loadFrameConfig() {
    const saved = localStorage.getItem('frameConfig');
    if (saved) {
        frameConfig = JSON.parse(saved);
    }
}

// 保存抽帧配置
function saveFrameConfig() {
    frameConfig = {
        highRiskInterval: parseFloat(document.getElementById('highRiskInterval')?.value || 0.5),
        mediumRiskInterval: parseFloat(document.getElementById('mediumRiskInterval')?.value || 1.0),
        lowRiskInterval: parseFloat(document.getElementById('lowRiskInterval')?.value || 2.0)
    };
    
    localStorage.setItem('frameConfig', JSON.stringify(frameConfig));
    showToast('抽帧配置已保存', 'success');
    console.log('保存的抽帧配置:', frameConfig);
}

// 根据风险等级获取抽帧间隔
function getIntervalForRiskLevel(riskLevel) {
    const configKey = riskLevelMapping[riskLevel];
    return configKey ? frameConfig[configKey] : frameConfig.mediumRiskInterval;
}

// 获取风险等级徽章
function getRiskBadge(riskLevel) {
    const badges = {
        '高': '<span class="badge bg-danger risk-badge-animated">高风险</span>',
        '中': '<span class="badge bg-warning risk-badge-animated">中风险</span>',
        '低': '<span class="badge bg-success risk-badge-animated">低风险</span>',
        'high': '<span class="badge bg-danger risk-badge-animated">高风险</span>',
        'medium': '<span class="badge bg-warning risk-badge-animated">中风险</span>',
        'low': '<span class="badge bg-success risk-badge-animated">低风险</span>'
    };
    return badges[riskLevel] || '<span class="badge bg-secondary">未知</span>';
}

// 兼容保留函数：快速设置抽帧间隔，不再依赖预设按钮
function applyPreset(presetType) {
    const presets = {
        'fast': { high: 0.3, medium: 0.5, low: 1.0 },
        'balanced': { high: 0.5, medium: 1.0, low: 2.0 },
        'efficient': { high: 1.0, medium: 2.0, low: 3.0 }
    };

    const preset = presets[presetType];
    if (!preset) return;

    // 更新输入框（若存在于当前页面）
    const highInput = document.getElementById('highRiskInterval');
    const mediumInput = document.getElementById('mediumRiskInterval');
    const lowInput = document.getElementById('lowRiskInterval');

    if (highInput) highInput.value = preset.high;
    if (mediumInput) mediumInput.value = preset.medium;
    if (lowInput) lowInput.value = preset.low;

    // 保存并通知
    if (typeof saveFrameConfig === 'function') {
        saveFrameConfig();
    }
}

// 设置文件上传交互
function setupFileUpload() {
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('csvFile');
    
    if (!uploadArea || !fileInput) return;
    
    // 文件拖拽功能
    uploadArea.addEventListener('click', () => fileInput.click());
    
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });
    
    uploadArea.addEventListener('dragleave', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
    });
    
    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        
        const files = e.dataTransfer.files;
        if (files.length > 0 && files[0].type === 'text/csv') {
            fileInput.files = files;
            handleFileSelect({ target: { files: files } });
        } else {
            showToast('请拖放CSV格式文件', 'warning');
        }
    });
    
    fileInput.addEventListener('change', handleFileSelect);
}

// 处理文件选择
function handleFileSelect(event) {
    const file = event.target.files[0];
    if (file && file.type === 'text/csv') {
        console.log('选择了CSV文件:', file.name);
        
        // 显示文件名
        const uploadText = document.querySelector('.primary-text');
        if (uploadText) {
            uploadText.textContent = `已选择: ${file.name}`;
            uploadText.style.color = '#28a745';
        }
        
        // 添加成功动画
        const uploadArea = document.getElementById('uploadArea');
        if (uploadArea) {
            uploadArea.style.borderColor = '#28a745';
            uploadArea.style.background = 'linear-gradient(135deg, rgba(40, 167, 69, 0.1) 0%, rgba(56, 239, 125, 0.1) 100%)';
            
            setTimeout(() => {
                uploadArea.style.borderColor = '';
                uploadArea.style.background = '';
                if (uploadText) {
                    uploadText.textContent = '拖放CSV文件到这里';
                    uploadText.style.color = '';
                }
            }, 3000);
        }
    }
}

// 上传CSV文件
async function uploadCSV() {
    const fileInput = document.getElementById('csvFile');
    if (!fileInput) return;
    
    const file = fileInput.files[0];
    
    if (!file) {
        showToast('请选择CSV文件', 'warning');
        return;
    }
    
    if (file.type !== 'text/csv') {
        showToast('请选择CSV格式文件', 'error');
        return;
    }
    
    try {
        const formData = new FormData();
        formData.append('file', file);
        
        showLoading(true);
        const response = await fetch('/api/streams/config/upload', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showToast(`成功导入 ${result.added_count || 0} 个新视频流配置`, 'success');
            
            // 刷新数据
            if (typeof refreshStreams === 'function') {
                refreshStreams();
            } else if (typeof loadConfigurationStatus === 'function') {
                loadConfigurationStatus();
            }
            
            // 重置文件输入
            fileInput.value = '';
            
            // 添加成功动画效果
            const uploadArea = document.getElementById('uploadArea');
            if (uploadArea) {
                uploadArea.style.animation = 'pulse 0.5s ease-in-out';
                setTimeout(() => {
                    uploadArea.style.animation = '';
                }, 500);
            }
        } else {
            showToast('导入失败: ' + (result.error || '未知错误'), 'error');
        }
    } catch (error) {
        console.error('上传CSV失败:', error);
        showToast('上传失败: ' + error.message, 'error');
    } finally {
        showLoading(false);
    }
}

// 格式化时间
function formatTime(timestamp) {
    return new Date(timestamp * 1000).toLocaleString('zh-CN');
}

// 格式化文件大小
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// 工具函数：节流
function throttle(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// 工具函数：防抖
function debounce(func, wait, immediate) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            timeout = null;
            if (!immediate) func(...args);
        };
        const callNow = immediate && !timeout;
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
        if (callNow) func(...args);
    };
}

// ----------------- 通用响应解析 -----------------
function isSuccessResponse(res) {
    return res && (res.success === true || res.status === 'success');
}

function getErrorMessage(res) {
    if (!res) return '未知错误';
    return res.error || res.message || res.msg || '未知错误';
}

// 导出全局函数供其他脚本使用
window.videoStreamUtils = {
    showToast,
    showLoading,
    formatTime,
    formatFileSize,
    getRiskBadge,
    getIntervalForRiskLevel,
    throttle,
    debounce,
    animateNumber,
    isSuccessResponse,
    getErrorMessage
};

// remote_push 页面初始化，供 SPA 路由调用
function initializeRemotePush() {
    if (typeof loadConfig === 'function') loadConfig();
    if (typeof startStatsUpdate === 'function') startStatsUpdate();
    // 绑定事件（若尚未绑定）
    const form = document.getElementById('remotePushForm');
    if (form && !form.dataset._bound) {
        form.addEventListener('submit', saveConfig);
        form.dataset._bound = '1';
    }

    // 返回清理函数，负责停止定时器
    return function cleanupRemotePush() {
        if (typeof statsUpdateInterval !== 'undefined' && statsUpdateInterval) {
            clearInterval(statsUpdateInterval);
            statsUpdateInterval = null;
        }
    };
}

// -----------------------------
// 轻量级 SPA 路由 (单视图切换)
// -----------------------------

// 监听导航点击，拦截相同站点链接
document.addEventListener('click', (e) => {
    const anchor = e.target.closest('a.nav-link');
    if (!anchor) return;
    const href = anchor.getAttribute('href');
    if (!href || href.startsWith('http') || href.startsWith('#') || e.ctrlKey || e.metaKey) return;
    e.preventDefault();
    loadPage(href, true);
});

// 处理浏览器前进后退
window.addEventListener('popstate', (e) => {
    const path = e.state && e.state.path ? e.state.path : location.pathname;
    loadPage(path, false);
});

async function loadPage(path, pushState = false) {
    // ---- 离开旧页面：执行清理函数、取消定时器等 ----
    if (typeof currentCleanup === 'function') {
        try { currentCleanup(); } catch (e) { console.warn('page cleanup error', e); }
        currentCleanup = null;
    }

    showLoading(true);
    try {
        const resp = await fetch(path);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const html = await resp.text();

        // 解析 HTML 片段
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');
        // 仅替换主内容区域（避免选择到导航栏中的 container-fluid）
        const selector = '.container-fluid.mt-4, .container.mt-4';
        const newContent = doc.querySelector(selector);
        const container = document.querySelector(selector);

        if (newContent && container) {
            container.innerHTML = newContent.innerHTML;
        } else {
            console.warn('SPA 路由：未找到新的内容容器，页面可能无法正确刷新');
        }

        // 更新标题
        document.title = doc.title;

        // 更新 active link
        document.querySelectorAll('a.nav-link').forEach(a => a.classList.remove('active'));
        const activeLink = document.querySelector(`a.nav-link[href="${path}"]`);
        if (activeLink) activeLink.classList.add('active');

        // -------- 加载并执行页面脚本 (包含外链 & 内联) --------
        const scriptContainer = document.getElementById('pageScripts') || document.body;
        scriptContainer.innerHTML = '';

        const scriptNodes = Array.from(doc.querySelectorAll('script'));
        const loadPromises = [];

        scriptNodes.forEach((s) => {
            const src = s.getAttribute('src');
            if (src && !src.includes('/static/js/common.js')) {
                if (loadedScripts.has(src)) return; // 已加载过
                loadedScripts.add(src);
                const ns = document.createElement('script');
                ns.src = src;
                // 保证顺序 & onload 捕获
                loadPromises.push(new Promise((resolve) => {
                    ns.onload = ns.onerror = () => resolve();
                }));
                scriptContainer.appendChild(ns);
            } else if (!src && s.textContent.trim()) {
                // 直接执行内联脚本
                const inline = document.createElement('script');
                inline.textContent = s.textContent;
                scriptContainer.appendChild(inline);
            }
        });

        // 等待外链脚本加载完毕后调用初始化
        const invokePageInit = () => {
            const page = path.split('?')[0].split('#')[0].split('/').filter(Boolean).pop() || 'dashboard';
            const initMap = {
                'dashboard': 'initializeDashboard',
                'configuration': 'initializeConfiguration',
                'streams': 'initializeStreams',
                'results': 'initializeResults',
                'settings': 'initializeSettings',
                'remote_push': 'initializeRemotePush',
                'summary': 'refreshSummary'
            };
            const fnName = initMap[page];
            if (fnName && typeof window[fnName] === 'function') {
                try {
                    const ret = window[fnName]();
                    if (typeof ret === 'function') {
                        currentCleanup = ret;      // 记录清理函数
                    }
                } catch (e) { console.error('初始化函数执行失败:', e); }
            }
        };

        await Promise.all(loadPromises);
        invokePageInit();

        if (pushState) {
            history.pushState({ path }, '', path);
        }
    } catch (err) {
        console.error('加载页面失败:', err);
        showToast('加载页面失败: ' + err.message, 'error');
    } finally {
        showLoading(false);
    }
}

// -------------------------------------------------------------------
// WebSocket 客户端：连接 pusher-service（端口 8084）实时接收 5 min 汇总
// -------------------------------------------------------------------

let _socketClient = null;
let _socketLoading = false;

function initWebSocket() {
    if (_socketClient || _socketLoading) return;
    _socketLoading = true;

    const script = document.createElement('script');
    script.src = 'https://cdn.socket.io/4.7.2/socket.io.min.js';
    script.onload = () => {
        try {
            const host = location.hostname || 'localhost';
            _socketClient = io(`//${host}:8084`, {
                transports: ['websocket'],
                reconnection: true,
                timeout: 5000
            });

            window._globalSocket = _socketClient;               // 调试用
            _socketClient.on('connect', () => console.log('[WS] 已连接 pusher-service'));
            _socketClient.on('summary', handleSummaryPush);      // 监听 5 min 汇总
        } catch (e) {
            console.error('Socket.IO 初始化失败:', e);
        }
    };
    script.onerror = () => console.error('Socket.IO 客户端脚本加载失败');
    document.head.appendChild(script);
}

function handleSummaryPush(payload) {
    console.log('[WS] 收到 summary 推送', payload);
    const data = payload?.data ?? payload;

    // 如果页面已定义 summaryData / renderSummary，则刷新 UI
    if (Array.isArray(window.summaryData)) {
        window.summaryData.unshift(data);
        if (window.summaryData.length > 500) window.summaryData.length = 500;
        if (typeof window.renderSummary === 'function') {
            try { window.renderSummary(); } catch {}
        }
    }

    const stream = data.stream_id || '全部流';
    const total = data.total_detections ?? data.count ?? 0;
    showToast(`汇总(${stream})：${total} 次检测`, 'info');
}