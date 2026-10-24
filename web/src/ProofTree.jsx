import { useState } from "react";

/**
 * How the answer was reached.
 *
 * Each step names the ledger entry it used, and clicking one shows the
 * sentence that produced the clause and the agent's reasoning for translating
 * it that way. That link back to the conversation is the point of the whole
 * thing: a claim you can follow rather than take on trust.
 */
export default function ProofTree({ query, kb }) {
  const [openClause, setOpenClause] = useState(null);

  if (!query) {
    return <p className="muted pad">No query was run, so there is no proof to show.</p>;
  }

  if (!query.answers.length) {
    return (
      <div className="pad">
        <p className="verdict unknown">{query.verdict}</p>
        <p className="muted">
          No proof was found. That is not the same as the goal being false — this engine cannot
          tell those apart. Something may simply not have been said yet.
        </p>
      </div>
    );
  }

  const byId = new Map(kb.clauses.map((c) => [c.id, c]));

  return (
    <div className="pad">
      {query.answers.map((answer, index) => (
        <div key={index} className="answer">
          {query.answers.length > 1 && <div className="answer-number">answer {index + 1}</div>}
          {Object.keys(answer.bindings).length > 0 && (
            <div className="bindings">
              {Object.entries(answer.bindings).map(([name, value]) => (
                <span key={name} className="binding">
                  {name} = <strong>{value}</strong>
                </span>
              ))}
            </div>
          )}
          <Node node={answer.proof} byId={byId} open={openClause} onOpen={setOpenClause} />
        </div>
      ))}
      {query.truncated && <p className="muted">There are more answers than were returned.</p>}
    </div>
  );
}

function Node({ node, byId, open, onOpen, depth = 0 }) {
  if (!node) return null;

  const clause = node.clause_id ? byId.get(node.clause_id) : null;
  const isOpen = open === node.clause_id && clause;
  const negated = node.kind === "naf";

  return (
    <div className="proof-node" style={{ marginLeft: depth === 0 ? 0 : 16 }}>
      <div className={`proof-goal ${negated ? "naf" : ""} ${negated && !node.ground ? "loose" : ""}`}>
        <span className="goal-text">
          {negated ? <span className="not">not</span> : null} {node.goal}
        </span>

        {node.clause_id && (
          <button className="chip" onClick={() => onOpen(isOpen ? null : node.clause_id)}>
            {node.clause_id}
          </button>
        )}
        {negated && (
          <span className={`chip static ${node.ground ? "" : "warn"}`}>
            {node.ground ? "assumed false" : "assumed false, variable loose"}
          </span>
        )}
      </div>

      {isOpen && <ClauseDetail clause={clause} />}

      {(node.children ?? []).map((child, index) => (
        <Node key={index} node={child} byId={byId} open={open} onOpen={onOpen} depth={depth + 1} />
      ))}
    </div>
  );
}

function ClauseDetail({ clause }) {
  return (
    <div className="clause-detail">
      <code>{clause.text}</code>
      {clause.source_text && <p className="source">“{clause.source_text}”</p>}
      {clause.rationale && (
        <p className="rationale">
          <span className="label">because</span> {clause.rationale}
        </p>
      )}
      <p className="muted small">
        turn {clause.turn}
        {clause.topic ? ` · ${clause.topic}` : ""}
      </p>
    </div>
  );
}
