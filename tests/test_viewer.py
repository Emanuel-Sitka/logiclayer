"""The generated web page."""

from __future__ import annotations

import json
import re

import pytest

from logiclayer import viewer
from logiclayer.cli import OK, main
from logiclayer.core.parse import parse_clause


@pytest.fixture
def run(tmp_path, capsys):
    ledger = tmp_path / "kb.jsonl"

    def _run(*argv: str):
        code = main(["--kb", str(ledger), *argv])
        captured = capsys.readouterr()
        return code, captured.out + captured.err

    return _run


def embedded(html: str) -> dict:
    """The data the page was given."""
    match = re.search(
        r'<script id="logiclayer-data" type="application/json">(.*?)</script>',
        html,
        re.DOTALL,
    )
    assert match, "the page has no data in it"
    return json.loads(match.group(1))


class TestRecursionIsVisible:
    """Clause.predicates() lists each predicate once, so a rule that calls its
    own head loses that. Recursion is the shape that makes Prolog run forever,
    so it needs its own accessor."""

    def test_predicates_still_deduplicates(self):
        clause = parse_clause("ancestor(X, Y) :- parent(X, Z), ancestor(Z, Y).")
        assert clause.predicates() == ["ancestor/2", "parent/2"]

    def test_the_body_keeps_the_recursive_call(self):
        clause = parse_clause("ancestor(X, Y) :- parent(X, Z), ancestor(Z, Y).")
        assert clause.body_predicates() == ["parent/2", "ancestor/2"]

    def test_recursion_is_reported(self):
        assert parse_clause("ancestor(X, Y) :- parent(X, Z), ancestor(Z, Y).").is_recursive
        assert not parse_clause("ancestor(X, Y) :- parent(X, Y).").is_recursive
        assert not parse_clause("kind(anne).").is_recursive

    def test_inspect_sees_a_predicate_using_itself(self, run):
        run("declare", "ancestor/2", "--gloss", "ancestor(Older, Younger)")
        run("declare", "parent/2", "--gloss", "parent(Older, Younger)")
        run("assert", "ancestor(X, Y) :- parent(X, Z), ancestor(Z, Y).", "--because", "recursive case")
        _, out = run("inspect", "ancestor")
        assert "used in the body of 1 rule" in out


class TestPage:
    def test_the_data_is_embedded(self, run, tmp_path):
        run("declare", "kind/1", "--gloss", "kind(Person): Person is kind")
        run("assert", "kind(anne).", "--source", "Anne is kind.", "--because", "direct")
        target = tmp_path / "page.html"
        code, _ = run("export", "--format", "html", "--out", str(target))
        assert code == OK

        payload = embedded(target.read_text(encoding="utf-8"))
        assert payload["query"] is None
        assert payload["kb"]["clauses"][0]["source_text"] == "Anne is kind."
        assert payload["kb"]["clauses"][0]["rationale"] == "direct"

    def test_it_is_one_file_with_nothing_to_fetch(self, run, tmp_path):
        run("declare", "kind/1", "--gloss", "kind(Person)")
        run("assert", "kind(anne).", "--because", "direct")
        target = tmp_path / "page.html"
        run("export", "--format", "html", "--out", str(target))
        html = target.read_text(encoding="utf-8")

        # No external script or stylesheet, so the page works offline and can
        # be opened by double-clicking it.
        assert not re.search(r'<script[^>]+src="https?://', html)
        assert not re.search(r'<link[^>]+href="https?://', html)

    def test_the_head_and_body_predicates_are_separate(self, run, tmp_path):
        run("declare", "ancestor/2", "--gloss", "ancestor(Older, Younger)")
        run("declare", "parent/2", "--gloss", "parent(Older, Younger)")
        run("assert", "ancestor(X, Y) :- parent(X, Z), ancestor(Z, Y).", "--because", "recursive")
        target = tmp_path / "page.html"
        run("export", "--format", "html", "--out", str(target))

        clause = embedded(target.read_text(encoding="utf-8"))["kb"]["clauses"][0]
        assert clause["head_predicate"] == "ancestor/2"
        assert clause["body_predicates"] == ["parent/2", "ancestor/2"]
        assert clause["is_recursive"] is True

    def test_negated_uses_are_marked(self, run, tmp_path):
        for name in ["kind", "rough", "quiet"]:
            run("declare", f"{name}/1", "--gloss", f"{name}(Person)")
        run("assert", r"quiet(X) :- kind(X), \+ rough(X).", "--because", "conditional")
        target = tmp_path / "page.html"
        run("export", "--format", "html", "--out", str(target))

        clause = embedded(target.read_text(encoding="utf-8"))["kb"]["clauses"][0]
        assert clause["negated_predicates"] == ["rough/1"]


class TestWithdrawnClauses:
    """A withdrawn clause is kept rather than dropped. Dropping it would make a
    clause appear to vanish between one turn and the next with no explanation,
    which is what the append-only ledger exists to avoid."""

    def test_a_retracted_clause_still_reaches_the_page(self, run, tmp_path):
        run("declare", "kind/1", "--gloss", "kind(Person)")
        run("assert", "kind(anne).", "--source", "Anne is kind.", "--because", "direct")
        run("assert", "kind(bob).", "--source", "Bob is kind.", "--because", "misread")
        run("retract", "c2", "--because", "I misread the sentence")

        target = tmp_path / "page.html"
        run("export", "--format", "html", "--out", str(target))
        clauses = embedded(target.read_text(encoding="utf-8"))["kb"]["clauses"]

        assert [c["id"] for c in clauses] == ["c1", "c2"]
        assert clauses[0]["retracted"] is False
        assert clauses[1]["retracted"] is True
        assert clauses[1]["retracted_because"] == "I misread the sentence"
        assert clauses[1]["retracted_turn"] == 4

    def test_nothing_else_starts_showing_withdrawn_clauses(self, run, tmp_path):
        """The engine must still only see what is in force."""
        run("declare", "kind/1", "--gloss", "kind(Person)")
        run("assert", "kind(anne).", "--because", "direct")
        run("assert", "kind(bob).", "--because", "misread")
        run("retract", "c2", "--because", "wrong")

        _, program = run("export", "--format", "pl")
        assert "kind(anne)." in program
        assert "kind(bob)." not in program


class TestEscaping:
    def test_a_closing_script_tag_cannot_break_out(self):
        """Text containing </script> would otherwise end the tag early and the
        rest of the data would be parsed as HTML."""
        html = viewer.render({"kb": {"note": "</script><img onerror=alert(1)>"}, "query": None})
        assert "</script><img" not in html
        assert embedded(html)["kb"]["note"] == "</script><img onerror=alert(1)>"

    def test_the_json_stays_valid(self):
        html = viewer.render({"kb": {"text": "a < b & c > d"}, "query": None})
        assert embedded(html)["kb"]["text"] == "a < b & c > d"


class TestMissingTemplate:
    def test_it_says_how_to_build_it(self, monkeypatch, tmp_path):
        monkeypatch.setattr(viewer, "TEMPLATE", tmp_path / "gone.html")
        with pytest.raises(viewer.ViewerMissing, match="npm run build"):
            viewer.render({"kb": {}, "query": None})
