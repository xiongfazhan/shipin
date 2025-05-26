"""
简易测试数据生成器
使用简化路径和方法生成测试数据
"""

import os
import sqlite3
import random
import cv2
import numpy as np
from datetime import datetime, timedelta
import time

# 绝对路径
BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'instance', 'video_streams.db')
DETECTION_RESULTS_DIR = os.path.join(BASE_DIR, 'instance', 'detection_results')
STATIC_RESULTS_DIR = os.path.join(BASE_DIR, 'static', 'results')

def create_directories():
    """创建必要的目录"""
    os.makedirs(DETECTION_RESULTS_DIR, exist_ok=True)
    os.makedirs(STATIC_RESULTS_DIR, exist_ok=True)
    
    print(f"已创建检测结果目录: {DETECTION_RESULTS_DIR}")
    print(f"已创建静态结果目录: {STATIC_RESULTS_DIR}")

def clear_test_data():
    """清除测试数据"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
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
    conn.close()
    
    # 清除图像文件
    for f in os.listdir(DETECTION_RESULTS_DIR):
        if f.startswith('TEST') and f.endswith('.jpg'):
            os.remove(os.path.join(DETECTION_RESULTS_DIR, f))
    
    for f in os.listdir(STATIC_RESULTS_DIR):
        if f.startswith('TEST') and f.endswith('.jpg'):
            os.remove(os.path.join(STATIC_RESULTS_DIR, f))
    
    print("测试数据已清除")

def create_test_video_streams(count=5):
    """创建测试视频流数据"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 风险等级
    levels = ['高', '中', '低']
    
    # 生成测试数据
    for i in range(count):
        video_id = f"TEST{i+1:03d}"
        stream_url = f"rtsp://example.com/stream{i+1}"
        level = random.choice(levels)
        remarks = f"测试视频流 {i+1}"
        
        try:
            cursor.execute("""
                INSERT INTO video_streams (video_id, stream_url, level, remarks, is_active)
                VALUES (?, ?, ?, ?, 1)
            """, (video_id, stream_url, level, remarks))
        except sqlite3.IntegrityError:
            # 如果ID已存在，跳过
            pass
    
    conn.commit()
    conn.close()
    
    print(f"已创建 {count} 条测试视频流数据")

def create_test_image(width=640, height=480):
    """创建测试图像"""
    # 创建黑色背景
    img = np.zeros((height, width, 3), dtype=np.uint8)
    
    # 添加一些随机彩色矩形
    for _ in range(5):
        x1 = random.randint(0, width-100)
        y1 = random.randint(0, height-100)
        x2 = x1 + random.randint(50, 150)
        y2 = y1 + random.randint(50, 150)
        color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
        cv2.rectangle(img, (x1, y1), (x2, y2), color, -1)
    
    # 添加文本
    cv2.putText(img, "Test Image", (width//2-50, height//2), 
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    
    return img

def create_test_detection_results(count=20):
    """创建测试检测结果数据"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 获取所有测试视频流ID
    cursor.execute("SELECT video_id FROM video_streams WHERE video_id LIKE 'TEST%'")
    video_ids = [row[0] for row in cursor.fetchall()]
    
    if not video_ids:
        print("未找到测试视频流数据，请先创建视频流")
        conn.close()
        return
    
    # 目标类别
    classes = ['person', 'car', 'bicycle', 'dog', 'cat']
    
    # 当前时间
    now = datetime.now()
    
    # 生成检测结果
    for i in range(count):
        # 选择一个视频ID
        video_id = random.choice(video_ids)
        
        # 生成过去7天内的随机时间
        days_ago = random.randint(0, 7)
        random_time = now - timedelta(days=days_ago, 
                                      hours=random.randint(0, 23),
                                      minutes=random.randint(0, 59),
                                      seconds=random.randint(0, 59))
        
        # 生成不同的时间戳格式
        db_timestamp = random_time.strftime("%Y-%m-%d %H:%M:%S.%f")
        file_timestamp = random_time.strftime("%Y%m%d_%H%M%S")
        
        # 创建唯一的图像文件名
        image_filename = f"{video_id}_{file_timestamp}_{i}.jpg"
        image_path = os.path.join(DETECTION_RESULTS_DIR, image_filename)
        
        # 检测对象数量
        objects_count = random.randint(1, 4)
        
        # 创建基础图像
        img = create_test_image()
        
        # 保存图像
        try:
            cv2.imwrite(image_path, img)
            if not os.path.exists(image_path):
                print(f"警告: 图像创建失败: {image_path}")
                continue
        except Exception as e:
            print(f"图像创建失败: {e}")
            continue
        
        # 插入检测结果记录
        cursor.execute("""
            INSERT INTO detection_results 
            (video_id, timestamp, frame_path, detection_count)
            VALUES (?, ?, ?, ?)
        """, (video_id, db_timestamp, image_path, objects_count))
        
        result_id = cursor.lastrowid
        
        # 在图像上添加检测框并创建检测对象记录
        for j in range(objects_count):
            # 随机选择类别
            class_name = random.choice(classes)
            class_id = classes.index(class_name)
            confidence = random.uniform(0.6, 0.98)
            
            # 生成随机边界框
            x = random.randint(50, 550)
            y = random.randint(50, 390)
            w = random.randint(40, 150)
            h = random.randint(40, 120)
            
            # 在图像上绘制检测框
            color = (0, 255, 0)  # 绿色
            cv2.rectangle(img, (x, y), (x+w, y+h), color, 2)
            
            # 添加标签
            label = f"{class_name} {confidence:.2f}"
            cv2.putText(img, label, (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
            
            # 插入检测对象记录
            cursor.execute("""
                INSERT INTO detection_objects
                (result_id, class_id, class_name, confidence, 
                 bbox_x, bbox_y, bbox_width, bbox_height,
                 detection_type, parent_class, parent_bbox)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result_id, class_id, class_name, confidence, 
                x, y, w, h,
                'primary', None, None
            ))
        
        # 保存带检测框的图像
        cv2.imwrite(image_path, img)
        
        # 复制图像到静态目录
        static_path = os.path.join(STATIC_RESULTS_DIR, image_filename)
        try:
            with open(image_path, 'rb') as src, open(static_path, 'wb') as dst:
                dst.write(src.read())
        except Exception as e:
            print(f"复制图像到静态目录失败: {e}")
        
        # 每10个显示进度
        if (i + 1) % 5 == 0:
            print(f"已创建 {i+1}/{count} 条测试检测结果")
            conn.commit()
    
    conn.commit()
    conn.close()
    
    print(f"成功创建 {count} 条测试检测结果，并保存图像")
    
    # 检查图像文件数量
    detection_files = [f for f in os.listdir(DETECTION_RESULTS_DIR) if f.startswith('TEST') and f.endswith('.jpg')]
    static_files = [f for f in os.listdir(STATIC_RESULTS_DIR) if f.startswith('TEST') and f.endswith('.jpg')]
    
    print(f"检测结果目录中有 {len(detection_files)} 个图像文件")
    print(f"静态目录中有 {len(static_files)} 个图像文件")

def main():
    """主函数"""
    print("开始创建简化版测试数据...")
    
    # 创建目录结构
    create_directories()
    
    # 清除旧的测试数据
    clear_test_data()
    
    # 创建测试视频流
    create_test_video_streams(5)
    
    # 创建测试检测结果
    create_test_detection_results(20)
    
    print("测试数据创建完成!")

if __name__ == "__main__":
    main() 