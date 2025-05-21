/**
 * 数据库管理界面
 * 实现数据表的浏览、编辑、添加和删除功能
 */

// 全局变量
let currentTable = '';  // 当前选中的表
let currentSection = ''; // 当前选中的功能区域
let tableInfo = {};     // 表结构信息
let tableData = [];     // 表数据
let columnInfo = {};    // 列信息
let paginationInfo = {  // 分页信息
    page: 1,
    perPage: 20,
    total: 0,
    totalPages: 0
};
let currentRecord = null; // 当前编辑的记录
let primaryKeyColumn = ''; // 主键列名

/**
 * 初始化页面
 */
$(document).ready(function() {
    // 加载表列表
    loadTablesList();

    // 绑定侧边栏点击事件
    $('#dbSidebar').on('click', '.sidebar-item', function() {
        const item = $(this);
        
        // 高亮选中项
        $('.sidebar-item').removeClass('active');
        item.addClass('active');
        
        if (item.hasClass('table-item')) {
            // 切换到表数据视图
            currentTable = item.data('table');
            currentSection = 'table';
            loadTableData(currentTable);
        } else {
            // 切换到特殊功能区
            currentSection = item.data('section');
            
            switch(currentSection) {
                case 'sql':
                    showSqlQueryInterface();
                    break;
                case 'videos':
                    loadVideosManagement();
                    break;
                case 'detections':
                    loadDetectionsManagement();
                    break;
            }
        }
    });

    // 绑定保存记录按钮
    $('#saveRecord').on('click', function() {
        saveRecord();
    });
    
    // 绑定确认删除按钮
    $('#confirmDelete').on('click', function() {
        deleteRecord();
    });
});

/**
 * 加载数据库表列表
 */
function loadTablesList() {
    $.ajax({
        url: '/api/db/tables',
        method: 'GET',
        success: function(response) {
            if (response.code === 0) {
                const tables = response.data.tables;
                tableInfo = response.data.table_info;
                
                const tablesListHtml = tables.map(table => {
                    const recordCount = tableInfo[table].record_count;
                    return `
                        <div class="sidebar-item table-item" data-table="${table}">
                            <span>${table}</span>
                            <span class="badge-count">${recordCount}</span>
                        </div>
                    `;
                }).join('');
                
                $('.tables-list').html(tablesListHtml);
            } else {
                showError('加载表列表失败', response.message);
            }
        },
        error: function(xhr) {
            showError('加载表列表请求失败', xhr.statusText);
        }
    });
}

/**
 * 加载表数据
 */
function loadTableData(tableName, page = 1, perPage = 20) {
    $('#contentArea').html(`
        <div class="text-center p-5">
            <div class="spinner-border text-primary" role="status">
                <span class="sr-only">加载中...</span>
            </div>
            <p class="mt-3">正在加载表 ${tableName} 的数据...</p>
        </div>
    `);
    
    // 获取排序信息
    const sortBy = $('#sortColumn').val() || '';
    const sortOrder = $('#sortOrder').val() || 'asc';
    
    // 获取过滤信息
    const filterColumn = $('#filterColumn').val() || '';
    const filterValue = $('#filterValue').val() || '';
    
    $.ajax({
        url: `/api/db/table/${tableName}/data`,
        method: 'GET',
        data: {
            page: page,
            per_page: perPage,
            sort_by: sortBy,
            sort_order: sortOrder,
            filter_column: filterColumn,
            filter_value: filterValue
        },
        success: function(response) {
            if (response.code === 0) {
                // 更新全局变量
                tableData = response.data.records;
                paginationInfo = response.data.pagination;
                columnInfo = {};
                
                // 获取列信息
                const columns = response.data.columns;
                
                // 查找主键列
                primaryKeyColumn = '';
                if (tableInfo[tableName]) {
                    for (const col of tableInfo[tableName].columns) {
                        if (col.pk === 1) {
                            primaryKeyColumn = col.name;
                            break;
                        }
                        
                        // 保存列信息
                        columnInfo[col.name] = col;
                    }
                }
                
                // 创建表格视图
                displayTableData(tableName, columns, tableData, paginationInfo);
            } else {
                showError('加载表数据失败', response.message);
            }
        },
        error: function(xhr) {
            showError('加载表数据请求失败', xhr.statusText);
        }
    });
}

/**
 * 显示表格数据
 */
function displayTableData(tableName, columns, data, pagination) {
    // 创建表头和过滤器
    let tableHeaderHtml = `
        <div class="table-container">
            <div class="table-header">
                <h3>${tableName} <span class="badge badge-info">${pagination.total}条记录</span></h3>
                <div>
                    <button class="btn btn-sm btn-primary" onclick="showAddRecordForm('${tableName}')">添加记录</button>
                    <button class="btn btn-sm btn-secondary" onclick="refreshTable()">刷新</button>
                </div>
            </div>
            
            <div class="action-buttons">
                <form class="form-inline" onsubmit="return false;">
                    <div class="form-group">
                        <select id="filterColumn" class="form-control form-control-sm">
                            <option value="">选择过滤列</option>
                            ${columns.map(column => `<option value="${column}">${column}</option>`).join('')}
                        </select>
                    </div>
                    <div class="form-group">
                        <input type="text" id="filterValue" class="form-control form-control-sm" placeholder="过滤值">
                    </div>
                    <div class="form-group">
                        <select id="sortColumn" class="form-control form-control-sm">
                            <option value="">默认排序</option>
                            ${columns.map(column => `<option value="${column}">${column}</option>`).join('')}
                        </select>
                    </div>
                    <div class="form-group">
                        <select id="sortOrder" class="form-control form-control-sm">
                            <option value="asc">升序</option>
                            <option value="desc">降序</option>
                        </select>
                    </div>
                    <button class="btn btn-sm btn-info" onclick="applyFilters()">应用</button>
                    <button class="btn btn-sm btn-outline-secondary" onclick="clearFilters()">清除</button>
                </form>
            </div>
            
            <div class="table-responsive">
                <table class="table table-hover table-bordered">
                    <thead>
                        <tr>
                            ${columns.map(column => `<th>${column}</th>`).join('')}
                            <th width="100">操作</th>
                        </tr>
                    </thead>
                    <tbody>
    `;
    
    // 表格数据行
    let tableBodyHtml = '';
    if (data.length === 0) {
        tableBodyHtml = `<tr><td colspan="${columns.length + 1}" class="text-center">没有数据</td></tr>`;
    } else {
        data.forEach((row, index) => {
            tableBodyHtml += '<tr>';
            
            columns.forEach(column => {
                // 显示值（对于长文本或JSON进行截断）
                let cellValue = row[column];
                let displayValue = cellValue;
                
                if (cellValue === null || cellValue === undefined) {
                    displayValue = '<span class="text-muted">NULL</span>';
                } else if (typeof cellValue === 'object') {
                    displayValue = `<code>${JSON.stringify(cellValue).substr(0, 50)}...</code>`;
                } else if (typeof cellValue === 'string' && cellValue.length > 100) {
                    displayValue = `<span class="cell-limit" title="${escapeHtml(cellValue)}">${escapeHtml(cellValue.substr(0, 100))}...</span>`;
                }
                
                tableBodyHtml += `<td>${displayValue}</td>`;
            });
            
            // 操作按钮
            const rowId = row[primaryKeyColumn];
            tableBodyHtml += `
                <td>
                    <button class="btn btn-sm btn-info" onclick="editRecord(${index})">编辑</button>
                    <button class="btn btn-sm btn-danger" onclick="confirmDeleteRecord(${index})">删除</button>
                </td>
            `;
            
            tableBodyHtml += '</tr>';
        });
    }
    
    // 分页控件
    const paginationHtml = `
        <div class="pagination-controls">
            <div>
                显示 ${(pagination.page - 1) * pagination.per_page + 1} 
                到 ${Math.min(pagination.page * pagination.per_page, pagination.total)} 
                条，共 ${pagination.total} 条记录
            </div>
            <div>
                <button class="btn btn-sm btn-outline-primary" 
                    ${pagination.page <= 1 ? 'disabled' : ''} 
                    onclick="gotoPage(${pagination.page - 1})">上一页</button>
                <span class="mx-2">第 ${pagination.page} 页，共 ${pagination.total_pages} 页</span>
                <button class="btn btn-sm btn-outline-primary" 
                    ${pagination.page >= pagination.total_pages ? 'disabled' : ''} 
                    onclick="gotoPage(${pagination.page + 1})">下一页</button>
            </div>
        </div>
    `;
    
    // 组合完整的表格HTML
    const tableHtml = `
        ${tableHeaderHtml}
                ${tableBodyHtml}
            </tbody>
        </table>
        ${paginationHtml}
        </div>
    `;
    
    // 显示到内容区域
    $('#contentArea').html(tableHtml);
}

/**
 * 显示添加记录表单
 */
function showAddRecordForm(tableName) {
    // 重置表单
    $('#recordForm').html('');
    currentRecord = null;
    
    // 获取表的列信息
    const columns = tableInfo[tableName].columns;
    
    // 为每一列创建表单字段
    columns.forEach(column => {
        // 主键列，如果是自增主键则不显示
        if (column.pk === 1 && column.type.toLowerCase().includes('integer')) {
            return;
        }
        
        const required = column.notnull === 1 && column.dflt_value === null;
        
        let inputField = '';
        const columnType = column.type.toLowerCase();
        
        if (columnType.includes('text') && !column.name.toLowerCase().includes('path')) {
            // 文本域
            inputField = `<textarea class="form-control" id="field_${column.name}" name="${column.name}" 
                ${required ? 'required' : ''}></textarea>`;
        } else if (columnType.includes('integer') && column.name.toLowerCase().includes('active')) {
            // 布尔值选择器
            inputField = `
                <select class="form-control" id="field_${column.name}" name="${column.name}" ${required ? 'required' : ''}>
                    <option value="1">是</option>
                    <option value="0">否</option>
                </select>
            `;
        } else {
            // 默认为文本输入框
            inputField = `<input type="text" class="form-control" id="field_${column.name}" 
                name="${column.name}" ${required ? 'required' : ''}>`;
        }
        
        // 添加表单组
        $('#recordForm').append(`
            <div class="form-group">
                <label for="field_${column.name}">${column.name} ${column.type}</label>
                ${inputField}
                ${column.dflt_value ? `<small class="form-text text-muted">默认值: ${column.dflt_value}</small>` : ''}
            </div>
        `);
    });
    
    // 更新模态框标题和保存按钮数据
    $('#tableDataModalLabel').text(`添加 ${tableName} 记录`);
    $('#saveRecord').data('action', 'add').data('table', tableName);
    
    // 显示模态框
    $('#tableDataModal').modal('show');
}

/**
 * 编辑记录
 */
function editRecord(index) {
    const record = tableData[index];
    currentRecord = record;
    
    // 重置表单
    $('#recordForm').html('');
    
    // 获取表的列信息
    const columns = tableInfo[currentTable].columns;
    
    // 为每一列创建表单字段
    columns.forEach(column => {
        // 主键列只读
        const isPK = column.pk === 1;
        const required = column.notnull === 1 && column.dflt_value === null;
        const value = record[column.name] !== null ? record[column.name] : '';
        
        let inputField = '';
        const columnType = column.type.toLowerCase();
        
        if (isPK) {
            // 主键显示为只读
            inputField = `<input type="text" class="form-control" id="field_${column.name}" 
                name="${column.name}" value="${value}" readonly>`;
        } else if (columnType.includes('text') && !column.name.toLowerCase().includes('path')) {
            // 文本域
            inputField = `<textarea class="form-control" id="field_${column.name}" name="${column.name}" 
                ${required ? 'required' : ''}>${value}</textarea>`;
        } else if (columnType.includes('integer') && column.name.toLowerCase().includes('active')) {
            // 布尔值选择器
            inputField = `
                <select class="form-control" id="field_${column.name}" name="${column.name}" ${required ? 'required' : ''}>
                    <option value="1" ${value == 1 ? 'selected' : ''}>是</option>
                    <option value="0" ${value == 0 ? 'selected' : ''}>否</option>
                </select>
            `;
        } else {
            // 默认为文本输入框
            inputField = `<input type="text" class="form-control" id="field_${column.name}" 
                name="${column.name}" value="${value}" ${required ? 'required' : ''}>`;
        }
        
        // 添加表单组
        $('#recordForm').append(`
            <div class="form-group">
                <label for="field_${column.name}">${column.name} ${column.type}</label>
                ${inputField}
            </div>
        `);
    });
    
    // 更新模态框标题和保存按钮数据
    $('#tableDataModalLabel').text(`编辑 ${currentTable} 记录`);
    $('#saveRecord').data('action', 'edit').data('table', currentTable).data('id', record[primaryKeyColumn]);
    
    // 显示模态框
    $('#tableDataModal').modal('show');
}

/**
 * 确认删除记录
 */
function confirmDeleteRecord(index) {
    const record = tableData[index];
    currentRecord = record;
    
    // 显示确认对话框
    $('#confirmDeleteModal').modal('show');
    $('#confirmDelete').data('table', currentTable).data('id', record[primaryKeyColumn]);
}

/**
 * 保存记录
 */
function saveRecord() {
    const table = $('#saveRecord').data('table');
    const action = $('#saveRecord').data('action');
    
    // 收集表单数据
    const formData = {};
    $('#recordForm').serializeArray().forEach(item => {
        formData[item.name] = item.value === '' ? null : item.value;
    });
    
    // 发送请求
    if (action === 'add') {
        // 添加记录
        $.ajax({
            url: `/api/db/table/${table}/record`,
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(formData),
            success: function(response) {
                if (response.code === 0) {
                    // 关闭模态框
                    $('#tableDataModal').modal('hide');
                    
                    // 刷新表格
                    loadTableData(table, paginationInfo.page, paginationInfo.per_page);
                    
                    // 显示成功消息
                    showSuccess('添加记录成功');
                } else {
                    showError('添加记录失败', response.message);
                }
            },
            error: function(xhr) {
                showError('添加记录请求失败', xhr.statusText);
            }
        });
    } else if (action === 'edit') {
        // 编辑记录
        const id = $('#saveRecord').data('id');
        
        $.ajax({
            url: `/api/db/table/${table}/record/${id}`,
            method: 'PUT',
            contentType: 'application/json',
            data: JSON.stringify(formData),
            success: function(response) {
                if (response.code === 0) {
                    // 关闭模态框
                    $('#tableDataModal').modal('hide');
                    
                    // 刷新表格
                    loadTableData(table, paginationInfo.page, paginationInfo.per_page);
                    
                    // 显示成功消息
                    showSuccess('更新记录成功');
                } else {
                    showError('更新记录失败', response.message);
                }
            },
            error: function(xhr) {
                showError('更新记录请求失败', xhr.statusText);
            }
        });
    }
}

/**
 * 删除记录
 */
function deleteRecord() {
    const table = $('#confirmDelete').data('table');
    const id = $('#confirmDelete').data('id');
    
    $.ajax({
        url: `/api/db/table/${table}/record/${id}`,
        method: 'DELETE',
        success: function(response) {
            if (response.code === 0) {
                // 关闭模态框
                $('#confirmDeleteModal').modal('hide');
                
                // 刷新表格
                loadTableData(table, paginationInfo.page, paginationInfo.per_page);
                
                // 显示成功消息
                showSuccess('删除记录成功');
            } else {
                showError('删除记录失败', response.message);
            }
        },
        error: function(xhr) {
            showError('删除记录请求失败', xhr.statusText);
        }
    });
}

/**
 * 显示SQL查询界面
 */
function showSqlQueryInterface() {
    const sqlHtml = `
        <div class="card mb-4">
            <div class="card-header">
                <h5>SQL查询</h5>
            </div>
            <div class="card-body">
                <form id="sqlForm">
                    <div class="form-group">
                        <label for="sqlEditor">SQL语句</label>
                        <textarea id="sqlEditor" class="form-control sql-editor" placeholder="输入SQL查询语句..."></textarea>
                    </div>
                    <div class="form-check mb-3">
                        <input class="form-check-input" type="checkbox" id="readonlyMode" checked>
                        <label class="form-check-label" for="readonlyMode">
                            只读模式 (只允许SELECT语句)
                        </label>
                    </div>
                    <button type="button" id="executeSql" class="btn btn-primary">执行</button>
                </form>
                <div id="sqlResult" class="sql-result mt-4" style="display: none;">
                    <h6>查询结果:</h6>
                    <div id="sqlResultContent"></div>
                </div>
            </div>
        </div>
    `;
    
    $('#contentArea').html(sqlHtml);
    
    // 绑定执行按钮
    $('#executeSql').on('click', function() {
        executeSql();
    });
}

/**
 * 执行SQL查询
 */
function executeSql() {
    const sql = $('#sqlEditor').val().trim();
    if (!sql) {
        showError('SQL错误', '请输入SQL语句');
        return;
    }
    
    const readonly = $('#readonlyMode').is(':checked');
    
    // 显示加载状态
    $('#sqlResult').show();
    $('#sqlResultContent').html(`
        <div class="text-center py-3">
            <div class="spinner-border text-primary" role="status">
                <span class="sr-only">执行查询中...</span>
            </div>
            <p class="mt-2">正在执行SQL查询...</p>
        </div>
    `);
    
    $.ajax({
        url: '/api/db/exec',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            sql: sql,
            readonly: readonly
        }),
        success: function(response) {
            if (response.code === 0) {
                // 显示结果
                if (response.data.columns) {
                    // 显示查询结果表格
                    displaySqlResult(response.data);
                } else {
                    // 显示影响的行数
                    $('#sqlResultContent').html(`
                        <div class="alert alert-success">
                            执行成功！影响了 ${response.data.affected_rows} 行。
                        </div>
                    `);
                }
            } else {
                $('#sqlResultContent').html(`
                    <div class="alert alert-danger">
                        执行失败: ${response.message}
                    </div>
                `);
            }
        },
        error: function(xhr) {
            $('#sqlResultContent').html(`
                <div class="alert alert-danger">
                    请求错误: ${xhr.statusText}
                </div>
            `);
        }
    });
}

/**
 * 显示SQL查询结果
 */
function displaySqlResult(data) {
    const columns = data.columns;
    const records = data.records;
    
    let resultHtml = `
        <div class="alert alert-info">
            查询返回 ${records.length} 条记录
        </div>
        <div class="table-responsive">
            <table class="table table-sm table-bordered table-hover">
                <thead>
                    <tr>
                        ${columns.map(col => `<th>${col}</th>`).join('')}
                    </tr>
                </thead>
                <tbody>
    `;
    
    if (records.length === 0) {
        resultHtml += `<tr><td colspan="${columns.length}" class="text-center">无数据</td></tr>`;
    } else {
        records.forEach(record => {
            resultHtml += '<tr>';
            columns.forEach(col => {
                const value = record[col];
                let displayValue = value;
                
                if (value === null) {
                    displayValue = '<span class="text-muted">NULL</span>';
                } else if (typeof value === 'object') {
                    displayValue = `<code>${JSON.stringify(value)}</code>`;
                }
                
                resultHtml += `<td>${displayValue}</td>`;
            });
            resultHtml += '</tr>';
        });
    }
    
    resultHtml += `
                </tbody>
            </table>
        </div>
    `;
    
    $('#sqlResultContent').html(resultHtml);
}

/**
 * 加载视频源管理界面
 */
function loadVideosManagement() {
    $('#contentArea').html(`
        <div class="card mb-4">
            <div class="card-header">
                <h5>视频源管理</h5>
            </div>
            <div class="card-body">
                <div class="text-center p-3">
                    <div class="spinner-border text-primary" role="status">
                        <span class="sr-only">加载中...</span>
                    </div>
                    <p class="mt-2">正在加载视频源数据...</p>
                </div>
            </div>
        </div>
    `);
    
    $.ajax({
        url: '/api/db/videos',
        method: 'GET',
        success: function(response) {
            if (response.code === 0) {
                displayVideosData(response.data);
            } else {
                showError('加载视频源失败', response.message);
            }
        },
        error: function(xhr) {
            showError('加载视频源请求失败', xhr.statusText);
        }
    });
}

/**
 * 显示视频源数据
 */
function displayVideosData(videos) {
    let videosHtml = `
        <div class="card mb-4">
            <div class="card-header d-flex justify-content-between align-items-center">
                <h5>视频源管理</h5>
                <button class="btn btn-primary btn-sm" onclick="addVideoSource()">添加视频源</button>
            </div>
            <div class="card-body">
                <div class="table-responsive">
                    <table class="table table-bordered table-hover">
                        <thead>
                            <tr>
                                <th>视频ID</th>
                                <th>流地址</th>
                                <th>风险等级</th>
                                <th>备注</th>
                                <th>状态</th>
                                <th>检测数</th>
                                <th>操作</th>
                            </tr>
                        </thead>
                        <tbody>
    `;
    
    if (videos.length === 0) {
        videosHtml += `<tr><td colspan="7" class="text-center">暂无视频源数据</td></tr>`;
    } else {
        videos.forEach(video => {
            videosHtml += `
                <tr>
                    <td>${video.video_id}</td>
                    <td class="cell-limit" title="${video.stream_url}">${video.stream_url}</td>
                    <td>${video.level}</td>
                    <td>${video.remarks || ''}</td>
                    <td>${video.is_active ? '<span class="badge badge-success">启用</span>' : '<span class="badge badge-secondary">停用</span>'}</td>
                    <td>${video.detection_count}</td>
                    <td>
                        <button class="btn btn-sm btn-info" onclick="editVideoSource('${video.video_id}')">编辑</button>
                        <button class="btn btn-sm btn-danger" onclick="deleteVideoSource('${video.video_id}')">删除</button>
                    </td>
                </tr>
            `;
        });
    }
    
    videosHtml += `
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    `;
    
    $('#contentArea').html(videosHtml);
}

/**
 * 加载检测结果管理界面
 */
function loadDetectionsManagement() {
    $('#contentArea').html(`
        <div class="card mb-4">
            <div class="card-header">
                <h5>检测结果管理</h5>
            </div>
            <div class="card-body">
                <div class="text-center p-3">
                    <div class="spinner-border text-primary" role="status">
                        <span class="sr-only">加载中...</span>
                    </div>
                    <p class="mt-2">正在加载检测结果数据...</p>
                </div>
            </div>
        </div>
    `);
    
    $.ajax({
        url: '/api/db/detections',
        method: 'GET',
        success: function(response) {
            if (response.code === 0) {
                displayDetectionsData(response.data);
            } else {
                showError('加载检测结果失败', response.message);
            }
        },
        error: function(xhr) {
            showError('加载检测结果请求失败', xhr.statusText);
        }
    });
}

/**
 * 显示检测结果数据
 */
function displayDetectionsData(data) {
    const detections = data.detections;
    const pagination = data.pagination;
    
    let detectionsHtml = `
        <div class="card mb-4">
            <div class="card-header d-flex justify-content-between align-items-center">
                <h5>检测结果管理</h5>
                <div>
                    <select id="videoFilter" class="form-control form-control-sm" onchange="filterDetectionsByVideo()">
                        <option value="">全部视频源</option>
                        <!-- 动态加载视频源选项 -->
                    </select>
                </div>
            </div>
            <div class="card-body">
                <div class="table-responsive">
                    <table class="table table-bordered table-hover">
                        <thead>
                            <tr>
                                <th>结果ID</th>
                                <th>视频ID</th>
                                <th>时间戳</th>
                                <th>图像路径</th>
                                <th>检测数量</th>
                                <th>检测类别</th>
                                <th>操作</th>
                            </tr>
                        </thead>
                        <tbody>
    `;
    
    if (detections.length === 0) {
        detectionsHtml += `<tr><td colspan="7" class="text-center">暂无检测结果数据</td></tr>`;
    } else {
        detections.forEach(detection => {
            detectionsHtml += `
                <tr>
                    <td>${detection.result_id}</td>
                    <td>${detection.video_id}</td>
                    <td>${detection.timestamp}</td>
                    <td class="cell-limit" title="${detection.frame_path || ''}">${detection.frame_path || ''}</td>
                    <td>${detection.detection_count}</td>
                    <td>${detection.detected_classes || ''}</td>
                    <td>
                        <button class="btn btn-sm btn-info" onclick="viewDetectionDetails(${detection.result_id})">查看</button>
                        <button class="btn btn-sm btn-danger" onclick="deleteDetection(${detection.result_id})">删除</button>
                    </td>
                </tr>
            `;
        });
    }
    
    detectionsHtml += `
                        </tbody>
                    </table>
                </div>
                
                <!-- 分页控件 -->
                <div class="d-flex justify-content-between align-items-center mt-3">
                    <div>
                        显示 ${pagination.offset + 1} 到 ${Math.min(pagination.offset + detections.length, pagination.total)} 条，共 ${pagination.total} 条记录
                    </div>
                    <div>
                        <button class="btn btn-sm btn-outline-primary mr-2" 
                            ${pagination.offset <= 0 ? 'disabled' : ''} 
                            onclick="loadMoreDetections(${pagination.offset - pagination.limit})">上一页</button>
                        <button class="btn btn-sm btn-outline-primary" 
                            ${pagination.offset + pagination.limit >= pagination.total ? 'disabled' : ''} 
                            onclick="loadMoreDetections(${pagination.offset + pagination.limit})">下一页</button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    $('#contentArea').html(detectionsHtml);
    
    // 加载视频源过滤选项
    loadVideoFilterOptions();
}

/**
 * 加载视频源过滤选项
 */
function loadVideoFilterOptions() {
    $.ajax({
        url: '/api/db/videos',
        method: 'GET',
        success: function(response) {
            if (response.code === 0) {
                const videos = response.data;
                let optionsHtml = '<option value="">全部视频源</option>';
                
                videos.forEach(video => {
                    optionsHtml += `<option value="${video.video_id}">${video.video_id}</option>`;
                });
                
                $('#videoFilter').html(optionsHtml);
            }
        }
    });
}

/**
 * 根据视频源过滤检测结果
 */
function filterDetectionsByVideo() {
    const videoId = $('#videoFilter').val();
    
    $.ajax({
        url: '/api/db/detections',
        method: 'GET',
        data: {
            video_id: videoId,
            limit: 20,
            offset: 0
        },
        success: function(response) {
            if (response.code === 0) {
                displayDetectionsData(response.data);
            } else {
                showError('过滤检测结果失败', response.message);
            }
        },
        error: function(xhr) {
            showError('过滤检测结果请求失败', xhr.statusText);
        }
    });
}

/**
 * 加载更多检测结果
 */
function loadMoreDetections(offset) {
    const videoId = $('#videoFilter').val();
    
    $.ajax({
        url: '/api/db/detections',
        method: 'GET',
        data: {
            video_id: videoId,
            limit: 20,
            offset: offset
        },
        success: function(response) {
            if (response.code === 0) {
                displayDetectionsData(response.data);
            } else {
                showError('加载更多检测结果失败', response.message);
            }
        },
        error: function(xhr) {
            showError('加载更多检测结果请求失败', xhr.statusText);
        }
    });
}

/**
 * 查看检测结果详情
 */
function viewDetectionDetails(resultId) {
    // 跳转到独立的检测结果详情页面
    window.location.href = `/detection_results?result_id=${resultId}`;
}

/**
 * 刷新当前表格
 */
function refreshTable() {
    loadTableData(currentTable, paginationInfo.page, paginationInfo.per_page);
}

/**
 * 跳转到指定页
 */
function gotoPage(page) {
    loadTableData(currentTable, page, paginationInfo.per_page);
}

/**
 * 应用过滤器
 */
function applyFilters() {
    loadTableData(currentTable, 1, paginationInfo.per_page);
}

/**
 * 清除过滤器
 */
function clearFilters() {
    $('#filterColumn').val('');
    $('#filterValue').val('');
    $('#sortColumn').val('');
    $('#sortOrder').val('asc');
    
    loadTableData(currentTable, 1, paginationInfo.per_page);
}

/**
 * 转义HTML特殊字符
 */
function escapeHtml(text) {
    if (typeof text !== 'string') {
        return text;
    }
    
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

/**
 * 显示错误提示
 */
function showError(title, message) {
    alert(`${title}: ${message}`);
}

/**
 * 显示成功提示
 */
function showSuccess(message) {
    alert(message);
} 