"""The SWI-Prolog port, run against the real engine."""

from __future__ import annotations

import pytest

from logiclayer.core.parse import parse_clause, parse_goal
from logiclayer.engines.base import Program, SolveOpts, SourcedClause, Status
from logiclayer.engines.swipl import SwiPrologPort, find_swipl, render_program

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


@pytest.fixture(scope="module")
def port():
    return SwiPrologPort()


def solve(port, program, goal, **kwargs):
    return port.solve(program, parse_goal(goal), SolveOpts(**kwargs))


class TestRenderedProgram:
    """These do not need the engine."""

    def test_every_predicate_is_declared_dynamic(self):
        source = render_program(CHARACTERS)
        for predicate in ["kind/1", "rough/1", "quiet/1", "careful/1", "trusted/1"]:
            assert f":- dynamic {predicate}." in source

    def test_predicates_that_nothing_defines_are_still_declared(self):
        """Otherwise a goal about them raises instead of failing quietly."""
        program = build(("c1", r"p(X) :- \+ never_mentioned_elsewhere(X)."))
        assert ":- dynamic never_mentioned_elsewhere/1." in render_program(program)

    def test_clauses_appear_for_direct_calling(self):
        source = render_program(CHARACTERS)
        assert "kind(anne)." in source
        assert r"quiet(X) :- kind(X), \+ rough(X)." in source

    def test_clause_table_carries_ledger_ids(self):
        source = render_program(CHARACTERS)
        assert "ll_src(kind(anne), true, 'c1')." in source
        assert r"ll_src(quiet(X), (kind(X), \+ rough(X)), 'c5')." in source


@needs_swipl
class TestCapabilities:
    def test_prolog_cannot_prove_negatives(self, port):
        assert port.capabilities().classical_negation is False

    def test_prolog_can_loop_forever(self, port):
        assert port.capabilities().guaranteed_termination is False

    def test_proof_trees_are_ours_not_the_engines(self, port):
        assert port.capabilities().native_justification is False

    def test_version_is_reported(self, port):
        assert "SWI-Prolog" in port.capabilities().version


@needs_swipl
class TestSolving:
    def test_multi_step_deduction(self, port):
        assert solve(port, CHARACTERS, "trusted(anne)").status is Status.PROVED

    def test_negation_blocks_the_rule(self, port):
        """Carol is kind but also rough, so quiet/1 must not fire for her."""
        assert solve(port, CHARACTERS, "trusted(carol)").status is Status.UNKNOWN

    def test_unmentioned_individual_is_unknown_not_an_error(self, port):
        assert solve(port, CHARACTERS, "trusted(zoe)").status is Status.UNKNOWN

    def test_failure_is_never_reported_as_disproved(self, port):
        """Plain Prolog cannot tell "false" from "not provable", so it must
        never claim the stronger of the two."""
        assert solve(port, CHARACTERS, "trusted(carol)").status is not Status.DISPROVED

    def test_goal_about_an_entirely_unknown_predicate(self, port):
        """No clause mentions this at all. It should fail, not raise."""
        assert solve(port, CHARACTERS, "sleepy(anne)").status is Status.UNKNOWN

    def test_negated_goal_at_the_top_level(self, port):
        assert solve(port, CHARACTERS, r"\+ rough(anne)").status is Status.PROVED
        assert solve(port, CHARACTERS, r"\+ rough(bob)").status is Status.UNKNOWN

    def test_empty_program(self, port):
        assert solve(port, Program(), "anything(x)").status is Status.UNKNOWN


@needs_swipl
class TestBindings:
    def test_variable_keeps_the_name_the_caller_used(self, port):
        solution = solve(port, CHARACTERS, "trusted(Who)")
        assert solution.answers[0].bindings == {"Who": "anne"}

    def test_several_answers(self, port):
        solution = solve(port, CHARACTERS, "kind(Who)")
        assert [a.bindings["Who"] for a in solution.answers] == ["anne", "carol"]

    def test_no_variables_means_no_bindings(self, port):
        solution = solve(port, CHARACTERS, "trusted(anne)")
        assert solution.answers[0].bindings == {}

    def test_answers_are_capped_and_the_cap_is_reported(self, port):
        solution = solve(port, CHARACTERS, "kind(Who)", max_solutions=1)
        assert len(solution.answers) == 1
        assert solution.truncated is True
        assert "more" in solution.message

    def test_not_truncated_when_everything_fits(self, port):
        solution = solve(port, CHARACTERS, "kind(Who)", max_solutions=2)
        assert solution.truncated is False


@needs_swipl
class TestProofTree:
    def test_every_step_is_traced_to_a_ledger_entry(self, port):
        proof = solve(port, CHARACTERS, "trusted(anne)").justification
        assert proof.clause_ids() == ["c7", "c6", "c5", "c1"]

    def test_shape_follows_the_reasoning(self, port):
        proof = solve(port, CHARACTERS, "trusted(anne)").justification
        assert proof.goal == "trusted(anne)"
        assert proof.kind == "rule"

        careful = proof.children[0]
        quiet = careful.children[0]
        assert quiet.goal == "quiet(anne)"
        assert len(quiet.children) == 2

    def test_facts_are_marked_as_facts(self, port):
        proof = solve(port, CHARACTERS, "trusted(anne)").justification
        kind = proof.children[0].children[0].children[0]
        assert kind.kind == "fact"
        assert kind.clause_id == "c1"
        assert kind.children == ()

    def test_negation_records_that_nothing_proved_it(self, port):
        proof = solve(port, CHARACTERS, "trusted(anne)").justification
        negated = proof.children[0].children[0].children[1]
        assert negated.kind == "naf"
        assert negated.clause_id is None
        assert "rough(anne)" in negated.goal

    def test_rendered_tree_is_readable(self, port):
        proof = solve(port, CHARACTERS, "trusted(anne)").justification
        rendered = proof.render()
        assert rendered.splitlines()[0].startswith("trusted(anne)")
        assert "[c1]" in rendered
        assert "assumed false" in rendered

    def test_ascii_rendering_avoids_box_characters(self, port):
        """Some Windows consoles cannot encode them."""
        proof = solve(port, CHARACTERS, "trusted(anne)").justification
        rendered = proof.render(ascii_only=True)
        rendered.encode("cp1252")  # raises if it contains anything unencodable

    def test_no_proof_is_built_when_none_is_wanted(self, port):
        solution = solve(port, CHARACTERS, "trusted(anne)", want_proof=False)
        assert solution.status is Status.PROVED
        assert solution.justification is None


@needs_swipl
class TestFailureHandling:
    def test_a_looping_rule_is_stopped(self, port):
        """Left recursion: Prolog proves ancestor by first proving ancestor."""
        looping = build(
            ("c1", "parent(a, b)."),
            ("c2", "ancestor(X, Y) :- ancestor(X, Z), parent(Z, Y)."),
        )
        solution = solve(port, looping, "ancestor(a, Who)", timeout=3)
        assert solution.status is Status.ERROR
        assert "did not finish" in solution.message

    def test_timeout_must_be_positive(self):
        with pytest.raises(ValueError, match="no unlimited setting"):
            SolveOpts(timeout=0)

    def test_solutions_cap_must_be_sensible(self):
        with pytest.raises(ValueError):
            SolveOpts(max_solutions=0)

    def test_duration_is_recorded(self, port):
        assert solve(port, CHARACTERS, "trusted(anne)").duration_ms > 0
