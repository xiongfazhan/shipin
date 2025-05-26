"""
图像同步工具
将检测结果图像从实例目录复制到静态目录，使其可通过Web访问
"""

import os
import shutil
import time
import sys
from pathlib import Path
import traceback

def copy_detection_images():
    """将检测结果图像从实例目录复制到静态目录"""
    # 获取基础路径
    try:
        base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
        
        # 源目录和目标目录
        source_dir = os.path.join(base_dir, 'instance', 'detection_results')
        target_dir = os.path.join(base_dir, 'static', 'results')
        
        print(f"源目录: {source_dir}")
        print(f"目标目录: {target_dir}")
        
        # 确保目标目录存在
        os.makedirs(target_dir, exist_ok=True)
        
        # 检查源目录是否存在
        if not os.path.exists(source_dir):
            print(f"源目录不存在: {source_dir}")
            return False
        
        # 获取源目录中的所有文件
        try:
            # 使用Path对象处理路径，更好支持中文和特殊字符
            source_path = Path(source_dir)
            source_files = list(source_path.glob('*.jpg'))
            print(f"源目录中有 {len(source_files)} 个图像文件")
            
            if len(source_files) == 0:
                # 尝试直接列出目录内容进行诊断
                print("尝试列出源目录内容...")
                try:
                    all_files = list(os.listdir(source_dir))
                    print(f"源目录中所有文件: {all_files}")
                except Exception as list_error:
                    print(f"列出目录内容失败: {list_error}")
        except Exception as e:
            print(f"列出源目录文件时出错: {e}")
            traceback.print_exc()
            return False
        
        # 复制新文件
        copy_count = 0
        for source_file in source_files:
            # 获取文件名
            filename = source_file.name
            target_file = Path(target_dir) / filename
            
            # 如果目标文件不存在或源文件较新，则复制
            if not target_file.exists() or source_file.stat().st_mtime > target_file.stat().st_mtime:
                try:
                    # 使用shutil代替手动复制，处理权限和中文路径问题
                    shutil.copy2(source_file, target_file)
                    print(f"已复制: {filename}")
                    copy_count += 1
                except Exception as e:
                    print(f"复制文件 {filename} 时出错: {e}")
                    traceback.print_exc()
                    
                    # 尝试备用方法 - 二进制读写
                    try:
                        print(f"尝试使用二进制方式复制: {filename}")
                        with open(str(source_file), 'rb') as src_file:
                            with open(str(target_file), 'wb') as dst_file:
                                dst_file.write(src_file.read())
                        print(f"二进制方式复制成功: {filename}")
                        copy_count += 1
                    except Exception as e2:
                        print(f"备用复制方法也失败: {e2}")
        
        print(f"已复制 {copy_count} 个新图像文件到 {target_dir}")
        
        # 列出目标目录中的文件数量
        try:
            target_path = Path(target_dir)
            target_files = list(target_path.glob('*.jpg'))
            print(f"目标目录中有 {len(target_files)} 个图像文件")
        except Exception as e:
            print(f"列出目标目录文件时出错: {e}")
            traceback.print_exc()
        
        # 如果没有复制到任何文件但源目录有文件，则可能是路径问题
        if copy_count == 0 and len(source_files) > 0:
            print("警告: 未能复制任何文件，尽管源目录中有文件。可能存在路径解析问题。")
            print("尝试直接检查文件是否存在...")
            for source_file in source_files:
                print(f"检查文件: {source_file}")
                if os.path.exists(str(source_file)):
                    print(f"  文件存在")
                    print(f"  文件大小: {os.path.getsize(str(source_file))} 字节")
                else:
                    print(f"  文件不存在")
        
        return True
    except Exception as e:
        print(f"图像复制过程出错: {e}")
        traceback.print_exc()
        return False

def run_sync_loop(interval=10):
    """运行持续同步循环"""
    print(f"启动图像同步循环，间隔: {interval}秒")
    
    try:
        while True:
            copy_detection_images()
            time.sleep(interval)
    except KeyboardInterrupt:
        print("同步服务已停止")
    except Exception as e:
        print(f"同步过程中出错: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    # 检查命令行参数
    if len(sys.argv) > 1 and sys.argv[1] == "--daemon":
        # 后台模式，持续运行
        interval = 10  # 默认10秒
        if len(sys.argv) > 2:
            try:
                interval = int(sys.argv[2])
            except ValueError:
                pass
        run_sync_loop(interval)
    else:
        # 单次运行模式
        copy_detection_images() 