"""
清理测试数据
用于清除检测结果相关的数据，便于重新开始测试
"""

import os
import sys
import shutil
import sqlite3
from pathlib import Path

# 添加当前目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# 引入Flask应用以获取正确的上下文
from main import app

def clean_test_data(video_id=None, clean_images=True, clean_db=True, confirm=True):
    """清理测试数据
    
    Args:
        video_id: 要清理的视频ID，为None则清理所有
        clean_images: 是否清理图像文件
        clean_db: 是否清理数据库记录
        confirm: 是否需要用户确认
    
    Returns:
        bool: 是否成功清理
    """
    if confirm:
        if video_id:
            print(f"即将清理视频ID: {video_id} 的数据!")
        else:
            print("即将清理所有检测结果数据!")
            
        choice = input("确定要继续吗? (y/n): ").strip().lower()
        if choice != 'y':
            print("操作已取消")
            return False
    
    # 获取基础路径
    base_dir = current_dir
    
    # 清理图像文件
    if clean_images:
        # 定义需要清理的目录
        instance_results_dir = Path(base_dir) / "instance" / "detection_results"
        static_results_dir = Path(base_dir) / "static" / "results"
        
        dirs_to_clean = [instance_results_dir, static_results_dir]
        
        for dir_path in dirs_to_clean:
            if not dir_path.exists():
                print(f"目录不存在，跳过: {dir_path}")
                continue
                
            print(f"清理目录: {dir_path}")
            try:
                # 如果指定了视频ID，只删除该ID的图像
                if video_id:
                    pattern = f"{video_id}_*.jpg"
                    files_to_delete = list(dir_path.glob(pattern))
                    print(f"找到 {len(files_to_delete)} 个匹配 '{video_id}' 的文件")
                    
                    for file_path in files_to_delete:
                        try:
                            file_path.unlink()
                            print(f"已删除: {file_path.name}")
                        except Exception as e:
                            print(f"无法删除 {file_path.name}: {e}")
                else:
                    # 删除目录中的所有文件
                    for file_path in dir_path.glob("*.jpg"):
                        try:
                            file_path.unlink()
                        except Exception as e:
                            print(f"无法删除 {file_path.name}: {e}")
                    
                    print(f"已清空目录: {dir_path}")
            except Exception as e:
                print(f"清理目录时出错: {e}")
    
    # 清理数据库记录
    if clean_db:
        # 获取数据库路径
        db_path = Path(base_dir) / "instance" / "video_streams.db"
        if not db_path.exists():
            print(f"数据库不存在: {db_path}")
            return False
        
        print(f"清理数据库: {db_path}")
        
        try:
            # 连接数据库
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # 开始事务
            conn.execute("BEGIN TRANSACTION")
            
            # 删除检测对象记录
            if video_id:
                # 先查询匹配的结果ID
                cursor.execute(
                    "SELECT result_id FROM detection_results WHERE video_id = ?",
                    (video_id,)
                )
                result_ids = [row[0] for row in cursor.fetchall()]
                
                if result_ids:
                    # 将ID列表格式化为SQL IN子句
                    ids_str = ','.join('?' for _ in result_ids)
                    
                    # 删除检测对象
                    cursor.execute(
                        f"DELETE FROM detection_objects WHERE result_id IN ({ids_str})",
                        result_ids
                    )
                    
                    # 删除检测结果
                    cursor.execute(
                        f"DELETE FROM detection_results WHERE result_id IN ({ids_str})",
                        result_ids
                    )
                    
                    # 删除视频流（可选）
                    if input(f"是否也删除视频ID '{video_id}' 的记录? (y/n): ").strip().lower() == 'y':
                        cursor.execute(
                            "DELETE FROM video_streams WHERE video_id = ?",
                            (video_id,)
                        )
                        
                    # 提交事务
                    conn.commit()
                    print(f"已删除视频ID '{video_id}' 相关的 {len(result_ids)} 条检测结果记录")
                else:
                    print(f"未找到视频ID '{video_id}' 的检测结果记录")
                    conn.rollback()
            else:
                # 删除所有检测对象和结果
                cursor.execute("DELETE FROM detection_objects")
                cursor.execute("DELETE FROM detection_results")
                
                # 询问是否删除视频流配置
                if input("是否也删除所有视频流配置? (y/n): ").strip().lower() == 'y':
                    cursor.execute("DELETE FROM video_streams")
                
                # 提交事务
                conn.commit()
                print("已删除所有检测结果记录")
                
            # 关闭连接
            conn.close()
            
        except Exception as e:
            import traceback
            print(f"清理数据库时出错: {e}")
            traceback.print_exc()
            return False
    
    print("数据清理完成！")
    return True

def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='清理测试数据')
    parser.add_argument('--video-id', type=str, help='要清理的视频ID，不指定则清理所有')
    parser.add_argument('--no-images', action='store_true', help='不清理图像文件')
    parser.add_argument('--no-db', action='store_true', help='不清理数据库记录')
    parser.add_argument('--force', action='store_true', help='跳过确认直接清理')
    
    args = parser.parse_args()
    
    # 确保Flask应用上下文可用
    with app.app_context():
        success = clean_test_data(
            video_id=args.video_id,
            clean_images=not args.no_images,
            clean_db=not args.no_db,
            confirm=not args.force
        )
    
    if success:
        print("清理操作成功完成")
        return 0
    else:
        print("清理操作失败或被取消")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 