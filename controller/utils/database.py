import sqlite3
import os
import click
from flask import current_app, g
from flask.cli import with_appcontext

# 数据库文件的路径，存储在 Flask 实例文件夹中
# 实例文件夹是存放应用运行时产生的数据的地方，例如数据库文件、上传的文件等。
# 它应该在项目根目录之外，或者至少不被版本控制跟踪。
DATABASE_FILENAME = 'video_streams.db'

def get_instance_path():
    """获取实例文件夹路径
    Flask 会自动在应用实例文件夹下寻找数据库。对于直接运行时的情况，
    我们需要确保返回 controller/instance 路径
    """
    try:
        # 在应用上下文中，返回当前应用的 instance_path
        return current_app.instance_path
    except RuntimeError:
        # 不在应用上下文中时，手动构建路径
        # 假设我们的脚本位于 controller/utils 下
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        return os.path.join(base_dir, 'instance')

def get_database_path():
    instance_path = get_instance_path()
    return os.path.join(instance_path, DATABASE_FILENAME)

def get_db_connection():
    """获取数据库连接，如果当前上下文中不存在则创建"""
    if 'db' not in g:
        db_path = get_database_path()
        # 确保实例文件夹存在
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        g.db = sqlite3.connect(
            db_path,
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row # 允许通过列名访问数据
    return g.db

def close_db_connection(e=None):
    """关闭数据库连接"""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    """初始化数据库：创建表结构 (如果尚不存在)"""
    db = get_db_connection()
    try:
        # 尝试从应用资源加载 schema (如果存在)
        # with current_app.open_resource('schema.sql') as f:
        #     db.executescript(f.read().decode('utf8'))
        # print("Database schema loaded and tables created if they didn't exist.")
        
        # 直接执行SQL创建表
        print("Creating tables directly if they don't exist.")
        cursor = db.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS video_streams (
                video_id TEXT PRIMARY KEY,
                stream_url TEXT NOT NULL,
                level TEXT NOT NULL,
                remarks TEXT,
                is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1))
            );
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
            );
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
            );
        """)
        
        # 设置外键约束
        cursor.execute("PRAGMA foreign_keys = ON;")
        
        db.commit()
        print("Tables created successfully.")

    except Exception as e:
        print(f"Error during DB initialization: {e}")
        # raise # 开发时可以不重新抛出，避免中断应用，但生产环境应考虑

@click.command('init-db')
@with_appcontext
def init_db_command():
    """CLI 命令：flask init-db，用于初始化数据库"""
    init_db()
    click.echo('Initialized the database.')

def init_app(app):
    """注册数据库相关功能到 Flask 应用实例"""
    # 确保实例文件夹存在
    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:
        pass # 可能由于权限问题等原因无法创建，连接时会再次尝试

    app.teardown_appcontext(close_db_connection) # 应用上下文销毁时自动关闭连接
    app.cli.add_command(init_db_command)       # 添加 init-db CLI 命令

    # 打印数据库路径，方便确认
    with app.app_context(): # 需要应用上下文来调用get_database_path
        db_path_info = get_database_path()
        print(f"Database will be stored at: {db_path_info}")
    
    # 应用启动时自动初始化数据库表（如果它们不存在）
    with app.app_context():
        db_path = get_database_path()
        if not os.path.exists(db_path) or os.path.getsize(db_path) == 0:
            print(f"Database file not found or empty at {db_path}. Initializing new database.")
            init_db()
        else:
            # 即使数据库文件存在，也确保表结构是正确的
            print(f"Database file found at {db_path}. Ensuring tables exist...")
            init_db() # 这会确保表存在，如果不存在则创建 