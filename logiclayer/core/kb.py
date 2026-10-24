"""The knowledge base: an append-only ledger of everything that happened.

The ledger is the source of truth. The .pl file handed to the engine is
generated from it and is a build artifact -- delete it and nothing is lost.

Nothing is ever edited or removed. Retracting a clause appends a retract
event, so the full history survives and the conversation can be replayed. That
is what the visualization needs, and it means a mistake is always recoverable.

Every asserted clause records where it came from: which turn, the sentence that
produced it, and the agent's own reasoning for translating it that way. That
last field is what lets us tell a bad translation apart from bad deduction when
something goes wrong. See docs/concepts.md.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal as TypeLiteral

from .ast import Clause, format_clause
from .parse import parse_clause
from .safety import UnsafeClause
from .safety import check as check_safety

Op = TypeLiteral["assert", "retract", "declare"]

LEDGER_VERSION = 1


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass(frozen=True, slots=True)
class Entry:
    """One line of the ledger."""

    id: str
    op: Op
    created_at: str
    turn: int | None = None

    # assert only
    clause: str | None = None
    predicates: tuple[str, ...] = ()
    topic: str | None = None
    source_text: str | None = None
    rationale: str | None = None

    # retract only: the id of the assert being undone
    target: str | None = None

    # declare only
    indicator: str | None = None
    gloss: str | None = None

    def to_json(self) -> str:
        data = {
            "id": self.id,
            "op": self.op,
            "created_at": self.created_at,
        }
        optional = {
            "turn": self.turn,
            "clause": self.clause,
            "predicates": list(self.predicates) or None,
            "topic": self.topic,
            "source_text": self.source_text,
            "rationale": self.rationale,
            "target": self.target,
            "indicator": self.indicator,
            "gloss": self.gloss,
        }
        data.update({k: v for k, v in optional.items() if v is not None})
        return json.dumps(data, ensure_ascii=False)

    @classmethod
    def from_json(cls, line: str) -> Entry:
        data = json.loads(line)
        return cls(
            id=data["id"],
            op=data["op"],
            created_at=data["created_at"],
            turn=data.get("turn"),
            clause=data.get("clause"),
            predicates=tuple(data.get("predicates", ())),
            topic=data.get("topic"),
            source_text=data.get("source_text"),
            rationale=data.get("rationale"),
            target=data.get("target"),
            indicator=data.get("indicator"),
            gloss=data.get("gloss"),
        )


@dataclass(frozen=True, slots=True)
class Declaration:
    """A predicate the agent has declared, with what it means.

    The gloss is what makes the registry useful. Matching on spelling alone
    would catch is_kind and miss friendly. Returning the meaning lets the agent
    judge whether an existing predicate is the same concept.
    """

    indicator: str
    gloss: str
    entry_id: str
    turn: int | None = None


@dataclass(frozen=True, slots=True)
class ActiveClause:
    """An asserted clause.

    The retraction fields are filled in by clauses(), which returns everything
    ever asserted. active() returns only the ones still in force, where they
    are always empty. Nothing is ever removed from the ledger, so a withdrawn
    clause can still be shown with the reason it was withdrawn.
    """

    id: str
    clause: Clause
    text: str
    turn: int | None = None
    topic: str | None = None
    source_text: str | None = None
    rationale: str | None = None

    retracted: bool = False
    retracted_turn: int | None = None
    retracted_because: str | None = None


class KnowledgeBase:
    """Reads and appends to one ledger file.

    The file is opened, read and closed on each operation rather than held
    open. Commands are short-lived, and it means the visualization can edit the
    file between calls without anything going stale.
    """

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)

    # -- reading ------------------------------------------------------------

    def entries(self) -> list[Entry]:
        if not self.path.exists():
            return []
        out: list[Entry] = []
        with self.path.open("r", encoding="utf-8") as fh:
            for number, line in enumerate(fh, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(Entry.from_json(line))
                except (json.JSONDecodeError, KeyError) as exc:
                    raise ValueError(f"{self.path}: line {number} is not a valid ledger entry: {exc}") from exc
        return out

    def clauses(self) -> list[ActiveClause]:
        """Every clause ever asserted, in order, with any retraction attached.

        A withdrawn clause is kept rather than dropped, so the record can show
        that something was said and later taken back, and why. Dropping it
        would make a clause appear to vanish between one turn and the next with
        no explanation, which is what the append-only ledger exists to avoid.
        """
        entries = self.entries()
        withdrawals = {e.target: e for e in entries if e.op == "retract"}

        out: list[ActiveClause] = []
        for entry in entries:
            if entry.op != "assert":
                continue
            assert entry.clause is not None
            withdrawal = withdrawals.get(entry.id)
            out.append(
                ActiveClause(
                    id=entry.id,
                    clause=parse_clause(entry.clause),
                    text=entry.clause,
                    turn=entry.turn,
                    topic=entry.topic,
                    source_text=entry.source_text,
                    rationale=entry.rationale,
                    retracted=withdrawal is not None,
                    retracted_turn=withdrawal.turn if withdrawal else None,
                    retracted_because=withdrawal.rationale if withdrawal else None,
                )
            )
        return out

    def active(self) -> list[ActiveClause]:
        """Clauses currently in force, in the order they were asserted."""
        return [c for c in self.clauses() if not c.retracted]

    def declarations(self) -> dict[str, Declaration]:
        """Declared predicates, keyed by indicator. A later declare replaces an earlier one."""
        out: dict[str, Declaration] = {}
        for entry in self.entries():
            if entry.op == "declare":
                assert entry.indicator is not None and entry.gloss is not None
                out[entry.indicator] = Declaration(
                    indicator=entry.indicator,
                    gloss=entry.gloss,
                    entry_id=entry.id,
                    turn=entry.turn,
                )
        return out

    def find_duplicate(self, clause: Clause) -> ActiveClause | None:
        """An active clause identical to this one, if there is one.

        Prolog tolerates duplicate clauses, but the ledger should not hold two
        entries for one statement -- it makes the history misleading and gives
        a proof two ids to choose between. The caller decides what to do.
        """
        text = format_clause(clause)
        for item in self.active():
            if item.text == text:
                return item
        return None

    def find(self, entry_id: str) -> Entry | None:
        for entry in self.entries():
            if entry.id == entry_id:
                return entry
        return None

    def next_turn(self) -> int:
        turns = [e.turn for e in self.entries() if e.turn is not None]
        return max(turns) + 1 if turns else 1

    # -- writing ------------------------------------------------------------

    def _next_id(self, prefix: str) -> str:
        used = {e.id for e in self.entries()}
        n = 1
        while f"{prefix}{n}" in used:
            n += 1
        return f"{prefix}{n}"

    def _append(self, entry: Entry) -> Entry:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(entry.to_json() + "\n")
        return entry

    def add_clause(
        self,
        clause: Clause,
        *,
        turn: int | None = None,
        topic: str | None = None,
        source_text: str | None = None,
        rationale: str | None = None,
        allow_unsafe: bool = False,
    ) -> Entry:
        """Append a clause, refusing one whose negation would misbehave.

        The check happens before storage rather than at query time, because the
        ledger is what every later answer is drawn from. An unsafe clause in
        there quietly makes those answers wrong. See safety.py.

        allow_unsafe exists so tests can construct the broken case on purpose.
        Nothing else should pass it.
        """
        if not allow_unsafe:
            findings = check_safety(clause)
            if findings:
                raise UnsafeClause(clause, findings)

        return self._append(
            Entry(
                id=self._next_id("c"),
                op="assert",
                created_at=_now(),
                turn=turn,
                clause=format_clause(clause),
                predicates=tuple(clause.predicates()),
                topic=topic,
                source_text=source_text,
                rationale=rationale,
            )
        )

    def retract(self, target: str, *, turn: int | None = None, rationale: str | None = None) -> Entry:
        entry = self.find(target)
        if entry is None:
            raise KeyError(f"no such clause: {target}")
        if entry.op != "assert":
            raise ValueError(f"{target} is a {entry.op} entry, not a clause")
        if target in {e.target for e in self.entries() if e.op == "retract"}:
            raise ValueError(f"{target} has already been retracted")
        return self._append(
            Entry(
                id=self._next_id("r"),
                op="retract",
                created_at=_now(),
                turn=turn,
                target=target,
                rationale=rationale,
            )
        )

    def declare(self, indicator: str, gloss: str, *, turn: int | None = None) -> Entry:
        return self._append(
            Entry(
                id=self._next_id("d"),
                op="declare",
                created_at=_now(),
                turn=turn,
                indicator=indicator,
                gloss=gloss,
            )
        )

    # -- generating the engine's program ------------------------------------

    def to_prolog(self, *, header: bool = True) -> str:
        """The active clauses as a Prolog program.

        Each clause is preceded by a comment carrying its ledger id, so an
        error from the engine can be traced back to the sentence that caused
        it.
        """
        lines: list[str] = []
        if header:
            lines += [
                "% Generated by Logic Layer from the ledger. Do not edit.",
                f"% Source: {self.path.name}",
                "",
            ]
        for item in self.active():
            label = f"% [{item.id}]"
            if item.source_text:
                label += f" {item.source_text}"
            lines.append(label)
            lines.append(item.text)
            lines.append("")
        return "\n".join(lines)

    def write_prolog(self, target: str | os.PathLike[str]) -> Path:
        """Write the generated program, replacing the file in one step.

        Writing to a temporary file and moving it into place means a reader
        never sees a half-written program, and a crash midway leaves the old
        one intact.
        """
        destination = Path(target)
        destination.parent.mkdir(parents=True, exist_ok=True)
        handle, temp_name = tempfile.mkstemp(dir=destination.parent, suffix=".pl.tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(self.to_prolog())
            os.replace(temp_name, destination)
        except BaseException:
            Path(temp_name).unlink(missing_ok=True)
            raise
        return destination

    # -- replay -------------------------------------------------------------

    def replay(self) -> Iterator[tuple[int, list[ActiveClause]]]:
        """The state of the knowledge base after each turn.

        This is what drives the visualization's slider.
        """
        entries = self.entries()
        turns = sorted({e.turn for e in entries if e.turn is not None})
        for turn in turns:
            upto = [e for e in entries if e.turn is not None and e.turn <= turn]
            retracted = {e.target for e in upto if e.op == "retract"}
            state = [
                ActiveClause(
                    id=e.id,
                    clause=parse_clause(e.clause),  # type: ignore[arg-type]
                    text=e.clause,  # type: ignore[arg-type]
                    turn=e.turn,
                    topic=e.topic,
                    source_text=e.source_text,
                    rationale=e.rationale,
                )
                for e in upto
                if e.op == "assert" and e.id not in retracted
            ]
            yield turn, state
