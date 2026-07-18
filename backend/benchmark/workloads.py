"""P3 owns — spec 05, task P3-M1.
load(name="default") -> list[dict] from data/workloads/{name}.json, validated:
{id, category: trivial|math|reasoning|code, prompt, oracle: {type, ...}}
Oracle types: string_match | numeric_exact | unit_test | judge."""


def load(name: str = "default") -> list[dict]:
    raise NotImplementedError("P3-M1 — see specs/05-benchmark.md")
