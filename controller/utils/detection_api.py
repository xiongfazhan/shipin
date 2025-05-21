"""
检测结果查询API
提供用于查询视频检测结果的API端点
"""

from flask import Blueprint, request, jsonify
from .database import get_db_connection
import os
from datetime import datetime, timedelta

detection_api_bp = Blueprint('detection_api', __name__)

# 图像基础路径转换为Web路径
def convert_image_path_for_web(file_path):
    """将文件系统路径转换为Web路径"""
    if not file_path:
        return None
    
    # 转换路径分隔符
    web_path = file_path.replace('\\', '/')
    
    # 提取最后两个部分作为Web路径（假设文件存储在 instance/detection_results 中）
    parts = web_path.split('/')
    if len(parts) >= 2:
        relative_path = '/'.join(parts[-2:])  # 如 "detection_results/xxx.jpg"
        return f"/static/results/{os.path.basename(file_path)}"
    return None

@detection_api_bp.route('/api/detection/results', methods=['GET'])
def get_detection_results():
    """查询检测结果，支持按日期范围、视频ID和目标类别过滤"""
    # 获取查询参数
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    video_id = request.args.get('video_id')
    object_class = request.args.get('object_class')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    
    # 计算分页偏移量
    offset = (page - 1) * per_page

    # 构建SQL查询
    db = get_db_connection()
    cursor = db.cursor()
    
    # 基础SQL
    base_sql = """
        SELECT 
            r.result_id, r.video_id, r.timestamp, r.frame_path, r.detection_count,
            GROUP_CONCAT(DISTINCT o.class_name) as detected_classes
        FROM detection_results r
        JOIN detection_objects o ON r.result_id = o.result_id
    """
    
    # 构建WHERE子句
    conditions = []
    params = []
    
    if start_date:
        conditions.append("r.timestamp >= ?")
        params.append(start_date + " 00:00:00")
    
    if end_date:
        conditions.append("r.timestamp <= ?")
        params.append(end_date + " 23:59:59")
    
    if video_id:
        conditions.append("r.video_id = ?")
        params.append(video_id)
    
    if object_class:
        conditions.append("o.class_name LIKE ?")
        params.append(f"%{object_class}%")
    
    # 组装完整查询
    query = base_sql
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    
    # 添加分组和排序
    query += " GROUP BY r.result_id ORDER BY r.timestamp DESC LIMIT ? OFFSET ?"
    params.extend([per_page, offset])
    
    # 执行查询
    cursor.execute(query, params)
    results = cursor.fetchall()
    
    # 获取总记录数
    count_query = "SELECT COUNT(DISTINCT r.result_id) FROM detection_results r"
    if object_class:
        count_query += " JOIN detection_objects o ON r.result_id = o.result_id"
    
    if conditions:
        count_query += " WHERE " + " AND ".join(conditions)
    
    cursor.execute(count_query, params[:-2] if params else [])  # 移除LIMIT和OFFSET参数
    total_count = cursor.fetchone()[0]
    
    # 转换结果
    detection_results = []
    for row in results:
        # 转换图像路径为Web路径
        image_path = convert_image_path_for_web(row['frame_path']) if row['frame_path'] else None
        
        detection_results.append({
            'result_id': row['result_id'],
            'video_id': row['video_id'],
            'timestamp': row['timestamp'],
            'image_path': image_path,
            'detection_count': row['detection_count'],
            'detected_classes': row['detected_classes'].split(',') if row['detected_classes'] else []
        })
    
    # 返回结果
    return jsonify({
        'code': 0,
        'data': {
            'results': detection_results,
            'pagination': {
                'total': total_count,
                'page': page,
                'per_page': per_page,
                'total_pages': (total_count + per_page - 1) // per_page
            }
        }
    })

@detection_api_bp.route('/api/detection/detail/<int:result_id>', methods=['GET'])
def get_detection_detail(result_id):
    """获取检测结果的详细信息"""
    db = get_db_connection()
    cursor = db.cursor()
    
    # 查询主结果
    cursor.execute("""
        SELECT result_id, video_id, timestamp, frame_path, detection_count
        FROM detection_results
        WHERE result_id = ?
    """, (result_id,))
    
    result = cursor.fetchone()
    if not result:
        return jsonify({'code': 1, 'message': '未找到指定的检测结果'}), 404
    
    # 查询检测对象详情
    cursor.execute("""
        SELECT 
            object_id, class_id, class_name, confidence,
            bbox_x, bbox_y, bbox_width, bbox_height,
            detection_type, parent_class, parent_bbox
        FROM detection_objects
        WHERE result_id = ?
    """, (result_id,))
    
    objects = cursor.fetchall()
    
    # 转换结果
    detection_objects = []
    for obj in objects:
        detection_objects.append({
            'object_id': obj['object_id'],
            'class_id': obj['class_id'],
            'class_name': obj['class_name'],
            'confidence': obj['confidence'],
            'bbox': {
                'x': obj['bbox_x'],
                'y': obj['bbox_y'],
                'width': obj['bbox_width'],
                'height': obj['bbox_height']
            },
            'detection_type': obj['detection_type'],
            'parent_class': obj['parent_class'],
            'parent_bbox': obj['parent_bbox']
        })
    
    # 转换图像路径
    image_path = convert_image_path_for_web(result['frame_path']) if result['frame_path'] else None
    
    # 组装详细结果
    detail = {
        'result_id': result['result_id'],
        'video_id': result['video_id'],
        'timestamp': result['timestamp'],
        'image_path': image_path,
        'detection_count': result['detection_count'],
        'objects': detection_objects
    }
    
    return jsonify({'code': 0, 'data': detail})

@detection_api_bp.route('/api/detection/videos', methods=['GET'])
def get_detection_videos():
    """获取有检测结果的视频ID列表"""
    db = get_db_connection()
    cursor = db.cursor()
    
    cursor.execute("""
        SELECT DISTINCT video_id 
        FROM detection_results
        ORDER BY video_id
    """)
    
    videos = [row['video_id'] for row in cursor.fetchall()]
    
    return jsonify({'code': 0, 'data': videos})

@detection_api_bp.route('/api/detection/classes', methods=['GET'])
def get_detection_classes():
    """获取检测到的目标类别列表"""
    db = get_db_connection()
    cursor = db.cursor()
    
    cursor.execute("""
        SELECT DISTINCT class_name 
        FROM detection_objects
        ORDER BY class_name
    """)
    
    classes = [row['class_name'] for row in cursor.fetchall()]
    
    return jsonify({'code': 0, 'data': classes})

@detection_api_bp.route('/api/detection/stats', methods=['GET'])
def get_detection_stats():
    """获取检测统计信息"""
    # 获取查询参数
    days = int(request.args.get('days', 7))  # 默认显示7天的统计
    
    # 计算日期范围
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # 格式化日期
    start_date_str = start_date.strftime('%Y-%m-%d 00:00:00')
    end_date_str = end_date.strftime('%Y-%m-%d 23:59:59')
    
    db = get_db_connection()
    cursor = db.cursor()
    
    # 按日期统计检测结果数量
    cursor.execute("""
        SELECT 
            date(timestamp) as detection_date,
            COUNT(*) as detection_count
        FROM detection_results
        WHERE timestamp BETWEEN ? AND ?
        GROUP BY detection_date
        ORDER BY detection_date
    """, (start_date_str, end_date_str))
    
    date_stats = [dict(row) for row in cursor.fetchall()]
    
    # 按类别统计检测对象数量
    cursor.execute("""
        SELECT 
            class_name,
            COUNT(*) as object_count
        FROM detection_objects
        WHERE result_id IN (
            SELECT result_id 
            FROM detection_results 
            WHERE timestamp BETWEEN ? AND ?
        )
        GROUP BY class_name
        ORDER BY object_count DESC
        LIMIT 10
    """, (start_date_str, end_date_str))
    
    class_stats = [dict(row) for row in cursor.fetchall()]
    
    # 返回统计结果
    return jsonify({
        'code': 0, 
        'data': {
            'date_stats': date_stats,
            'class_stats': class_stats
        }
    }) 