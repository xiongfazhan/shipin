"""
数据库初始化脚本
在Flask应用上下文中初始化数据库结构
"""

from main import app
from utils.database import init_db

def main():
    """主函数：在应用上下文中初始化数据库"""
    print("开始初始化数据库...")
    with app.app_context():
        init_db()
    print("数据库初始化完成！")

if __name__ == "__main__":
    main() 