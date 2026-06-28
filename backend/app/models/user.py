from sqlalchemy import Boolean, Column, DateTime, Index, String, Text, func

from app.core.database import Base, ID_TYPE


class User(Base):
    __tablename__ = "users"

    id = Column(ID_TYPE, primary_key=True)
    email = Column(String(255), nullable=False, unique=True)
    password_hash = Column(Text, nullable=False)
    role = Column(String(50), nullable=False)
    is_active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("ix_users_role", "role"),
    )
