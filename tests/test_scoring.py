"""Scoring oracles (spec 05) — Layer 1 of the parity proof runs through these
functions, so a parsing bug here IS a wrong headline number."""
from backend.benchmark import scoring


# --- numeric parsing: models answer in prose, the oracle must find the number ---

def test_final_number_survives_prose_commas_and_dollars():
    """GSM8K answers arrive like 'so she makes $1,234 per day.' — the parser must
    take the LAST number, strip $ and thousands commas, and tolerate a trailing
    period. Each of these failing would mark a correct Opus answer wrong,
    corrupting the baseline accuracy the parity claim is measured against."""
    cases = [
        ("She makes 9 * 2 = $18 every day.", 18.0),
        ("The answer is 1,234.", 1234.0),
        ("First 16 - 3 - 4 = 9, then 9 x 2 = 18", 18.0),
        ("It dropped to -5 degrees", -5.0),
        ("The result is 3.5", 3.5),
    ]
    for text, want in cases:
        assert scoring.parse_final_number(text) == want, text


def test_no_number_is_incorrect_not_a_crash():
    """A rambling answer with no digits must score incorrect — not raise, and
    definitely not default to correct (spec 05: failed answers stay in totals)."""
    assert scoring.parse_final_number("I cannot determine that.") is None
    task = {"oracle": {"type": "numeric_exact", "answer": "42"}}
    assert scoring.score(task, "I cannot determine that.")["correct"] is False


def test_string_match_is_case_insensitive_containment():
    """Prompts say 'reply with only X' but models still add words. 'The capital
    is Paris.' must pass an oracle of 'Paris' — exact-match would fail nearly
    every verbose-but-correct answer and fake a huge accuracy gap."""
    task = {"oracle": {"type": "string_match", "answer": "Paris"}}
    assert scoring.score(task, "The capital of France is paris.")["correct"] is True
    assert scoring.score(task, "It is Lyon.")["correct"] is False


# --- code oracle: a real subprocess runs the model's code against our asserts ---

def test_unit_test_oracle_runs_real_code():
    """The code oracle is deterministic ground truth (spec 05) — a working
    function passes, a subtly wrong one fails. Both directions matter: an oracle
    that always passes would inflate BOTH arms equally and hide nothing visibly."""
    task = {"oracle": {"type": "unit_test", "tests": ["assert double(2) == 4", "assert double(0) == 0"]}}
    assert scoring.score(task, "def double(x):\n    return x * 2")["correct"] is True
    assert scoring.score(task, "def double(x):\n    return x + 2")["correct"] is False


def test_unit_test_extracts_markdown_fences():
    """Models wrap code in ```python fences more often than not — the oracle must
    unwrap before executing, or every fenced (correct) answer is a SyntaxError."""
    answer = "Here you go:\n```python\ndef double(x):\n    return x * 2\n```\nHope that helps!"
    task = {"oracle": {"type": "unit_test", "tests": ["assert double(3) == 6"]}}
    assert scoring.score(task, answer)["correct"] is True


def test_unit_test_hang_counts_as_failure():
    """An infinite loop in generated code must be killed by the timeout and score
    incorrect — without this, one bad generation freezes the whole benchmark
    (spec 05: subprocess, timeout, hang = failure)."""
    task = {"oracle": {"type": "unit_test", "tests": ["assert True"]}}
    assert scoring.score(task, "while True:\n    pass", timeout_s=1.0)["correct"] is False


# --- judge oracle: explicitly NOT scored here ---

def test_judge_oracle_defers_to_evaluation():
    """Judge-oracle tasks return correct=None at harness time — they're scored by
    blind pairwise judging at evaluation time (spec 09 layer 2). Scoring them
    here too would double the judge spend and let a runtime judgment leak into
    what's supposed to be a blind comparison."""
    task = {"oracle": {"type": "judge", "reference": "ref"}}
    assert scoring.score(task, "whatever")["correct"] is None
