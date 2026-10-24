"""What the engine had to take for granted, and whether it asked the right question.

Two different faults, both happening at a negation step and both invisible in
a plain yes/no answer:

  the engine invented a premise    -- "nothing says Anne is rough, so she isn't"
  the engine widened the question  -- "is ANY Orwell book damaged?" instead of
                                      "is THIS book damaged?"

One walk of the proof tree reports both.
"""

from __future__ import annotations

import pytest

from logiclayer.core.parse import parse_clause, parse_goal
from logiclayer.engines.base import Program, SolveOpts, SourcedClause, Status
from logiclayer.engines.swipl import SwiPrologPort, find_swipl

needs_swipl = pytest.mark.skipif(find_swipl() is None, reason="SWI-Prolog not installed")


def build(*pairs: tuple[str, str]) -> Program:
    return Program(tuple(SourcedClause(i, parse_clause(t)) for i, t in pairs))


CHARACTERS = build(
    ("c1", "kind(anne)."),
    ("c2", "rough(bob)."),
    ("c3", "kind(carol)."),
    ("c4", "rough(carol)."),
    ("c5", r"quiet(X) :- kind(X), \+ rough(X)."),
    ("c6", "careful(X) :- quiet(X)."),
    ("c7", "trusted(X) :- careful(X)."),
)

# A fact with a variable in it stands for a whole family of things: every
# Orwell book is in the library. When it binds the rule's variable, the
# negation that follows runs on a term with a hole still in it.
BOOKS = build(
    ("c1", "in_library(book(orwell, Title))."),
    ("c2", "damaged(book(orwell, nineteen84))."),
    ("c3", r"lendable(X) :- in_library(X), \+ damaged(X)."),
)


@pytest.fixture(scope="module")
def port():
    return SwiPrologPort()


def solve(port, program, goal, **kwargs):
    return port.solve(program, parse_goal(goal), SolveOpts(**kwargs))


@needs_swipl
class TestInventedPremises:
    def test_the_assumption_is_reported(self, port):
        solution = solve(port, CHARACTERS, "trusted(anne)")
        assert solution.status is Status.PROVED
        assert [a.goal for a in solution.assumptions] == ["rough(anne)"]

    def test_it_is_marked_as_ground(self, port):
        """Anne is a plain constant, so the negation asked about her alone."""
        assumption = solve(port, CHARACTERS, "trusted(anne)").assumptions[0]
        assert assumption.ground is True
        assert assumption.kind == "closed_world"

    def test_a_proof_without_negation_assumes_nothing(self, port):
        solution = solve(port, CHARACTERS, "kind(anne)")
        assert solution.status is Status.PROVED
        assert solution.assumptions == ()
        assert solution.conditional is False

    def test_the_verdict_says_so(self, port):
        assert solve(port, CHARACTERS, "trusted(anne)").verdict() == (
            "proved, conditional on 1 assumption"
        )

    def test_an_unconditional_verdict_stays_plain(self, port):
        assert solve(port, CHARACTERS, "kind(anne)").verdict() == "proved"

    def test_assumptions_are_per_answer(self, port):
        """Each proof carries the assumptions its own path relied on."""
        solution = solve(port, CHARACTERS, "trusted(Who)")
        assert [a.goal for a in solution.answers[0].assumptions] == ["rough(anne)"]

    def test_it_reads_as_a_sentence(self, port):
        assumption = solve(port, CHARACTERS, "trusted(anne)").assumptions[0]
        assert assumption.describe() == "rough(anne) is taken as false because nothing states it"


@needs_swipl
class TestWidenedQuestions:
    def test_the_two_answers_disagree(self, port):
        """Naming the book proves it lendable. Asking openly finds nothing.
        That contradiction is what the groundness flag exists to explain."""
        assert solve(port, BOOKS, "lendable(book(orwell, animal_farm))").status is Status.PROVED
        assert solve(port, BOOKS, "lendable(What)").status is Status.UNKNOWN

    def test_a_loose_variable_is_flagged(self, port):
        solution = solve(port, BOOKS, "lendable(book(orwell, animal_farm))")
        [assumption] = solution.assumptions
        assert assumption.ground is True  # the title was supplied by the caller

    def test_the_open_query_would_have_run_loose(self, port):
        """in_library(X) binds X to book(orwell, Title) with Title still free,
        so the negation asks about every Orwell book at once."""
        loose = build(
            ("c1", "in_library(book(orwell, Title))."),
            ("c2", "damaged(magazine)."),  # nothing of the book shape is damaged
            ("c3", r"lendable(X) :- in_library(X), \+ damaged(X)."),
        )
        solution = solve(port, loose, "lendable(What)")
        assert solution.status is Status.PROVED
        [assumption] = solution.assumptions
        assert assumption.ground is False
        assert "variable still loose" in assumption.describe()

    def test_the_verdict_warns_about_it(self, port):
        loose = build(
            ("c1", "in_library(book(orwell, Title))."),
            ("c2", "damaged(magazine)."),
            ("c3", r"lendable(X) :- in_library(X), \+ damaged(X)."),
        )
        verdict = solve(port, loose, "lendable(What)").verdict()
        assert "1 checked with a variable still loose" in verdict

    def test_unsound_assumptions_are_listed_separately(self, port):
        loose = build(
            ("c1", "in_library(book(orwell, Title))."),
            ("c2", "damaged(magazine)."),
            ("c3", r"lendable(X) :- in_library(X), \+ damaged(X)."),
        )
        solution = solve(port, loose, "lendable(What)")
        assert len(solution.unsound_assumptions) == 1


@needs_swipl
class TestNotLooking:
    """Skipping the proof means we did not check, which is not the same as
    finding nothing. Saying otherwise is the overclaiming this prevents."""

    def test_conditional_is_undetermined(self, port):
        solution = solve(port, CHARACTERS, "trusted(anne)", want_proof=False)
        assert solution.status is Status.PROVED
        assert solution.assumptions_checked is False
        assert solution.conditional is None

    def test_the_verdict_admits_it(self, port):
        solution = solve(port, CHARACTERS, "trusted(anne)", want_proof=False)
        assert solution.verdict() == "proved (assumptions not checked)"

    def test_checking_is_the_default(self, port):
        assert solve(port, CHARACTERS, "trusted(anne)").assumptions_checked is True


@needs_swipl
class TestRendering:
    def test_the_negation_reads_as_a_negation(self, port):
        """The node stores the bare goal; the tree puts the \\+ back."""
        proof = solve(port, CHARACTERS, "trusted(anne)").justification
        assert r"\+ rough(anne)   [assumed false]" in proof.render()

    def test_a_loose_variable_is_shouted_about(self, port):
        loose = build(
            ("c1", "in_library(book(orwell, Title))."),
            ("c2", "damaged(magazine)."),
            ("c3", r"lendable(X) :- in_library(X), \+ damaged(X)."),
        )
        proof = solve(port, loose, "lendable(What)").justification
        assert "BUT A VARIABLE WAS LOOSE" in proof.render()

    def test_arguments_are_spaced_like_our_own_printer(self, port):
        """Prolog writes book(orwell,animal_farm); we want a space after the
        comma, so that engine output and our output agree."""
        proof = solve(port, BOOKS, "lendable(book(orwell, animal_farm))").justification
        assert "book(orwell, animal_farm)" in proof.render()

    def test_bindings_are_spaced_too(self, port):
        owns = build(
            ("c1", "owns(anne, book(orwell, animal_farm))."),
        )
        solution = solve(port, owns, "owns(anne, What)")
        assert solution.answers[0].bindings == {"What": "book(orwell, animal_farm)"}
