"""
创建测试检测图像
生成简单的测试检测图像并保存到静态目录
"""

import os
import cv2
import numpy as np
import random
import shutil

# 确保路径使用英文，避免中文路径问题
RESULTS_DIR = os.path.join('static', 'results')

def ensure_dir(directory):
    """确保目录存在"""
    try:
        os.makedirs(directory, exist_ok=True)
        print(f"目录已就绪: {directory}")
        return True
    except Exception as e:
        print(f"创建目录失败: {e}")
        return False

def create_test_image(width=640, height=480, filename=None):
    """创建测试图像并保存
    
    Args:
        width: 图像宽度
        height: 图像高度
        filename: 文件名，如果为None则自动生成
        
    Returns:
        str: 保存的文件路径，失败返回None
    """
    try:
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
        
        # 添加检测框和标签
        for i in range(random.randint(1, 4)):
            x = random.randint(50, width-150)
            y = random.randint(50, height-150)
            w = random.randint(60, 150)
            h = random.randint(60, 150)
            
            # 检测框
            cv2.rectangle(img, (x, y), (x+w, y+h), (0, 255, 0), 2)
            
            # 标签
            classes = ['person', 'car', 'bicycle', 'dog', 'cat']
            class_name = random.choice(classes)
            confidence = random.uniform(0.6, 0.98)
            label = f"{class_name} {confidence:.2f}"
            
            cv2.putText(img, label, (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        
        # 生成文件名和路径
        if not filename:
            video_id = f"TEST{random.randint(1, 5):03d}"
            timestamp = random.randint(10000000, 99999999)
            filename = f"{video_id}_{timestamp}.jpg"
        
        filepath = os.path.join(RESULTS_DIR, filename)
        
        # 保存图像
        result = cv2.imwrite(filepath, img)
        if not result:
            print(f"保存图像失败: {filepath}")
            return None
        
        print(f"已保存图像: {filepath}")
        return filepath
        
    except Exception as e:
        print(f"创建图像出错: {e}")
        return None

def create_multiple_images(count=20):
    """创建多张测试图像
    
    Args:
        count: 创建的图像数量
    """
    # 确保结果目录存在
    if not ensure_dir(RESULTS_DIR):
        return
    
    # 生成多张图像
    success_count = 0
    for i in range(count):
        filepath = create_test_image()
        if filepath:
            success_count += 1
    
    print(f"成功创建 {success_count}/{count} 张测试图像")

def main():
    """主函数"""
    print("开始创建测试图像...")
    create_multiple_images(20)
    print("测试图像创建完成！")
    
    # 统计图像文件
    if os.path.exists(RESULTS_DIR):
        image_files = [f for f in os.listdir(RESULTS_DIR) if f.endswith('.jpg')]
        print(f"结果目录中有 {len(image_files)} 个图像文件")

if __name__ == "__main__":
    main() 