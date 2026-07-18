"""SQLite schema per spec 06 — one QueryResult row PER CALL (answer, classifier,
judge) so D4 overhead accounting is auditable straight from SQL."""
from datetime import datetime

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Run(Base):
    __tablename__ = "runs"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    started_at: Mapped[datetime]
    finished_at: Mapped[datetime | None]
    status: Mapped[str] = mapped_column(String, default="running")  # running|done|failed
    k: Mapped[int] = mapped_column(Integer, default=3)
    workload: Mapped[str] = mapped_column(String, default="default")
    config_json: Mapped[str] = mapped_column(Text)  # ladder/floor/zones snapshot — reproducibility


class QueryResult(Base):
    __tablename__ = "query_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    task_id: Mapped[str] = mapped_column(String, index=True)
    arm: Mapped[str]                      # a|b
    k_index: Mapped[int]
    seq: Mapped[int] = mapped_column(Integer, index=True)  # event cursor for /runs/{id}?after_seq
    role: Mapped[str]                     # answer|classifier|judge
    model_key: Mapped[str]
    tier: Mapped[str | None]
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    wh: Mapped[float] = mapped_column(Float, default=0.0)
    gco2: Mapped[float] = mapped_column(Float, default=0.0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    zone: Mapped[str | None]
    gco2_per_kwh: Mapped[float | None]
    intensity_label: Mapped[str | None]   # live|cached|snapshot|fallback
    energy_label: Mapped[str] = mapped_column(String, default="estimated")
    score: Mapped[float | None]           # judge/oracle score
    correct: Mapped[int | None]           # 1|0|NULL (overhead rows)
    escalated_from: Mapped[str | None]    # tier this call escalated from
    error: Mapped[str | None]


class CarbonSnapshot(Base):
    __tablename__ = "carbon_snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    zone: Mapped[str] = mapped_column(String, index=True)
    gco2_per_kwh: Mapped[float]
    label: Mapped[str]
    fetched_at: Mapped[str]


class Report(Base):
    __tablename__ = "reports"
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), primary_key=True)
    report_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime]
