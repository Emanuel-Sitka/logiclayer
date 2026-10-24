"""Everything the tool says, in one place.

The agent reads this output. That makes it the interface, not decoration, and
two rules follow.

Never print a bare status. "proved" on its own hides whether the engine had to
invent a premise to get there, and an agent reading it will state the result
as fact. Solution.verdict() carries the caveat, so it is what gets printed.

An error message has to contain the fix. An agent reads error messages far
more reliably than documentation, and it reads them at exactly the moment the
correction is needed. A message that only describes the problem wastes that.
"""

from __future__ import annotations

import sys
from typing import TextIO

from .core.kb import ActiveClause, Declaration, Entry
from .engines.base import Solution, Status

INDENT = "  "


def supports_unicode(stream: TextIO | None = None) -> bool:
    """Whether the terminal can show box-drawing characters.

    The default Windows console encoding cannot, and printing to it raises
    rather than degrading, so this is checked rather than assumed.
    """
    stream = stream or sys.stdout
    encoding = getattr(stream, "encoding", None)
    if not encoding:
        return False
    try:
        "└─│".encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return False
    return True


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


def query_result(solution: Solution, *, ascii_only: bool = False) -> str:
    lines = [f"{solution.verdict()}   ({solution.duration_ms:.0f}ms)"]

    if solution.status is Status.ERROR:
        if solution.message:
            lines += ["", _wrap(solution.message)]
        return "\n".join(lines)

    if solution.status is Status.UNKNOWN:
        lines += [
            "",
            _wrap(
                "No proof was found. That is not the same as the goal being false -- "
                "this engine cannot tell those apart. Something may simply not have "
                "been said yet."
            ),
        ]
        return "\n".join(lines)

    answers = solution.answers
    if len(answers) == 1 and answers[0].bindings:
        lines += ["", _bindings(answers[0].bindings)]
    elif len(answers) > 1:
        lines.append("")
        for number, answer in enumerate(answers, start=1):
            shown = _bindings(answer.bindings) if answer.bindings else "(no variables)"
            lines.append(f"{INDENT}{number}. {shown.strip()}")
        if solution.truncated:
            lines.append(f"{INDENT}... there are more")

    if solution.assumptions:
        lines += ["", "assuming"]
        lines += [f"{INDENT}{a.describe()}" for a in solution.assumptions]
        if solution.unsound_assumptions:
            lines += ["", _wrap(_LOOSE_WARNING)]

    proof = solution.justification
    if proof is not None:
        heading = "proof" if len(answers) == 1 else "proof of the first answer"
        lines += ["", heading]
        lines += [INDENT + line for line in proof.render(ascii_only=ascii_only).splitlines()]

    return "\n".join(lines)


_LOOSE_WARNING = (
    "A negation ran with a variable still loose inside it. There it asks whether "
    "anything at all of that shape holds, rather than asking about one particular "
    "thing, so this answer may be broader or narrower than intended."
)


def _bindings(bindings: dict[str, str]) -> str:
    return INDENT + ", ".join(f"{name} = {value}" for name, value in bindings.items())


# ---------------------------------------------------------------------------
# Changes to the knowledge base
# ---------------------------------------------------------------------------


def stored(entry: Entry) -> str:
    predicates = " ".join(entry.predicates)
    return f"stored {entry.id}   {predicates}".rstrip()


def declared(entry: Entry) -> str:
    return f"declared {entry.indicator}   {entry.gloss}"


def retracted(entry: Entry, target: ActiveClause) -> str:
    return (
        f"retracted {target.id}   {target.text}\n"
        f"{INDENT}the entry stays in the ledger; it is no longer in force"
    )


def already_present(existing: ActiveClause) -> str:
    lines = [
        f"{existing.text} is already stored as {existing.id}.",
        "",
    ]
    if existing.source_text:
        lines.append(f"{INDENT}from: {existing.source_text}")
    if existing.rationale:
        lines.append(f"{INDENT}because: {existing.rationale}")
    if len(lines) > 2:
        lines.append("")
    lines.append(
        _wrap(
            "Nothing was stored. If this is genuinely a second statement, retract "
            "the first one and assert again with a reason that distinguishes them."
        )
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Looking things up
# ---------------------------------------------------------------------------


def inspect_predicate(
    indicator: str,
    declaration: Declaration | None,
    defined_by: list[ActiveClause],
    used_by: list[ActiveClause],
) -> str:
    lines = [indicator]

    if declaration is None:
        lines.append(f"{INDENT}not declared")
    else:
        lines.append(f"{INDENT}{declaration.gloss}")
        if declaration.turn is not None:
            lines.append(f"{INDENT}declared on turn {declaration.turn}")

    lines.append("")
    if defined_by:
        lines.append(f"{len(defined_by)} clause(s) define it")
        lines += [INDENT + _clause_line(c) for c in defined_by]
    else:
        lines.append("nothing defines it yet")
        lines.append(
            _wrap(
                "A goal about it will fail rather than raise an error, because "
                "anything underivable is treated as false."
            )
        )

    if used_by:
        lines += ["", f"used in the body of {len(used_by)} rule(s)"]
        lines += [INDENT + _clause_line(c) for c in used_by]

    return "\n".join(lines)


def inspect_all(
    declarations: dict[str, Declaration],
    counts: dict[str, int],
) -> str:
    if not declarations and not counts:
        return "nothing declared and nothing stored"

    lines = []
    known = sorted(set(declarations) | set(counts))
    width = max(len(name) for name in known)

    for indicator in known:
        count = counts.get(indicator, 0)
        declaration = declarations.get(indicator)
        gloss = declaration.gloss if declaration else "NOT DECLARED"
        lines.append(f"{indicator:<{width}}  {count:>3} clause(s)   {gloss}")

    undeclared = [i for i in counts if i not in declarations]
    if undeclared:
        lines += [
            "",
            _wrap(
                "Some predicates in use were never declared. They were probably "
                "stored before the registry existed, or through the library rather "
                "than this tool."
            ),
        ]
    return "\n".join(lines)


def _clause_line(clause: ActiveClause) -> str:
    parts = [f"[{clause.id}]", clause.text]
    if clause.turn is not None:
        parts.append(f"turn {clause.turn}")
    if clause.source_text:
        parts.append(f'"{clause.source_text}"')
    return "   ".join(parts)


def history(entries: list[Entry], *, brief: bool = False) -> str:
    """Every entry, with the reasoning behind it.

    The rationale is shown by default rather than hidden behind a flag. It is
    the record of why each clause is the translation it is, which is what tells
    a bad translation apart from bad deduction when something goes wrong. A
    command for reading the ledger back that omits it would be showing the
    least interesting half.
    """
    if not entries:
        return "the ledger is empty"

    # Retract entries name an id. On its own that says nothing, so look up what
    # was actually withdrawn.
    clause_text = {e.id: e.clause for e in entries if e.op == "assert"}

    lines: list[str] = []
    for entry in entries:
        turn = f"turn {entry.turn}" if entry.turn is not None else "-"

        if entry.op == "assert":
            headline = entry.clause
        elif entry.op == "retract":
            withdrawn = clause_text.get(entry.target or "", "")
            headline = f"retract {entry.target}   {withdrawn}".rstrip()
        else:
            headline = f"declare {entry.indicator}"

        lines.append(f"{entry.id:<5} {turn:<8} {headline}")
        if brief:
            continue

        detail = " " * 14
        if entry.op == "declare" and entry.gloss:
            lines.append(f"{detail}{entry.gloss}")
        if entry.source_text:
            lines.append(f'{detail}"{entry.source_text}"')
        if entry.rationale:
            lines.append(f"{detail}because: {entry.rationale}")
        if entry.topic:
            lines.append(f"{detail}topic: {entry.topic}")

    return "\n".join(lines)


def _wrap(text: str, width: int = 76) -> str:
    import textwrap

    return "\n".join(textwrap.wrap(text, width=width, initial_indent=INDENT, subsequent_indent=INDENT))
