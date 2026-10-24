import pytest

from logiclayer.core.ast import format_clause
from logiclayer.core.kb import KnowledgeBase
from logiclayer.core.parse import parse_clause
from logiclayer.core.safety import UnsafeClause, check, explain, is_safe, suggest


def clause(text):
    return parse_clause(text)


class TestSafeRules:
    @pytest.mark.parametrize(
        "text",
        [
            "kind(anne).",                                  # a fact has no body
            "quiet(X) :- kind(X).",                         # no negation at all
            r"quiet(X) :- kind(X), \+ rough(X).",           # bound before the negation
            r"quiet(X) :- kind(X), calm(X), \+ rough(X).",  # bound two goals earlier
            r"quiet(X) :- \+ rough(anne), kind(X).",        # negation has no variables
            r"lonely(X) :- person(X), \+ friend(X, _).",    # _ is exempt on purpose
            r"nothing_rough :- \+ rough(_).",               # the existential reading, stated
        ],
    )
    def test_accepted(self, text):
        assert is_safe(clause(text))


class TestUnsafeRules:
    def test_negation_before_its_binder(self):
        findings = check(clause(r"quiet(X) :- \+ rough(X), kind(X)."))
        assert len(findings) == 1
        assert findings[0].variable == "X"
        assert findings[0].goal == "rough(X)"
        assert findings[0].binder == "kind(X)"
        assert findings[0].reorderable

    def test_nothing_can_bind_it(self):
        findings = check(clause(r"eligible(X) :- \+ warned(X)."))
        assert len(findings) == 1
        assert findings[0].binder is None
        assert not findings[0].reorderable

    def test_head_variables_do_not_count_as_bound(self):
        """quiet(anne) binds X, quiet(Who) does not, and we cannot know which
        the caller will ask. So the rule must be correct either way."""
        assert not is_safe(clause(r"quiet(X) :- \+ rough(X)."))

    def test_a_negation_cannot_bind_for_a_later_negation(self):
        findings = check(clause(r"p(X) :- \+ q(X), \+ r(X), s(X)."))
        assert [f.goal for f in findings] == ["q(X)", "r(X)"]

    def test_every_free_variable_is_reported(self):
        findings = check(clause(r"p(X, Y) :- \+ q(X, Y), r(X), s(Y)."))
        assert sorted(f.variable for f in findings) == ["X", "Y"]

    def test_only_the_free_ones_are_reported(self):
        findings = check(clause(r"p(X, Y) :- r(X), \+ q(X, Y), s(Y)."))
        assert [f.variable for f in findings] == ["Y"]

    def test_named_underscore_variable_is_not_exempt(self):
        """Only the bare _ signals "anything at all". _Foo is a real variable."""
        assert not is_safe(clause(r"p(X) :- person(X), \+ q(_Foo)."))


class TestSuggestion:
    def test_negations_move_to_the_end(self):
        fixed = suggest(clause(r"quiet(X) :- \+ rough(X), kind(X)."))
        assert format_clause(fixed) == r"quiet(X) :- kind(X), \+ rough(X)."

    def test_the_suggestion_is_itself_safe(self):
        fixed = suggest(clause(r"quiet(X) :- \+ rough(X), kind(X), calm(X)."))
        assert is_safe(fixed)

    def test_no_suggestion_when_reordering_cannot_help(self):
        assert suggest(clause(r"eligible(X) :- \+ warned(X).")) is None

    def test_no_suggestion_for_an_already_safe_rule(self):
        assert suggest(clause(r"quiet(X) :- kind(X), \+ rough(X).")) is None

    def test_head_is_preserved(self):
        fixed = suggest(clause(r"quiet(X) :- \+ rough(X), kind(X)."))
        assert fixed.head == clause(r"quiet(X) :- kind(X).").head


class TestExplanation:
    def test_reorderable_case_shows_the_corrected_rule(self):
        text = r"quiet(X) :- \+ rough(X), kind(X)."
        message = explain(clause(text))
        assert "unsafe negation" in message
        assert "X is not bound" in message
        assert r"quiet(X) :- kind(X), \+ rough(X)." in message

    def test_unbindable_case_suggests_a_domain_goal(self):
        message = explain(clause(r"eligible(X) :- \+ warned(X)."))
        assert r"eligible(X) :- domain(X), \+ warned(X)." in message
        assert "domain/1 is whatever says what it is" in message

    def test_mixed_case_reorders_and_adds_a_domain_only_where_needed(self):
        """person(X) can bind X, so X needs a reorder. Nothing can bind Y."""
        message = explain(clause(r"p(X, Y) :- \+ knows(X, Y), person(X)."))
        assert r"p(X, Y) :- domain(Y), person(X), \+ knows(X, Y)." in message
        assert "domain(X)" not in message

    def test_one_block_per_goal_not_per_variable(self):
        message = explain(clause(r"p(X, Y) :- \+ knows(X, Y), person(X)."))
        assert message.count("is not bound when") + message.count("are not bound when") == 1
        assert r"X, Y are not bound when  \+ knows(X, Y)  runs." in message

    def test_nothing_to_explain_when_safe(self):
        assert explain(clause(r"quiet(X) :- kind(X), \+ rough(X).")) == ""


class TestLedgerRefuses:
    @pytest.fixture
    def kb(self, tmp_path):
        return KnowledgeBase(tmp_path / "kb.jsonl")

    def test_unsafe_clause_is_not_stored(self, kb):
        with pytest.raises(UnsafeClause):
            kb.add_clause(clause(r"quiet(X) :- \+ rough(X), kind(X)."))
        assert kb.entries() == []

    def test_the_error_carries_the_fix(self, kb):
        with pytest.raises(UnsafeClause) as excinfo:
            kb.add_clause(clause(r"quiet(X) :- \+ rough(X), kind(X)."))
        assert format_clause(excinfo.value.suggestion) == r"quiet(X) :- kind(X), \+ rough(X)."
        assert r"quiet(X) :- kind(X), \+ rough(X)." in str(excinfo.value)

    def test_safe_clause_still_stores(self, kb):
        kb.add_clause(clause(r"quiet(X) :- kind(X), \+ rough(X)."))
        assert len(kb.active()) == 1

    def test_the_escape_hatch_works_for_tests(self, kb):
        kb.add_clause(clause(r"quiet(X) :- \+ rough(X), kind(X)."), allow_unsafe=True)
        assert len(kb.active()) == 1
