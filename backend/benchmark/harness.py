"""P3 owns — spec 05, task P3-M2 (KR1.2).
Arms interleaved A,B per task; K repeats; bounded concurrency w/ backoff on 429;
per-call rows committed immediately (resumable); spend estimate confirmed up front.
CLI: uv run python -m backend.benchmark.harness [--limit N] [--k K]"""


def run(workload: str = "default", k: int = 3, limit: int | None = None) -> str:
    raise NotImplementedError("P3-M2 — see specs/05-benchmark.md")


if __name__ == "__main__":
    raise SystemExit(run())
