"""{module} 模型 - {description}."""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase

from app.utils.time_utils import utcnow_naive


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 声明式基类。"""
    pass


class {Entity}Model(Base):
    """{description}模型。

    表名: {table_name}
    """
    __tablename__ = "{table_name}"

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True)

    # 通用字段
    created_at = Column(DateTime, nullable=False, default=utcnow_naive)
    updated_at = Column(DateTime, nullable=False, default=utcnow_naive, onupdate=utcnow_naive)
    is_deleted = Column(Boolean, nullable=False, default=False)

    {fields}

    def to_dict(self) -> dict:
        """转换为字典（用于序列化）。

        Returns:
            数据字典
        """
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            **{
                key: getattr(self, key)
                for key in self.__mapper__.columns.keys()
                if key not in ("created_at", "updated_at", "is_deleted")
            },
        }
