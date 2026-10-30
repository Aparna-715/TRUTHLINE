"""
TRUTHLINE — Evidence graph
===========================================================================
Nodes are CLAIMS, not documents. Edges are relations
(supports / contradicts / related) read from SQLite.

NetworkX is used IN MEMORY. There is no separate graph database — the graph is
rebuilt from SQLite on demand. That is the plan's deliberate simplification:
same graph data, same visualisation, no extra service.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

__all__ = ["build_graph", "render_graph", "graph_to_json"]

# Colour language shared with the UI (light theme, lime green accents).
EDGE_COLOURS = {
    "supports": "#22c55e",      # green
    "contradicts": "#ef4444",   # red
    "related": "#94a3b8",       # grey
}
NODE_COLOURS = {
    "FRESH": "#22c55e",
    "AGING": "#f59e0b",
    "STALE": "#f97316",
    "EXPIRED": "#ef4444",
    "unknown": "#84cc16",       # lime — the brand accent
}


def build_graph(claims: list[dict], relations: list[dict]) -> dict:
    """Build an in-memory NetworkX graph and return it as plain JSON.

    Returns:
        {nodes: [{id, label, location, source_type, freshness_label, ...}],
         edges: [{source, target, relation_type, colour}],
         stats: {node_count, edge_count, contradictions}}
    """
    import networkx as nx

    g = nx.Graph()
    contradictions = 0

    for c in claims:
        cid = c.get("claim_id") or c.get("id")
        if not cid:
            continue
        g.add_node(
            cid,
            label=c.get("object") or c.get("event") or cid,
            location=c.get("location"),
            source_type=c.get("source_type"),
            source_id=c.get("source_id"),
            freshness_label=c.get("freshness_label") or c.get("label") or "unknown",
            freshness_score=c.get("freshness_score") or c.get("score"),
        )

    for r in relations:
        a, b = r.get("claim_a"), r.get("claim_b")
        if not a or not b:
            continue
        kind = (r.get("relation_type") or "related").lower()
        if kind == "contradicts":
            contradictions += 1
        g.add_edge(
            a, b,
            relation_type=kind,
            colour=EDGE_COLOURS.get(kind, EDGE_COLOURS["related"]),
            reason=r.get("reason"),
        )

    nodes = []
    for nid, data in g.nodes(data=True):
        nodes.append({
            "id": nid,
            "label": data.get("label") or nid,
            "location": data.get("location"),
            "source_type": data.get("source_type"),
            "source_id": data.get("source_id"),
            "freshness_label": data.get("freshness_label") or "unknown",
            "freshness_score": data.get("freshness_score"),
            "colour": NODE_COLOURS.get(data.get("freshness_label") or "unknown",
                                       NODE_COLOURS["unknown"]),
        })

    edges = [
        {
            "source": u,
            "target": v,
            "relation_type": data.get("relation_type"),
            "colour": data.get("colour"),
            "reason": data.get("reason"),
        }
        for u, v, data in g.edges(data=True)
    ]

    return {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "node_count": g.number_of_nodes(),
            "edge_count": g.number_of_edges(),
            "contradictions": contradictions,
        },
    }


def graph_to_json(claims: list[dict], relations: list[dict]) -> str:
    import json

    return json.dumps(build_graph(claims, relations), indent=2)


def render_graph(claims: list[dict], relations: list[dict], out_path: str | Path | None = None) -> Path:
    """Render the graph to a PNG with matplotlib.

    Nodes are claims, coloured by freshness. Edges are coloured by relation
    type, so a red edge is a visible contradiction and a green edge is support.
    """
    import matplotlib

    matplotlib.use("Agg")  # headless — no display needed
    import matplotlib.pyplot as plt
    import networkx as nx

    data = build_graph(claims, relations)
    g = nx.Graph()

    for n in data["nodes"]:
        g.add_node(n["id"], **n)
    for e in data["edges"]:
        g.add_edge(e["source"], e["target"], **e)

    if g.number_of_nodes() == 0:
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.text(0.5, 0.5, "No claims to display", ha="center", va="center")
        ax.axis("off")
    else:
        fig, ax = plt.subplots(figsize=(11, 8))
        pos = nx.spring_layout(g, k=1.2, iterations=50, seed=42)

        node_cols = [g.nodes[n].get("colour", NODE_COLOURS["unknown"]) for n in g.nodes]
        nx.draw_networkx_nodes(g, pos, node_color=node_cols, node_size=1400,
                               edgecolors="#e2e8f0", linewidths=1.5, ax=ax)
        nx.draw_networkx_labels(
            g, pos,
            labels={n: g.nodes[n].get("label", n)[:18] for n in g.nodes},
            font_size=7, font_color="#1e293b", ax=ax,
        )

        for kind, colour in EDGE_COLOURS.items():
            pairs = [(e["source"], e["target"]) for e in data["edges"]
                     if e["relation_type"] == kind]
            if pairs:
                nx.draw_networkx_edges(g, pos, edgelist=pairs, edge_color=colour,
                                       width=2.0, alpha=0.85, ax=ax,
                                       label=kind)

        ax.legend(loc="lower left", fontsize=8, frameon=True)
        ax.set_title(
            f"TRUTHLINE evidence graph — {data['stats']['node_count']} claims, "
            f"{data['stats']['contradictions']} contradiction(s)",
            fontsize=11, color="#166534",
        )
        ax.axis("off")

    if out_path is None:
        out_path = Path(__file__).resolve().parent.parent / "data" / "evidence_graph.png"
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path, dpi=130, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out_path


if __name__ == "__main__":
    demo_claims = [
        {"claim_id": "E1", "object": "4 vehicles stationary", "location": "Grid-5",
         "source_type": "drone", "source_id": "E1", "freshness_label": "EXPIRED",
         "freshness_score": 0.0},
        {"claim_id": "E2", "object": "4 vehicles stationary", "location": "Grid-5",
         "source_type": "ground", "source_id": "E2", "freshness_label": "EXPIRED",
         "freshness_score": 0.0256},
        {"claim_id": "E3", "object": "4 vehicles departed", "location": "Grid-5",
         "source_type": "satellite", "source_id": "E3", "freshness_label": "FRESH",
         "freshness_score": 0.8465},
    ]
    demo_relations = [
        {"claim_a": "E1", "claim_b": "E2", "relation_type": "supports", "reason": "agree"},
        {"claim_a": "E1", "claim_b": "E3", "relation_type": "contradicts", "reason": "departed"},
        {"claim_a": "E2", "claim_b": "E3", "relation_type": "contradicts", "reason": "departed"},
    ]

    import json

    print("=== Evidence graph ===\n")
    print(json.dumps(build_graph(demo_claims, demo_relations), indent=2))
    out = render_graph(demo_claims, demo_relations)
    print(f"\nrendered -> {out}")
