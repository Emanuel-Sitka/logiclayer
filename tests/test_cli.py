"""The command line, driven the way an agent would drive it."""

from __future__ import annotations

import json

import pytest

from logiclayer.cli import ENGINE_FAILED, OK, REFUSED, main
from logiclayer.engines.swipl import find_swipl

needs_swipl = pytest.mark.skipif(find_swipl() is None, reason="SWI-Prolog not installed")


@pytest.fixture
def run(tmp_path, capsys):
    """Run a command; give back its exit code and everything it printed."""
    ledger = tmp_path / "kb.jsonl"

    def _run(*argv: str):
        code = main(["--kb", str(ledger), *argv])
        captured = capsys.readouterr()
        return code, captured.out + captured.err

    _run.ledger = ledger
    return _run


@pytest.fixture
def characters(run):
    """A knowledge base built the way a conversation would build it."""
    for name in ["kind", "rough", "quiet", "careful", "trusted"]:
        run("declare", f"{name}/1", "--gloss", f"{name}(Person): Person is {name}")
    run("assert", "kind(anne).", "--source", "Anne is kind.", "--because", "direct")
    run("assert", "rough(bob).", "--source", "Bob is rough.", "--because", "direct")
    run("assert", "kind(carol).", "--source", "Carol is kind.", "--because", "direct")
    run("assert", "rough(carol).", "--source", "Carol is rough.", "--because", "direct")
    run("assert", r"quiet(X) :- kind(X), \+ rough(X).", "--because", "conditional")
    run("assert", "careful(X) :- quiet(X).", "--because", "chaining")
    run("assert", "trusted(X) :- careful(X).", "--because", "chaining")
    return run


class TestDeclare:
    def test_a_predicate_can_be_declared(self, run):
        code, out = run("declare", "kind/1", "--gloss", "kind(Person): Person is kind")
        assert code == OK
        assert "declared kind/1" in out

    def test_declaring_the_same_thing_twice_is_harmless(self, run):
        run("declare", "kind/1", "--gloss", "same")
        code, out = run("declare", "kind/1", "--gloss", "same")
        assert code == OK
        assert "already declared" in out

    def test_a_malformed_indicator_is_refused(self, run):
        code, out = run("declare", "kind", "--gloss", "no arity")
        assert code == REFUSED
        assert "name/arity" in out


class TestAssert:
    def test_a_declared_clause_is_stored(self, run):
        run("declare", "kind/1", "--gloss", "kind(Person): Person is kind")
        code, out = run("assert", "kind(anne).", "--because", "direct statement")
        assert code == OK
        assert "stored c1" in out

    def test_an_undeclared_predicate_is_refused(self, run):
        code, out = run("assert", "kind(anne).", "--because", "direct")
        assert code == REFUSED
        assert "kind/1 has not been declared" in out
        assert "logic declare" in out

    def test_a_near_miss_names_the_predicate_it_probably_meant(self, run):
        run("declare", "kind/1", "--gloss", "kind(Person): Person has a kind disposition")
        code, out = run("assert", "is_kind(carol).", "--because", "drifted name")
        assert code == REFUSED
        assert "look close" in out
        assert "kind/1" in out
        assert "kind disposition" in out  # the gloss, so the agent can judge

    def test_the_same_name_with_a_different_arity_says_so(self, run):
        run("declare", "parent/2", "--gloss", "parent(Older, Younger): Older is a parent of Younger")
        code, out = run("assert", "parent(alice, bob, carol).", "--because", "three arguments")
        assert code == REFUSED
        assert "parent/2 is declared, with a different number of arguments" in out

    def test_an_unsafe_rule_is_refused_with_the_fix(self, run):
        for name in ["kind", "rough", "quiet"]:
            run("declare", f"{name}/1", "--gloss", f"{name}(Person)")
        code, out = run("assert", r"quiet(X) :- \+ rough(X), kind(X).", "--because", "wrong order")
        assert code == REFUSED
        assert "unsafe negation" in out
        assert r"quiet(X) :- kind(X), \+ rough(X)." in out

    def test_a_duplicate_is_refused_and_names_the_original(self, run):
        run("declare", "kind/1", "--gloss", "kind(Person)")
        run("assert", "kind(anne).", "--source", "Anne is kind.", "--because", "first time")
        code, out = run("assert", "kind(anne).", "--because", "second time")
        assert code == REFUSED
        assert "already stored as c1" in out
        assert "Anne is kind." in out

    def test_broken_syntax_points_at_the_character(self, run):
        run("declare", "kind/1", "--gloss", "kind(Person)")
        code, out = run("assert", "kind(anne", "--because", "unclosed")
        assert code == REFUSED
        assert "^" in out

    def test_provenance_is_kept(self, run):
        run("declare", "kind/1", "--gloss", "kind(Person)")
        run("assert", "kind(anne).", "--source", "Anne is kind.",
            "--because", "Direct statement.", "--topic", "characters")
        stored = json.loads(run.ledger.read_text(encoding="utf-8").strip().split("\n")[1])
        assert stored["source_text"] == "Anne is kind."
        assert stored["rationale"] == "Direct statement."
        assert stored["topic"] == "characters"

    def test_turns_count_up_on_their_own(self, run):
        run("declare", "kind/1", "--gloss", "kind(Person)")
        run("assert", "kind(anne).", "--because", "one")
        run("assert", "kind(bob).", "--because", "two")
        turns = [json.loads(line)["turn"]
                 for line in run.ledger.read_text(encoding="utf-8").strip().split("\n")]
        assert turns == [1, 2, 3]


@needs_swipl
class TestQuery:
    def test_multi_step_deduction(self, characters):
        code, out = characters("query", "trusted(anne).")
        assert code == OK
        assert "proved" in out

    def test_the_assumption_is_never_hidden(self, characters):
        _, out = characters("query", "trusted(anne).")
        assert "conditional on 1 assumption" in out
        assert "rough(anne) is taken as false because nothing states it" in out

    def test_the_proof_names_the_clauses(self, characters):
        _, out = characters("query", "trusted(anne).")
        for entry_id in ["c1", "c5", "c6", "c7"]:
            assert f"[{entry_id}]" in out

    def test_an_unproven_goal_is_not_called_false(self, characters):
        code, out = characters("query", "trusted(carol).")
        assert code == OK  # the command worked; the goal just did not hold
        assert "unknown" in out
        assert "not the same as the goal being false" in out

    def test_bindings_are_shown(self, characters):
        _, out = characters("query", "trusted(Who).")
        assert "Who = anne" in out

    def test_the_full_stop_is_optional(self, characters):
        code, _ = characters("query", "trusted(anne)")
        assert code == OK

    def test_a_timeout_is_an_engine_failure(self, run):
        run("declare", "ancestor/2", "--gloss", "ancestor(X, Y)")
        run("declare", "parent/2", "--gloss", "parent(X, Y)")
        run("assert", "parent(a, b).", "--because", "fact")
        run("assert", "ancestor(X, Y) :- ancestor(X, Z), parent(Z, Y).", "--because", "left recursive")
        code, out = run("query", "ancestor(a, Who).", "--timeout", "3")
        assert code == ENGINE_FAILED
        assert "did not finish" in out

    def test_skipping_the_proof_admits_it_did_not_check(self, characters):
        _, out = characters("query", "trusted(anne).", "--no-proof")
        assert "assumptions not checked" in out

    def test_ascii_output_avoids_box_characters(self, characters):
        _, out = characters("--ascii", "query", "trusted(anne).")
        out.encode("cp1252")  # raises if anything is unencodable


@needs_swipl
class TestJsonOutput:
    def test_the_caveat_sits_beside_the_status(self, characters):
        _, out = characters("--json", "query", "trusted(anne).")
        payload = json.loads(out)
        assert payload["status"] == "proved"
        assert payload["conditional"] is True
        assert payload["assumptions"][0]["goal"] == "rough(anne)"

    def test_not_checked_is_null_not_false(self, characters):
        _, out = characters("--json", "query", "trusted(anne).", "--no-proof")
        payload = json.loads(out)
        assert payload["conditional"] is None
        assert payload["assumptions_checked"] is False

    def test_the_proof_is_included(self, characters):
        _, out = characters("--json", "query", "trusted(anne).")
        payload = json.loads(out)
        assert payload["answers"][0]["clause_ids"] == ["c7", "c6", "c5", "c1"]
        assert payload["answers"][0]["proof"]["goal"] == "trusted(anne)"


class TestInspect:
    def test_one_predicate(self, run):
        run("declare", "kind/1", "--gloss", "kind(Person): Person has a kind disposition")
        run("assert", "kind(anne).", "--source", "Anne is kind.", "--because", "direct")
        code, out = run("inspect", "kind")
        assert code == OK
        assert "kind disposition" in out
        assert "[c1]" in out
        assert "Anne is kind." in out

    def test_the_arity_can_be_left_off(self, run):
        run("declare", "kind/1", "--gloss", "kind(Person)")
        code, out = run("inspect", "kind/1")
        assert code == OK
        assert "kind/1" in out

    def test_a_declared_predicate_with_no_clauses_says_so(self, run):
        run("declare", "rough/1", "--gloss", "rough(Person)")
        _, out = run("inspect", "rough")
        assert "nothing defines it yet" in out
        assert "will fail rather than raise" in out

    def test_everything_at_once(self, run):
        run("declare", "kind/1", "--gloss", "kind(Person)")
        run("assert", "kind(anne).", "--because", "direct")
        code, out = run("inspect")
        assert code == OK
        assert "kind/1" in out

    def test_an_empty_knowledge_base(self, run):
        _, out = run("inspect")
        assert "nothing declared" in out


class TestRetract:
    def test_a_clause_can_be_withdrawn(self, run):
        run("declare", "kind/1", "--gloss", "kind(Person)")
        run("assert", "kind(anne).", "--because", "direct")
        code, out = run("retract", "c1", "--because", "mistaken")
        assert code == OK
        assert "retracted c1" in out

    def test_the_entry_stays_in_the_ledger(self, run):
        run("declare", "kind/1", "--gloss", "kind(Person)")
        run("assert", "kind(anne).", "--because", "direct")
        run("retract", "c1")
        _, out = run("history")
        assert "kind(anne)." in out
        assert "retract c1" in out

    def test_an_unknown_id_is_refused(self, run):
        code, out = run("retract", "c99")
        assert code == REFUSED
        assert "not an active clause" in out


class TestExport:
    def test_prolog_source(self, run):
        run("declare", "kind/1", "--gloss", "kind(Person)")
        run("assert", "kind(anne).", "--because", "direct")
        code, out = run("export")
        assert code == OK
        assert "kind(anne)." in out
        assert ":- dynamic kind/1." in out

    def test_a_snapshot_for_the_visualization(self, run):
        run("declare", "kind/1", "--gloss", "kind(Person): Person is kind")
        run("assert", "kind(anne).", "--source", "Anne is kind.", "--because", "direct")
        _, out = run("--json", "export", "--format", "json")
        payload = json.loads(out)
        assert payload["clauses"][0]["source_text"] == "Anne is kind."
        assert payload["clauses"][0]["rationale"] == "direct"
        assert payload["declarations"][0]["gloss"].startswith("kind(Person)")
        assert payload["turns"][-1]["clause_ids"] == ["c1"]

    def test_writing_to_a_file(self, run, tmp_path):
        run("declare", "kind/1", "--gloss", "kind(Person)")
        run("assert", "kind(anne).", "--because", "direct")
        target = tmp_path / "out.pl"
        code, out = run("export", "--out", str(target))
        assert code == OK
        assert "kind(anne)." in target.read_text(encoding="utf-8")


class TestHistory:
    def test_an_empty_ledger(self, run):
        _, out = run("history")
        assert "empty" in out

    def test_everything_in_order(self, run):
        run("declare", "kind/1", "--gloss", "kind(Person)")
        run("assert", "kind(anne).", "--because", "direct")
        _, out = run("history", "--brief")
        lines = [line for line in out.strip().split("\n") if line.strip()]
        assert lines[0].startswith("d1")
        assert lines[1].startswith("c1")

    def test_the_reasoning_is_shown_for_facts(self, run):
        run("declare", "kind/1", "--gloss", "kind(Person)")
        run("assert", "kind(anne).", "--source", "Anne is kind.",
            "--because", "direct statement about a named person")
        _, out = run("history")
        assert '"Anne is kind."' in out
        assert "because: direct statement about a named person" in out

    def test_the_reasoning_is_shown_for_rules_too(self, run):
        """The reasoning behind a rule is the harder judgement, so it is the
        one most worth reading back."""
        for name in ["kind", "rough", "quiet"]:
            run("declare", f"{name}/1", "--gloss", f"{name}(Person)")
        run("assert", r"quiet(X) :- kind(X), \+ rough(X).",
            "--source", "If someone is kind and not rough, they are quiet.",
            "--because", "conditional about anyone, so a rule with a variable")
        _, out = run("history")
        assert '"If someone is kind and not rough, they are quiet."' in out
        assert "because: conditional about anyone, so a rule with a variable" in out

    def test_brief_leaves_the_reasoning_out(self, run):
        run("declare", "kind/1", "--gloss", "kind(Person)")
        run("assert", "kind(anne).", "--source", "Anne is kind.", "--because", "direct")
        _, out = run("history", "--brief")
        assert "because:" not in out
        assert "Anne is kind." not in out
        assert "kind(anne)." in out

    def test_a_retraction_says_what_was_withdrawn(self, run):
        run("declare", "kind/1", "--gloss", "kind(Person)")
        run("assert", "kind(anne).", "--because", "direct")
        run("retract", "c1", "--because", "contradicted on a later turn")
        _, out = run("history")
        assert "retract c1   kind(anne)." in out
        assert "because: contradicted on a later turn" in out

    def test_the_topic_is_shown_when_set(self, run):
        run("declare", "kind/1", "--gloss", "kind(Person)")
        run("assert", "kind(anne).", "--because", "direct", "--topic", "characters")
        _, out = run("history")
        assert "topic: characters" in out
