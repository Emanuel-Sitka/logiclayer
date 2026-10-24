"""Refuses rules whose negations would mean something other than intended.

Prolog runs a rule body left to right, carrying variable bindings forward. A
positive goal can bind variables. A negated goal never can -- it succeeds
precisely when its inner goal fails, and a failed goal leaves nothing bound.

So a negated goal placed before whatever would have bound its variable gets a
free variable, and there is no later chance to fix that. With a free variable,
`\\+ rough(X)` asks "is there anything at all that is rough?" rather than "is
this particular X rough?". Those are different questions with different
answers.

    quiet(X) :- kind(X), \\+ rough(X).    kind(X) binds X first. Correct.
    quiet(X) :- \\+ rough(X), kind(X).    X still free. Asks the wrong question.

The two rules are not variants of one statement. The second reads "if nothing
anywhere is rough, then every kind thing is quiet".

What makes this worth refusing rather than warning about is how quietly it
fails. Ask a closed question and the caller supplies the binding, so the broken
rule works. Ask an open one and it silently returns nothing. A rule whose
correctness depends on how it is called is not something to leave in a ledger
that later answers are drawn from.

The condition below is standard: a rule is safe, or range-restricted, when
every variable in a negated goal also appears in a positive goal earlier in the
body. Datalog requires it. Prolog does not.
"""

from __future__ import annotations

from dataclasses import dataclass

from .ast import Clause, Literal, format_clause, format_term, variables

# The anonymous variable is exempt. Writing \+ friend(X, _) is a deliberate way
# of saying "no friend at all", and that reading is often what was meant. A
# named variable is ambiguous, so we make the author choose.
ANONYMOUS = "_"


@dataclass(frozen=True, slots=True)
class UnsafeNegation:
    """One variable that is still free when a negated goal runs."""

    variable: str
    goal: str            # the negated goal, without the \+
    position: int        # which goal in the body, counting from zero
    binder: str | None   # a later positive goal that would bind it, if any

    @property
    def reorderable(self) -> bool:
        return self.binder is not None


class UnsafeClause(ValueError):
    """Raised instead of storing a rule whose negation would misbehave."""

    def __init__(self, clause: Clause, findings: list[UnsafeNegation]) -> None:
        self.clause = clause
        self.findings = findings
        self.suggestion = suggest(clause)
        super().__init__(explain(clause, findings))


def check(clause: Clause) -> list[UnsafeNegation]:
    """Every free variable appearing under a negation, in body order.

    Head variables deliberately do not count as bound. Whether they are bound
    depends on how the rule is called -- quiet(anne) binds X, quiet(Who) does
    not -- and we cannot know which will happen. So the rule has to be correct
    either way.
    """
    findings: list[UnsafeNegation] = []
    bound: set[str] = set()

    for position, literal in enumerate(clause.body):
        if not literal.negated:
            # Only positive goals can bind anything.
            bound.update(variables(literal.goal))
            continue

        for name in variables(literal.goal):
            if name == ANONYMOUS or name in bound:
                continue
            findings.append(
                UnsafeNegation(
                    variable=name,
                    goal=format_term(literal.goal),
                    position=position,
                    binder=_later_binder(clause.body, position, name),
                )
            )

    return findings


def is_safe(clause: Clause) -> bool:
    return not check(clause)


def _later_binder(body: tuple[Literal, ...], position: int, name: str) -> str | None:
    """A positive goal after `position` that would bind `name`."""
    for literal in body[position + 1 :]:
        if not literal.negated and name in variables(literal.goal):
            return format_term(literal.goal)
    return None


def suggest(clause: Clause) -> Clause | None:
    """The same rule with its negations moved to the end, if that fixes it.

    Moving a negation later can only leave more variables bound, so the
    reordering is always at least as safe as the original. It returns None when
    reordering cannot help, which means no positive goal binds the variable at
    all and the rule needs a goal saying what it ranges over.
    """
    if not clause.body:
        return None

    positives = tuple(lit for lit in clause.body if not lit.negated)
    negatives = tuple(lit for lit in clause.body if lit.negated)
    if not positives or not negatives:
        return None

    reordered = Clause(head=clause.head, body=positives + negatives)
    if reordered.body == clause.body:
        return None  # already in this order, so this is not the problem

    return reordered if is_safe(reordered) else None


def explain(clause: Clause, findings: list[UnsafeNegation] | None = None) -> str:
    """Why the rule was refused, and what to write instead.

    An agent reads error messages far more reliably than documentation, so the
    message carries the corrected clause rather than describing it.
    """
    findings = check(clause) if findings is None else findings
    if not findings:
        return ""

    lines = ["unsafe negation", "", f"    {format_clause(clause)}", ""]

    # One block per negated goal, however many of its variables are free.
    for goal, names in _group_by_goal(findings):
        joined = ", ".join(names)
        verb = "is" if len(names) == 1 else "are"
        lines += [
            f"  {joined} {verb} not bound when  \\+ {goal}  runs.",
            f"  There it means \"nothing at all satisfies {goal}\", not",
            f"  \"{goal} is false for this particular {names[0]}\".",
            "",
        ]

    # Variables no positive goal can bind, wherever it is placed. These need a
    # new goal saying what they range over; reordering will not reach them.
    unbindable = sorted({f.variable for f in findings if f.binder is None})

    lines += ["  Write it as:", "", f"      {_fixed_shape(clause, unbindable)}"]
    if unbindable:
        lines += [
            "",
            "  where domain/1 is whatever says what it is -- person(X),",
            "  file(X), employee(X). Or write _ in place of a variable if",
            "  you really mean \"there is nothing at all like this\".",
        ]

    return "\n".join(lines)


def _group_by_goal(findings: list[UnsafeNegation]) -> list[tuple[str, list[str]]]:
    """Free variables gathered per negated goal, so one goal gives one block."""
    grouped: dict[tuple[int, str], list[str]] = {}
    for finding in findings:
        grouped.setdefault((finding.position, finding.goal), []).append(finding.variable)
    return [(goal, names) for (_, goal), names in grouped.items()]


def _fixed_shape(clause: Clause, unbindable: list[str]) -> str:
    """The corrected rule: domain goals first, then positives, then negations.

    Built as text because domain/1 is a placeholder rather than a real
    predicate, and the printer would quote it.
    """
    from .ast import format_literal

    parts = [f"domain({name})" for name in unbindable]
    parts += [format_literal(lit) for lit in clause.body if not lit.negated]
    parts += [format_literal(lit) for lit in clause.body if lit.negated]
    return f"{format_term(clause.head)} :- {', '.join(parts)}."
