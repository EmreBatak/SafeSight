"""Database tables (CLAUDE.md §5) and connection.

The URL comes from SAFESIGHT_DB_URL; the default matches docker-compose.yml. Tables are created on
start-up if missing (no migrations yet; drop the Docker volume to start over after a schema change).
"""

import os
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

DEFAULT_URL = "postgresql+psycopg://safesight:safesight@localhost:5433/safesight"


def db_url() -> str:
    return os.environ.get("SAFESIGHT_DB_URL", DEFAULT_URL)


class Base(DeclarativeBase):
    pass


class Worker(Base):
    __tablename__ = "workers"
    id: Mapped[int] = mapped_column(primary_key=True)
    badge_no: Mapped[str] = mapped_column(String(64), unique=True)  # the text in the worker's QR
    name: Mapped[str] = mapped_column(String(200))
    department: Mapped[str] = mapped_column(String(200), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    reference_photo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)


class Station(Base):
    __tablename__ = "stations"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    location: Mapped[str] = mapped_column(String(200), default="")


class Check(Base):
    __tablename__ = "checks"
    id: Mapped[int] = mapped_column(primary_key=True)
    worker_id: Mapped[int] = mapped_column(ForeignKey("workers.id"), index=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer)
    decision: Mapped[str] = mapped_column(String(16))  # 'APPROVED' | 'REJECTED'
    reason: Mapped[str] = mapped_column(String(32))  # 'proper' | 'improper' | 'no_mask' | 'no_face' | 'multiple_people'
    proper_ratio: Mapped[float] = mapped_column(Float)
    snapshot_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    review_status: Mapped[str | None] = mapped_column(String(16), nullable=True)  # NULL | pending | confirmed | overturned
    reviewed_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(primary_key=True)
    worker_id: Mapped[int] = mapped_column(ForeignKey("workers.id"), index=True)
    check_id: Mapped[int] = mapped_column(ForeignKey("checks.id"))
    type: Mapped[str] = mapped_column(String(32))  # 'repeated_rejection'
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)


def make_sessionmaker(url: str | None = None) -> sessionmaker:
    url = url or db_url()
    kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
    if url == "sqlite://":  # in-memory, for tests: one shared connection
        from sqlalchemy.pool import StaticPool

        kwargs["poolclass"] = StaticPool
    engine = create_engine(url, **kwargs)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)
