import pandas as pd
from flask import Blueprint, request, jsonify
import re
from .database import get_db_connection # Removed close_db_connection as it's not directly used here

data_processing_bp = Blueprint('data_processing', __name__)

# 允许的视频流等级
ALLOWED_LEVELS = ['高', '中', '低', 'high', 'medium', 'low']
NORMALIZED_LEVELS = {
    'high': '高', 'medium': '中', 'low': '低',
    '高': '高', '中': '中', '低': '低'
}

# 预期的Excel/CSV列名 (程序会尝试匹配这些列名，不区分大小写)
EXPECTED_COLUMNS = {
    'videoid': 'VideoID',
    'streamurl': 'StreamURL',
    'level': 'Level',
    'remarks': 'Remarks'
}

def validate_url(url):
    """简单的URL格式校验"""
    if not url or not isinstance(url, str):
        return False
    # 简单校验是否以常见协议开头
    return re.match(r'^(rtsp|rtmp|http|https)://', url, re.IGNORECASE) is not None

@data_processing_bp.route('/api/videos/import_excel', methods=['POST'])
# 函数名保持 import_videos_from_excel 但现在也处理CSV
def import_videos_from_excel(): 
    if 'excel_file' not in request.files:
        return jsonify({'code': 1, 'message': '未找到名为 "excel_file" 的文件部分'}), 400

    file = request.files['excel_file']

    if file.filename == '':
        return jsonify({'code': 1, 'message': '未选择文件'}), 400

    allowed_extensions = {'.xlsx', '.xls', '.csv'}
    file_ext = '.' + file.filename.split('.')[-1].lower()

    if file_ext not in allowed_extensions:
        return jsonify({'code': 1, 'message': f'文件格式不支持，请上传 {", ".join(sorted(list(allowed_extensions)))} 文件'}), 400

    try:
        if file_ext == '.csv':
            df = pd.read_csv(file, dtype=str)
        else: # .xlsx or .xls
            df = pd.read_excel(file, dtype=str)
        
        df = df.rename(columns=lambda x: str(x).strip().lower().replace(' ', '').replace('_', '')) # 标准化列名

        processed_rows = 0
        imported_count = 0
        failed_rows_count = 0
        errors = []
        
        missing_cols = []
        actual_cols_map = {}

        for expected_std_col, display_col_name in EXPECTED_COLUMNS.items():
            found = False
            for col in df.columns:
                if expected_std_col == col:
                    actual_cols_map[expected_std_col] = col
                    found = True
                    break
            if not found and display_col_name in ['VideoID', 'StreamURL', 'Level']:
                 missing_cols.append(display_col_name)
        
        if missing_cols:
            return jsonify({'code': 1, 'message': f"文件缺少必要的列: {', '.join(missing_cols)}"}), 400

        db = get_db_connection()
        cursor = db.cursor()

        for index, row in df.iterrows():
            processed_rows += 1
            row_number = index + 2 
            row_errors = []

            video_id = str(row.get(actual_cols_map.get('videoid', 'videoid'), '')).strip()
            stream_url = str(row.get(actual_cols_map.get('streamurl', 'streamurl'), '')).strip()
            level = str(row.get(actual_cols_map.get('level', 'level'), '')).strip()
            remarks = str(row.get(actual_cols_map.get('remarks', 'remarks'), '')).strip()

            if not video_id:
                row_errors.append('VideoID 不能为空')
            else:
                # 检查 VideoID 是否已存在于数据库
                cursor.execute("SELECT video_id FROM video_streams WHERE video_id = ?", (video_id,))
                if cursor.fetchone():
                    row_errors.append(f'VideoID "{video_id}" 已存在于数据库中')

            if not stream_url:
                row_errors.append('StreamURL 不能为空')
            elif not validate_url(stream_url):
                row_errors.append(f'StreamURL "{stream_url}" 格式无效')
            
            if not level:
                row_errors.append('Level 不能为空')
            elif level.lower() not in [l.lower() for l in ALLOWED_LEVELS]:
                row_errors.append(f'Level "{level}" 无效，允许的值: {", ".join(list(set(ALLOWED_LEVELS)))}')
            else:
                level = NORMALIZED_LEVELS[level.lower()]

            if row_errors:
                failed_rows_count += 1
                errors.append({
                    'row': row_number,
                    'video_id': video_id if video_id else 'N/A',
                    'messages': row_errors
                })
            else:
                try:
                    cursor.execute("""
                        INSERT INTO video_streams (video_id, stream_url, level, remarks, is_active)
                        VALUES (?, ?, ?, ?, ?)
                    """, (video_id, stream_url, level, remarks, 1)) # 默认 is_active 为 1 (True)
                    imported_count += 1
                except Exception as e_db:
                    failed_rows_count += 1
                    errors.append({
                        'row': row_number,
                        'video_id': video_id,
                        'messages': [f'数据库插入错误: {str(e_db)}']
                    })
        
        if imported_count > 0:
            db.commit()

        if imported_count > 0 and failed_rows_count == 0:
            message = f'成功导入 {imported_count} 条视频流数据到数据库。'
        elif imported_count > 0 and failed_rows_count > 0:
            message = f'导入完成，成功 {imported_count} 条到数据库，失败 {failed_rows_count} 条。详情请查看错误列表。'
        elif imported_count == 0 and failed_rows_count > 0:
            message = f'导入失败，处理了 {processed_rows} 行数据，有 {failed_rows_count} 行存在错误。'
        elif processed_rows == 0:
             message = '上传的文件为空或不包含有效数据行。'
        else: 
             message = '未导入任何数据到数据库，请检查文件内容是否符合规范或包含有效数据。'

        return jsonify({
            'code': 0 if failed_rows_count == 0 and imported_count > 0 else (1 if failed_rows_count > 0 else 2),
            'message': message,
            'data': {
                'total_processed_rows': processed_rows,
                'imported_count': imported_count,
                'failed_row_count': failed_rows_count,
                'errors': errors,
            }
        }), 200 if failed_rows_count == 0 and imported_count > 0 else (400 if failed_rows_count > 0 else 200)

    except pd.errors.EmptyDataError:
        return jsonify({'code': 1, 'message': '上传的文件为空或格式不正确'}), 400
    except Exception as e:
        print(f"Error during file import: {str(e)}") 
        return jsonify({'code': 1, 'message': f'处理文件时发生内部错误: {str(e)}'}), 500

@data_processing_bp.route('/api/video_streams', methods=['GET'])
def get_video_streams():
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("SELECT video_id, stream_url, level, remarks, is_active FROM video_streams ORDER BY video_id")
    rows = cursor.fetchall()

    streams = [dict(row) for row in rows] # 将 sqlite3.Row 转换为字典
    return jsonify({'code': 0, 'data': streams})

@data_processing_bp.route('/api/video_streams/<video_id>', methods=['PUT'])
def update_video_stream(video_id):
    data = request.json
    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute("SELECT video_id FROM video_streams WHERE video_id = ?", (video_id,))
    stream_exists = cursor.fetchone()

    if not stream_exists:
        return jsonify({'code': 1, 'message': '未找到指定的视频流。'}), 404

    if 'is_active' in data and isinstance(data['is_active'], bool):
        try:
            new_status = 1 if data['is_active'] else 0
            cursor.execute("UPDATE video_streams SET is_active = ? WHERE video_id = ?", (new_status, video_id))
            db.commit()
            
            cursor.execute("SELECT video_id, stream_url, level, remarks, is_active FROM video_streams WHERE video_id = ?", (video_id,))
            updated_stream = dict(cursor.fetchone())
            return jsonify({'code': 0, 'message': f'视频流 {video_id} 状态已更新。', 'data': updated_stream})
        except Exception as e_db:
            return jsonify({'code': 1, 'message': f'数据库更新错误: {str(e_db)}'}), 500
    else:
        return jsonify({'code': 1, 'message': '无效的更新请求或参数 (需要布尔型的 is_active)。'}), 400

@data_processing_bp.route('/api/video_streams/<video_id>', methods=['DELETE'])
def delete_video_stream(video_id):
    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute("SELECT video_id FROM video_streams WHERE video_id = ?", (video_id,))
    stream_exists = cursor.fetchone()

    if not stream_exists:
        return jsonify({'code': 1, 'message': '未找到指定的视频流。'}), 404
    
    try:
        cursor.execute("DELETE FROM video_streams WHERE video_id = ?", (video_id,))
        db.commit()
        return jsonify({'code': 0, 'message': f'视频流 {video_id} 已删除。'})
    except Exception as e_db:
        return jsonify({'code': 1, 'message': f'数据库删除错误: {str(e_db)}'}), 500 