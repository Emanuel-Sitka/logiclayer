# Benchmark: does an agent reason better with the tool?

One problem, given to two agent sessions: one with Logic Layer available, one
without. Both scored 20 out of 20. The main [README](../README.md) says what
that means and what was not tested.

## The problem

Document access at a fictional research group, written as a policy and a set
of tables: 36 people, 14 roles, 24 documents, 20 questions. It was built so
that each thing a logic engine should help with actually matters to some
answer.

**Inheritance has to be computed.** Several roles have a lower clearance of
their own than something they inherit. `auditor` is listed as public but
inherits `principal`, which is secret, and `archivist` reaches secret through
three steps. There is no shortcut to "a role's level is its own listed level".

**Conditions on conditions.** An exemption overrides a denial only if the
person who issued it outranks the person who recorded the denial, which is a
second walk up the same role hierarchy, inside a negation. Four of the six
exemptions succeed and two fail. An embargo lapses if a later version of the
document is not itself embargoed, and versions chain, so one embargo lapses
only through two steps.

**Size.** Large enough that building the full table by hand is real work.

## Files

| | |
|---|---|
| `problem.md` | Given to both sessions. Nothing else is. |
| `answers.md` | Ground truth and scoring. Do not show either session. |
| `generate.py` | Builds the problem and computes the answers. |
| `ground_truth.pl` | Generated. Run through SWI-Prolog directly, not through Logic Layer, so the answers do not depend on the tool being right. |
| `reference_encoding.py` | The same problem encoded through Logic Layer, to show it can be expressed. **Not given out** — it would be the answer. |
| `CLAUDE-with-tool.md` | The only thing the with-tool session is told about the tool. |
| `result-with.md`, `result-without.md` | What each session answered, and how. |

```
python generate.py              # rebuilds problem.md, answers.md and ground_truth.pl
python reference_encoding.py    # encodes it through Logic Layer and checks all twenty
```

## What the tool makes you work for

The reference encoding needs 183 facts and 17 rules. Two parts of it are worth
knowing about before watching an agent attempt it.

The clearance ordering has to be a table of one-step facts plus a rule for
"anything further down", because the clause syntax has no arithmetic and no
comparison.

Three rules contain a negation. One of them, written the natural way, is
refused as unsafe: the person has to be named by an earlier goal before the
negation can ask about them. Whether the agent reads the refusal and fixes the
rule in one attempt is worth watching.

## Questions worth watching

| | why |
|---|---|
| 2 | The deepest chain. Kowalski is an archivist, listed as public, and reaches secret through three steps of inheritance. Then the document's embargo has to be checked for a lapse. |
| 14 | d17's embargo lapses only because d24 replaces d21, which replaces d17, and d24 is not embargoed. |
| 18 | The answer is **nobody**. d14's embargo never lapses, so only its author could read it — and the author is denied it, with an exemption that fails because the issuer does not outrank the person who recorded the denial. Three rules have to interact. |
| 7 and 8 | Same shape, opposite answers. The difference lies entirely in the role hierarchy. |
| 20 | Twelve of thirty-six people. Easy to miss one. |

## Running it yourself

1. Make two empty directories outside this repository, `with` and `without`.
2. Copy `problem.md` into both.
3. Copy `CLAUDE-with-tool.md` into `with` as `CLAUDE.md` (or `AGENTS.md` for
   Codex), then delete everything above its horizontal rule — that part is a
   note to you.
4. Start a fresh agent session in each, with the same model, and give both the
   same instruction:

   > Read problem.md and answer the twenty questions at the end. Show your
   > working for each.

5. Score both against `answers.md`.

`with` gets the instruction file and `without` does not. That is the only
difference.

**Run it several times.** The recorded results are one run per side, which
could be luck. How often each side gets all twenty is the number worth having.

## How much the with-tool session is told

`CLAUDE-with-tool.md` is deliberately thin: the tool exists, here is its name,
run `--help`. Nothing about how to model the problem, which predicates to use,
or how to order goals inside a rule. Say more, and the comparison measures the
instructions rather than the tool.
