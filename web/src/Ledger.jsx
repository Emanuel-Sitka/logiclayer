import { useMemo, useState } from "react";
import { upTo, isWithdrawn } from "./model.js";

/**
 * Everything that was said, in the order it was said.
 *
 * The graph shows how the reasoning connects and the proof shows how one
 * answer was reached. Neither shows the conversation. This does: each sentence
 * that arrived, the clause it became, and the reason the agent wrote it that
 * way.
 *
 * Order is by turn rather than grouped by predicate, because the sequence is
 * the story. Withdrawn clauses stay in place, struck through, since a clause
 * vanishing between one turn and the next with no explanation is exactly what
 * the append-only ledger exists to avoid.
 */
export default function Ledger({ kb, turn, usedClauses, selected, onSelect }) {
  const [filter, setFilter] = useState("");
  const [onlyProof, setOnlyProof] = useState(false);

  const rows = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    return upTo(kb.clauses, turn).filter((clause) => {
      if (onlyProof && !usedClauses.has(clause.id)) return false;
      if (!needle) return true;
      return [clause.text, clause.source_text, clause.rationale, clause.head_predicate, clause.topic]
        .filter(Boolean)
        .some((field) => field.toLowerCase().includes(needle));
    });
  }, [kb, turn, filter, onlyProof, usedClauses]);

  return (
    <div className="ledger">
      <div className="ledger-controls">
        <input
          type="search"
          placeholder="filter by text, sentence, reason…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        {usedClauses.size > 0 && (
          <label className="only-proof">
            <input
              type="checkbox"
              checked={onlyProof}
              onChange={(e) => setOnlyProof(e.target.checked)}
            />
            only the proof
          </label>
        )}
      </div>

      <p className="muted small pad-x">
        {rows.length} of {kb.clauses.length} clauses
      </p>

      {rows.length === 0 ? (
        <p className="muted pad">Nothing matches.</p>
      ) : (
        <ol className="ledger-list">
          {rows.map((clause) => (
            <Row
              key={clause.id}
              clause={clause}
              withdrawn={isWithdrawn(clause, turn)}
              used={usedClauses.has(clause.id)}
              selected={clause.head_predicate === selected}
              onSelect={onSelect}
            />
          ))}
        </ol>
      )}
    </div>
  );
}

function Row({ clause, withdrawn, used, selected, onSelect }) {
  const kind = clause.is_fact ? "fact" : "rule";
  const classes = [
    `is-${kind}`,
    withdrawn ? "withdrawn" : "",
    used ? "used" : "",
    selected ? "selected" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <li className={classes}>
      {/* What kind of statement this is comes first and is the thing that
          reads at a glance: a fact asserts something, a rule derives it. */}
      <div className="row-top">
        <span className={`kind-tag ${kind}`}>{kind}</span>
        <button className="chip" onClick={() => onSelect(clause.head_predicate)}>
          {clause.head_predicate}
        </button>
        {used && <span className="kind-tag proof">in the proof</span>}
      </div>

      <code className="row-clause">{clause.text}</code>

      {clause.source_text && <p className="source">“{clause.source_text}”</p>}
      {clause.rationale && (
        <p className="rationale">
          <span className="label">because</span> {clause.rationale}
        </p>
      )}

      {withdrawn && (
        <p className="withdrawn-note">
          withdrawn{clause.retracted_turn !== null ? ` on turn ${clause.retracted_turn}` : ""}
          {clause.retracted_because ? ` — ${clause.retracted_because}` : ""}
        </p>
      )}

      {/* The ledger id is kept but kept quiet. It is how you act on a clause
          from the command line (logic retract c4) and how a proof step, shown
          as [c4], matches a row here. It is not something to read first. */}
      <p className="row-footer">
        turn {clause.turn}
        {clause.topic ? ` · ${clause.topic}` : ""}
        <span className="row-id">{clause.id}</span>
      </p>
    </li>
  );
}
