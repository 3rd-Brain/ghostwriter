import uuid
import enum
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from app.database import Base


class TemplateCategory(str, enum.Enum):
    short_form = "short_form"
    atomic = "atomic"
    mid_form = "mid_form"


class Template(Base):
    __tablename__ = "templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[TemplateCategory] = mapped_column(SAEnum(TemplateCategory), default=TemplateCategory.short_form)
    embedding = mapped_column(Vector(1536), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
