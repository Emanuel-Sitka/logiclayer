import { activeAt } from "./model.js";

/**
 * What is known about one predicate.
 *
 * This is where individual facts live. Keeping them out of the graph is what
 * lets the graph stay readable: a conversation about a hundred people has a
 * hundred facts about kind/1, and they belong in a list rather than as a
 * hundred nodes.
 */
export default function PredicatePanel({ kb, indicator, turn, usedClauses }) {
  if (!indicator) {
    return <p className="muted pad">Click a predicate in the graph to see what is known about it.</p>;
  }

  const declaration = kb.declarations.find((d) => d.indicator === indicator);
  const visible = activeAt(kb.clauses, turn);
  const defines = visible.filter((c) => c.head_predicate === indicator);
  const usedIn = visible.filter((c) => c.body_predicates.includes(indicator));

  return (
    <div className="pad">
      <h2>{indicator}</h2>

      {declaration ? (
        <>
          <p className="gloss">{declaration.gloss}</p>
          <p className="muted small">declared on turn {declaration.turn}</p>
        </>
      ) : (
        <p className="warn">
          Not declared. It was probably stored through the library rather than the command line,
          which does not enforce the registry.
        </p>
      )}

      <h3>
        {defines.length === 0 ? "Nothing defines it" : `Defined by ${defines.length}`}
      </h3>
      {defines.length === 0 ? (
        <p className="muted">
          A goal about it will fail rather than raise an error, because anything that cannot be
          derived is treated as false.
        </p>
      ) : (
        <ul className="clause-list">
          {defines.map((clause) => (
            <ClauseRow key={clause.id} clause={clause} used={usedClauses.has(clause.id)} />
          ))}
        </ul>
      )}

      {usedIn.length > 0 && (
        <>
          <h3>Used by {usedIn.length}</h3>
          <ul className="clause-list">
            {usedIn.map((clause) => (
              <ClauseRow key={clause.id} clause={clause} used={usedClauses.has(clause.id)} />
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

/** Laid out like a ledger row, since it is the same information. */
function ClauseRow({ clause, used }) {
  const kind = clause.is_fact ? "fact" : "rule";
  return (
    <li className={`is-${kind} ${used ? "used" : ""}`}>
      <div className="row-top">
        <span className={`kind-tag ${kind}`}>{kind}</span>
        {used && <span className="kind-tag proof">in the proof</span>}
      </div>
      <code className="row-clause">{clause.text}</code>
      {clause.source_text && <p className="source">“{clause.source_text}”</p>}
      {clause.rationale && (
        <p className="rationale">
          <span className="label">because</span> {clause.rationale}
        </p>
      )}
      <p className="row-footer">
        turn {clause.turn}
        {clause.topic ? ` · ${clause.topic}` : ""}
        <span className="row-id">{clause.id}</span>
      </p>
    </li>
  );
}
