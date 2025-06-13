// 系统设置页面专用JavaScript

// 用于记录本页面创建的 interval ID
const settingsIntervals = [];

// 页面初始化
document.addEventListener('DOMContentLoaded', function() {
    initializeSettings();
});

function initializeSettings() {
    console.log('初始化系统设置页面...');
    
    // 加载当前设置
    loadCurrentSettings();
    
    // 启动监控更新
    startSystemMonitoring();
    
    // 初始化事件监听
    initializeEventListeners();
    
    // 初始化系统运行时间
    initSystemUptime();

    // 返回清理函数，供 SPA 调用
    return function cleanupSettings() {
        settingsIntervals.forEach(id => clearInterval(id));
        settingsIntervals.length = 0;
    };
}

// 初始化事件监听
function initializeEventListeners() {
    // 置信度滑块
    const confidenceSlider = document.getElementById('detectionConfidence');
    const confidenceDisplay = document.getElementById('confidenceDisplay');
    
    if (confidenceSlider && confidenceDisplay) {
        confidenceSlider.addEventListener('input', function() {
            confidenceDisplay.textContent = this.value;
        });
    }
}

// 加载当前设置
async function loadCurrentSettings() {
    try {
        const resp = await fetch('/api/settings');
        const data = await resp.json();
        if (data.success) {
            applySettingsToForm(data.settings || {});
            // 同步到 localStorage 作为离线缓存
            localStorage.setItem('systemSettings', JSON.stringify(data.settings || {}));
        } else {
            throw new Error(data.error || '未获取到设置');
        }
    } catch (err) {
        console.warn('从后端加载设置失败, 回退本地缓存:', err);
        const saved = localStorage.getItem('systemSettings');
        if (saved) {
            applySettingsToForm(JSON.parse(saved));
        }
    }
}

// 应用设置到表单
function applySettingsToForm(settings) {
    if (settings.maxStreams) {
        const maxStreamsInput = document.getElementById('maxStreams');
        if (maxStreamsInput) maxStreamsInput.value = settings.maxStreams;
    }
    
    if (settings.detectionConfidence) {
        const confidenceSlider = document.getElementById('detectionConfidence');
        const confidenceDisplay = document.getElementById('confidenceDisplay');
        if (confidenceSlider) {
            confidenceSlider.value = settings.detectionConfidence;
            if (confidenceDisplay) confidenceDisplay.textContent = settings.detectionConfidence;
        }
    }
    
    if (settings.resultRetention) {
        const retentionSelect = document.getElementById('resultRetention');
        if (retentionSelect) retentionSelect.value = settings.resultRetention;
    }
    
    if (settings.logLevel) {
        const logLevelSelect = document.getElementById('logLevel');
        if (logLevelSelect) logLevelSelect.value = settings.logLevel;
    }
    
    if (typeof settings.autoStart === 'boolean') {
        const autoStartCheckbox = document.getElementById('autoStart');
        if (autoStartCheckbox) autoStartCheckbox.checked = settings.autoStart;
    }
    
    if (typeof settings.saveFrames === 'boolean') {
        const saveFramesCheckbox = document.getElementById('saveFrames');
        if (saveFramesCheckbox) saveFramesCheckbox.checked = settings.saveFrames;
    }
    
    if (settings.modelDevice) {
        const deviceSelect = document.getElementById('modelDevice');
        if (deviceSelect) deviceSelect.value = settings.modelDevice;
    }
}

// 保存系统配置
async function saveSystemConfig() {
    const settings = {
        maxStreams: parseInt(document.getElementById('maxStreams')?.value || 10),
        detectionConfidence: parseFloat(document.getElementById('detectionConfidence')?.value || 0.5),
        resultRetention: document.getElementById('resultRetention')?.value || '7',
        logLevel: document.getElementById('logLevel')?.value || 'INFO',
        autoStart: document.getElementById('autoStart')?.checked || false,
        saveFrames: document.getElementById('saveFrames')?.checked || true,
        modelDevice: document.getElementById('modelDevice')?.value || 'cpu'
    };

    try {
        showLoading(true);
        const resp = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });
        const data = await resp.json();
        if (data.success) {
            localStorage.setItem('systemSettings', JSON.stringify(settings));
            showToast('系统配置已保存', 'success');
        } else {
            throw new Error(data.error || '保存失败');
        }
    } catch (err) {
        console.error('保存系统配置失败:', err);
        showToast('保存失败: ' + err.message, 'error');
    } finally {
        showLoading(false);
    }
}

// 更新模型配置
function updateModelConfig() {
    const deviceSelect = document.getElementById('modelDevice');
    
    const config = {
        device: deviceSelect?.value || 'cpu'
    };
    
    // TODO: 发送到后端API更新模型配置
    console.log('更新模型配置:', config);
    showToast('模型配置已更新', 'success');
}

// 重新加载模型
async function reloadModel() {
    if (!confirm('确定要重新加载YOLO模型吗？这可能需要一些时间。')) {
        return;
    }
    
    try {
        showLoading(true);
        
        // TODO: 调用后端API重新加载模型
        await new Promise(resolve => setTimeout(resolve, 2000)); // 模拟加载时间
        
        showToast('模型重新加载成功', 'success');
        
    } catch (error) {
        console.error('重新加载模型失败:', error);
        showToast('重新加载失败: ' + error.message, 'error');
    } finally {
        showLoading(false);
    }
}

// 启动系统监控
function startSystemMonitoring() {
    settingsIntervals.push(setInterval(updateSystemStatus, 5000));
    settingsIntervals.push(setInterval(updateSystemUptime, 1000));
    settingsIntervals.push(setInterval(updateResourceUsage, 30000));
    
    // 初始加载
    updateSystemStatus();
    updateResourceUsage();
}

// 更新系统状态
async function updateSystemStatus() {
    try {
        const response = await fetch('/api/system_status');
        const result = await response.json();
        
        if (result.success) {
            // 系统状态正常
        } else {
            console.warn('系统状态异常');
        }
    } catch (error) {
        console.error('获取系统状态失败:', error);
    }
}

// 更新资源使用情况
function updateResourceUsage() {
    // 模拟资源使用数据（实际应该从后端API获取）
    const memoryUsage = Math.random() * 80 + 10; // 10-90%
    const cpuUsage = Math.random() * 60 + 5;     // 5-65%
    const diskUsage = Math.random() * 50 + 20;   // 20-70%
    
    updateResourceDisplay('memory', memoryUsage);
    updateResourceDisplay('cpu', cpuUsage);
    updateResourceDisplay('disk', diskUsage);
}

// 更新资源显示
function updateResourceDisplay(resource, usage) {
    const usageElement = document.getElementById(`${resource}Usage`);
    const progressElement = document.getElementById(`${resource}Progress`);
    
    if (usageElement) {
        usageElement.textContent = `${usage.toFixed(1)}%`;
    }
    
    if (progressElement) {
        progressElement.style.width = `${usage}%`;
        
        // 根据使用率设置颜色
        progressElement.className = 'progress-bar';
        if (usage > 80) {
            progressElement.classList.add('bg-danger');
        } else if (usage > 60) {
            progressElement.classList.add('bg-warning');
        } else {
            progressElement.classList.add('bg-success');
        }
    }
}

// 初始化系统运行时间
function initSystemUptime() {
    const startTime = Date.now();
    const uptimeElement = document.getElementById('systemUptime');
    if (uptimeElement) {
        uptimeElement.dataset.startTime = startTime;
    }
}

// 更新系统运行时间
function updateSystemUptime() {
    const uptimeElement = document.getElementById('systemUptime');
    if (!uptimeElement) return;
    
    const startTime = parseInt(uptimeElement.dataset.startTime) || Date.now();
    const uptime = Date.now() - startTime;
    
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

// 日志管理
let allLogs = [
    { time: '2024-01-15 10:30:00', level: 'INFO', message: '系统启动完成' },
    { time: '2024-01-15 10:30:05', level: 'INFO', message: 'YOLO模型加载成功' },
    { time: '2024-01-15 10:30:10', level: 'SUCCESS', message: 'Web服务器启动在端口8088' },
    { time: '2024-01-15 10:35:00', level: 'INFO', message: '视频流配置已加载' },
    { time: '2024-01-15 10:40:00', level: 'WARNING', message: '检测到网络延迟' }
];

// 刷新日志
function refreshLogs() {
    displayLogs(allLogs);
    showToast('日志已刷新', 'info');
}

// 清空日志
function clearLogs() {
    if (confirm('确定要清空所有日志吗？')) {
        allLogs = [];
        displayLogs(allLogs);
        showToast('日志已清空', 'success');
    }
}

// 下载日志
function downloadLogs() {
    const logText = allLogs.map(log => 
        `${log.time} [${log.level}] ${log.message}`
    ).join('\n');
    
    const blob = new Blob([logText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `system_logs_${new Date().toISOString().split('T')[0]}.txt`;
    
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    showToast('日志已下载', 'success');
}

// 过滤日志
function filterLogs() {
    const levelFilter = document.getElementById('logLevelFilter')?.value || '';
    const filteredLogs = levelFilter ? 
        allLogs.filter(log => log.level === levelFilter) : 
        allLogs;
    
    displayLogs(filteredLogs);
}

// 搜索日志
function searchLogs() {
    const searchTerm = document.getElementById('logSearchInput')?.value.toLowerCase() || '';
    const filteredLogs = searchTerm ? 
        allLogs.filter(log => log.message.toLowerCase().includes(searchTerm)) : 
        allLogs;
    
    displayLogs(filteredLogs);
}

// 显示日志
function displayLogs(logs) {
    const container = document.getElementById('logContainer');
    if (!container) return;
    
    if (logs.length === 0) {
        container.innerHTML = '<div class="text-muted text-center">暂无日志</div>';
        return;
    }
    
    container.innerHTML = logs.map(log => `
        <div class="log-entry">
            <span class="log-time">${log.time}</span>
            <span class="log-level log-level-${log.level.toLowerCase()}">${log.level}</span>
            <span class="log-message">${log.message}</span>
        </div>
    `).join('');
}

// 系统操作函数
function restartSystem() {
    const confirmMsg = '确定要重启系统吗？这将停止所有视频流并重新启动服务。';
    showConfirmModal(confirmMsg, () => {
        showLoading(true);
        // TODO: 调用重启API
        setTimeout(() => {
            showLoading(false);
            showToast('系统重启中...', 'info');
        }, 2000);
    });
}

function backupData() {
    if (confirm('确定要备份数据吗？这可能需要一些时间。')) {
        showLoading(true);
        // TODO: 调用备份API
        setTimeout(() => {
            showLoading(false);
            showToast('数据备份完成', 'success');
        }, 3000);
    }
}

function exportConfig() {
    try {
        const config = {
            system_settings: JSON.parse(localStorage.getItem('systemSettings') || '{}'),
            frame_config: JSON.parse(localStorage.getItem('frameConfig') || '{}'),
            timestamp: new Date().toISOString()
        };
        
        const blob = new Blob([JSON.stringify(config, null, 2)], {
            type: 'application/json'
        });
        
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `system_config_${new Date().toISOString().split('T')[0]}.json`;
        
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        showToast('配置已导出', 'success');
        
    } catch (error) {
        console.error('导出配置失败:', error);
        showToast('导出失败: ' + error.message, 'error');
    }
}

function resetToDefaults() {
    const confirmMsg = '确定要恢复所有设置到默认值吗？这将清除所有自定义配置。';
    showConfirmModal(confirmMsg, () => {
        // 清除本地存储
        localStorage.removeItem('systemSettings');
        localStorage.removeItem('frameConfig');
        
        // 重置表单
        document.getElementById('systemConfigForm')?.reset();
        
        // 重新加载默认设置
        loadCurrentSettings();
        
        showToast('已恢复默认设置', 'success');
    });
}

// 显示确认模态框
function showConfirmModal(message, callback) {
    const modal = document.getElementById('confirmModal');
    const messageElement = document.getElementById('confirmMessage');
    const confirmButton = document.getElementById('confirmAction');
    
    if (messageElement) {
        messageElement.textContent = message;
    }
    
    if (confirmButton) {
        confirmButton.onclick = () => {
            bootstrap.Modal.getInstance(modal).hide();
            callback();
        };
    }
    
    if (modal) {
        new bootstrap.Modal(modal).show();
    }
}

// 添加新日志条目（模拟）
function addLogEntry(level, message) {
    const now = new Date();
    const timeString = now.toLocaleString('zh-CN');
    
    allLogs.push({
        time: timeString,
        level: level,
        message: message
    });
    
    // 限制日志数量
    if (allLogs.length > 100) {
        allLogs = allLogs.slice(-100);
    }
    
    // 如果没有过滤，则显示新日志
    const levelFilter = document.getElementById('logLevelFilter')?.value;
    const searchTerm = document.getElementById('logSearchInput')?.value;
    
    if (!levelFilter && !searchTerm) {
        displayLogs(allLogs);
    }
}

// 模拟添加一些日志（仅用于演示）
setTimeout(() => {
    addLogEntry('INFO', 'CSV配置文件上传成功');
}, 5000);

setTimeout(() => {
    addLogEntry('SUCCESS', '视频流启动成功');
}, 10000);

// 初始显示日志
setTimeout(() => {
    displayLogs(allLogs);
}, 1000); 