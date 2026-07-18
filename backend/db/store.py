"""Engine + session helpers (P1 owns: fill remaining helpers per spec 06 / task M2)."""
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend import config
from backend.db.models import Base

DB_PATH = config.DATA / "ember.sqlite"
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)


def init_db() -> None:
    Base.metadata.create_all(engine)


@contextmanager
def session():
    with Session(engine) as s:
        yield s
        s.commit()


# --- P1 TODO (spec 06 / task P1-M2): ---
# def record_call(run_id, task_id, arm, k_index, role, impact: dict, **kw) -> int: ...
# def get_run_events(run_id: str, after_seq: int = 0) -> list[dict]: ...
# def run_totals(run_id: str) -> dict: ...   # per-arm sums for /runs/{id}
# def completed_tuples(run_id: str) -> set[tuple]: ...  # harness resume support
