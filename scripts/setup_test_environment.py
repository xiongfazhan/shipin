"""
测试环境初始化脚本
完成数据库初始化、测试图像创建和测试数据生成
"""

from datetime import datetime
import os
import sys
import sqlite3
from pathlib import Path
import time
import traceback

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Define controller_dir for path constructions
controller_dir = os.path.join(project_root, 'controller')


def setup_directories():
    """创建必要的目录结构"""
    print("1. 创建必要的目录结构...")
    
    # 创建实例目录 (relative to controller_dir)
    instance_dir = os.path.join(controller_dir, 'instance')
    os.makedirs(instance_dir, exist_ok=True)
    
    # 创建检测结果目录
    detection_results_dir = os.path.join(instance_dir, 'detection_results')
    os.makedirs(detection_results_dir, exist_ok=True)
    
    # 创建静态结果目录 (relative to controller_dir)
    static_results_dir = os.path.join(controller_dir, 'static', 'results')
    os.makedirs(static_results_dir, exist_ok=True)
    
    print(f"- 实例目录: {instance_dir}")
    print(f"- 检测结果目录: {detection_results_dir}")
    print(f"- 静态结果目录: {static_results_dir}")
    
    return True

def initialize_database_with_flask():
    """使用Flask应用上下文初始化数据库"""
    print("\n2. 使用Flask应用上下文初始化数据库...")
    
    try:
        # 导入Flask应用和数据库初始化函数
        from controller.main import app
        from controller.utils.database import init_db
        
        # 创建应用上下文并初始化数据库
        with app.app_context():
            print("- 在Flask应用上下文中初始化数据库")
            init_db()
            print("- 数据库初始化成功")
        
        return True
    except Exception as e:
        print(f"- 使用Flask应用上下文初始化数据库失败: {e}")
        traceback.print_exc()
        
        # 尝试直接初始化数据库
        return initialize_database_directly()

def initialize_database_directly():
    """直接初始化数据库和表结构"""
    print("- 尝试直接初始化数据库...")
    
    db_path = os.path.join(controller_dir, 'instance', 'video_streams.db') # Use controller_dir
    print(f"  数据库路径: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 创建视频流表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS video_streams (
                video_id TEXT PRIMARY KEY,
                stream_url TEXT NOT NULL,
                level TEXT NOT NULL,
                remarks TEXT,
                is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1))
            )
        """)
        
        # 创建检测结果表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS detection_results (
                result_id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                frame_path TEXT,
                detection_count INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (video_id) REFERENCES video_streams (video_id) ON DELETE CASCADE
            )
        """)
        
        # 创建检测对象详情表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS detection_objects (
                object_id INTEGER PRIMARY KEY AUTOINCREMENT,
                result_id INTEGER NOT NULL,
                class_id INTEGER NOT NULL,
                class_name TEXT NOT NULL,
                confidence REAL NOT NULL,
                bbox_x INTEGER NOT NULL,
                bbox_y INTEGER NOT NULL,
                bbox_width INTEGER NOT NULL,
                bbox_height INTEGER NOT NULL,
                detection_type TEXT NOT NULL DEFAULT 'primary',
                parent_class TEXT,
                parent_bbox TEXT,
                FOREIGN KEY (result_id) REFERENCES detection_results (result_id) ON DELETE CASCADE
            )
        """)
        
        # 启用外键约束
        cursor.execute("PRAGMA foreign_keys = ON")
        
        conn.commit()
        print("  数据库表结构初始化成功")
        
        conn.close()
        return True
    except Exception as e:
        print(f"  数据库初始化失败: {e}")
        traceback.print_exc()
        return False

def create_test_data():
    """创建测试数据"""
    print("\n3. 创建测试数据...")
    
    # 清理现有测试数据
    print("- 清理现有测试数据...")
    try:
        from scripts.clean_test_data import clean_test_data # Updated path
        clean_test_data(confirm=False) # Assuming direct call without confirmation
    except Exception as e:
        print(f"  清理测试数据失败: {e}")
        traceback.print_exc()
    
    # 生成测试图像
    print("- 生成测试图像...")
    try:
        from scripts.create_test_images import create_multiple_images # Updated path
        create_multiple_images(20)
    except Exception as e:
        print(f"  生成测试图像失败: {e}")
        traceback.print_exc()
    
    # 复制图像到静态目录
    print("- 复制图像到静态目录...")
    try:
        from scripts.copy_images import copy_detection_images # Updated path
        copy_detection_images()
    except Exception as e:
        print(f"  复制图像失败: {e}")
        traceback.print_exc()
    
    # 创建测试视频流记录
    print("- 创建测试视频流记录...")
    try:
        # 先创建视频流数据
        db_path = os.path.join(controller_dir, 'instance', 'video_streams.db') # Use controller_dir
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 清理已有视频流
        cursor.execute("DELETE FROM video_streams WHERE video_id LIKE 'TEST%'")
        
        # 创建5个测试视频流
        levels = ['高', '中', '低']
        for i in range(1, 6):
            video_id = f"TEST{i:03d}"
            stream_url = f"rtsp://example.com/stream{i}"
            level = levels[i % 3]
            remarks = f"测试视频流 {i}"
            
            cursor.execute("""
                INSERT INTO video_streams (video_id, stream_url, level, remarks, is_active)
                VALUES (?, ?, ?, ?, 1)
            """, (video_id, stream_url, level, remarks))
        
        conn.commit()
        print(f"  成功创建5个测试视频流")
        
        # 创建测试检测结果记录
        print("- 创建测试检测结果记录...")
        
        # 获取测试图像
        static_results_dir = os.path.join(controller_dir, 'static', 'results') # Use controller_dir
        images = [f for f in os.listdir(static_results_dir) if f.startswith('TEST') and f.endswith('.jpg')]
        
        if not images:
            print("  没有找到测试图像，跳过创建检测结果")
            return True
        
        # 为每个图像创建检测结果记录
        for img_file in images:
            # 从文件名解析视频ID
            parts = img_file.split('_')
            if len(parts) < 2:
                continue
                
            video_id = parts[0]
            # 使用带微秒的时间戳格式
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
            image_path = f"/static/results/{img_file}"
            detection_count = 3  # 每个图像创建3个检测对象
            
            # 插入检测结果记录
            cursor.execute("""
                INSERT INTO detection_results
                (video_id, timestamp, frame_path, detection_count)
                VALUES (?, ?, ?, ?)
            """, (video_id, timestamp, image_path, detection_count))
            
            result_id = cursor.lastrowid
            
            # 创建检测对象
            classes = ['person', 'car', 'bicycle', 'dog', 'cat']
            
            for i in range(detection_count):
                class_name = classes[i % len(classes)]
                class_id = i
                confidence = 0.85 + (i * 0.05)
                bbox_x = 50 + (i * 100)
                bbox_y = 50 + (i * 80)
                bbox_width = 100
                bbox_height = 80
                
                cursor.execute("""
                    INSERT INTO detection_objects
                    (result_id, class_id, class_name, confidence,
                     bbox_x, bbox_y, bbox_width, bbox_height,
                     detection_type, parent_class, parent_bbox)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    result_id, class_id, class_name, confidence,
                    bbox_x, bbox_y, bbox_width, bbox_height,
                    'primary', None, None
                ))
        
        conn.commit()
        conn.close()
        
        print(f"  成功为{len(images)}个图像创建了检测结果记录")
        return True
        
    except Exception as e:
        print(f"  创建测试数据记录失败: {e}")
        traceback.print_exc()
        return False

def verify_test_data():
    """验证测试数据"""
    print("\n4. 验证测试数据...")
    
    # 检查数据库表和记录
    db_path = os.path.join(controller_dir, 'instance', 'video_streams.db') # Use controller_dir
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 获取数据库中的表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"- 数据库中的表: {', '.join(tables)}")
        
        # 检查视频流表
        if 'video_streams' in tables:
            cursor.execute("SELECT COUNT(*) FROM video_streams WHERE video_id LIKE 'TEST%'")
            streams_count = cursor.fetchone()[0]
            print(f"- 视频流记录: {streams_count}条")
        else:
            print("- 视频流表不存在")
        
        # 检查检测结果表
        if 'detection_results' in tables:
            cursor.execute("SELECT COUNT(*) FROM detection_results WHERE video_id LIKE 'TEST%'")
            results_count = cursor.fetchone()[0]
            print(f"- 检测结果记录: {results_count}条")
        else:
            print("- 检测结果表不存在")
        
        # 检查检测对象表
        if 'detection_objects' in tables:
            cursor.execute("""
                SELECT COUNT(*) FROM detection_objects 
                WHERE result_id IN (SELECT result_id FROM detection_results WHERE video_id LIKE 'TEST%')
            """)
            objects_count = cursor.fetchone()[0]
            print(f"- 检测对象记录: {objects_count}条")
        else:
            print("- 检测对象表不存在")
        
        conn.close()
        
    except Exception as e:
        print(f"- 检查数据库记录失败: {e}")
        traceback.print_exc()
    
    # 检查图像文件
    detection_results_dir = os.path.join(controller_dir, 'instance', 'detection_results') # Use controller_dir
    static_results_dir = os.path.join(controller_dir, 'static', 'results') # Use controller_dir
    
    detection_images = []
    static_images = []
    
    if os.path.exists(detection_results_dir):
        detection_images = [f for f in os.listdir(detection_results_dir) if f.startswith('TEST') and f.endswith('.jpg')]
    
    if os.path.exists(static_results_dir):
        static_images = [f for f in os.listdir(static_results_dir) if f.startswith('TEST') and f.endswith('.jpg')]
    
    print(f"- 检测结果目录中的图像文件: {len(detection_images)}个")
    print(f"- 静态目录中的图像文件: {len(static_images)}个")
    
    return True

def main():
    """主函数"""
    print("=== 开始初始化测试环境 ===")
    
    # 设置目录结构
    if not setup_directories():
        print("目录设置失败，终止初始化")
        return 1
    
    # 初始化数据库
    if not initialize_database_with_flask():
        print("数据库初始化失败，终止初始化")
        return 1
    
    # 创建测试数据
    create_test_data()
    
    # 验证测试数据
    verify_test_data()
    
    print("\n=== 测试环境初始化完成 ===")
    print("您现在可以运行 python main.py 启动应用程序")
    return 0

if __name__ == "__main__":
    sys.exit(main()) 