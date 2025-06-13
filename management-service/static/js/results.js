// 检测结果页面专用JavaScript

let allResults = [];
let filteredResults = [];
let currentPage = 1;
let resultsPerPage = 20;
let autoRefreshInterval;

// 页面初始化
document.addEventListener('DOMContentLoaded', function() {
    initializeResults();
});

function initializeResults() {
    console.log('初始化检测结果页面...');
    
    // 加载数据
    refreshResults();
    
    // 启动自动刷新
    startAutoRefresh();
    
    // 初始化过滤器
    initializeFilters();
    
    // 初始化视图模式
    initializeViewMode();
    
    // 返回清理函数，停止自动刷新 interval
    return function cleanupResults() {
        if (autoRefreshInterval) {
            clearInterval(autoRefreshInterval);
            autoRefreshInterval = null;
        }
    };
}

// 启动自动刷新
function startAutoRefresh() {
    const autoRefreshCheckbox = document.getElementById('autoRefresh');
    if (autoRefreshCheckbox && autoRefreshCheckbox.checked) {
        autoRefreshInterval = setInterval(refreshResults, 5000); // 5秒刷新一次
    }
}

// 切换自动刷新
function toggleAutoRefresh() {
    const autoRefreshCheckbox = document.getElementById('autoRefresh');
    
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
        autoRefreshInterval = null;
    }
    
    if (autoRefreshCheckbox && autoRefreshCheckbox.checked) {
        startAutoRefresh();
        showToast('已启用自动刷新', 'info');
    } else {
        showToast('已关闭自动刷新', 'info');
    }
}

// 刷新检测结果
async function refreshResults(limit = 10000) {
    try {
        const response = await fetch(`/api/results/latest?limit=${limit}`);
        const result = await response.json();
        
        if (result.success) {
            allResults = result.results || [];
            updateDetectionClassOptions(); // 更新检测类型选项
            applyFilters();
            updateResultsDisplay();
            updateResultsStats();
            
            // 更新数据限制说明
            const dataLimitInfo = document.getElementById('dataLimitInfo');
            if (dataLimitInfo) {
                dataLimitInfo.textContent = `显示最近${limit}条记录`;
            }
        }
    } catch (error) {
        console.error('刷新结果失败:', error);
    }
}

// 加载更多结果
async function loadMoreResults() {
    const currentLimit = allResults.length;
    const newLimit = Math.min(currentLimit + 10000, 50000); // 最多加载50000条
    
    if (newLimit > currentLimit) {
        await refreshResults(newLimit);
        showToast(`已加载更多数据，当前显示${allResults.length}条记录`, 'success');
    } else {
        showToast('已加载全部可用数据', 'info');
    }
}

// 初始化过滤器
function initializeFilters() {
    // 置信度滑块
    const confidenceFilter = document.getElementById('confidenceFilter');
    const confidenceValue = document.getElementById('confidenceValue');
    
    if (confidenceFilter && confidenceValue) {
        confidenceFilter.addEventListener('input', function() {
            confidenceValue.textContent = this.value + '%';
            filterResults();
        });
    }
    
    // 加载视频流选项
    loadStreamOptions();
    
    // 更新检测类型选项
    updateDetectionClassOptions();
}

// 加载视频流选项
async function loadStreamOptions() {
    try {
        const response = await fetch('/api/streams?offset=0&limit=1000');
        const result = await response.json();
        
        if (result.success) {
            const streamFilter = document.getElementById('streamFilter');
            if (streamFilter) {
                // 清空现有选项（保留"所有视频流"）
                const defaultOption = streamFilter.querySelector('option[value=""]');
                streamFilter.innerHTML = '';
                if (defaultOption) {
                    streamFilter.appendChild(defaultOption);
                }
                
                // 添加视频流选项
                result.streams.forEach(stream => {
                    const option = document.createElement('option');
                    option.value = stream.stream_id || stream.name;
                    option.textContent = stream.name || stream.stream_id;
                    streamFilter.appendChild(option);
                });
            }
        }
    } catch (error) {
        console.error('加载视频流选项失败:', error);
    }
}

// 更新检测类型选项（基于实际检测结果）
async function updateDetectionClassOptions() {
    const classFilter = document.getElementById('classFilter');
    if (!classFilter) return;
    
    try {
        // 从API获取检测类别
        const response = await fetch('/api/detection_classes');
        const result = await response.json();
        
        let detectedClasses = [];
        if (result.success) {
            detectedClasses = result.classes;
        } else {
            // 降级到本地计算
            const classSet = new Set();
            allResults.forEach(result => {
                if (result.detections) {
                    result.detections.forEach(detection => {
                        classSet.add(detection.class_name);
                    });
                }
            });
            detectedClasses = Array.from(classSet).sort();
        }
        
        // 保存默认选项
        const defaultOption = classFilter.querySelector('option[value=""]');
        classFilter.innerHTML = '';
        if (defaultOption) {
            classFilter.appendChild(defaultOption);
        }
        
        // 添加检测到的类别选项
        detectedClasses.forEach(className => {
            const option = document.createElement('option');
            option.value = className;
            option.textContent = className;
            classFilter.appendChild(option);
        });
        
    } catch (error) {
        console.error('获取检测类别失败:', error);
        // 降级到本地计算
        const detectedClasses = new Set();
        allResults.forEach(result => {
            if (result.detections) {
                result.detections.forEach(detection => {
                    detectedClasses.add(detection.class_name);
                });
            }
        });
        
        // 保存默认选项
        const defaultOption = classFilter.querySelector('option[value=""]');
        classFilter.innerHTML = '';
        if (defaultOption) {
            classFilter.appendChild(defaultOption);
        }
        
        // 添加检测到的类别选项
        Array.from(detectedClasses).sort().forEach(className => {
            const option = document.createElement('option');
            option.value = className;
            option.textContent = className;
            classFilter.appendChild(option);
        });
    }
}

// 应用过滤器
function applyFilters() {
    const streamFilter = document.getElementById('streamFilter')?.value || '';
    const classFilter = document.getElementById('classFilter')?.value || '';
    const timeFilter = document.getElementById('timeFilter')?.value || '24h';
    const confidenceFilter = parseFloat(document.getElementById('confidenceFilter')?.value || 50) / 100;
    
    // 时间过滤
    const now = Date.now() / 1000;
    const timeFilters = {
        '1h': now - 3600,
        '6h': now - 6 * 3600,
        '24h': now - 24 * 3600,
        'all': 0
    };
    const timeThreshold = timeFilters[timeFilter] || 0;
    
    filteredResults = allResults.filter(result => {
        // 时间过滤
        if (result.timestamp < timeThreshold) return false;
        
        // 视频流过滤
        if (streamFilter && result.stream_id !== streamFilter) return false;
        
        // 置信度过滤 - 至少有一个检测对象超过阈值
        if (result.detections) {
            const hasHighConfidence = result.detections.some(det => det.confidence >= confidenceFilter);
            if (!hasHighConfidence) return false;
        }
        
        // 检测类型过滤
        if (classFilter && result.detections) {
            const hasClass = result.detections.some(det => det.class_name === classFilter);
            if (!hasClass) return false;
        }
        
        return true;
    });
    
    // 重置分页
    currentPage = 1;
}

// 过滤结果
function filterResults() {
    applyFilters();
    updateResultsDisplay();
    updateResultsStats();
}

// 更新结果显示
function updateResultsDisplay() {
    const cardView = document.getElementById('cardView');
    const viewMode = cardView && cardView.checked ? 'card' : 'list';
    
    if (viewMode === 'card') {
        updateCardView();
    } else {
        updateListView();
    }
    
    updatePagination();
    updateResultCount();
}

// 更新卡片视图
function updateCardView() {
    const container = document.getElementById('cardViewContainer');
    const listContainer = document.getElementById('listViewContainer');
    
    if (container) {
        container.style.display = 'block';
    }
    if (listContainer) {
        listContainer.style.display = 'none';
    }
    
    if (!container) return;
    
    if (filteredResults.length === 0) {
        container.innerHTML = `
            <div class="empty-results">
                <i class="bi bi-search empty-icon"></i>
                <div class="empty-text">没有找到匹配的结果</div>
                <small class="empty-subtext">尝试调整过滤条件</small>
            </div>
        `;
        return;
    }
    
    const startIndex = (currentPage - 1) * resultsPerPage;
    const endIndex = startIndex + resultsPerPage;
    const pageResults = filteredResults.slice(startIndex, endIndex);
    
    container.innerHTML = pageResults.map(result => {
        const timestamp = formatTime(result.timestamp);
        const detectionSummary = result.detections.slice(0, 3).map(det => 
            `${det.class_name} (${(det.confidence * 100).toFixed(1)}%)`
        ).join(', ');
        
        return `
            <div class="result-card" onclick="showResultDetail('${result.stream_id}', ${result.timestamp})">
                <div class="result-header">
                    <div class="stream-info">
                        <strong>${result.stream_name || result.stream_id}</strong>
                        <small class="text-muted">${timestamp}</small>
                    </div>
                    <span class="badge bg-primary">${result.total_objects || result.detections.length} 个对象</span>
                </div>
                ${result.frame_path ? 
                    `<img src="/${result.frame_path}" class="result-image" alt="检测结果">` :
                    `<div class="result-placeholder">
                        <i class="bi bi-image"></i>
                        <span>无图像</span>
                    </div>`
                }
                <div class="result-content">
                    <div class="detection-summary">${detectionSummary}</div>
                    <div class="processing-time">
                        处理时间: ${(result.processing_time * 1000).toFixed(0)}ms
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

// 更新列表视图
function updateListView() {
    const container = document.getElementById('cardViewContainer');
    const listContainer = document.getElementById('listViewContainer');
    const tbody = document.getElementById('resultsList');
    
    if (container) {
        container.style.display = 'none';
    }
    if (listContainer) {
        listContainer.style.display = 'block';
    }
    
    if (!tbody) return;
    
    if (filteredResults.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="text-center">
                    <div class="empty-results">
                        <i class="bi bi-search empty-icon"></i>
                        <div class="empty-text">没有找到匹配的结果</div>
                    </div>
                </td>
            </tr>
        `;
        return;
    }
    
    const startIndex = (currentPage - 1) * resultsPerPage;
    const endIndex = startIndex + resultsPerPage;
    const pageResults = filteredResults.slice(startIndex, endIndex);
    
    tbody.innerHTML = pageResults.map(result => {
        const timestamp = formatTime(result.timestamp);
        const mainDetection = result.detections[0];
        
        return `
            <tr>
                <td>${timestamp}</td>
                <td>${result.stream_name || result.stream_id}</td>
                <td>
                    ${mainDetection ? 
                        `${mainDetection.class_name} ${result.detections.length > 1 ? `+${result.detections.length - 1}` : ''}` :
                        '无检测'
                    }
                </td>
                <td>
                    ${mainDetection ? 
                        `<span class="badge ${getConfidenceBadgeClass(mainDetection.confidence)}">${(mainDetection.confidence * 100).toFixed(1)}%</span>` :
                        '-'
                    }
                </td>
                <td>
                    ${result.frame_path ? 
                        `<img src="/${result.frame_path}" class="result-thumb" style="width: 60px; height: 45px; object-fit: cover;" alt="预览">` :
                        '<span class="text-muted">无图像</span>'
                    }
                </td>
                <td>
                    <button class="btn btn-sm btn-outline-primary" onclick="showResultDetail('${result.stream_id}', ${result.timestamp})">
                        <i class="bi bi-zoom-in"></i>
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

// 获取置信度徽章样式
function getConfidenceBadgeClass(confidence) {
    if (confidence >= 0.8) return 'bg-success';
    if (confidence >= 0.6) return 'bg-warning';
    return 'bg-danger';
}

// 更新分页
function updatePagination() {
    const totalPages = Math.ceil(filteredResults.length / resultsPerPage);
    const paginationContainer = document.getElementById('paginationContainer');
    const pagination = document.getElementById('pagination');
    
    if (!pagination) return;
    
    if (totalPages <= 1) {
        if (paginationContainer) {
            paginationContainer.style.display = 'none';
        }
        return;
    }
    
    if (paginationContainer) {
        paginationContainer.style.display = 'block';
    }
    
    let paginationHtml = '';
    
    // 上一页
    paginationHtml += `
        <li class="page-item ${currentPage === 1 ? 'disabled' : ''}">
            <a class="page-link" href="#" onclick="changePage(${currentPage - 1})">上一页</a>
        </li>
    `;
    
    // 页码
    const startPage = Math.max(1, currentPage - 2);
    const endPage = Math.min(totalPages, currentPage + 2);
    
    for (let i = startPage; i <= endPage; i++) {
        paginationHtml += `
            <li class="page-item ${i === currentPage ? 'active' : ''}">
                <a class="page-link" href="#" onclick="changePage(${i})">${i}</a>
            </li>
        `;
    }
    
    // 下一页
    paginationHtml += `
        <li class="page-item ${currentPage === totalPages ? 'disabled' : ''}">
            <a class="page-link" href="#" onclick="changePage(${currentPage + 1})">下一页</a>
        </li>
    `;
    
    pagination.innerHTML = paginationHtml;
}

// 切换页面
function changePage(page) {
    const totalPages = Math.ceil(filteredResults.length / resultsPerPage);
    if (page < 1 || page > totalPages) return;
    
    currentPage = page;
    updateResultsDisplay();
}

// 更新统计信息
async function updateResultsStats() {
    try {
        // 先基于客户端现有结果计算
        updateLocalStats();

        // 再尝试调用后端汇总接口，若有效数据则覆盖本地统计
        const response = await fetch('/api/statistics');
        const result = await response.json();

        if (result.success && result.statistics) {
            const stats = result.statistics;

            // 仅当后端返回的计数大于本地值时才覆盖，避免 0 覆盖真实数据
            if (stats.total_results > 0) {
                updateStatElement('totalResults', stats.total_results);
            }
            if (stats.total_objects > 0) {
                updateStatElement('totalObjects', stats.total_objects);
            }
            if (typeof stats.recent_results === 'number') {
                updateStatElement('recentResults', stats.recent_results);
            }
            if (typeof stats.avg_processing_time === 'number') {
                updateStatElement('avgProcessTime', (stats.avg_processing_time * 1000).toFixed(0) + 'ms');
            }
        }
    } catch (error) {
        console.warn('统计接口不可用，已使用本地统计:', error);
    }
}

// 本地统计计算（降级方案）
function updateLocalStats() {
    // 更新检测结果条数
    updateStatElement('totalResults', allResults.length);
    
    // 更新检测对象总数
    const totalObjects = allResults.reduce((sum, result) => 
        sum + (result.total_objects || result.detections.length), 0);
    updateStatElement('totalObjects', totalObjects);
    
    // 更新最近1小时结果数
    const oneHourAgo = Date.now() / 1000 - 3600;
    const recentCount = allResults.filter(r => r.timestamp > oneHourAgo).length;
    updateStatElement('recentResults', recentCount);
    
    // 更新平均处理时间
    if (allResults.length > 0) {
        const avgTime = allResults.reduce((sum, r) => sum + (r.processing_time || 0), 0) / allResults.length;
        updateStatElement('avgProcessTime', (avgTime * 1000).toFixed(0) + 'ms');
    }
}

// 更新结果计数和分页信息
function updateResultCount() {
    const resultCount = document.getElementById('resultCount');
    const pageInfo = document.getElementById('pageInfo');
    
    if (resultCount) {
        resultCount.textContent = filteredResults.length;
    }
    
    if (pageInfo) {
        const totalPages = Math.ceil(filteredResults.length / resultsPerPage);
        if (filteredResults.length > 0) {
            const startIndex = (currentPage - 1) * resultsPerPage + 1;
            const endIndex = Math.min(currentPage * resultsPerPage, filteredResults.length);
            pageInfo.textContent = `(第${currentPage}页，共${totalPages}页，显示第${startIndex}-${endIndex}条)`;
        } else {
            pageInfo.textContent = '';
        }
    }
}

// 初始化视图模式
function initializeViewMode() {
    const cardView = document.getElementById('cardView');
    const listView = document.getElementById('listView');
    
    if (cardView) {
        cardView.addEventListener('change', changeViewMode);
    }
    if (listView) {
        listView.addEventListener('change', changeViewMode);
    }
}

// 切换视图模式
function changeViewMode() {
    updateResultsDisplay();
}

// 改变每页显示数量
function changePageSize() {
    const pageSize = document.getElementById('pageSize');
    if (pageSize) {
        resultsPerPage = parseInt(pageSize.value);
        currentPage = 1; // 重置到第一页
        updateResultsDisplay();
        showToast(`已设置每页显示 ${resultsPerPage} 条结果`, 'info');
    }
}

// 显示结果详情
function showResultDetail(streamId, timestamp) {
    const result = allResults.find(r => r.stream_id === streamId && r.timestamp === timestamp);
    if (!result) return;
    
    const modal = new bootstrap.Modal(document.getElementById('resultDetailModal'));
    const content = document.getElementById('resultDetailContent');
    
    const timestamp_formatted = formatTime(result.timestamp);
    
    content.innerHTML = `
        <div class="result-detail">
            <div class="row mb-3">
                <div class="col-md-6">
                    ${result.frame_path ? 
                        `<img src="/${result.frame_path}" class="img-fluid rounded" alt="检测结果">` :
                        `<div class="no-image-placeholder">
                            <i class="bi bi-image"></i>
                            <span>无图像数据</span>
                        </div>`
                    }
                </div>
                <div class="col-md-6">
                    <h6>基本信息</h6>
                    <table class="table table-sm">
                        <tr><td>视频流:</td><td>${result.stream_name || result.stream_id}</td></tr>
                        <tr><td>检测时间:</td><td>${timestamp_formatted}</td></tr>
                        <tr><td>处理时间:</td><td>${(result.processing_time * 1000).toFixed(0)}ms</td></tr>
                        <tr><td>检测对象数:</td><td>${result.total_objects || result.detections.length}</td></tr>
                    </table>
                </div>
            </div>
            
            <h6>检测详情</h6>
            <div class="detections-list">
                ${result.detections.map((det, index) => `
                    <div class="detection-item">
                        <span class="detection-class">${det.class_name}</span>
                        <span class="badge ${getConfidenceBadgeClass(det.confidence)} ms-2">${(det.confidence * 100).toFixed(1)}%</span>
                        ${det.bbox ? `<small class="text-muted ms-2">位置: (${det.bbox.join(', ')})</small>` : ''}
                    </div>
                `).join('')}
            </div>
        </div>
    `;
    
    modal.show();
}

// 下载结果图片
function downloadResultImage() {
    // 获取当前显示的图片
    const modal = document.getElementById('resultDetailModal');
    const img = modal.querySelector('img');
    
    if (img) {
        const link = document.createElement('a');
        link.href = img.src;
        link.download = `detection_result_${Date.now()}.jpg`;
        link.click();
    }
}

// 清空结果
async function clearResults() {
    if (confirm('确定要清空所有检测结果吗？此操作不可撤销。')) {
        try {
            const response = await fetch('/api/results/clear', {
                method: 'POST'
            });
            
            if (response.ok) {
                allResults = [];
                filteredResults = [];
                updateResultsDisplay();
                showToast('检测结果已清空', 'success');
            } else {
                showToast('清空失败', 'error');
            }
        } catch (error) {
            console.error('清空结果失败:', error);
            showToast('清空失败: ' + error.message, 'error');
        }
    }
}

// 导出结果
function exportResults() {
    if (filteredResults.length === 0) {
        showToast('没有结果可导出', 'warning');
        return;
    }
    
    const data = filteredResults.map(result => ({
        stream_id: result.stream_id,
        stream_name: result.stream_name,
        timestamp: result.timestamp,
        formatted_time: formatTime(result.timestamp),
        detections: result.detections,
        total_objects: result.total_objects,
        processing_time: result.processing_time
    }));
    
    const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: 'application/json'
    });
    
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `detection_results_${new Date().toISOString().split('T')[0]}.json`;
    
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    showToast('结果已导出', 'success');
}

// 添加样式
const style = document.createElement('style');
style.textContent = `
    .result-card {
        border: 1px solid #dee2e6;
        border-radius: 8px;
        margin-bottom: 1rem;
        background: white;
        transition: all 0.3s ease;
        cursor: pointer;
    }
    
    .result-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
    }
    
    .result-header {
        padding: 1rem;
        border-bottom: 1px solid #f8f9fa;
        display: flex;
        justify-content: between;
        align-items: center;
    }
    
    .result-image {
        width: 100%;
        height: 200px;
        object-fit: cover;
    }
    
    .result-placeholder {
        height: 200px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        background: #f8f9fa;
        color: #6c757d;
    }
    
    .result-content {
        padding: 1rem;
    }
    
    .detection-summary {
        font-weight: 500;
        margin-bottom: 0.5rem;
    }
    
    .processing-time {
        font-size: 0.875rem;
        color: #6c757d;
    }
    
    .result-thumb {
        transition: transform 0.3s ease;
    }
    
    .result-thumb:hover {
        transform: scale(1.1);
    }
    
    .detection-item {
        padding: 0.5rem;
        border: 1px solid #e9ecef;
        border-radius: 4px;
        margin-bottom: 0.5rem;
        display: flex;
        align-items: center;
    }
    
    .detection-class {
        font-weight: 500;
    }
    
    .no-image-placeholder {
        height: 200px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        background: #f8f9fa;
        color: #6c757d;
        border-radius: 8px;
    }
    
    .results-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
        gap: 1rem;
    }
`;
document.head.appendChild(style); 