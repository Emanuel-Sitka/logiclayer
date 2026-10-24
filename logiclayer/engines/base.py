"""What every engine has to provide, and nothing more.

The boundary is: the layer does the bookkeeping, the engine does the deduction.
So an engine never sees an assert or a retract. It is handed a complete program
and a goal, and asked to solve it.

That shape was chosen over the more obvious assert/query/retract interface
because Prolog can be added to incrementally but answer set and Datalog engines
cannot -- they solve a whole program at once. A stateless engine is the only
version all of them can implement.

Handing over the whole program each time costs milliseconds at conversational
scale. If it ever matters, a warm process can hide behind this interface
without the contract changing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, runtime_checkable

from ..core.ast import Clause, Literal


class Status(Enum):
    """The outcome of a query.

    Three values rather than two, and this is the most important detail in the
    interface. A boolean would let a Prolog engine quietly report "false" when
    all it means is "I could not find a proof". Those are different claims, and
    only some engines can make the stronger one.
    """

    PROVED = "proved"
    DISPROVED = "disproved"  # the engine proved the negation
    UNKNOWN = "unknown"      # no proof found, which is not the same as false
    ERROR = "error"          # timeout, resource limit, or engine fault


@dataclass(frozen=True, slots=True)
class Capabilities:
    """What an engine can actually do.

    Engines genuinely differ. Declaring the differences lets the layer refuse a
    request or handle it explicitly, instead of quietly returning something
    weaker than the caller assumed.
    """

    name: str
    version: str = "unknown"

    naf: bool = True                     # negation as failure: "could not prove"
    classical_negation: bool = False     # can prove that something is false
    function_symbols: bool = True        # nested terms; false for grounded ASP
    native_justification: bool = False   # engine emits its own proof tree
    guaranteed_termination: bool = False # false for Prolog and s(CASP)

    def describe(self) -> str:
        supported = [
            label
            for label, on in [
                ("negation as failure", self.naf),
                ("classical negation", self.classical_negation),
                ("function symbols", self.function_symbols),
                ("native justification", self.native_justification),
                ("guaranteed termination", self.guaranteed_termination),
            ]
            if on
        ]
        return f"{self.name} {self.version}: " + (", ".join(supported) or "nothing declared")


@dataclass(frozen=True, slots=True)
class SourcedClause:
    """A clause together with the ledger entry it came from.

    The id travels into the proof tree so a conclusion can be traced back to
    the sentence that produced it.
    """

    id: str
    clause: Clause


@dataclass(frozen=True, slots=True)
class Program:
    """Everything the engine should reason over."""

    clauses: tuple[SourcedClause, ...] = ()

    def __len__(self) -> int:
        return len(self.clauses)


@dataclass(frozen=True, slots=True)
class SolveOpts:
    """How to run one query.

    The timeout is not optional and has no unlimited setting. Prolog can loop
    forever on rules that look perfectly reasonable, and so can s(CASP).
    """

    timeout: float = 10.0
    max_solutions: int = 100
    want_proof: bool = True

    def __post_init__(self) -> None:
        if self.timeout <= 0:
            raise ValueError("timeout must be positive; there is no unlimited setting")
        if self.max_solutions < 1:
            raise ValueError("max_solutions must be at least 1")


_BOX_GLYPHS = {"last": "└─ ", "mid": "├─ ", "gap": "   ", "bar": "│  "}
_ASCII_GLYPHS = {"last": "`- ", "mid": "|- ", "gap": "   ", "bar": "|  "}


@dataclass(frozen=True, slots=True)
class Assumption:
    """Something the engine took to be false because nothing said otherwise.

    When a proof uses negation, the engine does not establish that the goal is
    false. It looks, finds nothing, and treats it as false -- the closed-world
    assumption. That is a premise the answer rests on which nobody supplied,
    and an answer that does not report it is overclaiming.

    These are also the useful questions to ask back: if the conversation later
    supplies one of them, the answer that relied on it no longer holds.
    """

    goal: str                   # "rough(anne)", taken to be false
    kind: str = "closed_world"
    ground: bool = True
    """Whether the goal was fully filled in when the negation ran.

    False means a variable was still loose inside it, so the engine asked about
    a whole family of things rather than one thing -- "is any Orwell book
    damaged?" rather than "is this book damaged?". The answer is then sound by
    Prolog's own rules but is not the question the rule intended.
    """

    def describe(self) -> str:
        if self.ground:
            return f"{self.goal} is taken as false because nothing states it"
        return (
            f"{self.goal} was checked with a variable still loose in it, "
            f"so the engine asked about every term of that shape at once"
        )


@dataclass(frozen=True, slots=True)
class Justification:
    """One step of a proof.

    kind is one of:
      fact    a clause with no conditions was used
      rule    a clause with conditions was used; children are those conditions
      naf     a negated goal succeeded because the goal could not be proved
    """

    goal: str
    kind: str
    clause_id: str | None = None
    children: tuple[Justification, ...] = ()
    ground: bool = True  # naf nodes only: was the goal fully filled in?

    def render(self, *, ascii_only: bool = False) -> str:
        """The proof as an indented tree, for terminal output.

        ascii_only avoids the box-drawing characters, which some Windows
        consoles cannot encode.
        """
        glyphs = _ASCII_GLYPHS if ascii_only else _BOX_GLYPHS
        lines = [self._label() + self._tag()]
        self._render_children(lines, "", glyphs)
        return "\n".join(lines)

    def _render_children(self, lines: list[str], prefix: str, glyphs: dict[str, str]) -> None:
        for i, child in enumerate(self.children):
            last = i == len(self.children) - 1
            branch = glyphs["last"] if last else glyphs["mid"]
            lines.append(f"{prefix}{branch}{child._label()}{child._tag()}")
            child._render_children(lines, prefix + (glyphs["gap"] if last else glyphs["bar"]), glyphs)

    def _label(self) -> str:
        """A naf node stores the bare positive goal, so put the \\+ back."""
        return f"\\+ {self.goal}" if self.kind == "naf" else self.goal

    def _tag(self) -> str:
        if self.kind == "naf":
            if not self.ground:
                return "   [assumed false -- BUT A VARIABLE WAS LOOSE]"
            return "   [assumed false]"
        return f"   [{self.clause_id}]" if self.clause_id else ""

    def assumptions(self) -> tuple[Assumption, ...]:
        """Everything this proof took to be false, in the order first used."""
        seen: dict[str, Assumption] = {}
        stack = [self]
        while stack:
            node = stack.pop(0)
            if node.kind == "naf":
                seen.setdefault(node.goal, Assumption(goal=node.goal, ground=node.ground))
            stack.extend(node.children)
        return tuple(seen.values())

    def clause_ids(self) -> list[str]:
        """Every ledger id this proof depended on, in the order first used."""
        seen: dict[str, None] = {}
        stack = [self]
        while stack:
            node = stack.pop(0)
            if node.clause_id:
                seen.setdefault(node.clause_id, None)
            stack.extend(node.children)
        return list(seen)


@dataclass(frozen=True, slots=True)
class Answer:
    """One way the goal was satisfied."""

    bindings: dict[str, str] = field(default_factory=dict)
    justification: Justification | None = None

    @property
    def assumptions(self) -> tuple[Assumption, ...]:
        """What this particular proof took to be false.

        Per answer rather than per query, because different proofs of the same
        goal can rest on different assumptions.
        """
        return self.justification.assumptions() if self.justification else ()


@dataclass(frozen=True, slots=True)
class Solution:
    """The result of one query."""

    status: Status
    answers: tuple[Answer, ...] = ()
    engine: str = "unknown"
    duration_ms: float = 0.0
    message: str | None = None   # why it errored, or why it stopped early
    truncated: bool = False      # there were more answers than max_solutions
    assumptions_checked: bool = True
    """Whether we looked for assumptions at all.

    False when the query ran without building a proof. There is then no tree to
    walk, so an empty assumption list means "we did not look", not "there were
    none". Reporting the second when we mean the first is exactly the
    overclaiming this machinery exists to prevent, so verdict() keeps them
    apart.
    """

    @property
    def proved(self) -> bool:
        return self.status is Status.PROVED

    @property
    def justification(self) -> Justification | None:
        """The proof for the first answer, if there is one."""
        return self.answers[0].justification if self.answers else None

    @property
    def assumptions(self) -> tuple[Assumption, ...]:
        """Everything any answer took to be false, without duplicates."""
        seen: dict[str, Assumption] = {}
        for answer in self.answers:
            for assumption in answer.assumptions:
                seen.setdefault(assumption.goal, assumption)
        return tuple(seen.values())

    @property
    def conditional(self) -> bool | None:
        """Whether the result rests on anything unstated.

        None means we did not check. Not False -- that would be a claim we have
        not earned.
        """
        if not self.assumptions_checked:
            return None
        return bool(self.assumptions)

    @property
    def unsound_assumptions(self) -> tuple[Assumption, ...]:
        """Assumptions where a variable was still loose when the check ran."""
        return tuple(a for a in self.assumptions if not a.ground)

    def verdict(self) -> str:
        """The status together with what it rests on, as one phrase.

        Nothing should print the bare status. A caller that reads only the
        verdict gets the honest version, which is the point.
        """
        base = self.status.value
        if self.status in (Status.ERROR, Status.UNKNOWN) and not self.assumptions:
            return base
        if not self.assumptions_checked:
            return f"{base} (assumptions not checked)"
        if not self.assumptions:
            return base

        count = len(self.assumptions)
        noun = "assumption" if count == 1 else "assumptions"
        phrase = f"{base}, conditional on {count} {noun}"
        loose = len(self.unsound_assumptions)
        if loose:
            phrase += f" ({loose} checked with a variable still loose)"
        return phrase


@runtime_checkable
class Port(Protocol):
    """The whole contract an engine has to satisfy."""

    def capabilities(self) -> Capabilities: ...

    def solve(self, program: Program, goal: Literal, opts: SolveOpts) -> Solution: ...
