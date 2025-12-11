import enum

from sqlalchemy import Column, Enum, Index, Integer, String

from app.database import Base


class EntryKind(str, enum.Enum):
    book = "book"
    article = "article"
    other = "other"


class EntryStatus(str, enum.Enum):
    planned = "planned"
    reading = "reading"
    done = "done"


class EntryDB(Base):
    __tablename__ = "entries"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    kind = Column(Enum(EntryKind), nullable=False)
    link = Column(String(2048), nullable=True)
    status = Column(Enum(EntryStatus), nullable=False)

    __table_args__ = (
        Index("ix_entries_status", "status"),
        Index("ix_entries_kind", "kind"),
    )
