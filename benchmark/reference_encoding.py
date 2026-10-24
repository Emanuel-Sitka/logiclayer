"""Encode the benchmark through Logic Layer and check it against the ground truth.

Not given to either instance -- it is the answer. Its job is to establish that
the problem is expressible in our clause subset before we send an agent at it,
and to show where the subset makes you work.

    python reference_encoding.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from itertools import pairwise
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from generate import (  # noqa: E402
    AUTHORS,
    DENIALS,
    DOCUMENTS,
    EMBARGOED,
    EXEMPTIONS,
    LEVELS,
    PEOPLE,
    QUESTIONS,
    ROLES,
    SUPERSEDES,
    compute_answers,
)

KB = HERE / "reference.jsonl"


def logic(*args: str) -> str:
    proc = subprocess.run(
        [sys.executable, "-m", "logiclayer.cli", "--kb", str(KB), *args],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        print(f"\nREFUSED: {' '.join(args[:2])}")
        print(proc.stdout + proc.stderr)
        raise SystemExit(1)
    return proc.stdout


DECLARATIONS = [
    ("level/1", "level(L): L is a clearance level"),
    ("above/2", "above(Higher, Lower): Higher is one step above Lower"),
    ("covers/2", "covers(Higher, Lower): Higher is enough to see Lower"),
    ("role_level/2", "role_level(Role, Level): the role's own listed level"),
    ("inherits/2", "inherits(Role, Parent): Role inherits directly from Parent"),
    ("inherits_from/2", "inherits_from(Role, Ancestor): directly or indirectly"),
    ("role_grants/2", "role_grants(Role, Level): own or inherited"),
    ("person/1", "person(P): P is a named member of staff"),
    ("holds/2", "holds(Person, Role): Person holds Role"),
    ("person_grants/2", "person_grants(Person, Level): reached through some role"),
    ("outranks/2", "outranks(Role, Other): Role inherits from Other"),
    ("person_outranks/2", "person_outranks(A, B): A holds a role outranking one of B's"),
    ("classified/2", "classified(Doc, Level): the document's classification"),
    ("author/2", "author(Person, Doc): Person is an author of Doc"),
    ("embargoed/1", "embargoed(Doc): Doc is under embargo"),
    ("supersedes/2", "supersedes(Later, Earlier): Later supersedes Earlier"),
    ("supersedes_trans/2", "supersedes_trans(Later, Earlier): directly or indirectly"),
    ("lapsed/1", "lapsed(Doc): Doc's embargo has lapsed"),
    ("embargo_active/1", "embargo_active(Doc): Doc is embargoed and has not lapsed"),
    ("denied/3", "denied(Person, Doc, By): By recorded a denial of Doc for Person"),
    ("exemption/3", "exemption(Person, Doc, By): By issued Person an exemption for Doc"),
    ("overridden/2", "overridden(Person, Doc): the denial has been overridden"),
    ("blocked/2", "blocked(Person, Doc): Person is blocked from Doc"),
    ("can_read/2", "can_read(Person, Doc): Person may read Doc"),
]

RULES = [
    # R5. No arithmetic in the subset, so the ordering is a one-step table plus
    # its transitive closure rather than a comparison.
    ("covers(L, L) :- level(L).", "R5, a level covers itself"),
    ("covers(H, L) :- above(H, M), covers(M, L).", "R5, and everything below"),

    ("inherits_from(R, S) :- inherits(R, S).", "R2 base case"),
    ("inherits_from(R, S) :- inherits(R, T), inherits_from(T, S).", "R2 transitive"),
    ("role_grants(R, L) :- role_level(R, L).", "R3, the role's own level"),
    ("role_grants(R, L) :- inherits_from(R, S), role_level(S, L).", "R3, inherited"),
    ("person_grants(P, L) :- holds(P, R), role_grants(R, L).",
     "R4. Every level any held role reaches. Comparing with covers/2 later makes "
     "asking for the single highest unnecessary."),

    ("outranks(R, S) :- inherits_from(R, S).", "R6 for roles"),
    ("person_outranks(A, B) :- holds(A, RA), holds(B, RB), outranks(RA, RB).", "R6 for people"),

    ("overridden(P, D) :- denied(P, D, By), exemption(P, D, Issuer), "
     "person_outranks(Issuer, By).", "R8"),

    ("supersedes_trans(A, B) :- supersedes(A, B).", "R9 base case"),
    ("supersedes_trans(A, B) :- supersedes(A, M), supersedes_trans(M, B).", "R9 transitive"),
    (r"lapsed(D) :- supersedes_trans(Later, D), \+ embargoed(Later).",
     "R9. supersedes_trans binds Later before the negation runs."),
    (r"embargo_active(D) :- embargoed(D), \+ lapsed(D).", "R10"),

    (r"blocked(P, D) :- denied(P, D, _), \+ overridden(P, D).",
     "R11a. denied/3 binds both P and D before the negation."),
    (r"blocked(P, D) :- person(P), embargo_active(D), \+ author(P, D).",
     "R11b. person(P) first, or the negation would ask whether anyone at all "
     "authored D rather than whether this person did."),

    (r"can_read(P, D) :- person_grants(P, Held), classified(D, Needed), "
     r"covers(Held, Needed), \+ blocked(P, D).", "R12"),
]


def facts() -> list[tuple[str, str]]:
    out = [(f"level({lv}).", "R1, the levels") for lv in LEVELS]
    out += [(f"above({hi}, {lo}).", "R1, one step apart")
            for lo, hi in pairwise(LEVELS)]
    for role, (level, parents) in ROLES.items():
        out.append((f"role_level({role}, {level}).", "roles table, own level"))
        out += [(f"inherits({role}, {p}).", "roles table, inheritance") for p in parents]
    for person, roles in PEOPLE.items():
        out.append((f"person({person}).", "R11b needs a domain of people"))
        out += [(f"holds({person}, {r}).", "people table") for r in roles]
    out += [(f"classified({d}, {lv}).", "documents table") for d, lv in DOCUMENTS.items()]
    out += [(f"author({w}, {d}).", "authorship table") for w, d in AUTHORS]
    out += [(f"embargoed({d}).", "embargo list") for d in EMBARGOED]
    out += [(f"supersedes({a}, {b}).", "succession table") for a, b in SUPERSEDES]
    out += [(f"denied({p}, {d}, {by}).", "denials table") for p, d, by in DENIALS]
    out += [(f"exemption({p}, {d}, {by}).", "exemptions table") for p, d, by in EXEMPTIONS]
    return out


def main() -> int:
    KB.unlink(missing_ok=True)
    for indicator, gloss in DECLARATIONS:
        logic("declare", indicator, "--gloss", gloss)
    body = facts()
    for clause, why in body:
        logic("assert", clause, "--because", why)
    for clause, why in RULES:
        logic("assert", clause, "--because", why)
    print(f"stored {len(body)} facts and {len(RULES)} rules\n")

    expected = compute_answers(HERE / "ground_truth.pl")

    wrong = 0
    for index, (question, goal) in enumerate(QUESTIONS, start=1):
        want = expected[f"q{index}"]
        if goal.startswith("WHO "):
            out = logic("--json", "query", goal[4:] + ".", "--limit", "200")
            names = sorted({a["bindings"]["P"] for a in json.loads(out)["answers"]})
            got = "[" + ",".join(names) + "]"
        else:
            got = "yes" if logic("query", goal + ".", "--no-proof").startswith("proved") else "no"
        ok = got == want
        wrong += not ok
        print(f"  {'ok   ' if ok else 'WRONG'} {index:>2}. {question:<42} {got}")
        if not ok:
            print(f"        expected {want}")

    print("\nall twenty match the ground truth" if not wrong else f"\n{wrong} disagree")
    return 1 if wrong else 0


if __name__ == "__main__":
    sys.exit(main())
