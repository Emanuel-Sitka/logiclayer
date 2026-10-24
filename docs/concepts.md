# Concepts

The ideas behind Logic Layer, for readers new to logic programming.

---

## The idea

An agent normally reasons in text: it reads a problem and writes its way to
an answer. Logic Layer gives it a second option. The agent can write the facts
and rules it has understood into a logic engine, ask the engine questions, and
get back answers that come with a proof.

The division of labour is strict:

> **The agent translates. The engine deduces.**

The agent decides what a sentence means and writes it down as logic. The
engine never interprets anything; it only works out what follows. So a wrong
answer has exactly two possible causes: something was written down wrongly, or
the deduction went wrong — and the second should never happen.

---

## Facts and rules

Everything the agent writes is one of two things.

A **fact** is a plain statement:

```prolog
kind(anne).
rough(bob).
```

Read: "anne is kind", "bob is rough". The word in front is the **predicate**;
the things in brackets are its **arguments**. `kind/1` means "the predicate
`kind`, taking one argument".

A **rule** is a conditional:

```prolog
quiet(X) :- kind(X), \+ rough(X).
```

Read `:-` as "if", the comma as "and", and `\+` as "not". So: *X is quiet if X
is kind and X is not rough*. Capitalised names like `X` are **variables** and
stand for anything; lowercase names like `anne` are specific things.

All the facts and rules together are the **knowledge base**. Unlike a
database, it holds more than was stored. `quiet(anne)` appears nowhere above,
but it is true in this knowledge base, because it follows.

---

## Asking a question

A **query** asks the engine to prove a goal:

```prolog
quiet(anne).
```

The engine works backwards. It finds the rule for `quiet`, matches
`quiet(anne)` against `quiet(X)` — so `X = anne` — and then has to prove
`kind(anne)` and `\+ rough(anne)`. The first is a fact. The second holds
because nothing says Anne is rough. Proved.

When a path fails, the engine goes back and tries another; this is called
**backtracking**. A query with a variable, `quiet(Who)`, returns every value
that makes it true.

---

## "Not proved" is not "false"

`\+ rough(anne)` does not mean "Anne is proved not to be rough". It means "I
could not prove that Anne is rough". The engine treats anything it cannot
derive as false — the **closed-world assumption**.

That has two consequences for what Logic Layer reports.

**Three answers, not two.** A query answers *proved*, *unknown* or
*disproved*. When no proof is found, the honest report is *unknown*: the fact
that would settle it may simply not have been written down yet.

**Every answer says what it assumed.** If a proof relied on a `\+`, the result
lists the goals it took to be false:

```
proved, conditional on 1 assumption
  rough(anne) is taken as false because nothing states it
```

Those are exactly the facts that would overturn the answer if someone later
stated them.

---

## Under negation, order matters

These two rules look like the same statement with the conditions swapped:

```prolog
quiet(X) :- kind(X), \+ rough(X).
quiet(X) :- \+ rough(X), kind(X).
```

With `kind(anne)`, `kind(bob)` and `rough(bob)` known, ask `quiet(Who)`. The
first rule answers `anne`. The second answers nothing.

The engine works through a rule from left to right, and only a goal that
succeeds can fill in a variable. `kind(X)` succeeds and fills in `X = anne`.
`\+ rough(X)` never fills in anything: it succeeds exactly when `rough(X)`
*fails*, and a failed goal leaves nothing behind.

So in the second rule, `X` is still empty when `\+ rough(X)` runs, and
`rough(X)` asks "is anyone at all rough?" Bob is, so the negation fails — for
everybody. The second rule really says *"if nobody anywhere is rough, every
kind person is quiet"*.

In ordinary logic, "A and B" means the same as "B and A". With negation as
failure it does not. And the mistake hides well: the closed question
`quiet(anne)` works with both rules, because naming Anne fills in `X` before
the rule starts. Only the open question shows the difference.

The rule that avoids it: **every variable inside a `\+` must also appear in an
ordinary goal earlier in the same rule.** A rule that obeys this is called
**safe**. Logic Layer refuses unsafe rules, and the refusal contains the
corrected rule.

The same thing can happen through a fact with a variable in it, such as
`in_library(book(orwell, Title))` — "every Orwell book is in the library". A
safe rule can still receive that half-filled value, and the negation then asks
about every Orwell book at once. That cannot be seen by reading the rule, so it
is checked when the query runs and reported as an assumption made with a
variable still loose.

---

## What Logic Layer adds around the engine

The engine is SWI-Prolog, an established Prolog system, run as a separate
program. Logic Layer is everything around it that makes the agent's use of it
checkable.

**A ledger.** Every clause is stored with the sentence it came from and the
agent's reason for translating it that way. Nothing is ever deleted;
withdrawing a clause records when and why. The ledger is the record of what
the agent asserted, not only of what is currently true.

**Checks on what goes in.** Every predicate has to be declared with its
meaning before use, and a name close to an existing one is refused — which
stops the same idea drifting into two names over a long conversation. Unsafe
rules are refused, as above.

**A proof, not an account.** The proof is recorded by the engine as it runs.
It is a record of what was computed, not an explanation written afterwards.
So checking an answer splits into two separate questions: was each clause
written down correctly — which a person can judge by reading the sentence and
the reason — and does the conclusion follow — which the engine guarantees.

**What a stronger engine would add.** Plain Prolog can only fail to prove
something. s(CASP), an extension of SWI-Prolog, can prove that something is
false and explain *why not*. Today a proof goes silent exactly where a
negation succeeds, and that is often the part of an answer most worth
explaining.

---

## Vocabulary

| Term | Meaning |
|---|---|
| Fact | A plain statement: `kind(anne).` |
| Rule | A conditional: `quiet(X) :- kind(X).` |
| Clause | A fact or a rule |
| Predicate | The name of a relation, with its number of arguments: `kind/1` |
| Variable | A capitalised name standing for anything: `X`, `Who` |
| Knowledge base | All clauses together |
| Query | A goal the engine is asked to prove |
| Backtracking | Undoing a failed choice and trying another path |
| Negation as failure | "Not" meaning "could not prove it" |
| Closed-world assumption | Treating anything that cannot be derived as false |
| Ground | Containing no unfilled variables: `rough(anne)`, not `rough(X)` |
| Safe rule | One where every variable inside a `\+` is filled in by an earlier goal |
| Proof | The record of which clauses were used, and how, to reach an answer |
