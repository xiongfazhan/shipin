// 视频流管理页面专用JavaScript

let selectedStreams = new Set();
let currentStreamData = [];
const STREAM_PAGE_SIZE = 50;
let streamOffset = 0;
let hasMoreStreams = true;
let loadingMore = false;
let sse;

// 页面初始化
document.addEventListener('DOMContentLoaded', function() {
    initializeStreams();
    initStreamSSE();
});

function initializeStreams() {
    console.log('初始化视频流管理页面...');
    
    // 加载数据
    refreshStreams(true);
    
    // 启动更新器
    startStreamsUpdaters();
    
    // 初始化批量选择
    initializeBatchSelection();

    // 设置虚拟滚动 sentinel
    const tbody = document.getElementById('streamsList');
    if (tbody) {
        const sentinel = document.createElement('tr');
        sentinel.id = 'loadMoreSentinel';
        sentinel.innerHTML = '<td colspan="7" class="text-center text-muted">加载中...</td>';
        tbody.parentElement.appendChild(sentinel);

        const observer = new IntersectionObserver(entries => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    loadMoreStreams();
                }
            });
        });
        observer.observe(sentinel);
    }

    // 返回清理函数
    return function cleanupStreams() {
        streamIntervals.forEach(id => clearInterval(id));
        streamIntervals.length = 0;
        if (sse) { try { sse.close(); } catch(e){} sse = null; }
    };
}

// interval registry for this page
const streamIntervals = [];

// 启动更新器
function startStreamsUpdaters() {
    streamIntervals.push(setInterval(refreshStreams, 10000));
    streamIntervals.push(setInterval(updateStreamsStats, 5000));
}

// 刷新视频流数据
async function refreshStreams(reset = true) {
    try {
        if (loadingMore) return;
        if (reset) {
            streamOffset = 0;
            hasMoreStreams = true;
            currentStreamData = [];
        }

        const response = await fetch(`/api/streams?offset=${streamOffset}&limit=${STREAM_PAGE_SIZE}`);
        const result = await response.json();
        
        if (result.success) {
            if (reset) {
                currentStreamData = result.streams;
            } else {
                currentStreamData = currentStreamData.concat(result.streams);
            }
            // 计算是否还有更多
            if (currentStreamData.length >= result.total) {
                hasMoreStreams = false;
                document.getElementById('loadMoreSentinel').style.display = 'none';
            } else {
                hasMoreStreams = true;
            }
            updateStreamsTable();
            updateStreamsStats();
            streamOffset = currentStreamData.length;
        } else {
            console.error('获取视频流失败:', result.error);
        }
    } catch (error) {
        console.error('刷新视频流失败:', error);
    }
}

// 更新视频流表格
function updateStreamsTable() {
    const tbody = document.getElementById('streamsList');
    if (!tbody) return;
    
    if (currentStreamData.length === 0) {
        tbody.innerHTML = `
            <tr class="empty-state">
                <td colspan="7" class="text-center">
                    <div class="empty-content">
                        <i class="bi bi-inbox empty-icon"></i>
                        <div class="empty-text">暂无视频流配置</div>
                        <small class="empty-subtext">请先导入CSV文件或添加配置</small>
                    </div>
                </td>
            </tr>
        `;
    } else {
        tbody.innerHTML = currentStreamData.map(stream => {
            const streamId = stream.stream_id || stream.name;
            // 使用从后端获取的真实运行状态
            const isActive = stream.is_running || false;
            
            return `
                <tr data-stream-id="${streamId}">
                    <td>
                        <input type="checkbox" class="stream-checkbox" value="${streamId}" onchange="updateSelection()">
                    </td>
                    <td>
                        <strong>${stream.name || streamId}</strong>
                        ${stream.description ? `<br><small class="text-muted">${stream.description}</small>` : ''}
                    </td>
                    <td>
                        <code class="stream-url">${stream.url}</code>
                    </td>
                    <td>
                        ${getRiskBadge(stream.risk_level)}
                    </td>
                    <td>
                        <span class="badge bg-secondary">${getIntervalForRiskLevel(stream.risk_level)}s</span>
                    </td>
                    <td>
                        ${isActive ? 
                            '<span class="badge bg-success"><i class="bi bi-play-fill me-1"></i>运行中</span>' :
                            '<span class="badge bg-secondary"><i class="bi bi-stop-fill me-1"></i>已停止</span>'
                        }
                    </td>
                    <td>
                        <div class="btn-group btn-group-sm" role="group">
                            ${isActive ? 
                                `<button class="btn btn-outline-danger" onclick="stopSingleStream('${streamId}')" title="停止">
                                    <i class="bi bi-stop-fill"></i>
                                </button>` :
                                `<button class="btn btn-outline-success" onclick="startSingleStream('${streamId}')" title="启动">
                                    <i class="bi bi-play-fill"></i>
                                </button>`
                            }
                            <button class="btn btn-outline-primary" onclick="viewStreamDetail('${streamId}')" title="详情">
                                <i class="bi bi-info-circle"></i>
                            </button>
                            <button class="btn btn-outline-secondary" onclick="editStream('${streamId}')" title="编辑">
                                <i class="bi bi-pencil"></i>
                            </button>
                            <button class="btn btn-outline-info" onclick="previewStream('${streamId}')" title="预览">
                                <i class="bi bi-eye"></i>
                            </button>
                            <button class="btn btn-outline-danger" onclick="deleteSingleStream('${streamId}')" title="删除">
                                <i class="bi bi-trash"></i>
                            </button>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');
    }
}

// 更新统计信息
function updateStreamsStats() {
    const totalElement = document.getElementById('totalStreams');
    const activeElement = document.getElementById('activeStreams');
    
    if (totalElement) {
        totalElement.textContent = currentStreamData.length;
    }
    
    if (activeElement) {
        const activeCount = currentStreamData.filter(stream => {
            const streamId = stream.stream_id || stream.name;
            return stream.is_running;
        }).length;
        activeElement.textContent = activeCount;
    }
}

// 启动单个视频流
async function startSingleStream(streamId) {
    try {
        showLoading(true);
        
        const stream = currentStreamData.find(s => (s.stream_id || s.name) === streamId);
        if (!stream) return;
        
        const interval = getIntervalForRiskLevel(stream.risk_level);
        const response = await fetch(`/api/streams/${streamId}/start`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                frame_config: { frameInterval: interval }
            })
        });
        
        const result = await response.json();
        
        if (isSuccessResponse(result)) {
            showToast(`视频流 ${streamId} 启动成功`, 'success');
            refreshStreams();
        } else {
            showToast(`启动失败: ${getErrorMessage(result)}`, 'error');
        }
    } catch (error) {
        console.error('启动视频流失败:', error);
        showToast('启动失败: ' + error.message, 'error');
    } finally {
        showLoading(false);
    }
}

// 停止单个视频流
async function stopSingleStream(streamId) {
    try {
        showLoading(true);
        
        const response = await fetch(`/api/streams/${streamId}/stop`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({})
        });
        
        const result = await response.json();
        
        if (isSuccessResponse(result)) {
            showToast(`视频流 ${streamId} 停止成功`, 'success');
            refreshStreams();
        } else {
            showToast(`停止失败: ${getErrorMessage(result)}`, 'error');
        }
    } catch (error) {
        console.error('停止视频流失败:', error);
        showToast('停止失败: ' + error.message, 'error');
    } finally {
        showLoading(false);
    }
}

// 启动所有视频流
async function startAllStreams() {
    if (currentStreamData.length === 0) {
        showToast('没有可启动的视频流', 'warning');
        return;
    }
    
    try {
        showLoading(true);
        
        const response = await fetch('/api/streams/start_all', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ frame_config: frameConfig })
        });
        
        const result = await response.json();
        
        if (isSuccessResponse(result)) {
            showToast(result.message || '已批量启动', 'success');
            refreshStreams();
        } else {
            showToast(`批量启动失败: ${getErrorMessage(result)}`, 'error');
        }
    } catch (error) {
        console.error('批量启动失败:', error);
        showToast('批量启动失败: ' + error.message, 'error');
    } finally {
        showLoading(false);
    }
}

// 停止所有视频流
async function stopAllStreams() {
    if (currentStreamData.length === 0) {
        showToast('没有可停止的视频流', 'warning');
        return;
    }
    
    try {
        showLoading(true);
        
        const response = await fetch('/api/streams/stop_all', {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (isSuccessResponse(result)) {
            showToast(result.message || '已批量停止', 'success');
            refreshStreams();
        } else {
            showToast(`批量停止失败: ${getErrorMessage(result)}`, 'error');
        }
    } catch (error) {
        console.error('批量停止失败:', error);
        showToast('批量停止失败: ' + error.message, 'error');
    } finally {
        showLoading(false);
    }
}

// 过滤视频流
function filterStreams() {
    const riskFilter = document.getElementById('riskFilter').value;
    const statusFilter = document.getElementById('statusFilter').value;
    
    const rows = document.querySelectorAll('#streamsList tr');
    
    rows.forEach(row => {
        if (row.classList.contains('empty-state')) return;
        
        const streamId = row.dataset.streamId;
        const stream = currentStreamData.find(s => (s.stream_id || s.name) === streamId);
        
        if (!stream) return;
        
        let show = true;
        
        // 风险等级过滤
        if (riskFilter && stream.risk_level !== riskFilter) {
            show = false;
        }
        
        // 状态过滤
        if (statusFilter) {
            if (statusFilter === 'running' && !stream.is_running) {
                show = false;
            } else if (statusFilter === 'stopped' && stream.is_running) {
                show = false;
            }
        }
        
        row.style.display = show ? '' : 'none';
    });
}

// 初始化批量选择功能
function initializeBatchSelection() {
    const selectAllCheckbox = document.getElementById('selectAll');
    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', toggleSelectAll);
    }
}

// 切换全选
function toggleSelectAll() {
    const selectAll = document.getElementById('selectAll').checked;
    const checkboxes = document.querySelectorAll('.stream-checkbox');
    
    checkboxes.forEach(checkbox => {
        checkbox.checked = selectAll;
        if (selectAll) {
            selectedStreams.add(checkbox.value);
        } else {
            selectedStreams.delete(checkbox.value);
        }
    });
    
    updateBatchOperations();
}

// 更新选择状态
function updateSelection() {
    selectedStreams.clear();
    
    const checkboxes = document.querySelectorAll('.stream-checkbox:checked');
    checkboxes.forEach(checkbox => {
        selectedStreams.add(checkbox.value);
    });
    
    // 更新全选状态
    const selectAllCheckbox = document.getElementById('selectAll');
    const allCheckboxes = document.querySelectorAll('.stream-checkbox');
    
    if (selectAllCheckbox && allCheckboxes.length > 0) {
        selectAllCheckbox.checked = selectedStreams.size === allCheckboxes.length;
        selectAllCheckbox.indeterminate = selectedStreams.size > 0 && selectedStreams.size < allCheckboxes.length;
    }
    
    updateBatchOperations();
}

// 更新批量操作面板
function updateBatchOperations() {
    const batchPanel = document.getElementById('batchOperations');
    const selectedCount = document.getElementById('selectedCount');
    
    if (batchPanel) {
        batchPanel.style.display = selectedStreams.size > 0 ? 'block' : 'none';
    }
    
    if (selectedCount) {
        selectedCount.textContent = selectedStreams.size;
    }
}

// 批量启动选中的流
function startSelectedStreams() {
    if (selectedStreams.size === 0) {
        showToast('请先选择要启动的视频流', 'warning');
        return;
    }
    
    Promise.all(Array.from(selectedStreams).map(streamId => startSingleStream(streamId)))
        .then(() => {
            showToast(`批量启动完成`, 'success');
        })
        .catch(error => {
            console.error('批量启动失败:', error);
        });
}

// 批量停止选中的流
function stopSelectedStreams() {
    if (selectedStreams.size === 0) {
        showToast('请先选择要停止的视频流', 'warning');
        return;
    }
    
    Promise.all(Array.from(selectedStreams).map(streamId => stopSingleStream(streamId)))
        .then(() => {
            showToast(`批量停止完成`, 'success');
        })
        .catch(error => {
            console.error('批量停止失败:', error);
        });
}

// 清除选择
function clearSelection() {
    selectedStreams.clear();
    
    const checkboxes = document.querySelectorAll('.stream-checkbox');
    checkboxes.forEach(checkbox => {
        checkbox.checked = false;
    });
    
    const selectAllCheckbox = document.getElementById('selectAll');
    if (selectAllCheckbox) {
        selectAllCheckbox.checked = false;
        selectAllCheckbox.indeterminate = false;
    }
    
    updateBatchOperations();
}

// 查看视频流详情
function viewStreamDetail(streamId) {
    const stream = currentStreamData.find(s => (s.stream_id || s.name) === streamId);
    if (!stream) return;
    
    const modal = new bootstrap.Modal(document.getElementById('streamDetailModal'));
    const content = document.getElementById('streamDetailContent');
    const actions = document.getElementById('streamActions');
    
    const isActive = stream.is_running;
    
    content.innerHTML = `
        <div class="stream-detail">
            <div class="row mb-3">
                <div class="col-sm-3"><strong>名称:</strong></div>
                <div class="col-sm-9">${stream.name || streamId}</div>
            </div>
            <div class="row mb-3">
                <div class="col-sm-3"><strong>视频源:</strong></div>
                <div class="col-sm-9"><code>${stream.url}</code></div>
            </div>
            <div class="row mb-3">
                <div class="col-sm-3"><strong>风险等级:</strong></div>
                <div class="col-sm-9">${getRiskBadge(stream.risk_level)}</div>
            </div>
            <div class="row mb-3">
                <div class="col-sm-3"><strong>抽帧间隔:</strong></div>
                <div class="col-sm-9">${getIntervalForRiskLevel(stream.risk_level)} 秒</div>
            </div>
            <div class="row mb-3">
                <div class="col-sm-3"><strong>状态:</strong></div>
                <div class="col-sm-9">
                    ${isActive ? 
                        '<span class="badge bg-success"><i class="bi bi-play-fill me-1"></i>运行中</span>' :
                        '<span class="badge bg-secondary"><i class="bi bi-stop-fill me-1"></i>已停止</span>'
                    }
                </div>
            </div>
            ${stream.description ? `
            <div class="row mb-3">
                <div class="col-sm-3"><strong>描述:</strong></div>
                <div class="col-sm-9">${stream.description}</div>
            </div>
            ` : ''}
        </div>
    `;
    
    actions.innerHTML = `
        ${isActive ? 
            `<button type="button" class="btn btn-danger" onclick="stopSingleStream('${streamId}'); bootstrap.Modal.getInstance(document.getElementById('streamDetailModal')).hide();">
                <i class="bi bi-stop-fill me-2"></i>停止
            </button>` :
            `<button type="button" class="btn btn-success" onclick="startSingleStream('${streamId}'); bootstrap.Modal.getInstance(document.getElementById('streamDetailModal')).hide();">
                <i class="bi bi-play-fill me-2"></i>启动
            </button>`
        }
        <button type="button" class="btn btn-outline-primary ms-2" onclick="editStream('${streamId}'); bootstrap.Modal.getInstance(document.getElementById('streamDetailModal')).hide();">
            <i class="bi bi-pencil me-2"></i>编辑
        </button>
    `;
    
    modal.show();
}

// 编辑视频流
function editStream(streamId) {
    const stream = currentStreamData.find(s => (s.stream_id || s.name) === streamId);
    if (!stream) return;
    
    const modal = new bootstrap.Modal(document.getElementById('editStreamModal'));
    
    // 填充表单
    document.getElementById('editStreamName').value = stream.name || '';
    document.getElementById('editStreamUrl').value = stream.url || '';
    document.getElementById('editStreamRisk').value = stream.risk_level || '中';
    document.getElementById('editStreamDesc').value = stream.description || '';
    
    // 存储当前编辑的流ID
    document.getElementById('editStreamForm').dataset.streamId = streamId;
    
    modal.show();
}

// 保存编辑
function saveStreamEdit() {
    const form = document.getElementById('editStreamForm');
    const streamId = form.dataset.streamId;

    const payload = {
        name: document.getElementById('editStreamName').value.trim(),
        url: document.getElementById('editStreamUrl').value.trim(),
        risk_level: document.getElementById('editStreamRisk').value,
        description: document.getElementById('editStreamDesc').value.trim()
    };

    showLoading(true);
    fetch(`/api/streams/${streamId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ config: payload })
    })
    .then(res => res.json().then(data => ({ ok: res.ok, data })))
    .then(({ ok, data }) => {
        if (ok && (data.status === 'success' || data.success)) {
            showToast('已保存到服务器', 'success');
            bootstrap.Modal.getInstance(document.getElementById('editStreamModal')).hide();
            refreshStreams();
        } else {
            showToast(`保存失败: ${data.message || data.error || '未知错误'}`, 'error');
        }
    })
    .catch(err => {
        console.error('保存失败:', err);
        showToast('保存失败: ' + err.message, 'error');
    })
    .finally(() => showLoading(false));
}

// 添加样式
const style = document.createElement('style');
style.textContent = `
    .stream-url {
        max-width: 200px;
        display: inline-block;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        font-size: 0.85rem;
    }
    
    .risk-badge-animated {
        animation: pulse 2s infinite;
    }
    
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.7; }
        100% { opacity: 1; }
    }
    
    .streams-table tr:hover {
        background-color: rgba(0, 123, 255, 0.05);
    }
    
    .stream-checkbox {
        transform: scale(1.2);
    }
    
    #batchOperations {
        animation: slideDown 0.3s ease-out;
    }
    
    @keyframes slideDown {
        from {
            opacity: 0;
            transform: translateY(-10px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
`;
document.head.appendChild(style);

function loadMoreStreams() {
    if (!hasMoreStreams || loadingMore) return;
    loadingMore = true;
    refreshStreams(false).finally(() => loadingMore = false);
}

// 初始化 SSE
function initStreamSSE() {
    if (!!window.EventSource) {
        sse = new EventSource('/api/streams/updates');
        sse.onmessage = function(event) {
            const changes = JSON.parse(event.data);
            Object.keys(changes).forEach(sid => {
                const state = changes[sid];
                // 更新本地数据
                const item = currentStreamData.find(s => (s.stream_id || s.name) === sid);
                if (item) {
                    item.is_running = state === 'running';
                }
                // 更新行 UI
                const row = document.querySelector(`tr[data-stream-id="${sid}"]`);
                if (row) {
                    const statusTd = row.children[5]; // 状态列 index 5
                    if (statusTd) {
                        statusTd.innerHTML = state === 'running'
                            ? '<span class="badge bg-success"><i class="bi bi-play-fill me-1"></i>运行中</span>'
                            : '<span class="badge bg-secondary"><i class="bi bi-stop-fill me-1"></i>已停止</span>';
                    }
                }
            });
            updateStreamsStats();
        };
    } else {
        console.warn('浏览器不支持 EventSource, 回退到轮询');
    }
}

// 预览视频流快照
function previewStream(streamId) {
    // 构建/获取模态框
    let modalEl = document.getElementById('previewStreamModal');
    if (!modalEl) {
        const html = `
        <div class="modal fade" id="previewStreamModal" tabindex="-1">
            <div class="modal-dialog modal-lg modal-dialog-centered">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title"><i class="bi bi-eye me-2"></i>视频流预览</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body text-center">
                        <img id="previewImage" src="" alt="预览" style="max-width:100%; border-radius:6px;"/>
                    </div>
                </div>
            </div>
        </div>`;
        document.body.insertAdjacentHTML('beforeend', html);
        modalEl = document.getElementById('previewStreamModal');
    }

    const img = modalEl.querySelector('#previewImage');
    let refreshTimer;
    let errorCount = 0;

    const updateImage = () => {
        img.src = `/api/streams/${streamId}/snapshot?ts=` + Date.now();
    };

    img.onerror = () => {
        errorCount++;
        img.src = '';
        img.alt = '暂无画面';
        if (errorCount >= 3) {
            clearInterval(refreshTimer);
            const parent = img.parentElement;
            if (parent && !parent.querySelector('.error-hint')) {
                const hint = document.createElement('div');
                hint.className = 'text-muted mt-3 error-hint';
                hint.innerHTML = `无法获取画面，可能的原因：<br>• 流未启动或 URL 无效<br>• 网络不可达 / 防火墙阻断<br><br>请检查视频流源后重试。`;
                parent.appendChild(hint);
            }
        }
    };

    modalEl.addEventListener('shown.bs.modal', () => {
        updateImage();
        refreshTimer = setInterval(updateImage, 1000); // 每秒刷新
    }, { once: true });

    modalEl.addEventListener('hidden.bs.modal', () => {
        clearInterval(refreshTimer);
    });

    const modal = new bootstrap.Modal(modalEl);
    modal.show();
}

// 删除单个视频流
async function deleteSingleStream(streamId) {
    if (!confirm('确定要删除该视频流配置？该操作不可恢复。')) return;

    try {
        showLoading(true);
        const res = await fetch(`/api/streams/${streamId}`, { method: 'DELETE' });
        const result = await res.json();
        if (res.ok && (result.success || result.status === 'success')) {
            showToast('删除成功', 'success');
            refreshStreams(true);
        } else {
            showToast('删除失败: ' + (result.error || '未知错误'), 'error');
        }
    } catch (err) {
        console.error('删除失败:', err);
        showToast('删除失败: ' + err.message, 'error');
    } finally {
        showLoading(false);
    }
}

// 辅助函数（若 common.js 未加载，可作为后备）
function isSuccessResponse(res) {
    return res && (res.success || res.status === 'success');
}

function getErrorMessage(res) {
    return res && (res.error || res.message || '未知错误');
} 