import pytest

from logiclayer.core.ast import Atom, Num, Struct, Var, format_clause
from logiclayer.core.parse import ParseError, parse_clause, parse_goal


def roundtrip(text: str) -> str:
    """Text in, structure, text back out. Should be stable."""
    return format_clause(parse_clause(text))


class TestFacts:
    def test_atom_fact(self):
        clause = parse_clause("kind(anne).")
        assert clause.is_fact
        assert clause.indicator == "kind/1"
        assert clause.head == Struct("kind", (Atom("anne"),))

    def test_zero_argument_fact(self):
        clause = parse_clause("raining.")
        assert clause.head == Atom("raining")
        assert clause.indicator == "raining/0"

    def test_several_arguments(self):
        clause = parse_clause("between(a, b, c).")
        assert clause.indicator == "between/3"

    def test_numbers(self):
        clause = parse_clause("age(anne, 34).")
        assert clause.head.args[1] == Num(34)

    def test_float(self):
        assert parse_clause("mass(earth, 5.97).").head.args[1] == Num(5.97)

    def test_nested_term(self):
        clause = parse_clause("owns(anne, book(prolog)).")
        assert clause.head.args[1] == Struct("book", (Atom("prolog"),))

    def test_quoted_atom(self):
        clause = parse_clause("lives(anne, 'New York').")
        assert clause.head.args[1] == Atom("New York")

    def test_doubled_quote_inside_an_atom(self):
        """The ISO way of escaping a quote."""
        clause = parse_clause("says(anne, 'it''s fine').")
        assert clause.head.args[1] == Atom("it's fine")

    def test_backslash_escaped_quote(self):
        """SWI also accepts this form."""
        clause = parse_clause(r"says(anne, 'it\'s fine').")
        assert clause.head.args[1] == Atom("it's fine")

    def test_quotes_are_written_back_doubled(self):
        """We print the ISO form regardless of which form came in."""
        assert roundtrip(r"says(anne, 'it\'s fine').") == "says(anne, 'it''s fine')."


class TestRules:
    def test_simple_rule(self):
        clause = parse_clause("quiet(X) :- kind(X).")
        assert not clause.is_fact
        assert len(clause.body) == 1
        assert clause.body[0].goal == Struct("kind", (Var("X"),))

    def test_conjunction(self):
        clause = parse_clause("quiet(X) :- kind(X), calm(X).")
        assert len(clause.body) == 2

    def test_negation(self):
        clause = parse_clause(r"quiet(X) :- kind(X), \+ rough(X).")
        assert clause.body[0].negated is False
        assert clause.body[1].negated is True

    def test_predicates_lists_head_first_without_duplicates(self):
        clause = parse_clause(r"p(X) :- q(X), r(X), q(X).")
        assert clause.predicates() == ["p/1", "q/1", "r/1"]


class TestRoundTrip:
    @pytest.mark.parametrize(
        "text",
        [
            "kind(anne).",
            "raining.",
            "parent(alice, bob).",
            "quiet(X) :- kind(X).",
            r"quiet(X) :- kind(X), \+ rough(X).",
            "owns(anne, book(prolog)).",
            "age(anne, 34).",
            "lives(anne, 'New York').",
        ],
    )
    def test_text_survives_the_round_trip(self, text):
        assert roundtrip(text) == text

    def test_reformats_sloppy_spacing(self):
        assert roundtrip("quiet(X):-kind(X),  calm(X) .") == "quiet(X) :- kind(X), calm(X)."


class TestRejections:
    """We reject what we do not understand rather than passing it to the engine."""

    @pytest.mark.parametrize(
        "text",
        [
            "kind(anne)",             # no full stop
            "kind(anne",              # unclosed bracket
            "X :- kind(X).",          # a variable cannot be a goal
            "kind(anne). extra(x).",  # two clauses at once
            "",                       # nothing
            "   ",                    # only whitespace
            "kind(anne) :- .",        # empty body
            "'unclosed.",             # unclosed quote
            "p(X) :- X = 3.",         # operators are not supported yet
            "p([1,2]).",              # lists are not supported yet
        ],
    )
    def test_rejected(self, text):
        with pytest.raises(ParseError):
            parse_clause(text)

    def test_error_points_at_the_problem(self):
        with pytest.raises(ParseError) as excinfo:
            parse_clause("kind(anne) :- 3.")
        assert "^" in excinfo.value.caret()


class TestGoals:
    def test_full_stop_is_optional(self):
        assert parse_goal("kind(anne)").goal == parse_goal("kind(anne).").goal

    def test_negated_goal(self):
        assert parse_goal(r"\+ rough(anne)").negated is True

    def test_variable_goal(self):
        assert parse_goal("kind(Who)").goal == Struct("kind", (Var("Who"),))

    def test_rejects_two_goals(self):
        with pytest.raises(ParseError):
            parse_goal("kind(anne), rough(bob)")
