"""The registry of what each predicate means.

The failure most likely to spoil a long conversation is not bad deduction. It
is the agent writing kind(anne) on turn 2 and is_kind(carol) on turn 7. Those
are two unrelated predicates as far as the engine is concerned, so a proof
that should succeed quietly fails and nothing looks wrong.

Argument order is the same problem. Does parent(X, Y) mean X is the parent of
Y, or the reverse? Whichever the agent picked first has to be what it picks
every time.

Asking the agent to check before it asserts does not work, because it will
sometimes forget and nothing will complain. So a predicate has to be declared
before it can be used, and a declaration carries a plain-English gloss.

The gloss is what makes this more than spell-checking. Matching on spelling
alone would catch is_kind and miss friendly. Handing back the meaning and the
sentence that first prompted it lets the agent judge whether an existing
predicate is the same idea.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass

from .ast import Clause
from .kb import Declaration


@dataclass(frozen=True, slots=True)
class Undeclared:
    """A predicate used without being declared, and what it might have meant."""

    indicator: str
    same_name: tuple[Declaration, ...] = ()  # right name, wrong number of arguments
    similar: tuple[Declaration, ...] = ()    # a name close enough to be a typo

    @property
    def name(self) -> str:
        return self.indicator.rsplit("/", 1)[0]

    @property
    def arity(self) -> int:
        return int(self.indicator.rsplit("/", 1)[1])


class UndeclaredPredicate(ValueError):
    """Raised instead of storing a clause that uses an undeclared predicate."""

    def __init__(self, clause: Clause, missing: list[Undeclared]) -> None:
        self.clause = clause
        self.missing = missing
        super().__init__(explain(missing))


def split(indicator: str) -> tuple[str, int]:
    """kind/1 -> ("kind", 1). Raises if the shape is wrong."""
    name, _, arity = indicator.rpartition("/")
    if not name or not arity.isdigit():
        raise ValueError(f"a predicate is written name/arity, like kind/1, not {indicator!r}")
    return name, int(arity)


def check(clause: Clause, declared: dict[str, Declaration]) -> list[Undeclared]:
    """Predicates this clause uses that have not been declared."""
    missing: list[Undeclared] = []

    for indicator in clause.predicates():
        if indicator in declared:
            continue
        name, _ = split(indicator)
        missing.append(
            Undeclared(
                indicator=indicator,
                same_name=tuple(d for i, d in declared.items() if split(i)[0] == name),
                similar=tuple(_similar(name, declared)),
            )
        )

    return missing


def _similar(name: str, declared: dict[str, Declaration]) -> list[Declaration]:
    """Declared predicates whose name is close enough to be the same idea.

    Spelling only. It catches is_kind for kind and misses friendly for kind,
    which is why the gloss is shown alongside -- the agent, not the edit
    distance, decides whether two names mean the same thing.
    """
    by_name: dict[str, Declaration] = {}
    for indicator, declaration in declared.items():
        by_name.setdefault(split(indicator)[0], declaration)

    close = difflib.get_close_matches(name, list(by_name), n=3, cutoff=0.7)
    return [by_name[n] for n in close if by_name[n].indicator.rsplit("/", 1)[0] != name]


def explain(missing: list[Undeclared]) -> str:
    """Why the clause was refused, and what to do about it."""
    if not missing:
        return ""

    lines: list[str] = []
    for item in missing:
        lines.append(f"{item.indicator} has not been declared.")
        lines.append("")

        if item.same_name:
            other = item.same_name[0]
            lines += [
                f"  {other.indicator} is declared, with a different number of arguments:",
                f"      {other.gloss}",
                "",
                "  A predicate always takes the same number of arguments. Either use",
                f"  {other.indicator}, or declare {item.indicator} as a separate thing.",
                "",
            ]
        elif item.similar:
            lines.append("  These are declared and look close:")
            for candidate in item.similar:
                lines.append(f"      {candidate.indicator}   {candidate.gloss}")
            lines += [
                "",
                "  If one of them is the same idea, use it instead.",
                "",
            ]

        lines += [
            "  Otherwise declare it, saying what it means and what the",
            "  arguments are, in order:",
            "",
            f"      logic declare {item.indicator!r} --gloss \"...\"",
            "",
        ]

    return "\n".join(lines).rstrip()
