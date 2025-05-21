/**
 * 检测结果查询与展示
 */

// 检测结果查询参数
let searchParams = {
    startDate: '',
    endDate: '',
    videoId: '',
    objectClass: '',
    page: 1,
    perPage: 10
};

// 当前查看的检测结果详情
let currentDetailedResult = null;

// 当前页面上显示的检测结果列表
let currentResults = [];

// 画布绘制检测框
const annotationCanvas = document.getElementById('annotationCanvas');
const canvasCtx = annotationCanvas ? annotationCanvas.getContext('2d') : null;

// 当前显示的结果索引
let currentResultIndex = 0;

/**
 * 初始化检测结果页面
 */
function initDetectionResults() {
    console.log('初始化检测结果页面...');
    
    // 加载视频源选项
    loadVideoSources();
    
    // 加载目标类别选项
    loadObjectClasses();
    
    // 初始化日期选择器为最近7天
    const today = new Date();
    const weekAgo = new Date();
    weekAgo.setDate(today.getDate() - 7);
    
    const startDateInput = document.getElementById('startDate');
    const endDateInput = document.getElementById('endDate');
    
    if (startDateInput && endDateInput) {
        startDateInput.valueAsDate = weekAgo;
        endDateInput.valueAsDate = today;
        
        // 更新查询参数
        searchParams.startDate = formatDate(weekAgo);
        searchParams.endDate = formatDate(today);
    }
    
    // 绑定查询按钮事件
    const queryBtn = document.getElementById('queryResultsBtn');
    if (queryBtn) {
        queryBtn.addEventListener('click', queryDetectionResults);
    }
    
    // 初始化统计图表
    loadDetectionStats();
    
    // 添加图像导航按钮
    addImageNavigation();
    
    // 首次加载检测结果
    queryDetectionResults();
    
    // 监听窗口大小变化，重新调整画布
    window.addEventListener('resize', () => {
        if (currentDetailedResult) {
            setTimeout(() => drawDetectionBoxes(currentDetailedResult), 300);
        }
    });
}

/**
 * 格式化日期为YYYY-MM-DD格式
 */
function formatDate(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

/**
 * 加载视频源选项
 */
function loadVideoSources() {
    fetch('/api/detection/videos')
        .then(response => response.json())
        .then(data => {
            if (data.code === 0 && data.data) {
                const videoSelect = document.getElementById('videoSourceFilter');
                if (videoSelect) {
                    videoSelect.innerHTML = '<option value="">全部</option>';
                    
                    data.data.forEach(videoId => {
                        const option = document.createElement('option');
                        option.value = videoId;
                        option.textContent = videoId;
                        videoSelect.appendChild(option);
                    });
                }
            }
        })
        .catch(error => console.error('加载视频源失败:', error));
}

/**
 * 加载目标类别选项
 */
function loadObjectClasses() {
    fetch('/api/detection/classes')
        .then(response => response.json())
        .then(data => {
            if (data.code === 0 && data.data) {
                const objectClassInput = document.getElementById('objectClassFilter');
                if (objectClassInput) {
                    // 创建datalist元素用于自动完成
                    let datalist = document.getElementById('objectClassList');
                    if (!datalist) {
                        datalist = document.createElement('datalist');
                        datalist.id = 'objectClassList';
                        document.body.appendChild(datalist);
                        objectClassInput.setAttribute('list', 'objectClassList');
                    }
                    
                    // 清空现有选项
                    datalist.innerHTML = '';
                    
                    // 添加所有类别
                    data.data.forEach(className => {
                        const option = document.createElement('option');
                        option.value = className;
                        datalist.appendChild(option);
                    });
                }
            }
        })
        .catch(error => console.error('加载目标类别失败:', error));
}

/**
 * 查询检测结果
 */
function queryDetectionResults() {
    // 收集表单参数
    const startDateInput = document.getElementById('startDate');
    const endDateInput = document.getElementById('endDate');
    const videoSourceSelect = document.getElementById('videoSourceFilter');
    const objectClassInput = document.getElementById('objectClassFilter');
    
    if (startDateInput) searchParams.startDate = startDateInput.value;
    if (endDateInput) searchParams.endDate = endDateInput.value;
    if (videoSourceSelect) searchParams.videoId = videoSourceSelect.value;
    if (objectClassInput) searchParams.objectClass = objectClassInput.value;
    
    // 重置为第一页
    searchParams.page = 1;
    
    // 构建查询URL
    const queryParams = new URLSearchParams();
    if (searchParams.startDate) queryParams.append('start_date', searchParams.startDate);
    if (searchParams.endDate) queryParams.append('end_date', searchParams.endDate);
    if (searchParams.videoId) queryParams.append('video_id', searchParams.videoId);
    if (searchParams.objectClass) queryParams.append('object_class', searchParams.objectClass);
    queryParams.append('page', searchParams.page);
    queryParams.append('per_page', searchParams.perPage);
    
    // 显示加载提示
    const screenshotsList = document.getElementById('screenshotsList');
    if (screenshotsList) {
        screenshotsList.innerHTML = '<div style="text-align: center; padding: 20px; color: #aaa;">加载中...</div>';
    }
    
    // 发送请求
    fetch(`/api/detection/results?${queryParams.toString()}`)
        .then(response => response.json())
        .then(data => {
            if (data.code === 0 && data.data) {
                displayDetectionResults(data.data.results, data.data.pagination);
            } else {
                console.error('查询检测结果失败:', data.message || '未知错误');
                if (screenshotsList) {
                    screenshotsList.innerHTML = `<div style="text-align: center; padding: 20px; color: #f44336;">查询失败: ${data.message || '未知错误'}</div>`;
                }
            }
        })
        .catch(error => {
            console.error('查询检测结果错误:', error);
            if (screenshotsList) {
                screenshotsList.innerHTML = `<div style="text-align: center; padding: 20px; color: #f44336;">查询出错: ${error.message}</div>`;
            }
        });
}

/**
 * 显示检测结果列表
 */
function displayDetectionResults(results, pagination) {
    currentResults = results;
    currentResultIndex = 0;
    
    // 获取缩略图列表容器
    const screenshotsList = document.getElementById('screenshotsList');
    if (!screenshotsList) return;
    
    screenshotsList.innerHTML = '';
    
    if (results.length === 0) {
        screenshotsList.innerHTML = '<div style="text-align: center; padding: 20px; color: #aaa;">没有找到符合条件的检测结果</div>';
        
        // 清空详情区域
        const screenshotImage = document.getElementById('screenshotImage');
        const screenshotInfo = document.getElementById('screenshotInfo');
        if (screenshotImage) screenshotImage.src = '';
        if (screenshotInfo) screenshotInfo.textContent = '';
        if (canvasCtx) clearCanvas();
        
        // 更新导航按钮状态
        updateNavigationButtons();
        
        return;
    }
    
    // 创建结果网格容器
    const gridContainer = document.createElement('div');
    gridContainer.className = 'screenshots-grid';
    gridContainer.style.display = 'grid';
    gridContainer.style.gridTemplateColumns = 'repeat(auto-fill, minmax(150px, 1fr))';
    gridContainer.style.gap = '10px';
    
    // 创建缩略图
    results.forEach((result, index) => {
        const thumbnailDiv = document.createElement('div');
        thumbnailDiv.className = 'screenshot-thumbnail';
        thumbnailDiv.dataset.index = index;
        thumbnailDiv.style.border = '2px solid transparent';
        thumbnailDiv.style.borderRadius = '4px';
        thumbnailDiv.style.overflow = 'hidden';
        thumbnailDiv.style.backgroundColor = 'rgba(0, 0, 0, 0.2)';
        thumbnailDiv.style.cursor = 'pointer';
        thumbnailDiv.style.transition = 'all 0.2s';
        
        // 创建缩略图内容
        let thumbnailContent = '';
        
        // 图像部分
        thumbnailContent += '<div style="height: 100px; display: flex; align-items: center; justify-content: center; overflow: hidden; background: #000;">';
        if (result.image_path) {
            thumbnailContent += `<img src="${result.image_path}" alt="检测结果 ${result.result_id}" style="max-width: 100%; max-height: 100%; object-fit: contain;">`;
        } else {
            thumbnailContent += '<div style="color: #aaa; text-align: center;">无图像</div>';
        }
        thumbnailContent += '</div>';
        
        // 信息部分
        const timestamp = new Date(result.timestamp).toLocaleString();
        thumbnailContent += `
            <div style="padding: 5px; font-size: 12px;">
                <div style="font-weight: bold; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">ID: ${result.video_id}</div>
                <div style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">时间: ${timestamp}</div>
                <div>检测: ${result.detection_count}个对象</div>
            </div>
        `;
        
        thumbnailDiv.innerHTML = thumbnailContent;
        
        // 添加点击事件
        thumbnailDiv.addEventListener('click', () => {
            // 更新当前索引
            currentResultIndex = index;
            
            // 高亮当前选中的缩略图
            document.querySelectorAll('.screenshot-thumbnail').forEach(item => {
                item.style.borderColor = 'transparent';
                item.style.transform = 'none';
                item.style.boxShadow = 'none';
            });
            thumbnailDiv.style.borderColor = '#1890ff';
            thumbnailDiv.style.transform = 'scale(1.03)';
            thumbnailDiv.style.boxShadow = '0 0 5px rgba(24, 144, 255, 0.5)';
            
            // 显示详情
            showDetectionDetail(result.result_id);
        });
        
        gridContainer.appendChild(thumbnailDiv);
    });
    
    screenshotsList.appendChild(gridContainer);
    
    // 如果有结果，默认显示第一个
    if (results.length > 0) {
        const firstThumbnail = gridContainer.querySelector('.screenshot-thumbnail');
        if (firstThumbnail) {
            firstThumbnail.style.borderColor = '#1890ff';
            firstThumbnail.style.transform = 'scale(1.03)';
            firstThumbnail.style.boxShadow = '0 0 5px rgba(24, 144, 255, 0.5)';
            showDetectionDetail(results[0].result_id);
        }
        
        // 更新导航按钮状态
        updateNavigationButtons();
    }
    
    // 创建分页控件
    createPagination(pagination);
}

/**
 * 创建分页控件
 */
function createPagination(pagination) {
    const paginationDiv = document.createElement('div');
    paginationDiv.style.display = 'flex';
    paginationDiv.style.justifyContent = 'space-between';
    paginationDiv.style.alignItems = 'center';
    paginationDiv.style.marginTop = '15px';
    paginationDiv.style.padding = '10px';
    paginationDiv.style.backgroundColor = 'rgba(0, 0, 0, 0.1)';
    paginationDiv.style.borderRadius = '4px';
    
    // 显示页数信息
    const infoDiv = document.createElement('div');
    infoDiv.textContent = `第 ${pagination.page}/${pagination.total_pages} 页，共 ${pagination.total} 条结果`;
    infoDiv.style.color = '#aaa';
    paginationDiv.appendChild(infoDiv);
    
    // 添加页面导航按钮
    const navDiv = document.createElement('div');
    navDiv.style.display = 'flex';
    navDiv.style.gap = '10px';
    
    // 上一页按钮
    const prevBtn = document.createElement('button');
    prevBtn.textContent = '上一页';
    prevBtn.className = 'control-button';
    prevBtn.style.padding = '5px 10px';
    prevBtn.style.fontSize = '12px';
    prevBtn.disabled = pagination.page <= 1;
    prevBtn.style.opacity = pagination.page <= 1 ? '0.5' : '1';
    prevBtn.style.cursor = pagination.page <= 1 ? 'not-allowed' : 'pointer';
    
    prevBtn.addEventListener('click', () => {
        if (pagination.page > 1) {
            searchParams.page = pagination.page - 1;
            queryDetectionResults();
        }
    });
    
    // 下一页按钮
    const nextBtn = document.createElement('button');
    nextBtn.textContent = '下一页';
    nextBtn.className = 'control-button';
    nextBtn.style.padding = '5px 10px';
    nextBtn.style.fontSize = '12px';
    nextBtn.disabled = pagination.page >= pagination.total_pages;
    nextBtn.style.opacity = pagination.page >= pagination.total_pages ? '0.5' : '1';
    nextBtn.style.cursor = pagination.page >= pagination.total_pages ? 'not-allowed' : 'pointer';
    
    nextBtn.addEventListener('click', () => {
        if (pagination.page < pagination.total_pages) {
            searchParams.page = pagination.page + 1;
            queryDetectionResults();
        }
    });
    
    navDiv.appendChild(prevBtn);
    navDiv.appendChild(nextBtn);
    paginationDiv.appendChild(navDiv);
    
    // 添加到缩略图容器后面
    const screenshotsList = document.getElementById('screenshotsList');
    if (screenshotsList) {
        screenshotsList.appendChild(paginationDiv);
    }
}

/**
 * 显示检测结果详情
 */
function showDetectionDetail(resultId) {
    // 显示加载状态
    const screenshotInfo = document.getElementById('screenshotInfo');
    if (screenshotInfo) {
        screenshotInfo.innerHTML = '<div style="color: #aaa;">加载详情中...</div>';
    }
    
    fetch(`/api/detection/detail/${resultId}`)
        .then(response => response.json())
        .then(data => {
            if (data.code === 0 && data.data) {
                displayDetailedResult(data.data);
            } else {
                console.error('获取检测详情失败:', data.message || '未知错误');
                if (screenshotInfo) {
                    screenshotInfo.innerHTML = `<div style="color: #f44336;">获取详情失败: ${data.message || '未知错误'}</div>`;
                }
            }
        })
        .catch(error => {
            console.error('获取检测详情错误:', error);
            if (screenshotInfo) {
                screenshotInfo.innerHTML = `<div style="color: #f44336;">获取详情出错: ${error.message}</div>`;
            }
        });
}

/**
 * 显示详细检测结果
 */
function displayDetailedResult(result) {
    currentDetailedResult = result;
    
    // 设置大图
    const screenshotImage = document.getElementById('screenshotImage');
    if (screenshotImage) {
        if (result.image_path) {
            screenshotImage.src = result.image_path;
            screenshotImage.style.display = 'block';
            
            // 图像加载完成后绘制检测框
            screenshotImage.onload = function() {
                drawDetectionBoxes(result);
            };
        } else {
            screenshotImage.style.display = 'none';
        }
    }
    
    // 设置信息
    const screenshotInfo = document.getElementById('screenshotInfo');
    if (screenshotInfo) {
        const timestamp = new Date(result.timestamp).toLocaleString();
        
        // 将检测对象按类别分组
        const objectsByClass = {};
        if (result.objects && result.objects.length > 0) {
            result.objects.forEach(obj => {
                if (!objectsByClass[obj.class_name]) {
                    objectsByClass[obj.class_name] = 0;
                }
                objectsByClass[obj.class_name]++;
            });
        }
        
        // 生成类别统计
        let classStats = '';
        for (const className in objectsByClass) {
            classStats += `<span style="margin-right: 10px;">${className}: ${objectsByClass[className]}</span>`;
        }
        
        // 显示导航信息（当前第几张/共几张）
        const navigationInfo = currentResults.length > 0 
            ? `<div style="margin-bottom: 5px; text-align: center;">第 ${currentResultIndex + 1} 张，共 ${currentResults.length} 张</div>` 
            : '';
        
        screenshotInfo.innerHTML = `
            ${navigationInfo}
            <div style="background: rgba(0,0,0,0.3); padding: 10px; border-radius: 4px; margin-bottom: 10px;">
                <div><strong>视频ID:</strong> ${result.video_id}</div>
                <div><strong>时间:</strong> ${timestamp}</div>
                <div><strong>检测结果:</strong> ${result.detection_count}个对象</div>
                <div><strong>目标类别:</strong> ${classStats || '无'}</div>
            </div>
        `;
    }
}

/**
 * 在画布上绘制检测框
 */
function drawDetectionBoxes(result) {
    if (!canvasCtx || !result.objects || !result.objects.length) return;
    
    const img = document.getElementById('screenshotImage');
    if (!img) return;
    
    // 调整画布大小与图像一致
    annotationCanvas.width = img.clientWidth;
    annotationCanvas.height = img.clientHeight;
    
    // 清除画布
    clearCanvas();
    
    // 计算缩放比例
    const scaleX = annotationCanvas.width / img.naturalWidth;
    const scaleY = annotationCanvas.height / img.naturalHeight;
    
    // 绘制每个检测框
    result.objects.forEach(obj => {
        // 获取边界框坐标
        const x = obj.bbox.x * scaleX;
        const y = obj.bbox.y * scaleY;
        const width = obj.bbox.width * scaleX;
        const height = obj.bbox.height * scaleY;
        
        // 设置框颜色
        canvasCtx.strokeStyle = obj.detection_type === 'primary' ? '#00FF00' : '#FF0000';
        canvasCtx.lineWidth = 2;
        
        // 绘制边界框
        canvasCtx.strokeRect(x, y, width, height);
        
        // 绘制标签
        canvasCtx.fillStyle = obj.detection_type === 'primary' ? 'rgba(0, 255, 0, 0.7)' : 'rgba(255, 0, 0, 0.7)';
        canvasCtx.font = '12px Arial';
        
        const label = `${obj.class_name} (${Math.round(obj.confidence * 100)}%)`;
        const labelWidth = canvasCtx.measureText(label).width;
        
        canvasCtx.fillRect(x, y - 20, labelWidth + 10, 20);
        canvasCtx.fillStyle = '#FFFFFF';
        canvasCtx.fillText(label, x + 5, y - 5);
    });
}

/**
 * 清除画布
 */
function clearCanvas() {
    if (canvasCtx) {
        canvasCtx.clearRect(0, 0, annotationCanvas.width, annotationCanvas.height);
    }
}

/**
 * 加载检测统计数据
 */
function loadDetectionStats() {
    fetch('/api/detection/stats?days=7')
        .then(response => response.json())
        .then(data => {
            if (data.code === 0 && data.data) {
                // 显示统计信息
                const statsContainer = document.getElementById('statsChartContainer');
                if (!statsContainer) return;
                
                let statsHtml = '<div style="color: white; padding: 10px; height: 100%;">';
                
                // 显示类别统计
                if (data.data.class_stats && data.data.class_stats.length > 0) {
                    statsHtml += '<h4 style="margin-top: 0;">检测类别TOP5:</h4><ul style="padding-left: 20px;">';
                    const topClasses = data.data.class_stats.slice(0, 5);
                    topClasses.forEach(item => {
                        statsHtml += `<li>${item.class_name}: ${item.object_count}个</li>`;
                    });
                    statsHtml += '</ul>';
                } else {
                    statsHtml += '<p>暂无类别统计数据</p>';
                }
                
                // 显示日期统计
                if (data.data.date_stats && data.data.date_stats.length > 0) {
                    statsHtml += '<h4>最近检测趋势:</h4>';
                    statsHtml += '<div style="display: flex; align-items: flex-end; height: 60px; gap: 3px;">';
                    
                    // 找出最大值用于归一化
                    const maxCount = Math.max(...data.data.date_stats.map(d => d.detection_count));
                    
                    data.data.date_stats.forEach(day => {
                        const height = Math.max(10, (day.detection_count / maxCount) * 60);
                        const date = new Date(day.detection_date).toLocaleDateString();
                        statsHtml += `
                            <div style="flex: 1; display: flex; flex-direction: column; align-items: center;">
                                <div style="height: ${height}px; width: 80%; background-color: #1890ff; border-radius: 2px 2px 0 0;" 
                                     title="${date}: ${day.detection_count}次检测"></div>
                                <div style="font-size: 10px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; width: 100%; text-align: center;">
                                    ${date.split('/').pop()}
                                </div>
                            </div>
                        `;
                    });
                    
                    statsHtml += '</div>';
                }
                
                statsHtml += '</div>';
                statsContainer.innerHTML = statsHtml;
            }
        })
        .catch(error => console.error('加载统计数据错误:', error));
}

/**
 * 添加图像导航功能
 */
function addImageNavigation() {
    // 获取导航区域
    const navArea = document.querySelector('.screenshot-navigation');
    if (!navArea) return;
    
    // 创建图像导航容器
    const navContainer = document.createElement('div');
    navContainer.className = 'image-navigation-container';
    navContainer.style.display = 'flex';
    navContainer.style.flexDirection = 'column';
    navContainer.style.alignItems = 'center';
    navContainer.style.width = '100%';
    navContainer.style.marginTop = '10px';
    navContainer.style.padding = '10px';
    navContainer.style.backgroundColor = 'rgba(0, 0, 0, 0.1)';
    navContainer.style.borderRadius = '4px';
    
    // 创建图像计数器
    const imageCounter = document.createElement('div');
    imageCounter.id = 'imageCounter';
    imageCounter.style.fontSize = '14px';
    imageCounter.style.fontWeight = 'bold';
    imageCounter.style.marginBottom = '8px';
    imageCounter.textContent = '浏览图片: 0/0';
    
    // 创建前一张/后一张按钮组
    const navButtons = document.createElement('div');
    navButtons.className = 'image-navigation-buttons';
    navButtons.style.display = 'flex';
    navButtons.style.gap = '15px';
    navButtons.style.width = '100%';
    navButtons.style.justifyContent = 'center';
    
    // 前一张按钮
    const prevButton = document.createElement('button');
    prevButton.innerHTML = '⬅️ 上一张';
    prevButton.className = 'nav-button prev-button';
    prevButton.style.padding = '8px 15px';
    prevButton.style.backgroundColor = '#1890ff';
    prevButton.style.border = 'none';
    prevButton.style.borderRadius = '4px';
    prevButton.style.color = 'white';
    prevButton.style.cursor = 'pointer';
    prevButton.style.fontWeight = 'bold';
    prevButton.style.minWidth = '100px';
    prevButton.style.boxShadow = '0 2px 4px rgba(0, 0, 0, 0.2)';
    prevButton.style.transition = 'all 0.2s';
    
    // 后一张按钮
    const nextButton = document.createElement('button');
    nextButton.innerHTML = '下一张 ➡️';
    nextButton.className = 'nav-button next-button';
    nextButton.style.padding = '8px 15px';
    nextButton.style.backgroundColor = '#1890ff';
    nextButton.style.border = 'none';
    nextButton.style.borderRadius = '4px';
    nextButton.style.color = 'white';
    nextButton.style.cursor = 'pointer';
    nextButton.style.fontWeight = 'bold';
    nextButton.style.minWidth = '100px';
    nextButton.style.boxShadow = '0 2px 4px rgba(0, 0, 0, 0.2)';
    nextButton.style.transition = 'all 0.2s';
    
    // 悬停效果
    prevButton.onmouseover = function() { 
        this.style.backgroundColor = '#40a9ff'; 
        this.style.boxShadow = '0 4px 8px rgba(0, 0, 0, 0.3)';
    };
    prevButton.onmouseout = function() { 
        this.style.backgroundColor = '#1890ff'; 
        this.style.boxShadow = '0 2px 4px rgba(0, 0, 0, 0.2)';
    };
    
    nextButton.onmouseover = function() { 
        this.style.backgroundColor = '#40a9ff'; 
        this.style.boxShadow = '0 4px 8px rgba(0, 0, 0, 0.3)';
    };
    nextButton.onmouseout = function() { 
        this.style.backgroundColor = '#1890ff'; 
        this.style.boxShadow = '0 2px 4px rgba(0, 0, 0, 0.2)';
    };
    
    // 添加点击事件
    prevButton.addEventListener('click', showPreviousImage);
    nextButton.addEventListener('click', showNextImage);
    
    // 添加按键提示
    const keyboardHint = document.createElement('div');
    keyboardHint.style.fontSize = '12px';
    keyboardHint.style.color = '#999';
    keyboardHint.style.marginTop = '8px';
    keyboardHint.textContent = '键盘快捷键: ← 上一张 | → 下一张';
    
    // 组装到导航区域
    navButtons.appendChild(prevButton);
    navButtons.appendChild(nextButton);
    navContainer.appendChild(imageCounter);
    navContainer.appendChild(navButtons);
    navContainer.appendChild(keyboardHint);
    navArea.appendChild(navContainer);
}

/**
 * 更新图片计数器
 */
function updateImageCounter() {
    const counter = document.getElementById('imageCounter');
    if (counter && currentResults.length > 0) {
        counter.textContent = `浏览图片: ${currentResultIndex + 1}/${currentResults.length}`;
    } else if (counter) {
        counter.textContent = '浏览图片: 0/0';
    }
}

/**
 * 显示前一张图片
 */
function showPreviousImage() {
    if (currentResults.length === 0) return;
    
    // 更新索引和UI按钮状态
    currentResultIndex = Math.max(0, currentResultIndex - 1);
    updateNavigationButtons();
    selectResultByIndex(currentResultIndex);
}

/**
 * 显示后一张图片
 */
function showNextImage() {
    if (currentResults.length === 0) return;
    
    // 更新索引和UI按钮状态
    currentResultIndex = Math.min(currentResults.length - 1, currentResultIndex + 1);
    updateNavigationButtons();
    selectResultByIndex(currentResultIndex);
}

/**
 * 更新导航按钮状态
 */
function updateNavigationButtons() {
    const prevButton = document.querySelector('.prev-button');
    const nextButton = document.querySelector('.next-button');
    
    if (prevButton) {
        prevButton.disabled = currentResultIndex <= 0;
        prevButton.style.opacity = currentResultIndex <= 0 ? '0.5' : '1';
        prevButton.style.cursor = currentResultIndex <= 0 ? 'not-allowed' : 'pointer';
    }
    
    if (nextButton) {
        nextButton.disabled = currentResultIndex >= currentResults.length - 1;
        nextButton.style.opacity = currentResultIndex >= currentResults.length - 1 ? '0.5' : '1';
        nextButton.style.cursor = currentResultIndex >= currentResults.length - 1 ? 'not-allowed' : 'pointer';
    }
    
    // 更新计数器
    updateImageCounter();
}

/**
 * 根据索引选择结果
 */
function selectResultByIndex(index) {
    if (index < 0 || index >= currentResults.length) return;
    
    // 更新当前索引
    currentResultIndex = index;
    
    // 获取当前结果
    const result = currentResults[index];
    
    // 高亮对应的缩略图
    const thumbnails = document.querySelectorAll('.screenshot-thumbnail');
    thumbnails.forEach((thumbnail, i) => {
        const isSelected = i === index;
        thumbnail.style.borderColor = isSelected ? '#1890ff' : 'transparent';
        thumbnail.style.transform = isSelected ? 'scale(1.03)' : 'none';
        thumbnail.style.boxShadow = isSelected ? '0 0 5px rgba(24, 144, 255, 0.5)' : 'none';
    });
    
    // 显示详情
    showDetectionDetail(result.result_id);
    
    // 滚动到对应的缩略图
    const selectedThumbnail = thumbnails[index];
    if (selectedThumbnail) {
        selectedThumbnail.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
    
    // 更新导航按钮状态
    updateNavigationButtons();
}

// 当DOM加载完成时初始化
document.addEventListener('DOMContentLoaded', function() {
    // 检测是否在检测结果页面
    if (document.getElementById('detectionResultView')) {
        initDetectionResults();
    }
}); 