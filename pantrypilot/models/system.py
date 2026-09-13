"""Small supporting tables: user notifications and app-wide settings."""

from datetime import datetime

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from pantrypilot.database import Base, UtcDateTime, utc_now


class Notification(Base):
    """A message for one user, e.g. "Hope Pantry will receive your 40 sandwiches"."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    message: Mapped[str] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(String(255), default=None)  # frontend page to open
    is_read: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)


class AppSetting(Base):
    """A simple key → value setting that the admin can change at runtime,
    e.g. key="supervised_mode", value="false"."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[str] = mapped_column(String(255))
