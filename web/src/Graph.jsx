import { useMemo } from "react";
import { ReactFlow, Background, Controls, MarkerType, Handle, Position } from "@xyflow/react";
import { buildGraph, layout, proofPredicates } from "./model.js";

/**
 * The knowledge base as predicates and the dependencies between them.
 *
 * Every node is a React component, which is why the graph can show a
 * predicate's meaning and how many clauses define it rather than being a dot
 * with a label beside it.
 */
export default function Graph({ kb, turn, selected, onSelect, query }) {
  const { nodes, edges } = useMemo(() => {
    const graph = buildGraph(kb, turn);
    const positions = layout(graph.nodes, graph.edges);
    const inProof = proofPredicates(query);

    const flowNodes = graph.nodes.map((node) => ({
      id: node.indicator,
      type: "predicate",
      position: positions.get(node.indicator),
      data: {
        ...node,
        selected: node.indicator === selected,
        inProof: inProof.has(node.indicator.split("/")[0]),
      },
    }));

    // A self-edge would be drawn as a line from a node to itself, which is
    // invisible at best. The node carries a badge instead.
    const flowEdges = graph.edges.filter((e) => e.source !== e.target).map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      className: edge.negated ? "edge-negated" : "edge-plain",
      // A dependency through a negation behaves differently from a plain one:
      // it says "this holds when that cannot be shown", so it is drawn apart.
      animated: false,
      style: edge.negated
        ? { stroke: "#b45309", strokeDasharray: "5 4", strokeWidth: 1.5 }
        : { stroke: "#94a3b8", strokeWidth: 1.5 },
      label: edge.negated ? "not" : undefined,
      labelStyle: { fill: "#b45309", fontSize: 11 },
      labelBgStyle: { fill: "#fffbeb" },
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: edge.negated ? "#b45309" : "#94a3b8",
        width: 16,
        height: 16,
      },
    }));

    return { nodes: flowNodes, edges: flowEdges };
  }, [kb, turn, selected, query]);

  if (nodes.length === 0) {
    return <div className="graph empty-graph">nothing declared or stored yet</div>;
  }

  return (
    <div className="graph">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={NODE_TYPES}
        onNodeClick={(_, node) => onSelect(node.id)}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.2}
        proOptions={{ hideAttribution: false }}
      >
        <Background gap={18} size={1} color="#e2e8f0" />
        <Controls showInteractive={false} />
      </ReactFlow>
      <Legend />
    </div>
  );
}

function PredicateNode({ data }) {
  const classes = [
    "node",
    data.selected ? "is-selected" : "",
    data.inProof ? "in-proof" : "",
    !data.declared ? "undeclared" : "",
    data.clauses.length === 0 ? "empty" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={classes} title={data.gloss ?? "not declared"}>
      <Handle type="target" position={Position.Top} />
      <div className="node-name">
        {data.indicator}
        {data.recursive && <span className="badge" title="this predicate is defined in terms of itself">recursive</span>}
      </div>
      <div className="node-meta">
        {data.clauses.length === 0 ? (
          <span className="muted">nothing defines it</span>
        ) : (
          <>
            {data.facts > 0 && <span>{data.facts} fact{data.facts === 1 ? "" : "s"}</span>}
            {data.facts > 0 && data.rules > 0 && <span className="dot">·</span>}
            {data.rules > 0 && <span>{data.rules} rule{data.rules === 1 ? "" : "s"}</span>}
          </>
        )}
      </div>
      {data.firstTurn !== null && <div className="node-turn">turn {data.firstTurn}</div>}
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}

const NODE_TYPES = { predicate: PredicateNode };

function Legend() {
  return (
    <div className="legend">
      <span><i className="swatch plain" /> depends on</span>
      <span><i className="swatch negated" /> depends on <em>not</em></span>
      <span><i className="swatch proof" /> used in the proof</span>
    </div>
  );
}
