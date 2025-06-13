// 汇总结果页面 JS

let summaryData = [];

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    refreshSummary();
    setInterval(refreshSummary, 10000); // 10 秒刷新
});

async function refreshSummary() {
    const windowSelect = document.getElementById('windowSelect');
    const windowParam = windowSelect ? windowSelect.value : '5m';
    try {
        const resp = await fetch(`/api/results/summary?window=${windowParam}`);
        const data = await resp.json();
        if (data.success) {
            summaryData = data.summary || data.results || [];
            renderSummary();
        } else {
            showPlaceholder('获取数据失败');
        }
    } catch (err) {
        console.error('获取汇总结果失败:', err);
        showPlaceholder('网络错误');
    }
}

function renderSummary() {
    const tbody = document.getElementById('summaryBody');
    if (!tbody) return;
    if (summaryData.length === 0) {
        showPlaceholder('暂无数据');
        return;
    }
    tbody.innerHTML = summaryData.map(row => `
        <tr>
            <td>${formatTime(row.window_start)} - ${formatTime(row.window_end)}</td>
            <td>${row.stream_name || row.stream_id || '全部'}</td>
            <td>${row.total_detections || 0}</td>
            <td>${(row.avg_processing_time_ms || 0).toFixed(0)}ms</td>
            <td>${row.anomaly_count || 0}</td>
        </tr>
    `).join('');
}

function showPlaceholder(text) {
    const tbody = document.getElementById('summaryBody');
    if (tbody) {
        tbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted">${text}</td></tr>`;
    }
}

// 依赖 common.js 中的工具
function formatTime(ts) {
    if (!ts) return '-';
    return new Date(ts * 1000).toLocaleString('zh-CN');
} 