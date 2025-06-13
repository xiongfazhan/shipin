// 配置管理页面专用JavaScript

// 页面初始化
document.addEventListener('DOMContentLoaded', function() {
    initializeConfiguration();
});

function initializeConfiguration() {
    console.log('初始化配置管理页面...');
    
    // 设置文件上传
    setupFileUpload();
    
    // 加载配置状态
    loadConfigurationStatus();
    
    // 初始化抽帧配置界面
    initFrameConfiguration();
}

// 初始化抽帧配置界面
function initFrameConfiguration() {
    // 加载保存的配置
    loadFrameConfig();
    
    // 更新界面显示
    updateFrameConfigDisplay();
    
    // 绑定配置变化事件
    const inputs = ['highRiskInterval', 'mediumRiskInterval', 'lowRiskInterval'];
    inputs.forEach(id => {
        const input = document.getElementById(id);
        if (input) {
            input.addEventListener('input', updateFrameConfigDisplay);
        }
    });
}

// 更新抽帧配置显示
function updateFrameConfigDisplay() {
    const highInput = document.getElementById('highRiskInterval');
    const mediumInput = document.getElementById('mediumRiskInterval');
    const lowInput = document.getElementById('lowRiskInterval');
    
    if (highInput && mediumInput && lowInput) {
        // 实时更新预设按钮的显示值
        const currentConfig = {
            high: parseFloat(highInput.value),
            medium: parseFloat(mediumInput.value),
            low: parseFloat(lowInput.value)
        };
        
        // 不再匹配预设，直接更新状态
        
        // 更新配置状态显示
        updateFrameConfigStatus(currentConfig);
    }
}

// 更新抽帧配置状态
function updateFrameConfigStatus(config) {
    const frameStatus = document.getElementById('frameStatus');
    if (frameStatus) {
        frameStatus.innerHTML = `
            <span class="badge bg-success">已配置</span>
            <small class="text-muted ms-2">高:${config.high}s 中:${config.medium}s 低:${config.low}s</small>
        `;
    }
}

// 加载配置状态
async function loadConfigurationStatus() {
    try {
        // 检查CSV导入状态
        const streamsResponse = await fetch('/api/streams?offset=0&limit=1');
        const streamsResult = await streamsResponse.json();
        
        const csvStatus = document.getElementById('csvStatus');
        if (csvStatus) {
            if (streamsResult.success && streamsResult.streams.length > 0) {
                csvStatus.innerHTML = `
                    <span class="badge bg-success">已导入</span>
                    <small class="text-muted ms-2">共${streamsResult.streams.length}个视频流配置</small>
                `;
            } else {
                csvStatus.innerHTML = `
                    <span class="badge bg-secondary">未导入</span>
                    <small class="text-muted ms-2">暂无视频流配置</small>
                `;
            }
        }
        
        // 检查系统状态
        const systemResponse = await fetch('/api/system_status');
        const systemResult = await systemResponse.json();
        
        const systemStatus = document.getElementById('systemStatus');
        if (systemStatus) {
            if (systemResult.success && systemResult.status === 'running') {
                systemStatus.innerHTML = `
                    <span class="badge bg-success">正常</span>
                    <small class="text-muted ms-2">所有组件运行正常</small>
                `;
            } else {
                systemStatus.innerHTML = `
                    <span class="badge bg-warning">异常</span>
                    <small class="text-muted ms-2">系统状态异常</small>
                `;
            }
        }
        
    } catch (error) {
        console.error('加载配置状态失败:', error);
    }
}

// 重置所有配置
function resetAllConfig() {
    if (confirm('确定要重置所有配置吗？这将清除所有视频流配置和抽帧设置。')) {
        showLoading(true);
        
        Promise.all([
            resetFrameConfig(),
            clearStreamConfigs()
        ]).then(() => {
            showToast('配置已重置', 'success');
            loadConfigurationStatus();
        }).catch(error => {
            console.error('重置配置失败:', error);
            showToast('重置失败: ' + error.message, 'error');
        }).finally(() => {
            showLoading(false);
        });
    }
}

// 重置抽帧配置
function resetFrameConfig() {
    return new Promise((resolve) => {
        // 重置为默认值
        const highInput = document.getElementById('highRiskInterval');
        const mediumInput = document.getElementById('mediumRiskInterval');
        const lowInput = document.getElementById('lowRiskInterval');
        
        if (highInput) highInput.value = 0.5;
        if (mediumInput) mediumInput.value = 1.0;
        if (lowInput) lowInput.value = 2.0;
        
        // 保存配置
        saveFrameConfig();
        
        resolve();
    });
}

// 清除视频流配置
async function clearStreamConfigs() {
    try {
        const response = await fetch('/api/streams/clear', {
            method: 'POST'
        });
        
        const result = await response.json();
        if (!result.success) {
            throw new Error(result.error || '清除失败');
        }
        
        return result;
    } catch (error) {
        console.error('清除视频流配置失败:', error);
        throw error;
    }
}

// 导出配置
async function exportConfig() {
    try {
        showLoading(true);
        
        const [streamsRes, configResp] = await Promise.all([
            fetch('/api/streams'),
            Promise.resolve({ frameConfig })
        ]);

        const streamsData = await streamsRes.json();
        
        const exportData = {
            timestamp: new Date().toISOString(),
            version: '1.0',
            frameConfig: frameConfig,
            streams: streamsData.success ? streamsData.streams : []
        };
        
        // 创建下载链接
        const blob = new Blob([JSON.stringify(exportData, null, 2)], {
            type: 'application/json'
        });
        
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `video_stream_config_${new Date().toISOString().split('T')[0]}.json`;
        
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        showToast('配置已导出', 'success');
        
    } catch (error) {
        console.error('导出配置失败:', error);
        showToast('导出失败: ' + error.message, 'error');
    } finally {
        showLoading(false);
    }
}

// 导入配置文件
function importConfig() {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json';
    
    input.addEventListener('change', async (event) => {
        const file = event.target.files[0];
        if (!file) return;
        
        try {
            showLoading(true);
            
            const text = await file.text();
            const configData = JSON.parse(text);
            
            // 验证配置格式
            if (!configData.frameConfig || !configData.streams) {
                throw new Error('配置文件格式无效');
            }
            
            // 导入抽帧配置
            frameConfig = configData.frameConfig;
            localStorage.setItem('frameConfig', JSON.stringify(frameConfig));
            
            // 更新界面
            if (configData.frameConfig.highRiskInterval !== undefined) {
                const highInput = document.getElementById('highRiskInterval');
                if (highInput) highInput.value = configData.frameConfig.highRiskInterval;
            }
            if (configData.frameConfig.mediumRiskInterval !== undefined) {
                const mediumInput = document.getElementById('mediumRiskInterval');
                if (mediumInput) mediumInput.value = configData.frameConfig.mediumRiskInterval;
            }
            if (configData.frameConfig.lowRiskInterval !== undefined) {
                const lowInput = document.getElementById('lowRiskInterval');
                if (lowInput) lowInput.value = configData.frameConfig.lowRiskInterval;
            }
            
            updateFrameConfigDisplay();
            
            // 导入视频流配置（需要后端支持）
            if (configData.streams.length > 0) {
                const response = await fetch('/api/import_streams', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ streams: configData.streams })
                });
                
                const result = await response.json();
                if (!result.success) {
                    throw new Error(result.error || '导入视频流配置失败');
                }
            }
            
            showToast('配置导入成功', 'success');
            loadConfigurationStatus();
            
        } catch (error) {
            console.error('导入配置失败:', error);
            showToast('导入失败: ' + error.message, 'error');
        } finally {
            showLoading(false);
        }
    });
    
    input.click();
}

// 添加导入配置按钮（如果需要的话）
function addImportButton() {
    const configStatus = document.getElementById('configStatus');
    if (configStatus) {
        const importBtn = document.createElement('button');
        importBtn.className = 'btn btn-outline-info ms-2';
        importBtn.innerHTML = '<i class="bi bi-upload me-2"></i> 导入配置';
        importBtn.onclick = importConfig;
        
        const buttonsContainer = configStatus.parentElement.querySelector('.mt-3');
        if (buttonsContainer) {
            buttonsContainer.appendChild(importBtn);
        }
    }
}

// 页面加载完成后添加导入按钮
setTimeout(addImportButton, 1000); 