/**
 * 系统调试工具函数
 */

// 在网页上显示一个诊断面板
function showDebugPanel() {
  // 创建调试面板
  const debugPanel = document.createElement('div');
  debugPanel.id = 'debug-panel';
  debugPanel.style.cssText = `
    position: fixed;
    bottom: 10px;
    right: 10px;
    background-color: rgba(0, 0, 0, 0.8);
    color: #00ff00;
    padding: 10px;
    border-radius: 5px;
    font-family: monospace;
    z-index: 9999;
    max-width: 500px;
    max-height: 300px;
    overflow: auto;
    font-size: 12px;
    border: 1px solid #1890ff;
  `;
  
  // 添加标题
  const title = document.createElement('h3');
  title.textContent = '系统诊断面板';
  title.style.cssText = `
    margin: 0 0 10px 0;
    color: #1890ff;
    border-bottom: 1px solid #1890ff;
    padding-bottom: 5px;
  `;
  debugPanel.appendChild(title);
  
  // 添加调试信息
  const info = document.createElement('div');
  info.id = 'debug-info';
  debugPanel.appendChild(info);
  
  // 添加关闭按钮
  const closeBtn = document.createElement('button');
  closeBtn.textContent = '关闭';
  closeBtn.style.cssText = `
    position: absolute;
    top: 5px;
    right: 5px;
    background: none;
    border: none;
    color: #fff;
    cursor: pointer;
  `;
  closeBtn.onclick = function() {
    document.body.removeChild(debugPanel);
  };
  debugPanel.appendChild(closeBtn);
  
  // 添加到页面
  document.body.appendChild(debugPanel);
  
  // 检查DOM结构
  checkDOMStructure();
  
  // 检查JavaScript变量
  checkJavaScriptState();
  
  // 检查CSS加载
  checkCSSLoading();
}

// 检查页面DOM结构
function checkDOMStructure() {
  const info = document.getElementById('debug-info');
  
  // 检查关键元素
  const criticalElements = [
    '#remoteControls',
    '#screenshotControls',
    '#targetUrl',
    '#screenshotBtn',
    '.function-grid',
    '.function-button',
    '.control-section'
  ];
  
  const results = [];
  criticalElements.forEach(selector => {
    const elements = document.querySelectorAll(selector);
    const status = elements.length > 0 ? 
      `<span style="color:#52c41a">✓ 找到 ${elements.length} 个元素</span>` : 
      `<span style="color:#ff4d4f">✗ 未找到元素</span>`;
    results.push(`<div>${selector}: ${status}</div>`);
    
    // 如果找到元素，检查其可见性
    if (elements.length > 0) {
      const visibleCount = Array.from(elements).filter(el => {
        const style = window.getComputedStyle(el);
        return style.display !== 'none' && style.visibility !== 'hidden';
      }).length;
      
      const visibilityStatus = visibleCount > 0 ? 
        `<span style="color:#52c41a">✓ ${visibleCount}/${elements.length} 个元素可见</span>` : 
        `<span style="color:#ff4d4f">✗ 所有元素不可见</span>`;
      
      results.push(`<div style="padding-left:15px;">${selector} 可见性: ${visibilityStatus}</div>`);
    }
  });
  
  // 检查控制面板显示状态
  const remoteControls = document.getElementById('remoteControls');
  if (remoteControls) {
    const hasActiveClass = remoteControls.classList.contains('active');
    const activeStatus = hasActiveClass ? 
      `<span style="color:#52c41a">✓ 控制面板有active类</span>` : 
      `<span style="color:#ff4d4f">✗ 控制面板没有active类</span>`;
    results.push(`<div>控制面板状态: ${activeStatus}</div>`);
  }
  
  info.innerHTML += `<div style="margin-bottom:10px;"><strong>DOM结构检查:</strong></div>`;
  info.innerHTML += results.join('');
}

// 检查JavaScript变量状态
function checkJavaScriptState() {
  const info = document.getElementById('debug-info');
  info.innerHTML += `<div style="margin:10px 0;"><strong>JavaScript状态检查:</strong></div>`;
  
  // 检查全局变量
  const targetUrlValue = window.targetUrl || '未设置';
  info.innerHTML += `<div>全局targetUrl: ${targetUrlValue}</div>`;
  
  // 检查功能初始化情况
  const initFunctions = [
    'initRemoteControl',
    'initCommandControl',
    'initScreenshotManager',
    'setupViewSwitching'
  ];
  
  initFunctions.forEach(funcName => {
    const exists = typeof window[funcName] === 'function';
    const status = exists ? 
      `<span style="color:#52c41a">✓ 函数已定义</span>` : 
      `<span style="color:#ff4d4f">✗ 函数未定义</span>`;
    info.innerHTML += `<div>${funcName}: ${status}</div>`;
  });
}

// 检查CSS加载状态
function checkCSSLoading() {
  const info = document.getElementById('debug-info');
  info.innerHTML += `<div style="margin:10px 0;"><strong>CSS加载检查:</strong></div>`;
  
  // 获取所有样式表
  const styleSheets = document.styleSheets;
  info.innerHTML += `<div>加载了 ${styleSheets.length} 个样式表:</div>`;
  
  // 列出所有样式表
  const cssFiles = [];
  for (let i = 0; i < styleSheets.length; i++) {
    try {
      const href = styleSheets[i].href || '内联样式';
      const rulesCount = styleSheets[i].cssRules ? styleSheets[i].cssRules.length : '无法访问';
      cssFiles.push(`<div style="padding-left:15px;">${href} (规则数: ${rulesCount})</div>`);
    } catch (e) {
      cssFiles.push(`<div style="padding-left:15px;">样式表 #${i}: 无法访问 (${e.message})</div>`);
    }
  }
  
  info.innerHTML += cssFiles.join('');
  
  // 检查关键样式类是否存在
  const criticalClasses = [
    '.control-section',
    '.function-grid',
    '.function-button',
    '.command-bar',
    '.control-title',
    '.robot-icon'
  ];
  
  info.innerHTML += `<div style="margin-top:10px;">关键CSS类检查:</div>`;
  
  criticalClasses.forEach(className => {
    let found = false;
    let source = '';
    
    // 尝试在所有样式表中查找这个类
    for (let i = 0; i < styleSheets.length; i++) {
      try {
        const rules = styleSheets[i].cssRules;
        if (!rules) continue;
        
        for (let j = 0; j < rules.length; j++) {
          if (rules[j].selectorText && rules[j].selectorText.includes(className)) {
            found = true;
            source = styleSheets[i].href || '内联样式';
            break;
          }
        }
        if (found) break;
      } catch (e) {
        // 跨域样式表可能无法访问规则
        continue;
      }
    }
    
    const status = found ? 
      `<span style="color:#52c41a">✓ 类已定义 (在 ${source})</span>` : 
      `<span style="color:#ff4d4f">✗ 类未找到</span>`;
    
    info.innerHTML += `<div style="padding-left:15px;">${className}: ${status}</div>`;
  });
}

// 为控制台添加debug命令
window.showDebug = function() {
  showDebugPanel();
};

// 在页面加载后添加调试按钮
document.addEventListener('DOMContentLoaded', function() {
  const debugBtn = document.createElement('button');
  debugBtn.textContent = '调试';
  debugBtn.style.cssText = `
    position: fixed;
    bottom: 10px;
    left: 10px;
    background-color: #1890ff;
    color: white;
    border: none;
    padding: 5px 10px;
    border-radius: 3px;
    cursor: pointer;
    z-index: 9999;
  `;
  debugBtn.onclick = showDebugPanel;
  document.body.appendChild(debugBtn);
  
  console.log('调试工具已加载，点击左下角"调试"按钮或在控制台执行window.showDebug()');
});
