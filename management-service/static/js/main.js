// 全局变量
let streams = [];
// 使用 common.js 中的全局 frameConfig，无需重新定义
let activeStreams = new Set();

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
    initializePage();
    startStatusUpdater();
    setupInteractiveEffects();
});

// 初始化页面
function initializePage() {
    console.log('初始化视频流分析系统...');
    loadFrameConfig();
    refreshStreams();
    
    // 绑定文件上传事件
    setupFileUpload();
}

// 设置文件上传交互
function setupFileUpload() {
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('csvFile');
    
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

// 设置交互效果
function setupInteractiveEffects() {
    // 为统计卡片添加点击效果
    document.querySelectorAll('.stat-item').forEach(item => {
        item.addEventListener('click', function() {
            this.style.transform = 'scale(0.95)';
            setTimeout(() => {
                this.style.transform = '';
            }, 150);
        });
    });
    
    // 添加平滑滚动
    document.querySelectorAll('a[href^="#"]').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
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

// 上传CSV文件
async function uploadCSV() {
    const fileInput = document.getElementById('csvFile');
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
        
        if (result.success) {
            showToast(`成功导入 ${result.count} 个视频流配置`, 'success');
            refreshStreams();
            
            // 重置文件输入
            fileInput.value = '';
            
            // 添加成功动画效果
            const uploadArea = document.getElementById('uploadArea');
            uploadArea.style.animation = 'pulse 0.5s ease-in-out';
            setTimeout(() => {
                uploadArea.style.animation = '';
            }, 500);
        } else {
            showToast('导入失败: ' + result.error, 'error');
        }
    } catch (error) {
        console.error('上传CSV失败:', error);
        showToast('上传失败: ' + error.message, 'error');
    } finally {
        showLoading(false);
    }
}

// 保存抽帧配置
function saveFrameConfig() {
    frameConfig = {
        highRiskInterval: parseFloat(document.getElementById('highRiskInterval').value),
        mediumRiskInterval: parseFloat(document.getElementById('mediumRiskInterval').value),
        lowRiskInterval: parseFloat(document.getElementById('lowRiskInterval').value)
    };
    
    localStorage.setItem('frameConfig', JSON.stringify(frameConfig));
    showToast('抽帧配置已保存', 'success');
    console.log('保存的抽帧配置:', frameConfig);
    
    // 添加保存动画效果
    const saveBtn = document.querySelector('.save-config-btn');
    const originalText = saveBtn.innerHTML;
    saveBtn.innerHTML = '<i class="bi bi-check2-circle me-2"></i> 已保存';
    saveBtn.classList.add('btn-success');
    
    setTimeout(() => {
        saveBtn.innerHTML = originalText;
    }, 2000);
    
    // 更新视频流列表显示
    updateStreamsList();
}

// 加载抽帧配置
function loadFrameConfig() {
    const saved = localStorage.getItem('frameConfig');
    if (saved) {
        frameConfig = JSON.parse(saved);
        
        // 更新界面
        document.getElementById('highRiskInterval').value = frameConfig.highRiskInterval || 0.5;
        document.getElementById('mediumRiskInterval').value = frameConfig.mediumRiskInterval || 1.0;
        document.getElementById('lowRiskInterval').value = frameConfig.lowRiskInterval || 2.0;
    }
}

// 根据风险等级获取抽帧间隔
function getIntervalForRiskLevel(riskLevel) {
    const configKey = riskLevelMapping[riskLevel];
    return configKey ? frameConfig[configKey] : frameConfig.mediumRiskInterval;
}

// 刷新视频流列表
async function refreshStreams() {
    try {
        const refreshBtn = document.querySelector('.refresh-btn');
        if (refreshBtn) {
            refreshBtn.style.animation = 'spin 1s linear infinite';
        }
        
        const response = await fetch('/api/streams');
        const result = await response.json();
        
        if (result.success) {
            streams = result.streams;
            updateStreamsList();
            updateStats();
        }
    } catch (error) {
        console.error('获取视频流列表失败:', error);
        showToast('刷新失败: ' + error.message, 'error');
    } finally {
        const refreshBtn = document.querySelector('.refresh-btn');
        if (refreshBtn) {
            refreshBtn.style.animation = '';
        }
    }
}

// 更新视频流列表显示
function updateStreamsList() {
    const tbody = document.getElementById('streamsList');
    
    if (streams.length === 0) {
        tbody.innerHTML = `
            <tr class="empty-state">
                <td colspan="5" class="text-center">
                    <div class="empty-content">
                        <i class="bi bi-inbox empty-icon"></i>
                        <div class="empty-text">暂无视频流配置</div>
                        <small class="empty-subtext">请导入CSV文件开始使用</small>
                    </div>
                </td>
            </tr>
        `;
        return;
    }
    
    tbody.innerHTML = streams.map((stream, index) => {
        const isActive = activeStreams.has(stream.stream_id);
        const statusBadge = isActive ? 
            '<span class="badge bg-success"><span class="status-indicator status-running"></span>运行中</span>' :
            '<span class="badge bg-secondary"><span class="status-indicator status-stopped"></span>已停止</span>';
        
        const riskBadge = getRiskBadge(stream.risk_level);
        
        // 获取抽帧间隔配置信息
        const actualInterval = getIntervalForRiskLevel(stream.risk_level);
        const configInfo = `${stream.risk_level}: ${actualInterval}s间隔`;
        
        return `
            <tr class="stream-row" style="animation-delay: ${index * 0.1}s">
                <td>
                    <div class="stream-info">
                        <strong class="stream-name">${stream.name}</strong>
                        ${stream.description ? `<br><small class="stream-desc text-muted">${stream.description}</small>` : ''}
                        <br><small class="config-info text-info">
                            <i class="bi bi-stopwatch me-1"></i> ${configInfo}
                        </small>
                    </div>
                </td>
                <td>
                    <code class="stream-url">${stream.url}</code>
                </td>
                <td>${riskBadge}</td>
                <td>${statusBadge}</td>
                <td>
                    <div class="btn-group btn-group-sm action-buttons" role="group">
                        ${isActive ? 
                            `<button class="btn btn-danger control-btn" onclick="stopStream('${stream.stream_id}')" title="停止流">
                                <i class="bi bi-stop-fill"></i>
                            </button>` :
                            `<button class="btn btn-success control-btn" onclick="startStream('${stream.stream_id}')" title="启动流">
                                <i class="bi bi-play-fill"></i>
                            </button>`
                        }
                        <button class="btn btn-outline-primary" onclick="viewStreamDetails('${stream.stream_id}')" title="查看详情">
                            <i class="bi bi-eye"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');
    
    // 添加行动画
    setTimeout(() => {
        document.querySelectorAll('.stream-row').forEach(row => {
            row.style.animation = 'slideInUp 0.5s ease-out forwards';
        });
    }, 50);
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

// 启动单个视频流
async function startStream(streamId) {
    try {
        showLoading(true);
        
        // 获取流配置以确定风险等级
        const stream = streams.find(s => s.stream_id === streamId);
        if (!stream) {
            showToast('未找到视频流配置', 'error');
            return;
        }
        
        // 确定最终的配置
        let finalConfig;
        finalConfig = {
            frameInterval: getIntervalForRiskLevel(stream.risk_level),
            applyToAll: false
        };
        
        const response = await fetch(`/api/streams/${streamId}/start`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                frame_config: finalConfig
            })
        });
        
        const result = await response.json();
        
        if (isSuccessResponse(result)) {
            activeStreams.add(streamId);
            showToast(`视频流 ${streamId} 启动成功`, 'success');
            updateStreamsList();
            startResultUpdater(streamId);
            
            // 添加启动动画效果
            const streamRow = document.querySelector(`tr:has(button[onclick*="${streamId}"])`);
            if (streamRow) {
                streamRow.style.background = 'linear-gradient(135deg, rgba(40, 167, 69, 0.1) 0%, rgba(56, 239, 125, 0.1) 100%)';
                setTimeout(() => {
                    streamRow.style.background = '';
                }, 2000);
            }
        } else {
            showToast('启动失败: ' + getErrorMessage(result), 'error');
        }
    } catch (error) {
        console.error('启动视频流失败:', error);
        showToast('启动失败: ' + error.message, 'error');
    } finally {
        showLoading(false);
    }
}

// 停止单个视频流
async function stopStream(streamId) {
    try {
        const response = await fetch(`/api/streams/${streamId}/stop`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({})
        });
        
        const result = await response.json();
        
        if (isSuccessResponse(result)) {
            activeStreams.delete(streamId);
            showToast(`视频流 ${streamId} 已停止`, 'info');
            updateStreamsList();
            
            // 添加停止动画效果
            const streamRow = document.querySelector(`tr:has(button[onclick*="${streamId}"])`);
            if (streamRow) {
                streamRow.style.background = 'linear-gradient(135deg, rgba(220, 53, 69, 0.1) 0%, rgba(252, 70, 107, 0.1) 100%)';
                setTimeout(() => {
                    streamRow.style.background = '';
                }, 2000);
            }
        } else {
            showToast('停止失败: ' + getErrorMessage(result), 'error');
        }
    } catch (error) {
        console.error('停止视频流失败:', error);
        showToast('停止失败: ' + error.message, 'error');
    }
}

// 启动所有视频流
async function startAllStreams() {
    if (streams.length === 0) {
        showToast('没有可启动的视频流', 'warning');
        return;
    }
    
    showLoading(true);
    let successCount = 0;
    
    for (const stream of streams) {
        if (!activeStreams.has(stream.stream_id)) {
            try {
                await startStream(stream.stream_id);
                successCount++;
                // 延迟一下避免同时启动太多
                await new Promise(resolve => setTimeout(resolve, 500));
            } catch (error) {
                console.error(`启动流 ${stream.stream_id} 失败:`, error);
            }
        }
    }
    
    showToast(`成功启动 ${successCount} 个视频流`, 'success');
    showLoading(false);
}

// 停止所有视频流
async function stopAllStreams() {
    if (activeStreams.size === 0) {
        showToast('没有运行中的视频流', 'warning');
        return;
    }
    
    const streamIds = Array.from(activeStreams);
    let successCount = 0;
    
    for (const streamId of streamIds) {
        try {
            await stopStream(streamId);
            successCount++;
        } catch (error) {
            console.error(`停止流 ${streamId} 失败:`, error);
        }
    }
    
    showToast(`成功停止 ${successCount} 个视频流`, 'info');
}

// 查看视频流详情
function viewStreamDetails(streamId) {
    const stream = streams.find(s => s.stream_id === streamId);
    if (!stream) return;
    
    // 创建详情模态框
    const modalHtml = `
        <div class="modal fade" id="streamDetailModal" tabindex="-1">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">
                            <i class="bi bi-info-circle me-2"></i>视频流详情
                        </h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="row">
                            <div class="col-md-6">
                                <h6>基本信息</h6>
                                <table class="table table-sm">
                                    <tr><td><strong>流ID:</strong></td><td>${stream.stream_id}</td></tr>
                                    <tr><td><strong>名称:</strong></td><td>${stream.name}</td></tr>
                                    <tr><td><strong>描述:</strong></td><td>${stream.description || '无'}</td></tr>
                                    <tr><td><strong>风险等级:</strong></td><td>${getRiskBadge(stream.risk_level)}</td></tr>
                                    <tr><td><strong>类型:</strong></td><td>${stream.type || '自动检测'}</td></tr>
                                </table>
                            </div>
                            <div class="col-md-6">
                                <h6>配置信息</h6>
                                <table class="table table-sm">
                                    <tr><td><strong>视频源:</strong></td><td><code>${stream.url}</code></td></tr>
                                    <tr><td><strong>抽帧间隔:</strong></td><td>${getIntervalForRiskLevel(stream.risk_level)}秒</td></tr>
                                    <tr><td><strong>状态:</strong></td><td>${activeStreams.has(stream.stream_id) ? '运行中' : '已停止'}</td></tr>
                                </table>
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">关闭</button>
                        ${activeStreams.has(stream.stream_id) ? 
                            `<button type="button" class="btn btn-danger" onclick="stopStream('${stream.stream_id}'); bootstrap.Modal.getInstance(document.getElementById('streamDetailModal')).hide();">停止流</button>` :
                            `<button type="button" class="btn btn-success" onclick="startStream('${stream.stream_id}'); bootstrap.Modal.getInstance(document.getElementById('streamDetailModal')).hide();">启动流</button>`
                        }
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // 移除旧的模态框
    const oldModal = document.getElementById('streamDetailModal');
    if (oldModal) oldModal.remove();
    
    // 添加新的模态框
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    const modal = new bootstrap.Modal(document.getElementById('streamDetailModal'));
    modal.show();
}

// 启动结果更新器
function startResultUpdater(streamId) {
    // 使用 Server-Sent Events 或定期轮询获取结果
    const interval = setInterval(async () => {
        if (!activeStreams.has(streamId)) {
            clearInterval(interval);
            return;
        }
        
        try {
            const response = await fetch(`/api/results/${streamId}`);
            const result = await response.json();
            
            if (result.success && result.results.length > 0) {
                updateResults(result.results);
            }
        } catch (error) {
            console.error('获取结果失败:', error);
        }
    }, 2000); // 每2秒更新一次
}

// 更新检测结果显示
function updateResults(results) {
    const container = document.getElementById('resultsContainer');
    
    // 清空提示信息
    if (container.querySelector('.empty-results')) {
        container.innerHTML = '';
    }
    
    results.forEach((result, index) => {
        const resultCard = createResultCard(result);
        container.insertAdjacentHTML('afterbegin', resultCard);
        
        // 添加入场动画
        setTimeout(() => {
            const newCard = container.firstElementChild;
            if (newCard) {
                newCard.style.animation = 'slideInLeft 0.5s ease-out';
            }
        }, index * 100);
        
        // 限制显示数量，移除旧的结果
        const cards = container.querySelectorAll('.result-card');
        if (cards.length > 10) {
            const oldCard = cards[cards.length - 1];
            oldCard.style.animation = 'slideOutRight 0.3s ease-out';
            setTimeout(() => oldCard.remove(), 300);
        }
    });
}

// 创建结果卡片
function createResultCard(result) {
    const timestamp = new Date(result.timestamp * 1000).toLocaleString();
    
    return `
        <div class="result-card">
            <div class="card-body">
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <h6 class="card-title mb-0">
                        <i class="bi bi-camera-video me-1"></i>${result.stream_id}
                    </h6>
                    <small class="text-muted">
                        <i class="bi bi-clock me-1"></i>${timestamp}
                    </small>
                </div>
                ${result.frame_path ? 
                    `<img src="/${result.frame_path}" class="result-image mb-2" alt="检测结果" loading="lazy">` : 
                    ''
                }
                <div class="detection-info">
                    <div class="detection-summary mb-2">
                        <i class="bi bi-search me-1"></i> 
                        检测到 <strong class="text-primary">${result.total_objects}</strong> 个对象
                    </div>
                    <div class="detection-tags">
                        ${result.detections.map(det => 
                            `<span class="badge bg-primary me-1 mb-1">
                                ${det.class_name} 
                                <span class="confidence">(${(det.confidence * 100).toFixed(1)}%)</span>
                            </span>`
                        ).join('')}
                    </div>
                </div>
            </div>
        </div>
    `;
}

// 定期更新状态
function startStatusUpdater() {
    setInterval(updateStats, 5000); // 每5秒更新一次状态
}

// 更新统计信息
async function updateStats() {
    try {
        const response = await fetch('/api/stats');
        const stats = await response.json();
        
        if (stats.success) {
            // 使用动画更新数字
            animateNumber('totalStreams', streams.length);
            animateNumber('activeStreams', activeStreams.size);
            animateNumber('totalDetections', stats.total_detections || 0);
            
            const avgTime = (stats.average_processing_time || 0).toFixed(0);
            document.getElementById('avgProcessTime').textContent = avgTime + 'ms';
        }
    } catch (error) {
        console.error('更新统计信息失败:', error);
    }
}

// 数字动画
function animateNumber(elementId, targetValue) {
    const element = document.getElementById(elementId);
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
    if (show) {
        overlay.classList.add('show');
    } else {
        overlay.classList.remove('show');
    }
}

// （已移除本地辅助函数，统一使用 common.js 中的 isSuccessResponse / getErrorMessage） 