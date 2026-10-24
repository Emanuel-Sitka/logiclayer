import json

import pytest

from logiclayer.core.kb import KnowledgeBase
from logiclayer.core.parse import parse_clause


@pytest.fixture
def kb(tmp_path):
    return KnowledgeBase(tmp_path / "test.jsonl")


def add(kb, text, **kwargs):
    return kb.add_clause(parse_clause(text), **kwargs)


class TestAppending:
    def test_empty_to_start(self, kb):
        assert kb.entries() == []
        assert kb.active() == []

    def test_ids_are_sequential(self, kb):
        assert add(kb, "kind(anne).").id == "c1"
        assert add(kb, "rough(bob).").id == "c2"

    def test_clause_comes_back(self, kb):
        add(kb, "kind(anne).", turn=2, source_text="Anne is kind.", rationale="Direct statement.")
        [item] = kb.active()
        assert item.text == "kind(anne)."
        assert item.turn == 2
        assert item.source_text == "Anne is kind."
        assert item.rationale == "Direct statement."

    def test_predicates_are_recorded(self, kb):
        entry = add(kb, r"quiet(X) :- kind(X), \+ rough(X).")
        assert entry.predicates == ("quiet/1", "kind/1", "rough/1")

    def test_one_line_per_entry(self, kb):
        add(kb, "kind(anne).")
        add(kb, "rough(bob).")
        lines = kb.path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2
        assert all(json.loads(line)["op"] == "assert" for line in lines)

    def test_optional_fields_are_left_out(self, kb):
        add(kb, "kind(anne).")
        stored = json.loads(kb.path.read_text(encoding="utf-8").strip())
        assert "rationale" not in stored
        assert "topic" not in stored


class TestRetraction:
    def test_retracted_clause_leaves_the_active_set(self, kb):
        entry = add(kb, "kind(anne).")
        add(kb, "rough(bob).")
        kb.retract(entry.id)
        assert [i.text for i in kb.active()] == ["rough(bob)."]

    def test_nothing_is_deleted_from_the_file(self, kb):
        entry = add(kb, "kind(anne).")
        kb.retract(entry.id)
        assert len(kb.entries()) == 2
        assert kb.find("c1") is not None

    def test_clauses_keeps_the_withdrawn_one_with_its_reason(self, kb):
        entry = add(kb, "kind(anne).", turn=1)
        add(kb, "rough(bob).", turn=2)
        kb.retract(entry.id, turn=3, rationale="misread the sentence")

        everything = kb.clauses()
        assert [c.id for c in everything] == ["c1", "c2"]
        assert everything[0].retracted is True
        assert everything[0].retracted_turn == 3
        assert everything[0].retracted_because == "misread the sentence"
        assert everything[1].retracted is False

    def test_active_is_the_subset_still_in_force(self, kb):
        entry = add(kb, "kind(anne).")
        add(kb, "rough(bob).")
        kb.retract(entry.id)
        assert [c.id for c in kb.active()] == ["c2"]
        assert [c.id for c in kb.clauses()] == ["c1", "c2"]

    def test_cannot_retract_twice(self, kb):
        entry = add(kb, "kind(anne).")
        kb.retract(entry.id)
        with pytest.raises(ValueError, match="already been retracted"):
            kb.retract(entry.id)

    def test_cannot_retract_something_that_is_not_there(self, kb):
        with pytest.raises(KeyError):
            kb.retract("c99")


class TestDeclarations:
    def test_declaration_is_stored(self, kb):
        kb.declare("kind/1", "kind(Person): Person has a kind disposition", turn=2)
        declared = kb.declarations()
        assert declared["kind/1"].gloss.startswith("kind(Person)")
        assert declared["kind/1"].turn == 2

    def test_later_declaration_replaces_the_earlier_one(self, kb):
        kb.declare("kind/1", "first")
        kb.declare("kind/1", "second")
        assert kb.declarations()["kind/1"].gloss == "second"


class TestGeneratedProgram:
    def test_contains_the_clauses(self, kb):
        add(kb, "kind(anne).")
        add(kb, r"quiet(X) :- kind(X), \+ rough(X).")
        program = kb.to_prolog()
        assert "kind(anne)." in program
        assert r"quiet(X) :- kind(X), \+ rough(X)." in program

    def test_clauses_carry_their_ledger_id(self, kb):
        add(kb, "kind(anne).", source_text="Anne is kind.")
        program = kb.to_prolog()
        assert "% [c1] Anne is kind." in program

    def test_retracted_clauses_are_left_out(self, kb):
        entry = add(kb, "kind(anne).")
        add(kb, "rough(bob).")
        kb.retract(entry.id)
        program = kb.to_prolog()
        assert "kind(anne)." not in program
        assert "rough(bob)." in program

    def test_written_file_replaces_cleanly(self, kb, tmp_path):
        add(kb, "kind(anne).")
        target = tmp_path / "build" / "kb.pl"
        kb.write_prolog(target)
        assert "kind(anne)." in target.read_text(encoding="utf-8")

        kb.write_prolog(target)  # again, over the top
        assert target.read_text(encoding="utf-8").count("kind(anne).") == 1
        assert not list(target.parent.glob("*.tmp"))


class TestReplay:
    def test_state_after_each_turn(self, kb):
        add(kb, "kind(anne).", turn=1)
        add(kb, "rough(bob).", turn=2)
        add(kb, "kind(carol).", turn=3)

        states = dict(kb.replay())
        assert len(states[1]) == 1
        assert len(states[2]) == 2
        assert len(states[3]) == 3

    def test_retraction_shows_up_at_the_right_turn(self, kb):
        entry = add(kb, "kind(anne).", turn=1)
        add(kb, "rough(bob).", turn=2)
        kb.retract(entry.id, turn=3)

        states = dict(kb.replay())
        assert len(states[1]) == 1
        assert len(states[2]) == 2
        assert [i.text for i in states[3]] == ["rough(bob)."]

    def test_next_turn_counts_up(self, kb):
        assert kb.next_turn() == 1
        add(kb, "kind(anne).", turn=1)
        assert kb.next_turn() == 2


class TestBadLedger:
    def test_broken_line_is_reported_with_its_number(self, kb):
        kb.path.write_text('{"id":"c1","op":"assert","created_at":"x","clause":"a."}\nnot json\n', encoding="utf-8")
        with pytest.raises(ValueError, match="line 2"):
            kb.entries()
