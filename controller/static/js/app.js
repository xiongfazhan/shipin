/**
 * 智能视频分析系统主应用模块
 * 负责初始化并协调各个功能模块
 */

// 全局变量共享
// window.targetUrl = ''; // 被控端URL，在新系统中可能用于连接YOLO服务或其他外部服务。此变量在旧系统中由 remote-control.js 或其他模块管理，现在需要按需定义和管理。
let currentView = 'data_import_config'; // 当前活动的视图
let currentConfirmAction = null; // 当前确认操作的回调

// 在文档加载完成后初始化应用
document.addEventListener('DOMContentLoaded', function() {
  initApp();
});

/**
 * 应用初始化
 */
function initApp() {
  try {
    console.log('开始初始化智能视频分析系统...');
    
    const styleSheets = document.styleSheets;
    console.log(`加载了 ${styleSheets.length} 个CSS文件`);
    
    // 设置初始界面状态
    console.log('设置初始界面状态...');
    switchView(currentView); 
    
    // 初始化检测结果管理模块 (screenshot.js 可能会被改造用于此目的)
    console.log('初始化检测结果管理模块 (依赖 screenshot.js 改造)...');
    if (typeof initScreenshotManager === 'function') {
      // initScreenshotManager(); // 需要适配新的 detectionResultView 和功能
      console.log('initScreenshotManager 调用被注释，待 screenshot.js 改造后启用并适配。');
    } else {
      console.warn('initScreenshotManager 函数未定义 (可能 screenshot.js 未加载或未包含此函数)');
    }
        
    console.log('设置界面切换事件...');
    setupViewSwitching();
    
    console.log('设置图像/画布调整事件 (依赖 screenshot.js 改造)...');
    if (typeof handleImageResize === 'function') {
        // handleImageResize(); // 需要适配新的 detectionResultView 和 canvas用途
        console.log('handleImageResize 调用被注释，待 screenshot.js 改造后启用并适配。');
    } else {
        // 如果 screenshot.js 被移除或不再定义此函数，则需要一个新实现
        // setupDynamicCanvasResizing(); // 示例：新的Canvas调整函数
        console.warn('handleImageResize 函数未定义。如果需要Canvas动态调整，请确保相关JS已加载或实现此功能。');
    }

    const uploadBtn = document.getElementById('uploadExcelBtn');
    if (uploadBtn) {
      uploadBtn.addEventListener('click', () => {
        handleExcelUpload(); 
      });
    }

    const queryBtn = document.getElementById('queryResultsBtn');
    if (queryBtn) {
      queryBtn.addEventListener('click', () => {
        alert('查询检测结果功能待实现');
        // handleQueryDetectionResults();
      });
    }
    
    // 清理旧的模态框相关事件绑定 (如果它们依赖已移除的JS)
    const commandModal = document.getElementById('commandModal');
    if(commandModal) {
        const closeCmdModalBtn = commandModal.querySelector('.close');
        if(closeCmdModalBtn && typeof closeCommandModal === 'undefined') { 
            console.warn("commandModal 的关闭按钮可能存在未定义的事件处理器。");
        }
        const execCmdBtn = commandModal.querySelector('button');
        if(execCmdBtn && typeof executeModalCommand === 'undefined') { 
            console.warn("commandModal 的执行按钮可能存在未定义的事件处理器。");
        }
        const modalCmdInput = document.getElementById('modalCmdInput');
        if(modalCmdInput && typeof handleModalCmdKeyPress === 'undefined'){
            console.warn("commandModal 的输入框可能存在未定义的事件处理器。");
        }
    }
    const labelDialog = document.getElementById('labelDialog');
    if(labelDialog){
        const confirmLabelBtn = labelDialog.querySelector('button[onclick="confirmLabel()"]');
        if(confirmLabelBtn && typeof confirmLabel === 'undefined'){ 
            console.warn("labelDialog 的确认按钮可能存在未定义的事件处理器 (confirmLabel)。");
        }
        const cancelLabelBtn = labelDialog.querySelector('button[onclick="cancelLabel()"]');
        if(cancelLabelBtn && typeof cancelLabel === 'undefined'){ 
            console.warn("labelDialog 的取消按钮可能存在未定义的事件处理器 (cancelLabel)。");
        }
    }

    // 初始化确认对话框
    initConfirmDialog();

    // Setup tab functionality
    setupTabs();

    console.log('智能视频分析系统初始化完成');
  } catch (error) {
    console.error('初始化过程出现错误:', error);
    alert('系统初始化出错: ' + error.message);
  }
}

/**
 * 初始化确认对话框
 */
function initConfirmDialog() {
  const confirmDialog = document.getElementById('confirmDialog');
  const confirmBtn = document.getElementById('confirmDialogOK');
  const cancelBtn = document.getElementById('confirmDialogCancel');
  
  // 点击确认按钮
  confirmBtn.addEventListener('click', function() {
    if (currentConfirmAction) {
      currentConfirmAction(); // 执行确认回调
    }
    confirmDialog.style.display = 'none';
  });
  
  // 点击取消按钮
  cancelBtn.addEventListener('click', function() {
    confirmDialog.style.display = 'none';
  });
  
  // 点击对话框外部关闭
  confirmDialog.addEventListener('click', function(e) {
    if (e.target === confirmDialog) {
      confirmDialog.style.display = 'none';
    }
  });
}

/**
 * 显示确认对话框
 * @param {string} title - 对话框标题
 * @param {string} message - 对话框消息
 * @param {Function} callback - 确认后的回调函数
 */
function showConfirmDialog(title, message, callback) {
  const confirmDialog = document.getElementById('confirmDialog');
  const titleEl = document.getElementById('confirmDialogTitle');
  const messageEl = document.getElementById('confirmDialogMessage');
  
  titleEl.textContent = title;
  messageEl.textContent = message;
  currentConfirmAction = callback;
  
  confirmDialog.style.display = 'block';
}

/**
 * 设置视图切换功能
 */
function setupViewSwitching() {
  const buttons = document.querySelectorAll('.nav-button');
  
  buttons.forEach(button => {
    button.addEventListener('click', function() {
      const viewType = this.getAttribute('data-view');
      if (viewType && viewType !== currentView) { 
      switchView(viewType);
      }
    });
  });
}

/**
 * 切换视图
 * @param {string} type - 'data_import_config' 或 'detection_results'
 */
function switchView(type) {
  // 如果切换到检测结果视图，重定向到独立的检测结果页面
  if (type === 'detection_results') {
    window.location.href = '/detection_results';
    return;
  }
  
  currentView = type;
  console.log(`切换到视图: ${type}`);

  const buttons = document.querySelectorAll('.nav-button');
  buttons.forEach(btn => {
    btn.classList.toggle('active', btn.getAttribute('data-view') === type);
  });

  const detectionResultView = document.getElementById('detectionResultView');
  const dataImportConfigControls = document.getElementById('dataImportConfigControls');
  const detectionResultControls = document.getElementById('detectionResultControls');

  if (detectionResultView) {
      detectionResultView.style.display = (type === 'detection_results') ? 'flex' : 'none';
  }
  
  if (dataImportConfigControls) {
    dataImportConfigControls.style.display = (type === 'data_import_config') ? 'flex' : 'none';
  }
  if (detectionResultControls) {
    detectionResultControls.style.display = (type === 'detection_results') ? 'flex' : 'none';
  }

  if (type === 'detection_results') {
    console.log('进入检测结果视图，准备加载结果...');
    
    if (typeof loadScreenshots === 'function') { 
        console.log("检测结果图像列表加载功能 (原loadScreenshots) 待适配");
    }

    const annotationCanvas = document.getElementById('annotationCanvas');
      const screenshotImage = document.getElementById('screenshotImage');

    if (annotationCanvas && screenshotImage) {
        if (screenshotImage.complete && screenshotImage.naturalWidth > 0) {
             console.log("检测结果Canvas初始化待适配");
        } else {
            screenshotImage.onload = () => {
                console.log("检测结果Canvas初始化待适配 (图片加载后)");
            };
        }
    }
  } else if (type === 'data_import_config') {
    console.log('进入数据导入与配置视图...');
    loadVideoStreamsList(); // 加载视频流列表
  }
}


function handleExcelUpload() {
    const excelFileInput = document.getElementById('excelFile');
    const uploadBtn = document.getElementById('uploadExcelBtn');
    const originalBtnText = uploadBtn ? uploadBtn.textContent : '上传并导入';
    const statusDiv = document.getElementById('excelUploadStatus');

    if (statusDiv) statusDiv.style.display = 'none'; // Hide previous messages

    if (!excelFileInput || !excelFileInput.files || excelFileInput.files.length === 0) {
        if (statusDiv) {
            statusDiv.innerHTML = '<div style="color: var(--warning-color);">请先选择一个Excel文件！</div>';
            statusDiv.style.display = 'block';
        } else {
            alert('请先选择一个Excel文件！');
        }
        return;
    }
    const file = excelFileInput.files[0];
    const formData = new FormData();
    formData.append('excel_file', file);

    if (statusDiv) {
        statusDiv.innerHTML = '<div style="color: var(--text-color);">正在上传并处理Excel文件...</div>';
        statusDiv.style.display = 'block';
    }
    
    if(uploadBtn) {
        uploadBtn.disabled = true;
        uploadBtn.textContent = '上传中...';
    }

    fetch('/api/videos/import_excel', { 
        method: 'POST',
        body: formData,
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(errData => {
                throw new Error(errData.message || `服务器错误: ${response.status}`);
            }).catch(() => {
                throw new Error(`服务器错误: ${response.status}`);
            });
        }
        return response.json();
    })
    .then(data => {
        console.log('上传响应:', data);
        let messageHtml = '';
        const importedCount = data.data?.imported_count || 0;
        const failedRowCount = data.data?.failed_row_count || 0; // Assuming this field exists for skipped/failed
        
        messageHtml = `<div style="color: var(--success-color);">Excel文件处理完成！ (导入 ${importedCount} 条，失败/跳过 ${failedRowCount} 条)</div>`;
        
        if (data.data && data.data.errors && data.data.errors.length > 0) {
            console.warn('导入过程中发生错误:', data.data.errors);
            messageHtml += '<div style="margin-top:10px; color: var(--warning-color);"><strong>以下行导入失败:</strong><ul>';
            data.data.errors.forEach(err => {
                messageHtml += `<li>行 ${err.row} (ID: ${err.video_id || 'N/A'}): ${err.messages.join(', ')}</li>`;
            });
            messageHtml += '</ul></div>';
        }
        
        if (statusDiv) {
            statusDiv.innerHTML = messageHtml;
            statusDiv.style.display = 'block';
        } else {
            alert(data.message || 'Excel文件处理完成！'); // Fallback
        }
        
        if (data.code === 0 || importedCount > 0) {
            loadVideoStreamsList(); // 刷新视频流列表
        }
    })
    .catch(error => {
        console.error('上传Excel文件失败:', error);
        if (statusDiv) {
            statusDiv.innerHTML = `<div style="color: var(--error-color);">导入失败: ${error.message}</div>`;
            statusDiv.style.display = 'block';
        } else {
            alert(`导入失败: ${error.message}`); // Fallback
        }
    })
    .finally(() => {
        if(uploadBtn) {
            uploadBtn.disabled = false;
            uploadBtn.textContent = originalBtnText;
        }
        excelFileInput.value = ''; // 清空文件选择，以便用户可以重新选择相同文件
    });
}

//移除了 handleImageResize，因为其依赖的 screenshot.js 中的 redrawCanvas 等函数可能已不适用或被移除。
// 如果需要Canvas动态调整，应结合新的Canvas绘制逻辑重新实现。
// function handleImageResize() { ... }

// 示例：后续阶段将实现的函数
// function handleQueryDetectionResults() { ... }
// function loadDetectionResults() { ... }
function loadVideoStreamsList() {
    console.log("loadVideoStreamsList: 开始加载视频流列表...");
    const listContainer = document.getElementById('videoStreamListContainer');
    if (!listContainer) {
        console.warn('视频流列表容器未找到 (videoStreamListContainer)');
        return;
    }

    listContainer.innerHTML = '<p style="color: #aaa;">正在加载视频流数据...</p>'; // 加载提示

    fetch('/api/video_streams')
        .then(response => {
            if (!response.ok) {
                throw new Error(`获取视频流失败: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.code === 0) {
                if (data.data && data.data.length > 0) {
                    listContainer.innerHTML = ''; // 清空加载提示
                    const ul = document.createElement('ul');
                    ul.style.listStyleType = 'none';
                    ul.style.padding = '0';
                    data.data.forEach(stream => {
                        const li = document.createElement('li');
                        li.style.padding = '8px';
                        li.style.borderBottom = '1px solid #1e3a5f';
                        li.style.color = 'white';
                        
                        // 创建信息部分
                        const infoDiv = document.createElement('div');
                        const statusIndicator = `<span style="display: inline-block; width: 10px; height: 10px; border-radius: 50%; background-color: ${stream.is_active ? 'var(--success-color)' : 'var(--border-color)'}; margin-right: 8px; vertical-align: middle;"></span>`;
                        const activeStatusText = stream.is_active ? `<span style="color:var(--success-color);">活动</span>` : `<span style="color:var(--warning-color);">暂停</span>`;
                        
                        let detailsHtml = `<p class="stream-param"><strong>ID:</strong> ${stream.video_id}</p>`;
                        detailsHtml += `<p class="stream-param"><strong>URL:</strong> <span class="long-text">${stream.stream_url || 'N/A'}</span></p>`;
                        detailsHtml += `<p class="stream-param"><strong>风险等级:</strong> ${stream.level || 'N/A'}</p>`; // Assuming stream.level is Risk Level
                        detailsHtml += `<p class="stream-param"><strong>状态:</strong> ${statusIndicator} ${activeStatusText}</p>`;
                        
                        // New optional parameters
                        detailsHtml += `<p class="stream-param"><strong>抽帧间隔:</strong> ${stream.frame_extraction_interval !== undefined && stream.frame_extraction_interval !== null ? stream.frame_extraction_interval + 's' : 'N/A'}</p>`;
                        detailsHtml += `<p class="stream-param"><strong>最大帧数:</strong> ${stream.max_frames_to_process || 'N/A'}</p>`;
                        detailsHtml += `<p class="stream-param"><strong>YOLO模型:</strong> <span class="long-text">${stream.yolo_model_name || 'N/A'}</span></p>`;
                        detailsHtml += `<p class="stream-param"><strong>置信度阈值:</strong> ${stream.detection_confidence_threshold || 'N/A'}</p>`;
                        detailsHtml += `<p class="stream-param"><strong>结果推送URL:</strong> <span class="long-text">${stream.result_destination_url || 'N/A'}</span></p>`;
                        
                        if (stream.remarks) {
                            detailsHtml += `<p class="stream-param"><strong>备注:</strong> <span class="long-text">${stream.remarks}</span></p>`;
                        }
                        
                        infoDiv.innerHTML = detailsHtml;
                        
                        // 创建操作按钮部分
                        const actionDiv = document.createElement('div');
                        actionDiv.style.marginTop = '8px';
                        actionDiv.style.display = 'flex';
                        actionDiv.style.gap = '8px';
                        
                        // 激活/停用按钮
                        const toggleBtn = document.createElement('button');
                        toggleBtn.className = 'control-button';
                        toggleBtn.style.padding = '4px 8px';
                        toggleBtn.style.fontSize = '12px';
                        toggleBtn.style.backgroundColor = stream.is_active ? '#ff9800' : '#4caf50';
                        toggleBtn.textContent = stream.is_active ? '停用' : '激活';
                        toggleBtn.onclick = () => toggleVideoStreamStatus(stream.video_id, !stream.is_active);
                        
                        // 删除按钮
                        const deleteBtn = document.createElement('button');
                        deleteBtn.className = 'control-button';
                        deleteBtn.style.padding = '4px 8px';
                        deleteBtn.style.fontSize = '12px';
                        deleteBtn.style.backgroundColor = '#f44336';
                        deleteBtn.textContent = '删除';
                        deleteBtn.onclick = () => deleteVideoStream(stream.video_id);
                        
                        actionDiv.appendChild(toggleBtn);
                        actionDiv.appendChild(deleteBtn);
                        
                        li.appendChild(infoDiv);
                        li.appendChild(actionDiv);
                        ul.appendChild(li);
                    });
                    listContainer.appendChild(ul);
                } else {
                    listContainer.innerHTML = '<p style="color: #aaa;">暂无视频流数据。</p>';
                }
            } else {
                listContainer.innerHTML = `<p style="color: #ff4d4f;">加载视频流失败: ${data.message}</p>`;
            }
        })
        .catch(error => {
            console.error('加载视频流列表错误:', error);
            listContainer.innerHTML = `<p style="color: #ff4d4f;">加载视频流时出错: ${error.message}</p>`;
        });
}

/**
 * 切换视频流的激活状态
 * @param {string} videoId - 视频ID
 * @param {boolean} newStatus - 新状态：true为激活，false为停用
 */
function toggleVideoStreamStatus(videoId, newStatus) {
    const action = newStatus ? '激活' : '停用';
    showConfirmDialog(
        `确认${action}`,
        `您确定要${action}视频流 ${videoId} 吗？`,
        () => {
            fetch(`/api/video_streams/${videoId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ is_active: newStatus }),
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`操作失败: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.code === 0) {
                    alert(`已${action}视频流 ${videoId}`);
                    loadVideoStreamsList(); // 刷新列表
                } else {
                    alert(`操作失败: ${data.message}`);
                }
            })
            .catch(error => {
                console.error(`${action}视频流失败:`, error);
                alert(`${action}失败: ${error.message}`);
            });
        }
    );
}

/**
 * 删除视频流
 * @param {string} videoId - 视频ID
 */
function deleteVideoStream(videoId) {
    showConfirmDialog(
        '确认删除',
        `您确定要删除视频流 ${videoId} 吗？此操作不可撤销。`,
        () => {
            fetch(`/api/video_streams/${videoId}`, {
                method: 'DELETE',
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`删除失败: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.code === 0) {
                    alert(`已删除视频流 ${videoId}`);
                    loadVideoStreamsList(); // 刷新列表
                } else {
                    alert(`删除失败: ${data.message}`);
                }
            })
            .catch(error => {
                console.error('删除视频流失败:', error);
                alert(`删除失败: ${error.message}`);
            });
        }
    );
}

// 移除了 initChatFeature 和 sendMessage 函数，因为 chat.js 已被移除
// function initChatFeature() { ... }
// function sendMessage() { ... }

function setupTabs() {
    const tabLinks = document.querySelectorAll('.tab-link');
    // Ensure tabContents are queried within the correct scope if necessary, 
    // for now, assuming they are globally unique or within dataImportConfigControls
    const tabContents = document.querySelectorAll('#dataImportConfigControls .tab-content');


    tabLinks.forEach(link => {
        link.addEventListener('click', function() {
            const tabId = this.dataset.tab;

            // Update active class for tab links
            tabLinks.forEach(innerLink => innerLink.classList.remove('active'));
            this.classList.add('active');

            // Show/hide tab content panes
            tabContents.forEach(content => {
                if (content.id === tabId) {
                    content.classList.add('active');
                } else {
                    content.classList.remove('active');
                }
            });
        });
    });
}

// Video upload function moved from index.html
function uploadAndProcessVideo() {
  const videoFile = document.getElementById('videoFile').files[0];
  if (!videoFile) {
    alert('请选择视频文件');
    return;
  }
  
  // 获取表单数据
  const formData = new FormData(document.getElementById('videoUploadForm'));
  
  // 显示状态
  const statusDiv = document.getElementById('videoProcessStatus');
  statusDiv.style.display = 'block';
  statusDiv.innerHTML = '<div style="color:var(--text-color);">正在上传视频文件，请稍候...</div>';
  
  // 禁用上传按钮
  const uploadBtn = document.getElementById('uploadVideoBtn');
  uploadBtn.disabled = true;
  uploadBtn.innerText = '上传中...';
  
  // 发送请求
  fetch('/api/videos/upload', {
    method: 'POST',
    body: formData
  })
  .then(response => {
    if (!response.ok) {
      return response.json().then(data => {
        throw new Error(data.message || '上传失败');
      });
    }
    return response.json();
  })
  .then(data => {
    console.log('上传成功:', data);
    statusDiv.innerHTML = `
      <div style="color:var(--success-color);">视频上传成功！</div>
      <div>视频ID: ${data.data.video_id}</div>
      <div>文件名: ${data.data.filename}</div>
      <div>任务ID: ${data.data.task_id}</div>
      <div style="margin-top:10px;">系统正在后台处理视频，完成后可在"检测结果查询"页面查看结果。</div>
    `;
    
    // 清空文件选择
    document.getElementById('videoFile').value = '';
  })
  .catch(error => {
    console.error('上传视频失败:', error);
    statusDiv.innerHTML = `<div style="color:var(--error-color);">上传失败: ${error.message}</div>`;
  })
  .finally(() => {
    // 恢复上传按钮
    uploadBtn.disabled = false;
    uploadBtn.innerText = '上传并处理视频';
  });
}
