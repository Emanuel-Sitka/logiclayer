---
name: logic-cli
description: Record facts and rules in a Prolog-backed logic engine and query it for multi-step deduction, where every answer carries a proof tree and the assumptions it rests on. Use when the task needs to write down facts or rules that later questions will depend on, prove or disprove a goal against many of them at once, check whether a stated constraint still holds after a change, find which facts a conclusion rests on, inspect what has already been asserted about a predicate, or produce a page showing how an answer was reached.
license: MIT
compatibility: Needs the logic command from Logic Layer (https://github.com/Emanuel-Sitka/logiclayer) and SWI-Prolog.
---

# `logic` — a logic engine on the command line

Facts and rules go in. Queries come back with a proof. State lives in
`logic.jsonl` in the current directory and persists between commands.

## Commands

| | |
|---|---|
| `logic declare 'kind/1' --gloss "kind(P): P is kind"` | name a predicate before using it |
| `logic assert 'kind(anne).' --because "..."` | add one fact or rule |
| `logic query 'quiet(Who).'` | prove a goal |
| `logic inspect kind` | what is known about a predicate |
| `logic retract c3 --because "..."` | withdraw a clause |
| `logic history` | every entry, with its reasoning |
| `logic export --format html --out kb.html` | draw the knowledge base |
| `logic query '...' --html out.html` | draw the proof |

Global: `--kb FILE`, `--json`, `--ascii`.

`--because` is required on `assert`: why this clause is the right translation
of whatever it came from. `--source` records the sentence itself.

## Clauses

    kind(anne).                        a fact
    parent(alice, bob).                argument order is yours to choose and keep
    quiet(X) :- kind(X).               a rule; :- is "if"
    quiet(X) :- kind(X), calm(X).      a comma is "and"
    quiet(X) :- kind(X), \+ rough(X).  \+ is "cannot be proved"

Capitals are variables, lowercase are constants, `_` is anything. One clause
per assert, ending in a full stop.

Every predicate must be declared first, and a name close to an existing one
is refused.

## Not accepted

Arithmetic and comparison (`>`, `=`, `is`) — write an ordering as a table of
facts. Lists. `;` for "or" — write two clauses with the same head.

A variable inside `\+` must be bound by a goal earlier in the same body, or
the negation asks about everything of that shape rather than one thing. A
refusal contains the corrected clause.

## Answers

| | |
|---|---|
| `proved` | a proof was found |
| `unknown` | no proof was found; **not** the same as false |
| `disproved` | the negation was proved (this engine never returns it) |

Anything that cannot be derived is treated as false, so `unknown` may mean
only that something has not been recorded yet.

An answer also lists what it assumed. Those are the goals the proof took to be
false, and the facts that would overturn it.

Exit codes: `0` the command worked, `1` the input was refused and nothing was
stored, `2` the engine failed.

`logic --help` has a worked example.
