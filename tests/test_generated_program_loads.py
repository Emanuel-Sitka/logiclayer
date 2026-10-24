"""The check that decides whether stage 1 is finished.

Everything else in the test suite is about our own structures. This one asks
the only question that matters: does the file we generate actually load in
SWI-Prolog, and does the engine reason over it correctly?

Skipped if SWI-Prolog is not installed, so the suite still runs on a machine
without it.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from logiclayer.core.kb import KnowledgeBase
from logiclayer.core.parse import parse_clause
from logiclayer.engines.swipl import find_swipl

SWIPL = find_swipl()
needs_swipl = pytest.mark.skipif(SWIPL is None, reason="SWI-Prolog not installed")


def prove(program: Path, goal: str, timeout: float = 10.0) -> bool:
    """True if the engine proves the goal against the generated program."""
    assert SWIPL is not None
    proc = subprocess.run(
        [
            str(SWIPL),
            "-q",
            "--no-tty",
            "-g",
            f"( {goal} -> writeln(yes) ; writeln(no) )",
            "-t",
            "halt",
            str(program),
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
        stdin=subprocess.DEVNULL,
    )
    if proc.returncode != 0:
        raise AssertionError(f"swipl failed ({proc.returncode}): {proc.stderr.strip()}")
    return proc.stdout.strip() == "yes"


@pytest.fixture
def built(tmp_path):
    """A knowledge base built turn by turn, and the .pl file generated from it."""
    kb = KnowledgeBase(tmp_path / "kb.jsonl")

    turns = [
        ("kind(anne).", "Anne is kind."),
        ("rough(bob).", "Bob is rough."),
        ("kind(carol).", "Carol is kind."),
        ("rough(carol).", "Carol is rough."),
        (r"quiet(X) :- kind(X), \+ rough(X).", "If someone is kind and not rough, they are quiet."),
        ("careful(X) :- quiet(X).", "Anyone quiet is careful."),
        ("trusted(X) :- careful(X).", "Anyone careful is trusted."),
    ]
    for turn, (text, sentence) in enumerate(turns, start=1):
        kb.add_clause(
            parse_clause(text),
            turn=turn,
            source_text=sentence,
            rationale=f"Turn {turn}. Translated directly.",
        )

    program = kb.write_prolog(tmp_path / "build" / "kb.pl")
    return kb, program


@needs_swipl
class TestGeneratedProgram:
    def test_it_loads_without_complaint(self, built):
        _, program = built
        assert prove(program, "true")

    def test_multi_step_deduction(self, built):
        """trusted <- careful <- quiet <- kind and not rough. Three steps."""
        _, program = built
        assert prove(program, "trusted(anne)")

    def test_the_negation_actually_bites(self, built):
        """Carol is kind but also rough, so the rule must not fire for her."""
        _, program = built
        assert not prove(program, "trusted(carol)")

    def test_unknown_individual(self, built):
        _, program = built
        assert not prove(program, "trusted(zoe)")

    def test_query_with_a_variable(self, built):
        _, program = built
        assert prove(program, "trusted(anne), \\+ trusted(carol), \\+ trusted(bob)")

    def test_retracting_changes_the_answer(self, built, tmp_path):
        """The point of the whole design: change the ledger, regenerate, re-ask."""
        kb, program = built
        assert prove(program, "trusted(anne)")

        [kind_anne] = [c for c in kb.active() if c.text == "kind(anne)."]
        kb.retract(kind_anne.id, turn=8, rationale="Withdrawn for the test.")
        regenerated = kb.write_prolog(tmp_path / "build" / "kb.pl")

        assert not prove(regenerated, "trusted(anne)")

    def test_awkward_atoms_survive(self, tmp_path):
        """Quoting has to hold up, or the engine sees a syntax error."""
        kb = KnowledgeBase(tmp_path / "kb.jsonl")
        kb.add_clause(parse_clause("lives(anne, 'New York')."), turn=1)
        kb.add_clause(parse_clause("greets(anne, 'it''s fine')."), turn=2)
        program = kb.write_prolog(tmp_path / "build" / "kb.pl")

        assert prove(program, "lives(anne, 'New York')")

    def test_replay_matches_what_the_engine_sees(self, built):
        """Each replay step should be a program the engine can load."""
        kb, _ = built
        states = dict(kb.replay())
        assert len(states[1]) == 1
        assert len(states[7]) == 7
