"""
测试数据生成器
生成模拟的视频流和检测结果数据，用于测试系统功能
"""

import os
import sqlite3
import random
import cv2
import numpy as np
from datetime import datetime, timedelta
import time
from pathlib import Path

def get_db_path():
    """获取数据库文件路径"""
    base_dir = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    return base_dir / 'instance' / 'video_streams.db'

def get_detection_results_dir():
    """获取检测结果图像保存目录"""
    base_dir = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    detection_dir = base_dir / 'instance' / 'detection_results'
    detection_dir.mkdir(exist_ok=True, parents=True)
    return detection_dir

def create_test_video_streams(count=5):
    """创建测试视频流数据"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 插入前检查是否已有测试数据
    cursor.execute("SELECT COUNT(*) FROM video_streams WHERE video_id LIKE 'TEST%'")
    existing_count = cursor.fetchone()[0]
    
    if existing_count >= count:
        print(f"已存在 {existing_count} 条测试视频流数据，跳过创建")
        conn.close()
        return
    
    # 风险等级
    levels = ['高', '中', '低']
    # 视频流协议
    protocols = ['rtsp://', 'rtmp://', 'http://']
    # 模拟服务器域名
    servers = ['camera1.example.com', 'video.test.org', 'stream.company.net', 
               'surveillance.local', 'cctv.monitor.com']
    
    # 生成测试数据
    for i in range(existing_count, count):
        video_id = f"TEST{i+1:03d}"
        protocol = random.choice(protocols)
        server = random.choice(servers)
        path = f"/live/stream{i+1}"
        level = random.choice(levels)
        remarks = f"测试视频流 {i+1}"
        stream_url = f"{protocol}{server}{path}"
        
        try:
            cursor.execute("""
                INSERT INTO video_streams (video_id, stream_url, level, remarks, is_active)
                VALUES (?, ?, ?, ?, 1)
            """, (video_id, stream_url, level, remarks))
        except sqlite3.IntegrityError:
            # 如果ID已存在，跳过
            continue
    
    conn.commit()
    print(f"已创建 {count - existing_count} 条测试视频流数据")
    conn.close()

def generate_test_frame(width=640, height=480):
    """生成测试图像帧"""
    # 创建黑色背景
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    
    # 添加一些随机颜色的矩形作为背景
    for _ in range(5):
        x1 = random.randint(0, width-100)
        y1 = random.randint(0, height-100)
        x2 = x1 + random.randint(50, 100)
        y2 = y1 + random.randint(50, 100)
        color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, -1)
    
    # 添加一些文本
    cv2.putText(frame, "测试图像", (width//2-50, height//2), 
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    
    return frame

def create_test_detection_results(count=50):
    """创建测试检测结果数据"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 获取所有测试视频流ID
    cursor.execute("SELECT video_id FROM video_streams WHERE video_id LIKE 'TEST%'")
    video_ids = [row[0] for row in cursor.fetchall()]
    
    if not video_ids:
        print("未找到测试视频流数据，请先创建视频流")
        conn.close()
        return
    
    # 目标类别
    classes = ['person', 'car', 'bicycle', 'dog', 'cat', 'truck', 'bus', 'chair', 'sofa', 'bottle']
    
    # 检查已存在的测试检测结果数量
    cursor.execute("""
        SELECT COUNT(*) FROM detection_results 
        WHERE video_id LIKE 'TEST%'
    """)
    existing_count = cursor.fetchone()[0]
    
    if existing_count >= count:
        print(f"已存在 {existing_count} 条测试检测结果数据，跳过创建")
        conn.close()
        return
    
    detection_dir = get_detection_results_dir()
    print(f"检测结果图像将保存到: {detection_dir}")
    
    # 确保目录存在
    os.makedirs(detection_dir, exist_ok=True)
    
    # 生成过去7天内的随机时间戳
    now = datetime.now()
    
    created_count = 0
    
    for i in range(existing_count, count):
        video_id = random.choice(video_ids)
        # 生成过去7天内的随机时间戳
        days_ago = random.randint(0, 7)
        hours_ago = random.randint(0, 23)
        minutes_ago = random.randint(0, 59)
        seconds_ago = random.randint(0, 59)
        timestamp = now - timedelta(days=days_ago, hours=hours_ago, minutes=minutes_ago, seconds=seconds_ago)
        timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")
        
        # 每个结果生成1-5个检测对象
        detection_count = random.randint(1, 5)
        
        # 生成图像文件名
        file_timestamp = timestamp.strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{video_id}_{file_timestamp}.jpg"
        filepath = os.path.join(str(detection_dir), filename)
        
        # 生成测试图像并添加一些矩形，模拟检测框
        frame = generate_test_frame(640, 480)
        
        # 保存图像
        try:
            print(f"保存图像到: {filepath}")
            cv2.imwrite(filepath, frame)
            if not os.path.exists(filepath):
                print(f"警告: 文件 {filepath} 未成功保存")
                continue
        except Exception as e:
            print(f"保存图像失败: {e}")
            continue
        
        # 图像保存成功后，插入检测结果记录
        cursor.execute("""
            INSERT INTO detection_results 
            (video_id, timestamp, frame_path, detection_count)
            VALUES (?, ?, ?, ?)
        """, (video_id, timestamp_str, filepath, detection_count))
        
        result_id = cursor.lastrowid
        
        # 生成并插入检测对象详情
        for j in range(detection_count):
            class_id = random.randint(0, len(classes)-1)
            class_name = classes[class_id]
            confidence = random.uniform(0.5, 0.99)
            
            # 生成随机边界框
            bbox_x = random.randint(50, 500)
            bbox_y = random.randint(50, 350)
            bbox_width = random.randint(50, 120)
            bbox_height = random.randint(50, 100)
            
            # 在图像上绘制检测框
            color = (0, 255, 0) if j % 2 == 0 else (255, 0, 0)  # 绿色或蓝色
            cv2.rectangle(frame, (bbox_x, bbox_y), (bbox_x + bbox_width, bbox_y + bbox_height), color, 2)
            
            # 绘制标签
            label = f"{class_name} {confidence:.2f}"
            cv2.putText(frame, label, (bbox_x, bbox_y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
            
            # 是否为二次检测
            detection_type = 'primary' if j % 3 != 0 else 'secondary'
            
            # 插入检测对象记录
            cursor.execute("""
                INSERT INTO detection_objects
                (result_id, class_id, class_name, confidence, 
                 bbox_x, bbox_y, bbox_width, bbox_height,
                 detection_type, parent_class, parent_bbox)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result_id, class_id, class_name, confidence, 
                bbox_x, bbox_y, bbox_width, bbox_height,
                detection_type, None if detection_type == 'primary' else 'furniture',
                None if detection_type == 'primary' else '[100, 100, 300, 200]'
            ))
        
        # 保存带检测框的图像
        try:
            cv2.imwrite(filepath, frame)
        except Exception as e:
            print(f"更新带检测框图像失败: {e}")
        
        created_count += 1
        
        # 显示进度
        if (i + 1) % 10 == 0:
            print(f"已生成 {i + 1} 条测试检测结果...")
            conn.commit()
        
        # 添加小延迟，避免时间戳完全相同
        time.sleep(0.01)
    
    conn.commit()
    print(f"已创建 {created_count} 条测试检测结果数据和图像")
    conn.close()

def main():
    """主函数"""
    print("开始生成测试数据...")
    
    # 创建测试视频流
    create_test_video_streams(5)
    
    # 创建测试检测结果
    create_test_detection_results(50)
    
    print("测试数据生成完成！")
    
    # 复制图像到静态目录
    from .copy_images import copy_detection_images
    copy_detection_images()
    
    # 列出文件以检查
    detection_dir = get_detection_results_dir()
    files = list(detection_dir.glob('*.jpg'))
    print(f"检测结果目录中有 {len(files)} 个图像文件")

if __name__ == "__main__":
    main() 