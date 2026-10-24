/**
 * Turning the knowledge base into something drawable.
 *
 * The graph shows predicates, not individual facts. A conversation about a
 * hundred people would otherwise be a hundred nodes with no readable shape.
 * What is worth seeing is how the reasoning connects: trusted depends on
 * quiet, which depends on kind and rough. Facts belong in the side panel,
 * where they can be read.
 */

import dagre from "@dagrejs/dagre";

const NODE_WIDTH = 190;
const NODE_HEIGHT = 64;

/** Entries that had arrived by the end of a given turn.
 *
 * Declarations are filtered the same way as clauses. A predicate declared on
 * turn 8 should not be on screen while replaying turn 3, or the graph is
 * complete from the first frame and the slider shows nothing happening.
 */
export function upTo(entries, turn) {
  if (turn === null || turn === undefined) return entries;
  return entries.filter((e) => e.turn === null || e.turn <= turn);
}

/**
 * Whether a clause had been withdrawn by the end of a given turn.
 *
 * A clause asserted on turn 5 and retracted on turn 9 was in force for turns 5
 * to 8. Replaying turn 6 should show it as ordinary, and turn 9 should show it
 * struck through rather than gone, so the correction is visible.
 */
export function isWithdrawn(clause, turn) {
  if (!clause.retracted) return false;
  if (turn === null || turn === undefined) return true;
  return clause.retracted_turn === null || clause.retracted_turn <= turn;
}

/** Clauses in force at the end of a given turn. */
export function activeAt(clauses, turn) {
  return upTo(clauses, turn).filter((c) => !isWithdrawn(c, turn));
}

/**
 * One node per predicate, one edge per dependency.
 *
 * A rule contributes an edge from the predicate it concludes to each predicate
 * it needs. Direction runs from conclusion down to evidence, so the thing being
 * established sits above what establishes it.
 */
export function buildGraph(snapshot, turn) {
  const clauses = activeAt(snapshot.clauses, turn);
  const declarations = new Map(upTo(snapshot.declarations, turn).map((d) => [d.indicator, d]));

  const predicates = new Map();
  const ensure = (indicator) => {
    if (!predicates.has(indicator)) {
      predicates.set(indicator, {
        indicator,
        gloss: declarations.get(indicator)?.gloss ?? null,
        declared: declarations.has(indicator),
        facts: 0,
        rules: 0,
        clauses: [],
        firstTurn: null,
      });
    }
    return predicates.get(indicator);
  };

  // Declared predicates appear even when nothing defines them yet. That is
  // worth seeing: a goal about one of them fails rather than raising, which is
  // easy to mistake for a bug.
  for (const declaration of declarations.values()) ensure(declaration.indicator);

  const edges = new Map();
  for (const clause of clauses) {
    // head and body are kept apart rather than taken from one deduplicated
    // list, because a recursive rule calls its own head and that is exactly
    // what deduplication would hide.
    const head = clause.head_predicate;
    const body = clause.body_predicates;
    const node = ensure(head);
    node.clauses.push(clause);
    if (clause.is_fact) node.facts += 1;
    else node.rules += 1;
    if (clause.turn !== null && (node.firstTurn === null || clause.turn < node.firstTurn)) {
      node.firstTurn = clause.turn;
    }

    if (clause.is_recursive) node.recursive = true;

    for (const used of body) {
      ensure(used);
      const key = `${head}->${used}`;
      if (!edges.has(key)) {
        edges.set(key, {
          id: key,
          source: head,
          target: used,
          negated: clause.negated_predicates?.includes(used) ?? false,
          recursive: head === used,
          viaClauses: [],
        });
      }
      edges.get(key).viaClauses.push(clause.id);
      // One rule may use a predicate both plainly and under a negation. If any
      // use is plain, the dependency is a plain one.
      if (!clause.negated_predicates?.includes(used)) edges.get(key).negated = false;
    }
  }

  return { nodes: [...predicates.values()], edges: [...edges.values()] };
}

/**
 * Place the nodes in rows.
 *
 * Rules point downward from conclusions to evidence, which makes the graph
 * mostly layered, and a layered drawing reads far better here than a spring
 * layout. Dagre handles cycles on its own, which matters for recursive
 * predicates like ancestor that depend on themselves.
 */
export function layout(nodes, edges) {
  const graph = new dagre.graphlib.Graph();
  graph.setDefaultEdgeLabel(() => ({}));
  graph.setGraph({ rankdir: "TB", nodesep: 40, ranksep: 70, marginx: 20, marginy: 20 });

  for (const node of nodes) graph.setNode(node.indicator, { width: NODE_WIDTH, height: NODE_HEIGHT });
  // A recursive predicate points at itself. That says nothing about which row
  // it belongs in, and dagre handles self-edges badly, so it is left out of
  // the layout and shown as a badge on the node instead.
  for (const edge of edges) {
    if (edge.source !== edge.target) graph.setEdge(edge.source, edge.target);
  }

  dagre.layout(graph);

  const positions = new Map();
  for (const node of nodes) {
    const placed = graph.node(node.indicator);
    positions.set(node.indicator, {
      x: placed.x - NODE_WIDTH / 2,
      y: placed.y - NODE_HEIGHT / 2,
    });
  }
  return positions;
}

/** Every ledger id the current proof relied on, for highlighting. */
export function proofClauseIds(query) {
  if (!query?.answers?.length) return new Set();
  const ids = new Set();
  const walk = (node) => {
    if (!node) return;
    if (node.clause_id) ids.add(node.clause_id);
    (node.children ?? []).forEach(walk);
  };
  query.answers.forEach((answer) => walk(answer.proof));
  return ids;
}

/** Predicates the current proof touched, for highlighting. */
export function proofPredicates(query) {
  const names = new Set();
  if (!query?.answers?.length) return names;
  const walk = (node) => {
    if (!node) return;
    // A node's goal is a plain term -- negated steps store the goal without
    // the \+ -- so its predicate name is whatever starts it.
    const match = /^[a-z][A-Za-z0-9_]*/.exec(node.goal);
    if (match) names.add(match[0]);
    (node.children ?? []).forEach(walk);
  };
  query.answers.forEach((answer) => walk(answer.proof));
  return names;
}

/** The span of turns to replay, over declarations as well as clauses. */
export function turnRange(kb) {
  const entries = [...(kb.declarations ?? []), ...(kb.clauses ?? [])];
  const turns = [
    ...entries.map((e) => e.turn),
    ...(kb.clauses ?? []).map((c) => c.retracted_turn),
  ].filter((t) => t !== null && t !== undefined);
  return turns.length ? { min: Math.min(...turns), max: Math.max(...turns) } : { min: 0, max: 0 };
}
