"""
更新测试数据
将数据库中的检测结果关联到已创建的测试图像
"""

import os
import sqlite3
import random
import traceback
from datetime import datetime, timedelta

# 数据库和图像目录路径
DB_PATH = os.path.join('instance', 'video_streams.db')
RESULTS_DIR = os.path.join('static', 'results')

def get_db_connection():
    """获取数据库连接"""
    try:
        print(f"连接数据库: {DB_PATH}")
        if not os.path.exists(DB_PATH):
            print(f"警告: 数据库文件不存在: {DB_PATH}")
            # 确保目录存在
            os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        
        # 连接数据库
        conn = sqlite3.connect(DB_PATH)
        print("数据库连接成功")
        return conn
    except Exception as e:
        print(f"数据库连接失败: {e}")
        traceback.print_exc()
        return None

def get_image_files():
    """获取所有测试图像文件"""
    try:
        print(f"检查图像目录: {RESULTS_DIR}")
        if not os.path.exists(RESULTS_DIR):
            print(f"警告: 图像目录不存在: {RESULTS_DIR}")
            return []
        
        image_files = [f for f in os.listdir(RESULTS_DIR) if f.startswith('TEST') and f.endswith('.jpg')]
        print(f"找到 {len(image_files)} 个测试图像文件")
        return image_files
    except Exception as e:
        print(f"获取图像文件失败: {e}")
        traceback.print_exc()
        return []

def create_test_data():
    """创建测试视频流和检测结果数据"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
        
        cursor = conn.cursor()
        
        # 检查数据库结构
        try:
            print("检查数据库表结构...")
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            print(f"数据库中的表: {[table[0] for table in tables]}")
            
            # 确保所需表存在
            if 'video_streams' not in [table[0] for table in tables]:
                print("警告: video_streams 表不存在，请先初始化数据库")
                return False
            
            if 'detection_results' not in [table[0] for table in tables]:
                print("警告: detection_results 表不存在，请先初始化数据库")
                return False
                
            if 'detection_objects' not in [table[0] for table in tables]:
                print("警告: detection_objects 表不存在，请先初始化数据库")
                return False
        except Exception as e:
            print(f"检查表结构失败: {e}")
            traceback.print_exc()
            return False
        
        # 清理已有测试数据
        try:
            print("清理已有测试数据...")
            cursor.execute("DELETE FROM detection_objects WHERE result_id IN (SELECT result_id FROM detection_results WHERE video_id LIKE 'TEST%')")
            cursor.execute("DELETE FROM detection_results WHERE video_id LIKE 'TEST%'")
            cursor.execute("DELETE FROM video_streams WHERE video_id LIKE 'TEST%'")
            conn.commit()
            print("已清理测试数据")
        except Exception as e:
            print(f"清理数据失败: {e}")
            traceback.print_exc()
            conn.rollback()
        
        # 创建测试视频流
        try:
            print("创建测试视频流...")
            levels = ['高', '中', '低']
            for i in range(1, 6):
                video_id = f"TEST{i:03d}"
                cursor.execute("""
                    INSERT INTO video_streams (video_id, stream_url, level, remarks, is_active)
                    VALUES (?, ?, ?, ?, 1)
                """, (
                    video_id, 
                    f"rtsp://example.com/stream{i}", 
                    random.choice(levels),
                    f"测试视频流 {i}"
                ))
            conn.commit()
            print("已创建测试视频流")
        except Exception as e:
            print(f"创建视频流失败: {e}")
            traceback.print_exc()
            conn.rollback()
        
        # 获取图像文件
        image_files = get_image_files()
        if not image_files:
            print("未找到测试图像文件")
            conn.close()
            return False
        
        # 创建检测结果记录
        try:
            print("创建检测结果记录...")
            now = datetime.now()
            
            for img_file in image_files:
                # 从文件名解析视频ID
                parts = img_file.split('_')
                if len(parts) >= 2:
                    video_id = parts[0]
                    
                    # 生成随机时间戳（过去7天内）
                    days_ago = random.randint(0, 7)
                    hours_ago = random.randint(0, 23)
                    minutes_ago = random.randint(0, 59)
                    timestamp = now - timedelta(days=days_ago, hours=hours_ago, minutes=minutes_ago)
                    timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")
                    
                    # 图像完整路径（用于前端访问）
                    image_path = f"/static/results/{img_file}"
                    
                    # 随机检测对象数量（1-5个）
                    detection_count = random.randint(1, 5)
                    
                    # 插入检测结果记录
                    cursor.execute("""
                        INSERT INTO detection_results
                        (video_id, timestamp, frame_path, detection_count)
                        VALUES (?, ?, ?, ?)
                    """, (video_id, timestamp_str, image_path, detection_count))
                    
                    result_id = cursor.lastrowid
                    
                    # 创建检测对象记录
                    classes = ['person', 'car', 'bicycle', 'dog', 'cat', 'truck', 'bus']
                    
                    for i in range(detection_count):
                        class_name = random.choice(classes)
                        class_id = classes.index(class_name)
                        confidence = random.uniform(0.6, 0.98)
                        
                        # 随机边界框
                        bbox_x = random.randint(50, 500)
                        bbox_y = random.randint(50, 350)
                        bbox_width = random.randint(50, 150)
                        bbox_height = random.randint(50, 150)
                        
                        # 检测类型
                        detection_type = 'primary' if random.random() > 0.2 else 'secondary'
                        
                        # 仅二次检测有父对象
                        parent_class = None
                        parent_bbox = None
                        if detection_type == 'secondary':
                            parent_class = 'table'
                            parent_bbox = '[100, 100, 300, 200]'
                        
                        cursor.execute("""
                            INSERT INTO detection_objects
                            (result_id, class_id, class_name, confidence,
                             bbox_x, bbox_y, bbox_width, bbox_height,
                             detection_type, parent_class, parent_bbox)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            result_id, class_id, class_name, confidence,
                            bbox_x, bbox_y, bbox_width, bbox_height,
                            detection_type, parent_class, parent_bbox
                        ))
            
            conn.commit()
            print("已创建检测结果记录")
            
            # 统计创建的记录数
            cursor.execute("SELECT COUNT(*) FROM detection_results WHERE video_id LIKE 'TEST%'")
            result_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM detection_objects WHERE result_id IN (SELECT result_id FROM detection_results WHERE video_id LIKE 'TEST%')")
            object_count = cursor.fetchone()[0]
            
            print(f"总共创建了 {result_count} 条检测结果记录和 {object_count} 条检测对象记录")
            
            return True
            
        except Exception as e:
            print(f"创建检测结果记录失败: {e}")
            traceback.print_exc()
            conn.rollback()
            return False
        
        finally:
            conn.close()
            
    except Exception as e:
        print(f"创建测试数据时出错: {e}")
        traceback.print_exc()
        return False

def main():
    """主函数"""
    try:
        print("开始更新测试数据...")
        success = create_test_data()
        if success:
            print("测试数据更新完成！")
        else:
            print("测试数据更新失败！")
    except Exception as e:
        print(f"更新测试数据时出错: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main() 