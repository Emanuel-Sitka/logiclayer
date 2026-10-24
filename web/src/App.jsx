import { useMemo, useState } from "react";
import Graph from "./Graph.jsx";
import ProofTree from "./ProofTree.jsx";
import PredicatePanel from "./PredicatePanel.jsx";
import Ledger from "./Ledger.jsx";
import { proofClauseIds, turnRange } from "./model.js";

export default function App({ data }) {
  if (!data) {
    return (
      <div className="empty">
        <h1>Logic Layer</h1>
        <p>
          This page has no knowledge base in it. It is the template the
          <code> logic </code> command fills in. Produce a filled one with:
        </p>
        <pre>logic query 'trusted(anne).' --html out.html</pre>
      </div>
    );
  }

  const { kb, query } = data;
  const range = useMemo(() => turnRange(kb), [kb]);
  const [turn, setTurn] = useState(range.max);
  const [selected, setSelected] = useState(null);
  const [tab, setTab] = useState(query ? "proof" : "ledger");

  const usedClauses = useMemo(() => proofClauseIds(query), [query]);

  const pick = (indicator) => {
    setSelected(indicator);
    setTab("predicate");
  };

  return (
    <div className="app">
      <Header query={query} />

      <div className="body">
        <section className="graph-pane">
          <TurnSlider range={range} turn={turn} onChange={setTurn} count={kb.clauses.length} />
          <Graph kb={kb} turn={turn} selected={selected} onSelect={pick} query={query} />
        </section>

        <aside className="panel">
          <nav className="tabs">
            <button
              className={tab === "proof" ? "on" : ""}
              onClick={() => setTab("proof")}
              disabled={!query}
            >
              Proof
            </button>
            <button className={tab === "ledger" ? "on" : ""} onClick={() => setTab("ledger")}>
              Ledger
            </button>
            <button className={tab === "predicate" ? "on" : ""} onClick={() => setTab("predicate")}>
              {selected ?? "Predicate"}
            </button>
          </nav>

          <div className="panel-body">
            {tab === "proof" && <ProofTree query={query} kb={kb} />}
            {tab === "ledger" && (
              <Ledger
                kb={kb}
                turn={turn}
                usedClauses={usedClauses}
                selected={selected}
                onSelect={pick}
              />
            )}
            {tab === "predicate" && (
              <PredicatePanel kb={kb} indicator={selected} turn={turn} usedClauses={usedClauses} />
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}

function Header({ query }) {
  if (!query) {
    return (
      <header className="header">
        <h1>Logic Layer</h1>
        <p className="muted">No query was run. This is the knowledge base on its own.</p>
      </header>
    );
  }

  const loose = query.assumptions.filter((a) => !a.ground);

  return (
    <header className="header">
      <h1>
        <span className="muted">?-</span> {query.goal}
      </h1>
      <p className={`verdict ${query.status}`}>{query.verdict}</p>

      {query.assumptions.length > 0 && (
        <div className="assumptions">
          <span className="label">assuming</span>
          <ul>
            {query.assumptions.map((a) => (
              <li key={a.goal} className={a.ground ? "" : "loose"}>
                {a.describe}
              </li>
            ))}
          </ul>
          {loose.length > 0 && (
            <p className="warn">
              A negation ran with a variable still loose in it, so it asked about every term of
              that shape at once rather than about one thing.
            </p>
          )}
        </div>
      )}
    </header>
  );
}

function TurnSlider({ range, turn, onChange, count }) {
  if (range.max <= range.min) return null;
  return (
    <div className="slider">
      <label htmlFor="turn">turn {turn}</label>
      <input
        id="turn"
        type="range"
        min={range.min}
        max={range.max}
        value={turn}
        onChange={(e) => onChange(Number(e.target.value))}
      />
      <span className="muted">
        {turn === range.max ? `all ${count} clauses` : "replaying"}
      </span>
    </div>
  );
}
