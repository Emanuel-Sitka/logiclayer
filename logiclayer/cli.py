"""The command line: how an agent reaches the knowledge base.

A command-line tool rather than an MCP server, so the knowledge base lives in
a file rather than a running process. That is what makes separate knowledge
bases, saving between sessions, version history and an editable visualization
come out free.

Nothing here does any reasoning. It validates, stores, and hands whole
programs to an engine. See docs/concepts.md.

Exit codes, because an agent will branch on them:
    0   the command did its job, including a query that found no proof
    1   the input was refused and nothing was stored
    2   the engine failed -- a timeout, or a fault
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
from pathlib import Path

from . import render, viewer
from .core.kb import KnowledgeBase
from .core.parse import ParseError, parse_clause, parse_goal
from .core.safety import UnsafeClause
from .core.signature import UndeclaredPredicate, split
from .core.signature import check as check_declared
from .engines.base import Program, SolveOpts, SourcedClause, Status
from .engines.swipl import EngineNotFound, SwiPrologPort

# The help an agent reads before it knows anything. It covers what the tool is
# for, what clause syntax is accepted, and -- as importantly -- what is not, so
# that discovering the limits does not cost several failed commands.
#
# It deliberately does not explain how to order goals inside a rule. The
# unsafe-negation refusal teaches that at the moment it matters, with the
# corrected clause in the message.
OVERVIEW = r"""
a worked example

    logic declare 'kind/1'  --gloss "kind(Person): Person has a kind disposition"
    logic declare 'rough/1' --gloss "rough(Person): Person behaves roughly"
    logic declare 'quiet/1' --gloss "quiet(Person): Person is quiet"

    logic assert 'kind(anne).'  --because "direct statement about a named person"
    logic assert 'rough(bob).'  --because "direct statement"
    logic assert 'quiet(X) :- kind(X), \+ rough(X).' --because "a conditional, so a rule"

    logic query 'quiet(Who).'       ->  proved, Who = anne

how a clause is written

    kind(anne).                          a fact
    parent(alice, bob).                  argument order is yours to decide and keep
    quiet(X) :- kind(X).                 a rule.  :-  means "if"
    quiet(X) :- kind(X), calm(X).        a comma means "and"
    quiet(X) :- kind(X), \+ rough(X).    \+ means "cannot be proved"

    Capitals are variables, lowercase are constants, _ is "anything".
    One clause per assert, always ending in a full stop.

what is not accepted

    Arithmetic and comparison: no  X > Y,  X = Y,  X is Y + 1.
      Write an ordering as a table of facts instead:
          covers(high, low).  covers(high, high).  covers(low, low).
    Lists: no  p([1, 2]).
    Disjunction with  ;  : write two clauses with the same head instead.
          happy(X) :- rich(X).
          happy(X) :- loved(X).
      Two clauses also make the proof say which one was used.

things worth knowing

    Every predicate must be declared before it can be used. The gloss says
    what it means and what its arguments are, in order.

    A query answers proved, disproved or unknown. Unknown means no proof was
    found, which is not the same as false -- anything that cannot be derived
    is treated as false, so something may simply not have been said yet.

    An answer reports what it had to assume. If a proof used \+ somewhere, the
    result says so: those are the facts that would overturn it.

    logic inspect <predicate>   what is already known about it
    logic history               everything asserted, with the reasoning
    logic query ... --html F    a page with the proof and a graph
"""

OK, REFUSED, ENGINE_FAILED = 0, 1, 2

DEFAULT_KB = "logic.jsonl"


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------


def _program(kb: KnowledgeBase) -> Program:
    """The active clauses, as something an engine can be handed.

    Built here rather than in core, because core knows nothing about engines.
    """
    return Program(tuple(SourcedClause(c.id, c.clause) for c in kb.active()))


def _fail(message: str) -> int:
    print(message, file=sys.stderr)
    return REFUSED


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_declare(args, kb: KnowledgeBase) -> int:
    try:
        split(args.predicate)
    except ValueError as exc:
        return _fail(str(exc))

    existing = kb.declarations().get(args.predicate)
    if existing and existing.gloss == args.gloss:
        print(f"{args.predicate} is already declared with that meaning")
        return OK

    entry = kb.declare(args.predicate, args.gloss, turn=args.turn or kb.next_turn())
    print(render.declared(entry))
    return OK


def cmd_assert(args, kb: KnowledgeBase) -> int:
    try:
        clause = parse_clause(args.clause)
    except ParseError as exc:
        return _fail(f"{exc}\n{exc.caret()}")

    missing = check_declared(clause, kb.declarations())
    if missing:
        return _fail(UndeclaredPredicate(clause, missing).args[0])

    duplicate = kb.find_duplicate(clause)
    if duplicate is not None:
        return _fail(render.already_present(duplicate))

    try:
        entry = kb.add_clause(
            clause,
            turn=args.turn or kb.next_turn(),
            topic=args.topic,
            source_text=args.source,
            rationale=args.because,
        )
    except UnsafeClause as exc:
        return _fail(str(exc))

    print(render.stored(entry))
    return OK


def cmd_retract(args, kb: KnowledgeBase) -> int:
    target = next((c for c in kb.active() if c.id == args.id), None)
    if target is None:
        return _fail(f"{args.id} is not an active clause. Try: logic history")

    entry = kb.retract(args.id, turn=args.turn or kb.next_turn(), rationale=args.because)
    print(render.retracted(entry, target))
    return OK


def cmd_query(args, kb: KnowledgeBase) -> int:
    try:
        goal = parse_goal(args.goal)
    except ParseError as exc:
        return _fail(f"{exc}\n{exc.caret()}")

    try:
        port = SwiPrologPort()
    except EngineNotFound as exc:
        return _fail(str(exc))

    solution = port.solve(
        _program(kb),
        goal,
        SolveOpts(timeout=args.timeout, max_solutions=args.limit, want_proof=not args.no_proof),
    )

    if args.html:
        payload = {"kb": _snapshot(kb), "query": {"goal": args.goal, **_as_json(solution)}}
        written = viewer.write(payload, args.html)
        print(f"written to {written}")
    elif args.json:
        print(json.dumps(_as_json(solution), indent=2))
    else:
        print(render.query_result(solution, ascii_only=_ascii(args)))

    return ENGINE_FAILED if solution.status is Status.ERROR else OK


def cmd_inspect(args, kb: KnowledgeBase) -> int:
    declarations = kb.declarations()
    active = kb.active()

    if args.predicate is None:
        counts: dict[str, int] = {}
        for clause in active:
            counts[clause.clause.indicator] = counts.get(clause.clause.indicator, 0) + 1
        print(render.inspect_all(declarations, counts))
        return OK

    # Accept either kind/1 or bare kind, since the agent will write both.
    if "/" in args.predicate:
        matches = [args.predicate]
    else:
        matches = sorted(
            {i for i in list(declarations) + [c.clause.indicator for c in active]
             if i.rsplit("/", 1)[0] == args.predicate}
        )
        if not matches:
            matches = [f"{args.predicate}/?"]

    blocks = []
    for indicator in matches:
        blocks.append(
            render.inspect_predicate(
                indicator,
                declarations.get(indicator),
                [c for c in active if c.clause.indicator == indicator],
                [c for c in active if indicator in c.clause.body_predicates()],
            )
        )
    print("\n\n".join(blocks))
    return OK


def cmd_export(args, kb: KnowledgeBase) -> int:
    if args.format == "html":
        written = viewer.write({"kb": _snapshot(kb), "query": None},
                               args.out or "logic.html")
        print(f"written to {written}")
        return OK

    if args.format == "pl":
        from .engines.swipl import render_program

        text = render_program(_program(kb))
    else:
        text = json.dumps(_snapshot(kb), indent=2)

    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"written to {args.out}")
    else:
        print(text)
    return OK


def cmd_history(args, kb: KnowledgeBase) -> int:
    print(render.history(kb.entries(), brief=args.brief))
    return OK


# ---------------------------------------------------------------------------
# Serialising
# ---------------------------------------------------------------------------


def _as_json(solution) -> dict:
    return {
        "status": solution.status.value,
        "verdict": solution.verdict(),
        # Right beside the status, so a caller reading one sees the other.
        # None means we did not check, which is not the same as False.
        "conditional": solution.conditional,
        "assumptions_checked": solution.assumptions_checked,
        "truncated": solution.truncated,
        "duration_ms": solution.duration_ms,
        "message": solution.message,
        "assumptions": [
            {"goal": a.goal, "kind": a.kind, "ground": a.ground, "describe": a.describe()}
            for a in solution.assumptions
        ],
        "answers": [
            {
                "bindings": answer.bindings,
                "clause_ids": answer.justification.clause_ids() if answer.justification else [],
                "proof": _proof_json(answer.justification),
            }
            for answer in solution.answers
        ],
    }


def _proof_json(node) -> dict | None:
    if node is None:
        return None
    return {
        "goal": node.goal,
        "kind": node.kind,
        "clause_id": node.clause_id,
        "ground": node.ground,
        "children": [_proof_json(c) for c in node.children],
    }


def _snapshot(kb: KnowledgeBase) -> dict:
    """The knowledge base as JSON, for the visualization to read."""
    return {
        "declarations": [
            {"indicator": d.indicator, "gloss": d.gloss, "turn": d.turn}
            for d in kb.declarations().values()
        ],
        # Everything ever asserted, including what was later withdrawn. The
        # page marks those rather than hiding them, so a clause does not
        # silently disappear between one turn and the next.
        "clauses": [
            {
                "id": c.id,
                "text": c.text,
                "turn": c.turn,
                "topic": c.topic,
                "source_text": c.source_text,
                "rationale": c.rationale,
                "predicates": c.clause.predicates(),
                "head_predicate": c.clause.indicator,
                "body_predicates": c.clause.body_predicates(),
                "negated_predicates": sorted(
                    {lit.indicator for lit in c.clause.body if lit.negated}
                ),
                "is_fact": c.clause.is_fact,
                "is_recursive": c.clause.is_recursive,
                "retracted": c.retracted,
                "retracted_turn": c.retracted_turn,
                "retracted_because": c.retracted_because,
            }
            for c in kb.clauses()
        ],
        "turns": [{"turn": turn, "clause_ids": [c.id for c in state]}
                  for turn, state in kb.replay()],
    }


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def _ascii(args) -> bool:
    return args.ascii or not render.supports_unicode()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="logic",
        description="Assert facts and rules into a logic engine, and ask it to prove things.",
        epilog=OVERVIEW,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--kb", default=os.environ.get("LOGICLAYER_KB", DEFAULT_KB),
                        help=f"ledger file (default: {DEFAULT_KB})")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--ascii", action="store_true",
                        help="avoid box-drawing characters in proof trees")
    subparsers = parser.add_subparsers(dest="command", required=True)

    declare = subparsers.add_parser(
        "declare", help="say what a predicate means before using it")
    declare.add_argument("predicate", help="name/arity, for example kind/1")
    declare.add_argument("--gloss", required=True,
                         help="what it means and what the arguments are, in order")
    declare.add_argument("--turn", type=int)
    declare.set_defaults(func=cmd_declare)

    assert_ = subparsers.add_parser("assert", help="add one fact or rule")
    assert_.add_argument("clause", help="one clause, ending in a full stop")
    assert_.add_argument("--because", required=True,
                         help="why this clause is the right translation")
    assert_.add_argument("--source", help="the sentence it came from")
    assert_.add_argument("--turn", type=int)
    assert_.add_argument("--topic")
    assert_.set_defaults(func=cmd_assert)

    retract = subparsers.add_parser("retract", help="withdraw a clause")
    retract.add_argument("id", help="the ledger id, for example c3")
    retract.add_argument("--because")
    retract.add_argument("--turn", type=int)
    retract.set_defaults(func=cmd_retract)

    query = subparsers.add_parser("query", help="ask the engine to prove a goal")
    query.add_argument("goal", help="a goal; the full stop is optional")
    query.add_argument("--limit", type=int, default=100, help="most answers to return")
    query.add_argument("--timeout", type=float, default=10.0, help="seconds")
    query.add_argument("--no-proof", action="store_true",
                       help="faster, but assumptions are then not checked")
    query.add_argument("--html", metavar="FILE",
                       help="write a self-contained page with the proof and the graph")
    query.set_defaults(func=cmd_query)

    inspect = subparsers.add_parser(
        "inspect", help="what is already known about a predicate")
    inspect.add_argument("predicate", nargs="?", help="kind/1 or just kind; omit for all")
    inspect.set_defaults(func=cmd_inspect)

    export = subparsers.add_parser("export", help="the generated program, or a snapshot")
    export.add_argument("--format", choices=["pl", "json", "html"], default="pl")
    export.add_argument("--out")
    export.set_defaults(func=cmd_export)

    history = subparsers.add_parser("history", help="every entry, in order")
    history.add_argument("--brief", action="store_true",
                         help="one line each, without the reasoning")
    history.set_defaults(func=cmd_history)

    return parser


def main(argv: list[str] | None = None) -> int:
    # The proof tree and the arrows in messages are not representable in the
    # default Windows console encoding, which raises rather than degrading.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            with contextlib.suppress(ValueError, OSError):
                stream.reconfigure(errors="replace")

    args = build_parser().parse_args(argv)
    kb = KnowledgeBase(args.kb)

    try:
        return args.func(args, kb)
    except viewer.ViewerMissing as exc:
        return _fail(str(exc))
    except (ValueError, KeyError, OSError) as exc:
        return _fail(str(exc))


if __name__ == "__main__":
    sys.exit(main())
