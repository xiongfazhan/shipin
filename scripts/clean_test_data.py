"""
清理测试数据
删除之前生成的测试数据，以便重新开始测试
"""

import sqlite3
import os
from pathlib import Path

def get_db_path():
    """获取数据库文件路径"""
    base_dir = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    return base_dir / 'instance' / 'video_streams.db'

def clean_test_data():
    """清理测试数据"""
    db_path = get_db_path()
    
    if not os.path.exists(db_path):
        print(f"数据库文件不存在: {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 查询测试视频流数量
        cursor.execute("SELECT COUNT(*) FROM video_streams WHERE video_id LIKE 'TEST%'")
        video_count = cursor.fetchone()[0]
        
        # 查询测试检测结果数量
        cursor.execute("SELECT COUNT(*) FROM detection_results WHERE video_id LIKE 'TEST%'")
        result_count = cursor.fetchone()[0]
        
        # 删除测试检测对象
        cursor.execute("""
            DELETE FROM detection_objects 
            WHERE result_id IN (
                SELECT result_id FROM detection_results WHERE video_id LIKE 'TEST%'
            )
        """)
        
        # 删除测试检测结果
        cursor.execute("DELETE FROM detection_results WHERE video_id LIKE 'TEST%'")
        
        # 删除测试视频流
        cursor.execute("DELETE FROM video_streams WHERE video_id LIKE 'TEST%'")
        
        conn.commit()
        
        print(f"已删除 {video_count} 条测试视频流数据")
        print(f"已删除 {result_count} 条测试检测结果数据")
        
    except Exception as e:
        print(f"清理数据库失败: {e}")
    
    conn.close()
    
    # 清理检测结果图像
    detection_dir = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) / 'instance' / 'detection_results'
    if detection_dir.exists():
        test_images = list(detection_dir.glob('TEST*.jpg'))
        for img in test_images:
            try:
                os.remove(img)
            except Exception as e:
                print(f"删除图像 {img} 失败: {e}")
        
        print(f"已删除 {len(test_images)} 个测试图像")
    
    # 清理静态结果目录中的测试图像
    static_dir = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) / 'static' / 'results'
    if static_dir.exists():
        static_test_images = list(static_dir.glob('TEST*.jpg'))
        for img in static_test_images:
            try:
                os.remove(img)
            except Exception as e:
                print(f"删除静态图像 {img} 失败: {e}")
        
        print(f"已删除 {len(static_test_images)} 个静态测试图像")

if __name__ == "__main__":
    print("开始清理测试数据...")
    clean_test_data()
    print("测试数据清理完成！") 