"""
Persistence for analysis jobs and results.

SQLAlchemy keeps the schema database-agnostic: SQLite by default
(zero setup); set DATABASE_URL=postgresql+psycopg://... to use
PostgreSQL without code changes.
"""

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import JSON, DateTime, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


DEFAULT_URL = "sqlite:///" + str(
    Path(__file__).resolve().parents[2] / "data" / "app.db"
).replace("\\", "/")


def utcnow():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class AnalysisJob(Base):

    __tablename__ = "analysis_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    ticker: Mapped[str] = mapped_column(String(32), index=True)
    # queued / running / done / failed
    status: Mapped[str] = mapped_column(String(16), index=True)
    include_news: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Small denormalised summary for history listings.
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Database:

    def __init__(self, url=None):

        url = url or os.environ.get("DATABASE_URL", DEFAULT_URL)

        if url.startswith("sqlite:///"):
            Path(url.replace("sqlite:///", "")).parent.mkdir(
                parents=True, exist_ok=True
            )

        connect_args = (
            {"check_same_thread": False} if url.startswith("sqlite") else {}
        )

        self.engine = create_engine(url, connect_args=connect_args)
        self.Session = sessionmaker(self.engine, expire_on_commit=False)

        Base.metadata.create_all(self.engine)

    def create_job(self, ticker, include_news):

        job = AnalysisJob(
            id=str(uuid.uuid4()),
            ticker=ticker,
            status="queued",
            include_news=include_news,
        )

        with self.Session() as session:
            session.add(job)
            session.commit()

        return job

    def update_job(self, job_id, **fields):

        with self.Session() as session:
            job = session.get(AnalysisJob, job_id)
            for key, value in fields.items():
                setattr(job, key, value)
            session.commit()
            return job

    def get_job(self, job_id):

        with self.Session() as session:
            return session.get(AnalysisJob, job_id)

    def _latest(self, ticker, statuses, include_news=None):

        query = (
            select(AnalysisJob)
            .where(AnalysisJob.ticker == ticker, AnalysisJob.status.in_(statuses))
            .order_by(AnalysisJob.created_at.desc())
        )

        if include_news is not None:
            query = query.where(AnalysisJob.include_news == include_news)

        with self.Session() as session:
            return session.scalars(query.limit(1)).first()

    def latest_done(self, ticker, include_news=None):
        return self._latest(ticker, ["done"], include_news)

    def active_job(self, ticker, include_news=None):
        return self._latest(ticker, ["queued", "running"], include_news)

    def history(self, ticker, limit=50):

        query = (
            select(AnalysisJob)
            .where(AnalysisJob.ticker == ticker, AnalysisJob.status == "done")
            .order_by(AnalysisJob.created_at.desc())
            .limit(limit)
        )

        with self.Session() as session:
            return list(session.scalars(query))

    def mark_interrupted(self):
        """Jobs left queued/running by a previous process can never finish."""

        with self.Session() as session:
            for job in session.scalars(
                select(AnalysisJob).where(
                    AnalysisJob.status.in_(["queued", "running"])
                )
            ):
                job.status = "failed"
                job.error = "Interrupted by server restart."
                job.finished_at = utcnow()
            session.commit()
