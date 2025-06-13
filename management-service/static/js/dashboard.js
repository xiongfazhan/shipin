// 仪表板页面专用JavaScript

// 页面初始化
document.addEventListener('DOMContentLoaded', function() {
    initializeDashboard();
});

function initializeDashboard() {
    console.log('初始化仪表板页面...');
    
    // 启动数据更新
    refreshDashboardData();
    startDashboardUpdaters();
    
    // 初始化系统运行时间
    initSystemUptime();

    // 返回清理函数
    return function cleanupDashboard() {
        dashboardIntervals.forEach(id => clearInterval(id));
        dashboardIntervals.length = 0;
    };
}

// 启动仪表板更新器
function startDashboardUpdaters() {
    // 记录intervalId 以便后续清理
    dashboardIntervals.push(setInterval(refreshDashboardData, 5000));
    dashboardIntervals.push(setInterval(updateSystemUptime, 1000));
    dashboardIntervals.push(setInterval(updateLatestResults, 3000));
}

// 刷新仪表板数据
async function refreshDashboardData() {
    await Promise.all([
        updateActiveStreams(),
        updateLatestResults(),
        updateGlobalStats()
    ]);
}

// 更新活跃视频流
async function updateActiveStreams() {
    try {
        const response = await fetch('/api/streams?offset=0&limit=200');
        const result = await response.json();
        
        if (result.success) {
            streams = result.streams;
            const activeStreamsList = document.getElementById('activeStreamsList');
            
            // 获取真实活跃流
            const activeList = streams.filter(s => s.is_running);
            
            if (activeList.length === 0) {
                activeStreamsList.innerHTML = `
                    <div class="empty-content">
                        <i class="bi bi-pause-circle empty-icon"></i>
                        <div class="empty-text">暂无活跃视频流</div>
                        <small class="empty-subtext">启动视频流后，状态信息将在此显示</small>
                    </div>
                `;
            } else {
                activeStreamsList.innerHTML = activeList.map(stream => `
                    <div class="active-stream-item mb-2 p-2 border rounded">
                        <div class="d-flex justify-content-between align-items-center">
                            <div>
                                <strong>${stream.name}</strong>
                                <br>
                                <small class="text-muted">${stream.url}</small>
                                <br>
                                ${getRiskBadge(stream.risk_level)}
                            </div>
                            <div class="text-end">
                                <span class="badge bg-success">
                                    <i class="bi bi-play-fill me-1"></i>运行中
                                </span>
                                <br>
                                <small class="text-muted">间隔: ${getIntervalForRiskLevel(stream.risk_level)}s</small>
                            </div>
                        </div>
                    </div>
                `).join('');
            }
        }
    } catch (error) {
        console.error('更新活跃视频流失败:', error);
    }
}

// 更新最新检测结果
async function updateLatestResults() {
    try {
        const response = await fetch('/api/results/latest?limit=3');
        const result = await response.json();
        
        if (result.success) {
            const latestResults = document.getElementById('latestResults');
            
            if (result.results.length === 0) {
                latestResults.innerHTML = `
                    <div class="empty-results">
                        <i class="bi bi-search empty-icon"></i>
                        <div class="empty-text">等待检测结果</div>
                        <small class="empty-subtext">启动视频流后，最新结果将在此显示</small>
                    </div>
                `;
            } else {
                latestResults.innerHTML = result.results.map(res => {
                    const timestamp = formatTime(res.timestamp);
                    return `
                        <div class="result-item mb-3 p-2 border rounded">
                            <div class="d-flex">
                                ${res.frame_path ? 
                                    `<img src="/${res.frame_path}" class="result-thumb me-3" style="width: 80px; height: 60px; object-fit: cover; border-radius: 4px;" alt="检测结果">` : 
                                    `<div class="result-thumb-placeholder me-3" style="width: 80px; height: 60px; background: #f8f9fa; border-radius: 4px; display: flex; align-items: center; justify-content: center;">
                                        <i class="bi bi-image text-muted"></i>
                                    </div>`
                                }
                                <div class="flex-grow-1">
                                    <div class="d-flex justify-content-between align-items-start mb-1">
                                        <strong class="text-primary">${res.stream_id}</strong>
                                        <small class="text-muted">${timestamp}</small>
                                    </div>
                                    <div class="detection-summary">
                                        检测到 <span class="text-success">${res.total_objects}</span> 个对象
                                    </div>
                                    <div class="detection-tags mt-1">
                                        ${res.detections.slice(0, 3).map(det => 
                                            `<span class="badge bg-secondary me-1" style="font-size: 0.7rem;">
                                                ${det.class_name} (${(det.confidence * 100).toFixed(1)}%)
                                            </span>`
                                        ).join('')}
                                        ${res.detections.length > 3 ? '<span class="text-muted">...</span>' : ''}
                                    </div>
                                </div>
                            </div>
                        </div>
                    `;
                }).join('');
            }
        }
    } catch (error) {
        console.error('更新最新检测结果失败:', error);
    }
}

// 初始化系统运行时间
function initSystemUptime() {
    const startTime = Date.now();
    updateSystemUptime(startTime);
}

// 更新系统运行时间
function updateSystemUptime(startTime = null) {
    const uptimeElement = document.getElementById('systemUptime');
    if (!uptimeElement) return;
    
    if (startTime) {
        uptimeElement.dataset.startTime = startTime;
    }
    
    const start = parseInt(uptimeElement.dataset.startTime) || Date.now();
    const now = Date.now();
    const uptime = now - start;
    
    const seconds = Math.floor(uptime / 1000) % 60;
    const minutes = Math.floor(uptime / (1000 * 60)) % 60;
    const hours = Math.floor(uptime / (1000 * 60 * 60)) % 24;
    const days = Math.floor(uptime / (1000 * 60 * 60 * 24));
    
    let uptimeText = '';
    if (days > 0) uptimeText += `${days}天 `;
    if (hours > 0) uptimeText += `${hours}小时 `;
    if (minutes > 0) uptimeText += `${minutes}分钟 `;
    uptimeText += `${seconds}秒`;
    
    uptimeElement.textContent = uptimeText;
}

// 刷新所有数据
function refreshAll() {
    const refreshBtn = event.target;
    const originalContent = refreshBtn.innerHTML;
    
    refreshBtn.innerHTML = '<i class="bi bi-arrow-clockwise me-2" style="animation: spin 1s linear infinite;"></i> 刷新中...';
    refreshBtn.disabled = true;
    
    Promise.all([
        refreshDashboardData(),
        updateGlobalStats()
    ]).then(() => {
        showToast('数据已刷新', 'success');
    }).catch(error => {
        console.error('刷新数据失败:', error);
        showToast('刷新失败: ' + error.message, 'error');
    }).finally(() => {
        refreshBtn.innerHTML = originalContent;
        refreshBtn.disabled = false;
    });
}

// 添加CSS动画
const style = document.createElement('style');
style.textContent = `
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    
    .active-stream-item {
        transition: all 0.3s ease;
        background: rgba(255, 255, 255, 0.8);
    }
    
    .active-stream-item:hover {
        transform: translateX(5px);
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
    }
    
    .result-item {
        transition: all 0.3s ease;
        background: rgba(255, 255, 255, 0.9);
    }
    
    .result-item:hover {
        transform: scale(1.02);
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
    }
    
    .result-thumb {
        transition: transform 0.3s ease;
    }
    
    .result-thumb:hover {
        transform: scale(1.1);
    }
`;
document.head.appendChild(style);

// 用于记录intervals
const dashboardIntervals = []; 