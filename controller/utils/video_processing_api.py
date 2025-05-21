"""
视频处理API
提供视频文件上传和处理的Web接口
"""

import os
import uuid
import time
from flask import Blueprint, request, jsonify, current_app, copy_current_request_context
from datetime import datetime
from werkzeug.utils import secure_filename
from .video_file_processing import process_video_file

# 创建蓝图
video_processing_bp = Blueprint('video_processing', __name__)

# 允许的视频文件扩展名
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv', 'wmv', 'flv'}

def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@video_processing_bp.route('/api/videos/upload', methods=['POST'])
def upload_video():
    """上传视频文件处理接口"""
    # 检查请求中是否有文件
    if 'video_file' not in request.files:
        return jsonify({'code': 1, 'message': '未找到视频文件'}), 400
    
    file = request.files['video_file']
    
    # 如果用户没有选择文件，浏览器也可能提交一个空的文件
    if file.filename == '':
        return jsonify({'code': 1, 'message': '未选择文件'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'code': 1, 'message': f'不支持的文件类型，请上传以下格式: {", ".join(ALLOWED_EXTENSIONS)}'}), 400
    
    try:
        # 生成安全的文件名
        filename = secure_filename(file.filename)
        
        # 使用时间戳和随机ID生成唯一的视频ID
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        video_id = request.form.get('video_id', f'VID{timestamp}{uuid.uuid4().hex[:6]}')
        
        # 获取其他参数
        interval = float(request.form.get('interval', 1.0))
        limit = int(request.form.get('limit', 20))
        
        # 设置上传目录为实例文件夹下的videos子目录
        upload_folder = os.path.join(current_app.instance_path, 'videos')
        os.makedirs(upload_folder, exist_ok=True)
        
        # 保存文件路径
        video_path = os.path.join(upload_folder, filename)
        
        # 保存上传的文件
        file.save(video_path)
        
        # 创建任务记录
        task_id = f"task_{timestamp}"
        task_info = {
            'task_id': task_id,
            'video_id': video_id,
            'filename': filename,
            'video_path': video_path,
            'interval': interval,
            'limit': limit,
            'status': 'uploaded',
            'upload_time': datetime.now().isoformat(),
            'start_time': None,
            'end_time': None
        }
        
        # 在后台线程中处理视频
        # 注意：在实际应用中，应考虑使用专门的任务队列如Celery而非直接在线程中处理
        
        # 创建一个应用上下文副本
        app = current_app._get_current_object()
        
        @copy_current_request_context
        def process_video_task():
            # 使用应用上下文包装处理函数
            with app.app_context():
                try:
                    # 更新任务状态
                    task_info['status'] = 'processing'
                    task_info['start_time'] = datetime.now().isoformat()
                    
                    # 处理视频文件
                    result = process_video_file(
                        video_path, 
                        video_id,
                        extraction_interval=interval,
                        frame_limit=limit
                    )
                    
                    # 更新任务状态
                    task_info['status'] = 'completed' if result['status'] == 'completed' else 'failed'
                    task_info['result'] = result
                except Exception as e:
                    # 异常处理
                    task_info['status'] = 'failed'
                    task_info['error'] = str(e)
                    print(f"视频处理错误: {str(e)}")
                
                # 更新结束时间
                task_info['end_time'] = datetime.now().isoformat()
        
        # 启动处理线程
        import threading
        thread = threading.Thread(target=process_video_task)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'code': 0,
            'message': '视频文件上传成功，处理任务已启动',
            'data': {
                'task_id': task_id,
                'video_id': video_id,
                'filename': filename
            }
        })
        
    except Exception as e:
        return jsonify({'code': 1, 'message': f'处理视频文件时出错: {str(e)}'}), 500

@video_processing_bp.route('/api/videos/process', methods=['POST'])
def process_existing_video():
    """处理已存在的视频文件"""
    data = request.json
    if not data:
        return jsonify({'code': 1, 'message': '无效的请求数据'}), 400
    
    video_path = data.get('video_path')
    if not video_path or not os.path.exists(video_path):
        return jsonify({'code': 1, 'message': f'视频文件不存在: {video_path}'}), 400
    
    try:
        # 获取处理参数
        video_id = data.get('video_id', f'VID{datetime.now().strftime("%Y%m%d%H%M%S")}')
        interval = float(data.get('interval', 1.0))
        limit = int(data.get('limit', 20))
        
        # 处理视频文件
        result = process_video_file(
            video_path, 
            video_id,
            extraction_interval=interval,
            frame_limit=limit
        )
        
        return jsonify({
            'code': 0,
            'message': '视频处理完成',
            'data': result
        })
        
    except Exception as e:
        return jsonify({'code': 1, 'message': f'处理视频文件时出错: {str(e)}'}), 500 