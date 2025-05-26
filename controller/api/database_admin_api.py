"""
数据库管理API
提供数据库表的可视化查询和编辑功能
"""

import os
import json
from flask import Blueprint, request, jsonify, g, current_app
from controller.utils.database import get_db_connection, get_database_path

# 创建蓝图
database_admin_bp = Blueprint('database_admin', __name__)

@database_admin_bp.route('/api/db/tables', methods=['GET'])
def list_tables():
    """获取数据库中的所有表信息"""
    db = get_db_connection()
    cursor = db.cursor()
    
    # 查询所有表
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    
    # 获取每个表的结构
    table_info = {}
    for table in tables:
        cursor.execute(f"PRAGMA table_info({table});")
        columns = [{
            'cid': col[0], 
            'name': col[1], 
            'type': col[2],
            'notnull': col[3],
            'dflt_value': col[4],
            'pk': col[5]
        } for col in cursor.fetchall()]
        
        # 获取记录数
        cursor.execute(f"SELECT COUNT(*) FROM {table};")
        count = cursor.fetchone()[0]
        
        table_info[table] = {
            'columns': columns,
            'record_count': count
        }
    
    return jsonify({
        'code': 0,
        'message': '获取数据库表信息成功',
        'data': {
            'tables': tables,
            'table_info': table_info,
            'db_path': get_database_path()
        }
    })

@database_admin_bp.route('/api/db/table/<table_name>/data', methods=['GET'])
def get_table_data(table_name):
    """获取指定表的数据"""
    db = get_db_connection()
    cursor = db.cursor()
    
    # 验证表是否存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table_name,))
    if not cursor.fetchone():
        return jsonify({
            'code': 1,
            'message': f'表 {table_name} 不存在'
        }), 404
    
    # 获取列信息
    cursor.execute(f"PRAGMA table_info({table_name});")
    columns = [col[1] for col in cursor.fetchall()]
    
    # 分页参数
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    offset = (page - 1) * per_page
    
    # 排序参数
    sort_column = request.args.get('sort_by', columns[0])
    sort_order = request.args.get('sort_order', 'asc').upper()
    if sort_order not in ['ASC', 'DESC']:
        sort_order = 'ASC'
    
    # 过滤参数
    filter_column = request.args.get('filter_column')
    filter_value = request.args.get('filter_value')
    
    # 构建查询
    query = f"SELECT * FROM {table_name}"
    count_query = f"SELECT COUNT(*) FROM {table_name}"
    params = []
    
    if filter_column and filter_value and filter_column in columns:
        query += f" WHERE {filter_column} LIKE ?"
        count_query += f" WHERE {filter_column} LIKE ?"
        params.append(f"%{filter_value}%")
    
    if sort_column in columns:
        query += f" ORDER BY {sort_column} {sort_order}"
    
    query += " LIMIT ? OFFSET ?"
    params.extend([per_page, offset])
    
    # 执行查询
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    # 获取总记录数
    filter_params = [f"%{filter_value}%"] if filter_column and filter_value else []
    cursor.execute(count_query, filter_params)
    total_count = cursor.fetchone()[0]
    
    # 构建结果
    data = []
    for row in rows:
        item = {}
        for i, column in enumerate(columns):
            item[column] = row[i]
        data.append(item)
    
    return jsonify({
        'code': 0,
        'message': '获取表数据成功',
        'data': {
            'columns': columns,
            'records': data,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total_count,
                'total_pages': (total_count + per_page - 1) // per_page
            }
        }
    })

@database_admin_bp.route('/api/db/table/<table_name>/record', methods=['POST'])
def add_record(table_name):
    """向指定表添加记录"""
    db = get_db_connection()
    cursor = db.cursor()
    
    # 验证表是否存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table_name,))
    if not cursor.fetchone():
        return jsonify({
            'code': 1,
            'message': f'表 {table_name} 不存在'
        }), 404
    
    # 获取请求数据
    data = request.json
    if not data:
        return jsonify({
            'code': 1,
            'message': '未提供数据'
        }), 400
    
    # 获取列信息
    cursor.execute(f"PRAGMA table_info({table_name});")
    columns_info = cursor.fetchall()
    columns = [col[1] for col in columns_info]
    
    # 过滤有效的列
    valid_data = {k: v for k, v in data.items() if k in columns}
    
    # 如果没有有效数据，返回错误
    if not valid_data:
        return jsonify({
            'code': 1,
            'message': '没有提供有效的列数据'
        }), 400
    
    # 构建插入语句
    columns_str = ', '.join(valid_data.keys())
    placeholders = ', '.join(['?' for _ in valid_data])
    values = list(valid_data.values())
    
    try:
        # 执行插入
        cursor.execute(f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})", values)
        db.commit()
        
        return jsonify({
            'code': 0,
            'message': '添加记录成功',
            'data': {
                'id': cursor.lastrowid
            }
        })
    except Exception as e:
        db.rollback()
        return jsonify({
            'code': 1,
            'message': f'添加记录失败: {str(e)}'
        }), 500

@database_admin_bp.route('/api/db/table/<table_name>/record/<record_id>', methods=['PUT'])
def update_record(table_name, record_id):
    """更新指定表的记录"""
    db = get_db_connection()
    cursor = db.cursor()
    
    # 验证表是否存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table_name,))
    if not cursor.fetchone():
        return jsonify({
            'code': 1,
            'message': f'表 {table_name} 不存在'
        }), 404
    
    # 获取主键列
    cursor.execute(f"PRAGMA table_info({table_name});")
    columns_info = cursor.fetchall()
    pk_column = None
    for col in columns_info:
        if col[5] == 1:  # 第6个元素是pk标志
            pk_column = col[1]
            break
    
    if not pk_column:
        return jsonify({
            'code': 1,
            'message': f'表 {table_name} 没有主键'
        }), 400
    
    # 获取请求数据
    data = request.json
    if not data:
        return jsonify({
            'code': 1,
            'message': '未提供数据'
        }), 400
    
    # 获取列信息
    columns = [col[1] for col in columns_info]
    
    # 过滤有效的列
    valid_data = {k: v for k, v in data.items() if k in columns and k != pk_column}
    
    # 如果没有有效数据，返回错误
    if not valid_data:
        return jsonify({
            'code': 1,
            'message': '没有提供有效的列数据'
        }), 400
    
    try:
        # 构建更新语句
        set_clause = ', '.join([f"{key} = ?" for key in valid_data.keys()])
        values = list(valid_data.values())
        values.append(record_id)
        
        # 执行更新
        cursor.execute(f"UPDATE {table_name} SET {set_clause} WHERE {pk_column} = ?", values)
        db.commit()
        
        if cursor.rowcount == 0:
            return jsonify({
                'code': 1,
                'message': f'记录不存在或未更改'
            }), 404
        
        return jsonify({
            'code': 0,
            'message': '更新记录成功',
            'data': {
                'affected_rows': cursor.rowcount
            }
        })
    except Exception as e:
        db.rollback()
        return jsonify({
            'code': 1,
            'message': f'更新记录失败: {str(e)}'
        }), 500

@database_admin_bp.route('/api/db/table/<table_name>/record/<record_id>', methods=['DELETE'])
def delete_record(table_name, record_id):
    """删除指定表的记录"""
    db = get_db_connection()
    cursor = db.cursor()
    
    # 验证表是否存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table_name,))
    if not cursor.fetchone():
        return jsonify({
            'code': 1,
            'message': f'表 {table_name} 不存在'
        }), 404
    
    # 获取主键列
    cursor.execute(f"PRAGMA table_info({table_name});")
    columns_info = cursor.fetchall()
    pk_column = None
    for col in columns_info:
        if col[5] == 1:  # 第6个元素是pk标志
            pk_column = col[1]
            break
    
    if not pk_column:
        return jsonify({
            'code': 1,
            'message': f'表 {table_name} 没有主键'
        }), 400
    
    try:
        # 执行删除
        cursor.execute(f"DELETE FROM {table_name} WHERE {pk_column} = ?", (record_id,))
        db.commit()
        
        if cursor.rowcount == 0:
            return jsonify({
                'code': 1,
                'message': f'记录不存在'
            }), 404
        
        return jsonify({
            'code': 0,
            'message': '删除记录成功',
            'data': {
                'affected_rows': cursor.rowcount
            }
        })
    except Exception as e:
        db.rollback()
        return jsonify({
            'code': 1,
            'message': f'删除记录失败: {str(e)}'
        }), 500

@database_admin_bp.route('/api/db/exec', methods=['POST'])
def execute_sql():
    """执行自定义SQL语句（需要授权）"""
    if not request.json or 'sql' not in request.json:
        return jsonify({
            'code': 1,
            'message': '未提供SQL语句'
        }), 400
    
    sql = request.json['sql']
    readonly = request.json.get('readonly', True)
    
    # 安全检查：禁止危险操作
    dangerous_commands = ['DROP', 'TRUNCATE']
    for cmd in dangerous_commands:
        if cmd in sql.upper():
            return jsonify({
                'code': 1,
                'message': f'禁止执行危险SQL: {cmd}'
            }), 403
    
    db = get_db_connection()
    cursor = db.cursor()
    
    try:
        cursor.execute(sql)
        
        # 如果是SELECT语句，返回结果
        if sql.upper().strip().startswith('SELECT'):
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()
            
            data = []
            for row in rows:
                item = {}
                for i, column in enumerate(columns):
                    item[column] = row[i]
                data.append(item)
            
            result = {
                'columns': columns,
                'records': data,
                'record_count': len(data)
            }
        else:
            # 非SELECT语句
            if not readonly:
                db.commit()
                result = {
                    'affected_rows': cursor.rowcount
                }
            else:
                db.rollback()
                return jsonify({
                    'code': 1,
                    'message': '只读模式下禁止执行非SELECT语句'
                }), 403
        
        return jsonify({
            'code': 0,
            'message': 'SQL执行成功',
            'data': result
        })
    except Exception as e:
        db.rollback()
        return jsonify({
            'code': 1,
            'message': f'SQL执行失败: {str(e)}'
        }), 500

@database_admin_bp.route('/api/db/videos', methods=['GET'])
def get_videos():
    """获取所有视频源"""
    db = get_db_connection()
    cursor = db.cursor()
    
    cursor.execute("""
        SELECT 
            video_id, 
            stream_url, 
            level, 
            remarks, 
            is_active,
            (SELECT COUNT(*) FROM detection_results WHERE detection_results.video_id = video_streams.video_id) AS detection_count
        FROM video_streams
        ORDER BY video_id
    """)
    
    rows = cursor.fetchall()
    columns = [description[0] for description in cursor.description]
    
    videos = []
    for row in rows:
        video = {}
        for i, column in enumerate(columns):
            video[column] = row[i]
        videos.append(video)
    
    return jsonify({
        'code': 0,
        'message': '获取视频源成功',
        'data': videos
    })

@database_admin_bp.route('/api/db/detections', methods=['GET'])
def get_latest_detections():
    """获取最近的检测结果"""
    limit = int(request.args.get('limit', 20))
    offset = int(request.args.get('offset', 0))
    video_id = request.args.get('video_id', '')
    
    db = get_db_connection()
    cursor = db.cursor()
    
    query = """
        SELECT 
            r.result_id, 
            r.video_id, 
            r.timestamp, 
            r.frame_path, 
            r.detection_count,
            GROUP_CONCAT(DISTINCT o.class_name) AS detected_classes
        FROM detection_results r
        LEFT JOIN detection_objects o ON r.result_id = o.result_id
    """
    
    params = []
    if video_id:
        query += " WHERE r.video_id = ?"
        params.append(video_id)
    
    query += """
        GROUP BY r.result_id
        ORDER BY r.timestamp DESC
        LIMIT ? OFFSET ?
    """
    
    params.extend([limit, offset])
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    columns = [description[0] for description in cursor.description]
    
    detections = []
    for row in rows:
        detection = {}
        for i, column in enumerate(columns):
            detection[column] = row[i]
        detections.append(detection)
    
    # 获取总记录数
    count_query = "SELECT COUNT(*) FROM detection_results"
    if video_id:
        count_query += " WHERE video_id = ?"
        cursor.execute(count_query, [video_id])
    else:
        cursor.execute(count_query)
    
    total_count = cursor.fetchone()[0]
    
    return jsonify({
        'code': 0,
        'message': '获取检测结果成功',
        'data': {
            'detections': detections,
            'pagination': {
                'total': total_count,
                'limit': limit,
                'offset': offset
            }
        }
    }) 