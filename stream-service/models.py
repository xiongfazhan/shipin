from __future__ import annotations

"""SQLAlchemy 数据模型 - Stream Service 持久化层
负责定义数据库表结构以及会话管理工具函数。
"""

import os
import datetime as _dt
from typing import Optional

from sqlalchemy import (
    Column,
    String,
    Text,
    Enum,
    DateTime,
    Integer,
    create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session

# 基础类
Base = declarative_base()


class Stream(Base):
    """视频流配置表"""

    __tablename__ = "streams"

    stream_id = Column(String, primary_key=True)  # 主键
    name = Column(String, nullable=False)
    url = Column(Text, nullable=False)
    risk_level = Column(String, default="中")  # 保持与前端一致的中文枚举
    description = Column(Text, nullable=True)
    type = Column(String, default="http")  # 例如 http / rtsp / file / camera
    push_endpoint = Column(String, nullable=True)
    push_type = Column(String, nullable=True)
    push_port = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=_dt.datetime.utcnow)
    updated_at = Column(
        DateTime,
        default=_dt.datetime.utcnow,
        onupdate=_dt.datetime.utcnow,
        nullable=False,
    )

    def as_dict(self):
        # 将SQLAlchemy对象转换为字典，便于序列化
        return {
            "stream_id": self.stream_id,
            "name": self.name,
            "url": self.url,
            "risk_level": self.risk_level,
            "description": self.description,
            "type": self.type,
            "push_endpoint": self.push_endpoint,
            "push_type": self.push_type,
            "push_port": self.push_port,
            "created_at": self.created_at.timestamp() if self.created_at else None,
            "updated_at": self.updated_at.timestamp() if self.updated_at else None,
        }


# 数据库初始化工具 ---------------------------------------------------------

def init_engine(db_path: str | None = None):
    """初始化并返回 SQLAlchemy engine & Session 工厂。

    如果未提供 db_path，则默认在当前工作目录创建 streams.db。
    """
    if not db_path:
        db_path = os.path.join(os.path.dirname(__file__), "streams.db")

    connect_str = f"sqlite:///{db_path}"
    engine = create_engine(connect_str, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Session = scoped_session(session_factory)
    return engine, Session 