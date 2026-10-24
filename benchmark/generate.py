"""Builds the benchmark problem, and computes its answers.

Written as a generator rather than by hand for two reasons. At this size the
tables are too long to get right by hand. And a generator can emit further
instances when we want repeated runs on fresh data.

The data is fixed rather than random, so the problem is reproducible and so it
could be tuned until the questions were interesting: a mix of yes and no, some
answers that a plausible shortcut gets wrong, and some people and documents
that appear in no answer at all.

Ground truth is computed by running the generated Prolog through SWI-Prolog
directly, not through Logic Layer, so the answers do not depend on our tool.

    python generate.py
"""

from __future__ import annotations

import subprocess
import sys
from itertools import pairwise
from pathlib import Path

from logiclayer.engines.swipl import INSTALL_HINT, find_swipl

HERE = Path(__file__).resolve().parent

LEVELS = ["public", "internal", "confidential", "secret", "top_secret"]

# ---------------------------------------------------------------------------
# Roles
#
# The point of this hierarchy is that inheritance has to be computed. Several
# roles have a LOWER own clearance than something they inherit from, so you
# cannot shortcut to "a role's level is its own listed level". If every role
# outranked its ancestors, inheritance would never change an answer and R2 and
# R3 would go untested.
# ---------------------------------------------------------------------------

ROLES: dict[str, tuple[str, list[str]]] = {
    # name:            (own level,      inherits from)
    "visitor":         ("public",       []),
    "contractor":      ("public",       ["visitor"]),
    "staff":           ("internal",     ["visitor"]),
    "analyst":         ("internal",     ["staff"]),
    "researcher":      ("internal",     ["staff"]),
    "senior_analyst":  ("confidential", ["analyst"]),
    "principal":       ("secret",       ["senior_analyst"]),
    # Lower own level than what it inherits. An auditor reads everything a
    # principal can, by inheritance, despite being listed as public.
    "auditor":         ("public",       ["principal"]),
    # Same trick one level deeper: reviewer -> auditor -> principal.
    "reviewer":        ("internal",     ["auditor"]),
    "archivist":       ("public",       ["reviewer"]),
    "lab_head":        ("confidential", ["researcher"]),
    "security_lead":   ("top_secret",   ["senior_analyst"]),
    # Inherits the top level without listing it.
    "deputy_director": ("internal",     ["lab_head", "security_lead"]),
    "director":        ("secret",       ["deputy_director"]),
}

PEOPLE: dict[str, list[str]] = {
    "adams": ["lab_head"],
    "barnes": ["researcher"],
    "chen": ["auditor"],                 # public on paper, secret by inheritance
    "dubois": ["visitor"],
    "eriksson": ["senior_analyst"],
    "farah": ["security_lead"],
    "gupta": ["director"],
    "hoffman": ["staff", "principal"],
    "ibrahim": ["analyst"],
    "jansen": ["contractor"],
    "kowalski": ["archivist"],           # public on paper, secret by inheritance
    "lindqvist": ["senior_analyst", "staff"],
    "moreau": ["reviewer"],              # internal on paper, secret by inheritance
    "nakamura": ["deputy_director"],     # internal on paper, top_secret inherited
    "okafor": ["researcher", "analyst"],
    "petrov": ["principal"],
    "quinn": ["visitor", "contractor"],
    "rossi": ["lab_head", "senior_analyst"],
    "silva": ["staff"],
    "tanaka": ["archivist", "researcher"],
    "ueda": ["analyst"],
    "vasquez": ["security_lead"],
    "wang": ["researcher"],
    "xu": ["contractor"],
    "yilmaz": ["auditor", "visitor"],
    "zhao": ["staff"],
    "abara": ["visitor"],
    "bianchi": ["analyst"],
    "costa": ["researcher"],
    "duarte": ["staff"],
    "elmi": ["contractor"],
    "fischer": ["senior_analyst"],
    "gallo": ["visitor"],
    "haddad": ["reviewer"],
    "ito": ["staff"],
    "jung": ["analyst"],
}

DOCUMENTS: dict[str, str] = {
    "d01": "public", "d02": "internal", "d03": "confidential", "d04": "secret",
    "d05": "top_secret", "d06": "confidential", "d07": "internal", "d08": "secret",
    "d09": "public", "d10": "confidential", "d11": "top_secret", "d12": "internal",
    "d13": "secret", "d14": "confidential", "d15": "public", "d16": "internal",
    "d17": "secret", "d18": "confidential", "d19": "top_secret", "d20": "internal",
    "d21": "confidential", "d22": "secret", "d23": "public", "d24": "internal",
}

AUTHORS = [
    ("adams", "d03"), ("adams", "d06"), ("barnes", "d07"), ("chen", "d04"),
    ("eriksson", "d10"), ("farah", "d05"), ("gupta", "d11"), ("gupta", "d19"),
    ("hoffman", "d13"), ("moreau", "d14"), ("okafor", "d18"), ("petrov", "d08"),
    ("rossi", "d21"), ("tanaka", "d22"), ("wang", "d16"), ("fischer", "d17"),
]

EMBARGOED = ["d04", "d06", "d11", "d14", "d17", "d19", "d21"]

# supersedes(Later, Earlier). Transitive.
SUPERSEDES = [
    ("d09", "d04"),   # d09 is public and not embargoed -> d04's embargo has lapsed
    ("d10", "d06"),   # d10 is itself not embargoed -> d06 lapsed
    ("d19", "d11"),   # d19 IS embargoed -> d11 not lapsed by this alone
    ("d20", "d19"),   # but d20 supersedes d19, and d20 is clear -> d11 lapses transitively
    ("d21", "d17"),   # d21 is embargoed -> d17 not lapsed
    ("d24", "d21"),   # d24 is clear -> d21 lapses, and so does d17, transitively
]

# denied(Subject, Document, RecordedBy)
DENIALS = [
    ("hoffman", "d13", "silva"),
    ("moreau", "d14", "ibrahim"),
    ("eriksson", "d10", "zhao"),
    ("okafor", "d18", "duarte"),
    ("rossi", "d03", "ito"),
    ("petrov", "d08", "jung"),
    ("chen", "d04", "bianchi"),
    ("wang", "d16", "silva"),
]

# exemption(Subject, Document, IssuedBy)
EXEMPTIONS = [
    ("hoffman", "d13", "gupta"),      # director outranks staff -> overrides
    ("moreau", "d14", "ueda"),        # analyst does not outrank analyst -> no
    ("eriksson", "d10", "farah"),     # security_lead outranks staff -> overrides
    ("okafor", "d18", "silva"),       # staff does not outrank staff -> no
    ("rossi", "d03", "nakamura"),     # deputy_director outranks staff -> overrides
    ("chen", "d04", "jansen"),        # contractor outranks nothing -> no
]

# ---------------------------------------------------------------------------

RULES_PROLOG = r"""
% --- clearance ordering, as a table. There is no arithmetic. ---
covers(L, L) :- level(L).
covers(H, L) :- above(H, M), covers(M, L).

% --- roles ---
inherits_from(R, S) :- inherits(R, S).
inherits_from(R, S) :- inherits(R, T), inherits_from(T, S).

role_grants(R, L) :- role_level(R, L).
role_grants(R, L) :- inherits_from(R, S), role_level(S, L).

person_grants(P, L) :- holds(P, R), role_grants(R, L).

% --- seniority: a role outranks whatever it inherits from ---
outranks(R, S) :- inherits_from(R, S).
person_outranks(A, B) :- holds(A, RA), holds(B, RB), outranks(RA, RB).

% --- an exemption overrides a denial when the issuer outranks the denier ---
overridden(P, D) :-
    denied(P, D, By),
    exemption(P, D, Issuer),
    person_outranks(Issuer, By).

% --- an embargo lapses if something that supersedes it is itself clear ---
supersedes_trans(A, B) :- supersedes(A, B).
supersedes_trans(A, B) :- supersedes(A, M), supersedes_trans(M, B).

lapsed(D) :- supersedes_trans(Later, D), \+ embargoed(Later).

embargo_active(D) :- embargoed(D), \+ lapsed(D).

% --- blocking ---
blocked(P, D) :- denied(P, D, _), \+ overridden(P, D).
blocked(P, D) :- person(P), embargo_active(D), \+ author(P, D).

can_read(P, D) :-
    person_grants(P, Held),
    classified(D, Needed),
    covers(Held, Needed),
    \+ blocked(P, D).
"""

QUESTIONS: list[tuple[str, str]] = [
    ("Can Chen read d05?", "can_read(chen, d05)"),
    ("Can Kowalski read d04?", "can_read(kowalski, d04)"),
    ("Can Moreau read d13?", "can_read(moreau, d13)"),
    ("Can Nakamura read d05?", "can_read(nakamura, d05)"),
    ("Can Dubois read d02?", "can_read(dubois, d02)"),
    ("Can Hoffman read d13?", "can_read(hoffman, d13)"),
    ("Can Moreau read d14?", "can_read(moreau, d14)"),
    ("Can Eriksson read d10?", "can_read(eriksson, d10)"),
    ("Can Okafor read d18?", "can_read(okafor, d18)"),
    ("Can Rossi read d03?", "can_read(rossi, d03)"),
    ("Can Chen read d04?", "can_read(chen, d04)"),
    ("Can Adams read d06?", "can_read(adams, d06)"),
    ("Can Silva read d11?", "can_read(silva, d11)"),
    ("Can Gupta read d17?", "can_read(gupta, d17)"),
    ("Can Jansen read d01?", "can_read(jansen, d01)"),
    ("Who can read d05?", "WHO can_read(P, d05)"),
    ("Who can read d19?", "WHO can_read(P, d19)"),
    ("Who can read d14?", "WHO can_read(P, d14)"),
    ("Which roles grant top_secret clearance?", "WHO role_grants(P, top_secret)"),
    ("Who can read d22?", "WHO can_read(P, d22)"),
]


def prolog_source() -> str:
    lines = ["% Generated by generate.py. Ground truth for the benchmark.", ""]
    lines += [f"level({level})." for level in LEVELS]
    lines += [f"above({hi}, {lo})." for lo, hi in pairwise(LEVELS)]
    lines.append("")
    for role, (level, parents) in ROLES.items():
        lines.append(f"role_level({role}, {level}).")
        lines += [f"inherits({role}, {parent})." for parent in parents]
    lines.append("")
    for person, roles in PEOPLE.items():
        lines.append(f"person({person}).")
        lines += [f"holds({person}, {role})." for role in roles]
    lines.append("")
    lines += [f"classified({doc}, {level})." for doc, level in DOCUMENTS.items()]
    lines.append("")
    lines += [f"author({who}, {doc})." for who, doc in AUTHORS]
    lines += [f"embargoed({doc})." for doc in EMBARGOED]
    lines += [f"supersedes({a}, {b})." for a, b in SUPERSEDES]
    lines += [f"denied({p}, {d}, {by})." for p, d, by in DENIALS]
    lines += [f"exemption({p}, {d}, {by})." for p, d, by in EXEMPTIONS]
    lines.append(RULES_PROLOG)

    lines.append("ask(Label, yes_no(G)) :- ( call(G) -> A = yes ; A = no ),")
    lines.append("    format(\"~w|~w~n\", [Label, A]).")
    lines.append("ask(Label, who(Template, G)) :-")
    lines.append("    ( setof(Template, G, Rs) -> true ; Rs = [] ),")
    lines.append("    format(\"~w|~w~n\", [Label, Rs]).")
    lines.append("")
    lines.append("main :-")
    asks = []
    for index, (_, goal) in enumerate(QUESTIONS, start=1):
        if goal.startswith("WHO "):
            body = goal[4:]
            asks.append(f"    ask(q{index}, who(P, {body}))")
        else:
            asks.append(f"    ask(q{index}, yes_no({goal}))")
    lines.append(",\n".join(asks) + ".")
    lines.append("")
    lines.append(":- initialization(main, main).")
    return "\n".join(lines)


def compute_answers(pl_path: Path) -> dict[str, str]:
    # Found the same way the tool finds it, though the answers are computed by
    # running SWI-Prolog directly rather than through Logic Layer.
    swipl = find_swipl()
    if swipl is None:
        raise SystemExit(f"SWI-Prolog not found. {INSTALL_HINT}")
    proc = subprocess.run(
        [str(swipl), "-q", str(pl_path)],
        capture_output=True, text=True, timeout=180,
    )
    if proc.returncode != 0:
        print(proc.stdout + proc.stderr)
        raise SystemExit("ground truth failed to run")
    answers = {}
    for line in proc.stdout.strip().splitlines():
        label, _, value = line.partition("|")
        answers[label.strip()] = value.strip()
    return answers


def table(headers: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out)


def title(name: str) -> str:
    return name.replace("_", " ").title()


def problem_markdown() -> str:
    role_rows = [[r, lvl, ", ".join(p) or "—"] for r, (lvl, p) in ROLES.items()]
    people_rows = [[title(p), ", ".join(rs)] for p, rs in PEOPLE.items()]
    doc_rows = [[d, lvl] for d, lvl in DOCUMENTS.items()]

    by_doc: dict[str, list[str]] = {}
    for who, doc in AUTHORS:
        by_doc.setdefault(doc, []).append(title(who))
    author_rows = [[d, ", ".join(a)] for d, a in sorted(by_doc.items())]

    return f"""# Data access review — Meridian Research Group

You are auditing the data access rules before an external review. The rules are
reproduced from the policy document, followed by the current state of the
system.

Answer the twenty questions at the end. For each, give the answer and show how
you reached it.

---

## The rules

**R1.** Clearance levels, lowest to highest: **public**, **internal**,
**confidential**, **secret**, **top_secret**.

**R2.** A role may inherit from one or more other roles. Inheritance is
transitive: if A inherits from B and B inherits from C, then A inherits from C.

**R3.** A role grants its own clearance level, and every clearance level
granted by any role it inherits from, directly or indirectly. A role's own
listed level is not necessarily the highest level it grants.

**R4.** A person may hold more than one role. A person's clearance is the
highest level granted by any role they hold.

**R5.** A clearance level covers its own level and every level below it.

**R6.** Role A **outranks** role B if A inherits from B, directly or
indirectly. Person A outranks person B if A holds some role that outranks some
role held by B.

**R7.** A denial is recorded against a person for a document, by a named
member of staff. A denial blocks that person from that document unless it has
been overridden.

**R8.** A denial is **overridden** if the person holds an exemption for that
same document, and the person who issued the exemption outranks the person who
recorded the denial.

**R9.** Succession: a document may supersede another, and succession is
transitive. An embargo on a document has **lapsed** if some document that
supersedes it, directly or indirectly, is not itself embargoed.

**R10.** An embargo is **active** if the document is embargoed and its embargo
has not lapsed.

**R11.** A person is **blocked** from a document if either:

  a. a denial is recorded against them for it that has not been overridden, or
  b. the document's embargo is active and they are not one of its authors.

**R12.** A person may read a document if their clearance covers the document's
classification **and** they are not blocked from it.

---

## Roles

{table(["Role", "Own clearance", "Inherits from"], role_rows)}

## People and the roles they hold

{table(["Person", "Roles"], people_rows)}

## Documents

{table(["Document", "Classification"], doc_rows)}

## Authorship

{table(["Document", "Authors"], author_rows)}

Documents not listed have no recorded author.

## Embargoes

Embargoed: {", ".join(f"**{d}**" for d in EMBARGOED)}.

## Succession

{table(["Supersedes", "The earlier document"], [[a, b] for a, b in SUPERSEDES])}

## Denials

{table(["Person", "Document", "Recorded by"],
       [[title(p), d, title(by)] for p, d, by in DENIALS])}

## Exemptions

{table(["Person", "Document", "Issued by"],
       [[title(p), d, title(by)] for p, d, by in EXEMPTIONS])}

---

## Questions

""" + "\n".join(f"{i}. {q}" for i, (q, _) in enumerate(QUESTIONS, start=1)) + "\n"


def answers_markdown(answers: dict[str, str]) -> str:
    rows = []
    for index, (question, _) in enumerate(QUESTIONS, start=1):
        raw = answers[f"q{index}"]
        if raw.startswith("["):
            names = [title(n) for n in raw.strip("[]").split(",") if n]
            shown = ", ".join(names) if names else "nobody"
        else:
            shown = raw
        rows.append([str(index), question, f"**{shown}**"])

    return f"""# Ground truth

Do not show either instance.

Computed by running `ground_truth.pl` through SWI-Prolog directly, not through
Logic Layer, so the answers do not depend on our tool being correct.

Regenerate everything with `python generate.py`.

{table(["", "Question", "Answer"], rows)}

## Scoring

Twenty points, one per question. An enumeration scores only if the set is
exactly right.

Record for each instance: the score, whether the working actually supports the
answer, and — for the tool — whether a wrong answer came from a wrong clause or
from wrong deduction.
"""


def main() -> int:
    pl_path = HERE / "ground_truth.pl"
    pl_path.write_text(prolog_source(), encoding="utf-8")
    answers = compute_answers(pl_path)

    (HERE / "problem.md").write_text(problem_markdown(), encoding="utf-8")
    (HERE / "answers.md").write_text(answers_markdown(answers), encoding="utf-8")

    print(f"{len(PEOPLE)} people, {len(ROLES)} roles, {len(DOCUMENTS)} documents")
    print(f"{len(QUESTIONS)} questions\n")
    for index, (question, _) in enumerate(QUESTIONS, start=1):
        print(f"  {index:>2}. {question:<42} {answers[f'q{index}']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
