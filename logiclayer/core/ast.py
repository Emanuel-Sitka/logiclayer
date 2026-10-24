"""How a clause is held in memory.

This is a data structure and a printer, nothing more. There is no unification,
no resolution and no solving here. The engines do all of that.

It exists so the stored knowledge base is not tied to Prolog's own syntax.
Engines disagree about surface details -- how negation is written, how a rule
ends -- so each engine port prints these structures its own way. Without this,
the ledger would hold Prolog source text and we would be married to Prolog.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# An atom can be written bare when it starts with a lowercase letter and holds
# only letters, digits and underscores. Anything else has to be quoted.
_BARE_ATOM = re.compile(r"^[a-z][a-zA-Z0-9_]*$")
_VALID_VAR = re.compile(r"^[A-Z_][a-zA-Z0-9_]*$")


class Term:
    """Base class for anything that can appear as an argument."""

    __slots__ = ()


@dataclass(frozen=True, slots=True)
class Atom(Term):
    """A specific named thing: anne, bob, 'New York'."""

    name: str

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("atom name cannot be empty")


@dataclass(frozen=True, slots=True)
class Var(Term):
    """A variable, standing for anything: X, Who, _.

    Written with a leading capital or underscore, which is how Prolog tells
    variables apart from atoms.
    """

    name: str

    def __post_init__(self) -> None:
        if not _VALID_VAR.match(self.name):
            raise ValueError(f"variable names start with a capital or underscore: {self.name!r}")


@dataclass(frozen=True, slots=True)
class Num(Term):
    """An integer or a float."""

    value: int | float


@dataclass(frozen=True, slots=True)
class Struct(Term):
    """A compound term: parent(alice, bob).

    An atom is the zero-argument case, but it is kept as its own type because
    the distinction reads more clearly everywhere else.
    """

    name: str
    args: tuple[Term, ...]

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("struct name cannot be empty")
        if not self.args:
            raise ValueError(f"{self.name} has no arguments; use Atom instead")

    @property
    def arity(self) -> int:
        return len(self.args)


# Only these can be the head of a clause or a goal in its body. A variable or a
# number in that position is not a statement about anything.
Callable = Atom | Struct


@dataclass(frozen=True, slots=True)
class Literal:
    """One goal in the body of a rule, possibly negated.

    `negated` means negation as failure: "this could not be proved". It does
    not mean "this is false". See docs/concepts.md.
    """

    goal: Callable
    negated: bool = False

    @property
    def indicator(self) -> str:
        return indicator(self.goal)


@dataclass(frozen=True, slots=True)
class Clause:
    """A fact or a rule.

    An empty body means a fact. A non-empty body means a rule, read as
    "head is true if every literal in the body is true".
    """

    head: Callable
    body: tuple[Literal, ...] = field(default=())

    @property
    def is_fact(self) -> bool:
        return not self.body

    @property
    def indicator(self) -> str:
        """The predicate this clause defines, as name/arity."""
        return indicator(self.head)

    def predicates(self) -> list[str]:
        """Every predicate this clause mentions, head first, without duplicates.

        A predicate appearing in both the head and the body is listed once. Use
        body_predicates() when you need to know what the body calls, because
        this deduplication hides recursion.
        """
        seen = {self.indicator: None}
        for literal in self.body:
            seen.setdefault(literal.indicator, None)
        return list(seen)

    def body_predicates(self) -> list[str]:
        """What the body calls, in order, without duplicates.

        Kept separate from predicates() because a rule whose body calls its own
        head is recursive, and predicates() loses that -- the head is already in
        the list, so the body occurrence disappears. Recursion is worth seeing:
        it is the shape that makes Prolog run forever.
        """
        seen: dict[str, None] = {}
        for literal in self.body:
            seen.setdefault(literal.indicator, None)
        return list(seen)

    @property
    def is_recursive(self) -> bool:
        """Whether the body calls the predicate the head defines."""
        return self.indicator in self.body_predicates()


def indicator(term: Callable) -> str:
    """The name/arity form used to identify a predicate: kind/1, parent/2."""
    if isinstance(term, Atom):
        return f"{term.name}/0"
    return f"{term.name}/{term.arity}"


def variables(term: Term) -> list[str]:
    """Every variable name in a term, in the order first seen."""
    found: dict[str, None] = {}

    def walk(t: Term) -> None:
        if isinstance(t, Var):
            found.setdefault(t.name, None)
        elif isinstance(t, Struct):
            for arg in t.args:
                walk(arg)

    walk(term)
    return list(found)


# ---------------------------------------------------------------------------
# Printing back to Prolog text.
#
# This lives here rather than in the engine port because plain Prolog syntax is
# also what we show the user and what the agent types. An engine that needs a
# different syntax overrides it.
# ---------------------------------------------------------------------------


def quote_atom(name: str) -> str:
    """Wrap an atom in single quotes if Prolog would not accept it bare.

    A quote inside the atom is doubled rather than backslash escaped. Both work
    in SWI-Prolog, but doubling is the ISO standard and so travels better to
    other engines. A backslash still has to be doubled, because inside a quoted
    atom it introduces an escape.
    """
    if _BARE_ATOM.match(name):
        return name
    escaped = name.replace("\\", "\\\\").replace("'", "''")
    return f"'{escaped}'"


def format_term(term: Term) -> str:
    if isinstance(term, Atom):
        return quote_atom(term.name)
    if isinstance(term, Var):
        return term.name
    if isinstance(term, Num):
        return repr(term.value)
    if isinstance(term, Struct):
        args = ", ".join(format_term(a) for a in term.args)
        return f"{quote_atom(term.name)}({args})"
    raise TypeError(f"not a term: {term!r}")


def format_literal(literal: Literal) -> str:
    text = format_term(literal.goal)
    return f"\\+ {text}" if literal.negated else text


def format_clause(clause: Clause) -> str:
    """One clause as Prolog source, including the closing full stop."""
    head = format_term(clause.head)
    if clause.is_fact:
        return f"{head}."
    body = ", ".join(format_literal(lit) for lit in clause.body)
    return f"{head} :- {body}."
