from __future__ import annotations

import argparse
import html as html_lib
import json
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.lines import Line2D


def load_json(path: str | Path):
    """Load JSON data from a file path."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def clean_text(value) -> str:
    """Clean and normalize text for display."""
    if value is None:
        return ""
    return html_lib.unescape(str(value)).replace("\xa0", " ").strip()


def clean_list(value) -> list[str]:
    """Normalize mixed input into a deduplicated list of clean strings."""
    if isinstance(value, list):
        items = value
    elif isinstance(value, tuple):
        items = list(value)
    elif isinstance(value, str):
        items = value.split("|")
    else:
        items = []
    out = []
    seen = set()
    for item in items:
        text = clean_text(item)
        if text and text not in seen:
            out.append(text)
            seen.add(text)
    return out


def safe_int(value, default=0):
    """Safely convert a value to an integer, returning a default if conversion fails."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_float(value, default=0.0):
    """Safely convert a value to a float, returning a default if conversion fails."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def community_key(value) -> str:
    """Generate a string key for a community ID, handling None values."""
    return str(value if value is not None else "-1")


def jaccard(a: set[str], b: set[str]) -> float:
    """Compute the Jaccard similarity between two sets."""
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def percent(value: float) -> str:
    """Format a decimal as a whole-number percentage string."""
    return f"{value * 100:.0f}%"


def darken_hex(hex_color: str, factor: float = 0.68) -> str:
    """Darken a hex color by the given factor."""
    r, g, b = mcolors.to_rgb(hex_color)
    return mcolors.to_hex((r * factor, g * factor, b * factor))


def lighten_hex(hex_color: str, factor: float = 0.18) -> str:
    """Lighten a hex color by moving it toward white."""
    r, g, b = mcolors.to_rgb(hex_color)
    return mcolors.to_hex(
        (
            min(1.0, r + (1.0 - r) * factor),
            min(1.0, g + (1.0 - g) * factor),
            min(1.0, b + (1.0 - b) * factor),
        )
    )


def to_script_json(data) -> str:
    """Serialize data safely for embedding inside an HTML script tag."""
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return (
        text.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )


def build_partition(clustered_nodes):
    """Build a username-to-community lookup from clustered node data."""
    partition = {}
    for node in clustered_nodes:
        username = clean_text(node.get("username"))
        if username:
            partition[username] = community_key(node.get("community_id", -1))
    return partition


def build_profile_lookup(profiles):
    """Normalize community profile keys for consistent lookup."""
    out = {}
    for cid, profile in profiles.items():
        out[community_key(cid)] = profile
    return out


def graph_stats(G):
    """Compute summary statistics for the full graph."""
    n = G.number_of_nodes()
    m = G.number_of_edges()
    density = nx.density(G) if n > 1 else 0.0
    avg_degree = (sum(dict(G.degree()).values()) / n) if n else 0.0
    avg_clustering = nx.average_clustering(G, weight="weight") if n > 1 and m > 0 else 0.0
    largest_cc = max((len(c) for c in nx.connected_components(G)), default=0) if n else 0
    return {
        "nodes": n,
        "edges": m,
        "density": density,
        "avg_degree": avg_degree,
        "avg_clustering": avg_clustering,
        "largest_cc": largest_cc,
    }


def community_stats(partition):
    """Summarize how nodes are distributed across communities."""
    counts = Counter(partition.values())
    if not counts:
        return {"count": 0, "largest": 0, "smallest": 0, "counts": counts}
    return {
        "count": len(counts),
        "largest": max(counts.values()),
        "smallest": min(counts.values()),
        "counts": counts,
    }


def normalized_map(values: dict[str, float]) -> dict[str, float]:
    """Scale numeric values into the 0-1 range."""
    if not values:
        return {}
    lo = min(values.values())
    hi = max(values.values())
    if hi == lo:
        return {k: 0.5 for k in values}
    return {k: (v - lo) / (hi - lo) for k, v in values.items()}


def compute_centrality_metrics(G):
    """Compute the node centrality metrics used by the visualization."""
    n = G.number_of_nodes()
    if n == 0:
        return {}, {}, {}, {}, {}

    degree = dict(G.degree())
    closeness = nx.closeness_centrality(G)
    pagerank = nx.pagerank(G, weight="weight")
    clustering = nx.clustering(G, weight="weight")

    if n > 300:
        sample_size = min(60, n)
        betweenness = nx.betweenness_centrality(G, k=sample_size, seed=42, weight="weight")
    else:
        betweenness = nx.betweenness_centrality(G, weight="weight")

    return degree, closeness, pagerank, clustering, betweenness


def color_palette(community_ids):
    """Assign a distinct color to each community id."""
    ids = sorted(community_ids, key=lambda x: str(x))
    cmap = plt.get_cmap("tab20", max(len(ids), 1))
    palette = {}
    for idx, cid in enumerate(ids):
        palette[cid] = mcolors.to_hex(cmap(idx))
    return palette


def make_color_pack(hex_color: str) -> dict:
    """Build the color variants expected by vis-network."""
    return {
        "background": hex_color,
        "border": darken_hex(hex_color, 0.78),
        "highlight": {"background": lighten_hex(hex_color, 0.22), "border": "#ffffff"},
        "hover": {"background": lighten_hex(hex_color, 0.16), "border": "#ffffff"},
    }


def aggregate_community_nodes(nodes, artists_by_node, tags_by_node):
    """Aggregate top artists and tags across a set of nodes."""
    artist_counter = Counter()
    tag_counter = Counter()
    for node in nodes:
        artist_counter.update(artists_by_node.get(node, []))
        tag_counter.update(tags_by_node.get(node, []))
    return {
        "top_artists": [name for name, _ in artist_counter.most_common(10)],
        "top_tags": [name for name, _ in tag_counter.most_common(10)],
    }


def build_recommendations(
    G,
    nodes,
    partition,
    artists_by_node,
    tags_by_node,
    community_by_node,
    degree_norm,
    betweenness_norm,
):
    """Generate similar-user, bridge, and neighbor recommendations per node."""
    pair_scores = defaultdict(list)
    bridge_scores = defaultdict(list)
    neighbor_scores = defaultdict(list)

    node_sets = {
        node: set(artists_by_node.get(node, [])) | set(tags_by_node.get(node, []))
        for node in nodes
    }

    for idx, left in enumerate(nodes):
        left_artists = set(artists_by_node.get(left, []))
        left_tags = set(tags_by_node.get(left, []))
        for right in nodes[idx + 1 :]:
            right_artists = set(artists_by_node.get(right, []))
            right_tags = set(tags_by_node.get(right, []))

            artist_score = jaccard(left_artists, right_artists)
            tag_score = jaccard(left_tags, right_tags)
            graph_bonus = 0.15 if G.has_edge(left, right) else 0.0
            community_bonus = 0.08 if community_by_node.get(left) == community_by_node.get(right) else 0.0
            score = 0.58 * artist_score + 0.30 * tag_score + graph_bonus + community_bonus

            if score <= 0:
                continue

            shared_artists = sorted(left_artists & right_artists)[:4]
            shared_tags = sorted(left_tags & right_tags)[:4]
            left_item = {
                "id": right,
                "score": round(score, 4),
                "community_id": community_by_node.get(right, "-1"),
                "community_label": "",
                "shared_artists": shared_artists,
                "shared_tags": shared_tags,
            }
            right_item = {
                "id": left,
                "score": round(score, 4),
                "community_id": community_by_node.get(left, "-1"),
                "community_label": "",
                "shared_artists": shared_artists,
                "shared_tags": shared_tags,
            }
            pair_scores[left].append(left_item)
            pair_scores[right].append(right_item)

            if community_by_node.get(left) != community_by_node.get(right):
                bridge_scores[left].append(left_item.copy())
                bridge_scores[right].append(right_item.copy())

            if G.has_edge(left, right):
                weight = safe_float(G[left][right].get("weight", 1), 1.0)
                neighbor_scores[left].append(
                    {
                        "id": right,
                        "weight": round(weight, 4),
                        "score": round(score, 4),
                        "community_id": community_by_node.get(right, "-1"),
                        "community_label": "",
                        "shared_artists": shared_artists,
                        "shared_tags": shared_tags,
                    }
                )
                neighbor_scores[right].append(
                    {
                        "id": left,
                        "weight": round(weight, 4),
                        "score": round(score, 4),
                        "community_id": community_by_node.get(left, "-1"),
                        "community_label": "",
                        "shared_artists": shared_artists,
                        "shared_tags": shared_tags,
                    }
                )

    recs = {}
    for node in nodes:
        recs[node] = {
            "similar": sorted(pair_scores.get(node, []), key=lambda x: (-x["score"], x["id"]))[:8],
            "bridges": sorted(bridge_scores.get(node, []), key=lambda x: (-x["score"], x["id"]))[:8],
            "neighbors": sorted(
                neighbor_scores.get(node, []),
                key=lambda x: (-x["weight"], -x["score"], x["id"]),
            )[:8],
        }
    return recs


def build_community_models(
    G,
    partition,
    profiles,
    artists_by_node,
    tags_by_node,
    degree,
    betweenness,
    closeness,
    pagerank,
    clustering,
):
    """Build enriched community-level summaries from the graph data."""
    community_nodes = defaultdict(list)
    for node, cid in partition.items():
        community_nodes[cid].append(node)

    communities = []
    community_map = {}
    for cid, members in community_nodes.items():
        subgraph = G.subgraph(members)
        size = len(members)
        possible_edges = size * (size - 1) / 2 if size > 1 else 0
        density = (subgraph.number_of_edges() / possible_edges) if possible_edges else 0.0
        member_degree_sum = sum(degree.get(m, 0) for m in members)
        avg_degree = member_degree_sum / size if size else 0.0

        artist_counter = Counter()
        tag_counter = Counter()
        for member in members:
            artist_counter.update(artists_by_node.get(member, []))
            tag_counter.update(tags_by_node.get(member, []))

        label = clean_text(profiles.get(cid, {}).get("label", f"Community {cid}"))
        description = clean_text(profiles.get(cid, {}).get("description", ""))
        top_artists = [name for name, _ in artist_counter.most_common(10)]
        top_tags = [name for name, _ in tag_counter.most_common(10)]

        size_norm = max(1, size)
        ranked_members = sorted(
            members,
            key=lambda n: (
                -(0.35 * degree.get(n, 0) + 0.35 * pagerank.get(n, 0) + 0.20 * betweenness.get(n, 0) + 0.10 * closeness.get(n, 0)),
                n,
            ),
        )
        top_nodes = [
            {
                "id": node,
                "degree": degree.get(node, 0),
                "pagerank": round(pagerank.get(node, 0.0), 6),
                "betweenness": round(betweenness.get(node, 0.0), 6),
                "closeness": round(closeness.get(node, 0.0), 6),
            }
            for node in ranked_members[:6]
        ]

        bridge_candidates = []
        for node in members:
            node_comm = community_key(partition.get(node, cid))
            neighbor_comms = {
                community_key(partition.get(neighbor, "-1"))
                for neighbor in G.neighbors(node)
                if community_key(partition.get(neighbor, "-1")) != node_comm
            }
            cross_fraction = 0.0
            deg = degree.get(node, 0)
            if deg:
                cross_edges = sum(
                    1 for neighbor in G.neighbors(node)
                    if community_key(partition.get(neighbor, "-1")) != node_comm
                )
                cross_fraction = cross_edges / deg

            bridge_score = (
                0.55 * betweenness.get(node, 0.0)
                + 0.25 * cross_fraction
                + 0.20 * (degree.get(node, 0) / max(1, max(degree.values(), default=1)))
            )
            if neighbor_comms:
                bridge_candidates.append(
                    {
                        "id": node,
                        "bridge_score": round(bridge_score, 6),
                        "cross_community_neighbors": len(neighbor_comms),
                        "cross_fraction": round(cross_fraction, 6),
                        "degree": degree.get(node, 0),
                    }
                )

        bridge_nodes = sorted(
            bridge_candidates,
            key=lambda x: (-x["bridge_score"], -x["cross_community_neighbors"], x["id"]),
        )[:6]

        communities.append(
            {
                "id": cid,
                "label": label,
                "description": description,
                "size": size,
                "density": round(density, 6),
                "avg_degree": round(avg_degree, 4),
                "top_artists": top_artists,
                "top_tags": top_tags,
                "top_nodes": top_nodes,
                "bridge_nodes": bridge_nodes,
            }
        )
        community_map[cid] = communities[-1]

    return communities, community_map


def link_related_communities(communities):
    """Link communities by overlap in their top artists and tags."""
    by_id = {c["id"]: c for c in communities}
    for community in communities:
        related = []
        a_artists = set(community.get("top_artists", []))
        a_tags = set(community.get("top_tags", []))
        for other in communities:
            if other["id"] == community["id"]:
                continue
            b_artists = set(other.get("top_artists", []))
            b_tags = set(other.get("top_tags", []))
            score = 0.62 * jaccard(a_artists, b_artists) + 0.38 * jaccard(a_tags, b_tags)
            if score > 0:
                related.append(
                    {
                        "id": other["id"],
                        "label": other["label"],
                        "score": round(score, 4),
                    }
                )
        community["related_communities"] = sorted(related, key=lambda x: (-x["score"], str(x["id"])))[:4]
    return by_id


def build_node_records(
    G,
    partition,
    profiles,
    palette,
    degree,
    closeness,
    pagerank,
    clustering,
    betweenness,
    node_importance,
    bridge_scores,
    community_map,
    artists_by_node,
    tags_by_node,
):
    """Convert graph nodes into rich records for the dashboard."""
    max_degree = max(degree.values(), default=1)
    max_page = max(pagerank.values(), default=1.0)

    node_records = []
    node_lookup = {}
    for node, data in G.nodes(data=True):
        cid = community_key(partition.get(node, "-1"))
        profile = profiles.get(cid, {})
        community = community_map.get(cid, {})
        color = palette.get(cid, "#7c3aed")
        node_size = 10 + 24 * (
            0.44 * (degree.get(node, 0) / max_degree if max_degree else 0)
            + 0.36 * (pagerank.get(node, 0.0) / max_page if max_page else 0)
            + 0.20 * node_importance.get(node, 0.5)
        )
        node_size = max(8, min(34, node_size))
        tooltip_text = "\n".join(
            [
                clean_text(node),
                f"Community: {clean_text(profile.get('label', f'Community {cid}'))}",
                f"Playcount: {safe_int(data.get('playcount', 0)):,}",
                f"Degree: {degree.get(node, 0)}",
                f"PageRank: {pagerank.get(node, 0.0):.4f}",
                f"Bridge: {bridge_scores.get(node, 0.0):.3f}",
                f"Artists: {', '.join(artists_by_node.get(node, [])[:4]) or 'No artist data'}",
                f"Tags: {', '.join(tags_by_node.get(node, [])[:4]) or 'No tag data'}",
            ]
        )

        record = {
            "id": node,
            "label": clean_text(node),
            "username": clean_text(node),
            "community_id": cid,
            "community_label": clean_text(profile.get("label", f"Community {cid}")),
            "community_size": community.get("size", 0),
            "playcount": safe_int(data.get("playcount", 0)),
            "top_artists": artists_by_node.get(node, []),
            "top_tags": tags_by_node.get(node, []),
            "degree": degree.get(node, 0),
            "closeness": round(closeness.get(node, 0.0), 6),
            "pagerank": round(pagerank.get(node, 0.0), 6),
            "clustering": round(clustering.get(node, 0.0), 6),
            "betweenness": round(betweenness.get(node, 0.0), 6),
            "importance": round(node_importance.get(node, 0.5), 6),
            "bridge_score": round(bridge_scores.get(node, 0.0), 6),
            "color_hex": color,
            "color": make_color_pack(color),
            "size": round(node_size, 2),
            "value": round(node_size, 2),
            "mass": max(0.6, 2.8 - node_size / 18),
            "title": tooltip_text,
            "font": {"color": "#F8FAFC", "size": 14, "face": "Manrope"},
            "borderWidth": 2,
            "borderWidthSelected": 5,
            "shadow": {"enabled": True, "size": 16, "color": "rgba(2, 6, 23, 0.45)", "x": 0, "y": 0},
            "shape": "dot",
            "search_text": " ".join(
                [
                    clean_text(node),
                    clean_text(profile.get("label", "")),
                    clean_text(profile.get("description", "")),
                    " ".join(artists_by_node.get(node, [])),
                    " ".join(tags_by_node.get(node, [])),
                ]
            ).lower(),
            "community_related": community.get("related_communities", []),
        }
        node_records.append(record)
        node_lookup[node] = record
    return node_records, node_lookup


def build_edge_records(G, partition, min_weight=1):
    """Convert graph edges into styled records for vis-network."""
    edges = []
    max_weight = 1.0
    for src, tgt, data in G.edges(data=True):
        max_weight = max(max_weight, safe_float(data.get("weight", 1), 1.0))

    for idx, (src, tgt, data) in enumerate(G.edges(data=True)):
        weight = safe_float(data.get("weight", 1), 1.0)
        etype = clean_text(data.get("etype", "connection"))
        width = 0.8 + 3.0 * (weight / max_weight if max_weight else 1.0)
        base_color = "rgba(148,163,184,0.32)"
        if etype.lower() == "friend":
            base_color = "rgba(96,165,250,0.42)"
        elif etype.lower() == "listener":
            base_color = "rgba(244,114,182,0.34)"
        edges.append(
            {
                "id": f"e{idx}",
                "from": src,
                "to": tgt,
                "value": round(weight, 4),
                "weight": round(weight, 4),
                "width": round(width, 2),
                "title": f"{clean_text(src)} <-> {clean_text(tgt)} Type:{etype} Weight: {weight:.2f}",
                "color": {
                    "color": base_color,
                    "highlight": "rgba(248,250,252,0.92)",
                    "hover": "rgba(248,250,252,0.92)",
                },
                "smooth": {"enabled": True, "type": "dynamic"},
            }
        )
    return edges


def build_dashboard_html(data):
    """Render the interactive dashboard HTML from the payload."""
    template = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Music Community Atlas</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Space+Grotesk:wght@500;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://unpkg.com/vis-network@9.1.9/styles/vis-network.min.css">
  <script src="https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js"></script>
  <style>
    :root {{
      --bg: #050816;
      --panel: rgba(10, 15, 30, 0.72);
      --panel-strong: rgba(14, 18, 35, 0.94);
      --stroke: rgba(148, 163, 184, 0.18);
      --stroke-strong: rgba(148, 163, 184, 0.36);
      --text: #e5eefb;
      --muted: #97a6c6;
      --accent: #7dd3fc;
      --accent-2: #c084fc;
      --accent-3: #f9a8d4;
      --good: #34d399;
      --warning: #fbbf24;
      --shadow: 0 24px 80px rgba(2, 6, 23, 0.45);
    }}
    * {{ box-sizing: border-box; }}
    html, body {{ height: 100%; }}
    body {{
      margin: 0;
      background:
        radial-gradient(circle at 15% 20%, rgba(125, 211, 252, 0.18), transparent 30%),
        radial-gradient(circle at 82% 15%, rgba(192, 132, 252, 0.17), transparent 28%),
        radial-gradient(circle at 50% 90%, rgba(249, 168, 212, 0.10), transparent 25%),
        linear-gradient(180deg, #050816 0%, #070b18 45%, #02040b 100%);
      color: var(--text);
      font-family: "Manrope", system-ui, sans-serif;
      overflow: hidden;
    }}
    .app {{
      position: relative;
      height: 100vh;
      padding: 12px;
    }}
    .shell {{
      height: 100%;
      display: grid;
      grid-template-rows: auto auto minmax(0, 1fr);
      gap: 10px;
    }}
    .hero {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 12px;
      align-items: end;
      padding: 12px 16px;
      border: 1px solid var(--stroke);
      border-radius: 24px;
      background: linear-gradient(135deg, rgba(12,16,31,0.88), rgba(11,16,30,0.62));
      box-shadow: var(--shadow);
      backdrop-filter: blur(20px);
    }}
    .eyebrow {{
      display: inline-flex;
      gap: 8px;
      align-items: center;
      text-transform: uppercase;
      letter-spacing: 0.18em;
      font-size: 11px;
      color: var(--accent);
      font-weight: 800;
      margin-bottom: 6px;
    }}
    .hero h1 {{
      margin: 0;
      font-family: "Space Grotesk", sans-serif;
      font-size: clamp(24px, 3vw, 42px);
      line-height: 1.02;
      letter-spacing: -0.04em;
    }}
    .hero-title {{
      background: linear-gradient(92deg, #8fe9ff 0%, #7dd3fc 22%, #c084fc 58%, #f9a8d4 100%);
      -webkit-background-clip: text;
      background-clip: text;
      color: transparent;
      filter: drop-shadow(0 10px 26px rgba(125, 211, 252, 0.12));
    }}
    .hero p {{
      margin: 8px 0 0;
      color: var(--muted);
      font-size: 13px;
      max-width: 72ch;
    }}
    .hero-actions {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }}
    .btn {{
      appearance: none;
      border: 1px solid var(--stroke);
      background: rgba(15, 23, 42, 0.72);
      color: var(--text);
      border-radius: 999px;
      padding: 10px 14px;
      font-weight: 700;
      cursor: pointer;
      transition: transform .18s ease, border-color .18s ease, background .18s ease;
    }}
    .btn:hover {{
      transform: translateY(-1px);
      border-color: rgba(125, 211, 252, 0.6);
      background: rgba(15, 23, 42, 0.96);
    }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(6, minmax(0, 1fr));
      gap: 10px;
    }}
    .metric {{
      border: 1px solid rgba(148, 163, 184, 0.16);
      border-radius: 18px;
      background: rgba(15, 23, 42, 0.88);
      backdrop-filter: blur(18px);
      padding: 12px 14px;
      box-shadow: 0 18px 44px rgba(2, 6, 23, 0.24);
      position: relative;
      overflow: hidden;
    }}
    .metric::before {{
      content: "";
      position: absolute;
      inset: 0;
      background: linear-gradient(135deg, rgba(255,255,255,0.06), transparent 30%);
      pointer-events: none;
    }}
    .metric strong {{
      font-size: 22px;
      line-height: 1;
      font-family: "Space Grotesk", sans-serif;
      position: relative;
      z-index: 1;
    }}
    .metric-nodes {{ border-color: rgba(125,211,252,0.26); background: rgba(24, 53, 86, 0.90); box-shadow: 0 18px 40px rgba(37,99,235,0.12); }}
    .metric-nodes strong {{ color: #b9ecff; }}
    .metric-edges {{ border-color: rgba(192,132,252,0.26); background: rgba(53, 35, 84, 0.90); box-shadow: 0 18px 40px rgba(147,51,234,0.12); }}
    .metric-edges strong {{ color: #e5c4ff; }}
    .metric-communities {{ border-color: rgba(249,168,212,0.26); background: rgba(83, 35, 65, 0.90); box-shadow: 0 18px 40px rgba(236,72,153,0.12); }}
    .metric-communities strong {{ color: #ffd3eb; }}
    .metric-visible-nodes {{ border-color: rgba(56,189,248,0.24); background: rgba(16, 66, 87, 0.90); box-shadow: 0 18px 40px rgba(14,165,233,0.12); }}
    .metric-visible-nodes strong {{ color: #caecff; }}
    .metric-visible-edges {{ border-color: rgba(251,191,36,0.24); background: rgba(89, 60, 18, 0.90); box-shadow: 0 18px 40px rgba(245,158,11,0.12); }}
    .metric-visible-edges strong {{ color: #ffe2a8; }}
    .metric-filter {{ border-color: rgba(148,163,184,0.24); background: rgba(42, 50, 69, 0.92); box-shadow: 0 18px 40px rgba(15,23,42,0.18); }}
    .metric-filter strong {{ color: #edf2ff; }}
    .metric span {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 6px;
      text-transform: uppercase;
      letter-spacing: 0.10em;
    }}
    .workspace {{
      min-height: 0;
      display: grid;
      grid-template-columns: 330px minmax(0, 1fr) 360px;
      gap: 10px;
    }}
    .vis-tooltip {{
      padding: 10px 12px !important;
      background: rgba(8, 13, 28, 0.96) !important;
      border: 1px solid rgba(125,211,252,0.20) !important;
      border-radius: 14px !important;
      box-shadow: 0 20px 48px rgba(2, 6, 23, 0.38) !important;
      color: #e5eefb !important;
      max-width: 320px;
      white-space: pre-line !important;
      line-height: 1.55 !important;
      font-size: 12px !important;
      font-family: "Manrope", system-ui, sans-serif !important;
    }}
    .vis-network .vis-navigation {{
      top: 18px !important;
      right: 18px !important;
      bottom: auto !important;
      left: auto !important;
      display: grid !important;
      gap: 10px !important;
      padding: 10px !important;
      border: 1px solid rgba(125,211,252,0.18) !important;
      border-radius: 18px !important;
      background: rgba(7, 11, 24, 0.58) !important;
      backdrop-filter: blur(16px) !important;
      box-shadow: 0 20px 36px rgba(2, 6, 23, 0.28) !important;
    }}
    .vis-network .vis-button {{
      position: relative !important;
      width: 42px !important;
      height: 42px !important;
      margin: 0 !important;
      background-image: none !important;
      background-color: transparent !important;
      border: 1px solid rgba(125,211,252,0.22) !important;
      border-radius: 14px !important;
      box-shadow: 0 14px 28px rgba(2, 6, 23, 0.24) !important;
      opacity: 0.98 !important;
      transition: transform .18s ease, border-color .18s ease, box-shadow .18s ease, background .18s ease !important;
    }}
    .vis-network .vis-button::before {{
      content: "" !important;
      position: absolute !important;
      inset: 0 !important;
      display: flex !important;
      align-items: center !important;
      justify-content: center !important;
      font-family: "Space Grotesk", sans-serif !important;
      font-size: 18px !important;
      font-weight: 700 !important;
      color: #edf7ff !important;
      text-shadow: 0 4px 12px rgba(15, 23, 42, 0.45) !important;
    }}
    .vis-network .vis-button:hover {{
      border-color: rgba(125,211,252,0.54) !important;
      box-shadow: 0 18px 34px rgba(2, 6, 23, 0.30) !important;
      transform: translateY(-1px) !important;
    }}
    .vis-network .vis-button:active {{
      transform: translateY(1px) !important;
    }}
    .vis-network .vis-zoomIn,
    .vis-network .vis-zoomOut,
    .vis-network .vis-zoomExtends,
    .vis-network .vis-manipulationButton {{
      background-image: none !important;
    }}
    .vis-network .vis-zoomIn {{
      background: linear-gradient(180deg, rgba(56,189,248,0.28), rgba(15,23,42,0.96)) !important;
    }}
    .vis-network .vis-zoomIn::before {{ content: "+" !important; }}
    .vis-network .vis-zoomOut {{
      background: linear-gradient(180deg, rgba(167,139,250,0.28), rgba(15,23,42,0.96)) !important;
    }}
    .vis-network .vis-zoomOut::before {{ content: "-" !important; }}
    .vis-network .vis-zoomExtends {{
      background: linear-gradient(180deg, rgba(244,114,182,0.26), rgba(15,23,42,0.96)) !important;
    }}
    .vis-network .vis-zoomExtends::before {{
      content: "[]" !important;
      font-size: 12px !important;
      letter-spacing: -0.08em !important;
    }}
    .vis-network .vis-up,
    .vis-network .vis-down,
    .vis-network .vis-left,
    .vis-network .vis-right {{
      background: linear-gradient(180deg, rgba(148,163,184,0.22), rgba(15,23,42,0.96)) !important;
    }}
    .vis-network .vis-up::before {{ content: "^" !important; }}
    .vis-network .vis-down::before {{ content: "v" !important; }}
    .vis-network .vis-left::before {{ content: "<" !important; }}
    .vis-network .vis-right::before {{ content: ">" !important; }}
    .panel {{
      min-height: 0;
      border: 1px solid var(--stroke);
      border-radius: 24px;
      background: var(--panel);
      backdrop-filter: blur(20px);
      box-shadow: var(--shadow);
      overflow: hidden;
    }}
    .sidebar {{
      display: grid;
      grid-template-rows: auto auto 1fr;
    }}
    .panel-header {{
      padding: 16px 18px;
      border-bottom: 1px solid rgba(148,163,184,0.12);
      background: linear-gradient(180deg, rgba(255,255,255,0.03), transparent);
    }}
    .panel-title {{
      margin: 0;
      font-family: "Space Grotesk", sans-serif;
      font-size: 18px;
    }}
    .panel-subtitle {{
      margin: 6px 0 0;
      font-size: 13px;
      color: var(--muted);
    }}
    .panel-body {{
      padding: 16px 18px 18px;
      min-height: 0;
      overflow: auto;
    }}
    .control-grid {{
      display: grid;
      gap: 12px;
    }}
    .field label {{
      display: block;
      font-size: 12px;
      color: var(--muted);
      margin-bottom: 8px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-weight: 700;
    }}
    .search-row {{
      display: flex;
      gap: 10px;
    }}
    .input, .select, .range {{
      width: 100%;
    }}
    .input, .select {{
      border: 1px solid rgba(148,163,184,0.22);
      background: rgba(15, 23, 42, 0.78);
      color: var(--text);
      border-radius: 14px;
      padding: 12px 14px;
      outline: none;
    }}
    .input:focus, .select:focus {{
      border-color: rgba(125, 211, 252, 0.75);
      box-shadow: 0 0 0 4px rgba(125, 211, 252, 0.12);
    }}
    .small-btn {{
      border-radius: 14px;
      border: 1px solid rgba(148,163,184,0.22);
      background: rgba(15,23,42,0.7);
      color: var(--text);
      padding: 12px 14px;
      cursor: pointer;
      font-weight: 700;
      transition: transform .18s ease, border-color .18s ease;
    }}
    .small-btn:hover {{
      transform: translateY(-1px);
      border-color: rgba(125,211,252,0.5);
    }}
    .toggle-row {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .toggle-pill {{
      display: inline-flex;
      gap: 8px;
      align-items: center;
      padding: 10px 12px;
      border-radius: 999px;
      border: 1px solid rgba(148,163,184,0.2);
      background: rgba(15,23,42,0.55);
      color: var(--text);
      cursor: pointer;
      font-size: 13px;
      font-weight: 700;
    }}
    .toggle-pill input {{ display: none; }}
    .toggle-pill.active {{
      border-color: rgba(125,211,252,0.7);
      background: rgba(15,23,42,0.92);
      box-shadow: 0 0 0 3px rgba(125,211,252,0.08) inset;
    }}
    .divider {{
      height: 1px;
      background: rgba(148,163,184,0.12);
      margin: 6px 0;
    }}
    .section-title {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      margin: 0 0 12px;
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0.11em;
      color: var(--muted);
      font-weight: 800;
    }}
    .results {{
      display: grid;
      gap: 10px;
      max-height: 270px;
      overflow: auto;
    }}
    .result {{
      text-align: left;
      width: 100%;
      border: 1px solid rgba(148,163,184,0.16);
      background: rgba(15,23,42,0.55);
      border-radius: 18px;
      color: var(--text);
      padding: 12px 14px;
      cursor: pointer;
      transition: transform .18s ease, border-color .18s ease;
    }}
    .result:hover {{
      transform: translateY(-1px);
      border-color: rgba(125,211,252,0.5);
    }}
    .result strong {{
      display: block;
      font-size: 14px;
      margin-bottom: 4px;
    }}
    .result span {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.4;
    }}
    .community-list {{
      display: grid;
      gap: 10px;
    }}
    .community-card {{
      border: 1px solid rgba(148,163,184,0.14);
      border-radius: 18px;
      background: rgba(15,23,42,0.58);
      overflow: hidden;
      cursor: pointer;
      transition: transform .18s ease, border-color .18s ease;
    }}
    .community-card:hover {{
      transform: translateY(-1px);
      border-color: rgba(125,211,252,0.46);
    }}
    .community-top {{
      height: 7px;
      background: var(--community-color, linear-gradient(90deg, #7dd3fc, #c084fc));
    }}
    .community-body {{
      padding: 12px 14px 14px;
    }}
    .community-body h4 {{
      margin: 0 0 6px;
      font-size: 15px;
      font-family: "Space Grotesk", sans-serif;
    }}
    .community-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 10px;
    }}
    .chip-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }}
    .chip {{
      display: inline-flex;
      align-items: center;
      padding: 6px 9px;
      border-radius: 999px;
      border: 1px solid rgba(148,163,184,0.16);
      background: rgba(2,6,23,0.26);
      color: #dbeafe;
      font-size: 12px;
      line-height: 1;
    }}
    .chip.soft {{
      color: #cbd5e1;
    }}
    .canvas-panel {{
      position: relative;
      display: grid;
      grid-template-rows: auto minmax(0, 1fr);
      padding: 10px;
      background:
        radial-gradient(circle at top, rgba(125,211,252,0.08), transparent 34%),
        linear-gradient(180deg, rgba(9, 12, 24, 0.76), rgba(6, 10, 20, 0.90));
    }}
    .canvas-toolbar {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      justify-content: space-between;
      padding: 4px 8px 0;
      margin-bottom: 2px;
      border: 0;
      background: transparent;
    }}
    .canvas-caption {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      align-items: center;
    }}
    .canvas-caption {{
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.01em;
    }}
    .status {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 9px 12px;
      border-radius: 999px;
      background: rgba(15,23,42,0.68);
      border: 1px solid rgba(148,163,184,0.14);
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }}
    .dot {{
      width: 8px;
      height: 8px;
      border-radius: 999px;
      background: var(--accent);
      box-shadow: 0 0 18px rgba(125,211,252,0.65);
    }}
    .canvas-stage {{
      min-height: 0;
      padding-top: 10px;
    }}
    #network {{
      min-height: 0;
      height: 100%;
      width: 100%;
      border-radius: 22px;
      border: 1px solid rgba(125,211,252,0.12);
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.03), 0 22px 48px rgba(2, 6, 23, 0.20);
      background:
        radial-gradient(circle at 50% 45%, rgba(125, 211, 252, 0.06), transparent 36%),
        radial-gradient(circle at 50% 50%, rgba(192, 132, 252, 0.05), transparent 60%),
        linear-gradient(180deg, rgba(4, 8, 18, 0.78), rgba(2, 6, 23, 0.54));
    }}
    .detail-stack {{
      display: grid;
      gap: 14px;
    }}
    .detail-card {{
      border: 1px solid rgba(148,163,184,0.14);
      border-radius: 20px;
      background: rgba(15,23,42,0.62);
      overflow: hidden;
    }}
    .detail-card.hero-card {{
      border-color: rgba(125,211,252,0.25);
      background:
        radial-gradient(circle at top left, rgba(125,211,252,0.16), transparent 36%),
        linear-gradient(180deg, rgba(15,23,42,0.92), rgba(15,23,42,0.68));
    }}
    .detail-head {{
      padding: 14px 16px;
      border-bottom: 1px solid rgba(148,163,184,0.12);
      background: linear-gradient(180deg, rgba(255,255,255,0.03), transparent);
    }}
    .node-badge {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 10px;
      padding: 7px 10px;
      border-radius: 999px;
      background: rgba(125,211,252,0.10);
      border: 1px solid rgba(125,211,252,0.18);
      color: #dff4ff;
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }}
    .node-dot {{
      width: 8px;
      height: 8px;
      border-radius: 999px;
      background: var(--accent);
      box-shadow: 0 0 18px rgba(125,211,252,0.7);
    }}
    .detail-head h3 {{
      margin: 0;
      font-size: 16px;
      font-family: "Space Grotesk", sans-serif;
    }}
    .detail-head p {{
      margin: 6px 0 0;
      color: var(--muted);
      font-size: 12px;
    }}
    .detail-body {{
      padding: 14px 16px 16px;
      display: grid;
      gap: 14px;
    }}
    .profile-hero {{
      display: grid;
      gap: 10px;
    }}
    .profile-hero h3 {{
      margin: 0;
      font-size: 24px;
      line-height: 1.05;
      letter-spacing: -0.03em;
      font-family: "Space Grotesk", sans-serif;
    }}
    .profile-hero p {{
      margin: 0;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.6;
    }}
    .stats-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }}
    .mini-stat {{
      border: 1px solid rgba(148,163,184,0.12);
      border-radius: 16px;
      background: rgba(2,6,23,0.18);
      padding: 10px 12px;
    }}
    .mini-stat span {{
      display: block;
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 5px;
      font-weight: 800;
    }}
    .mini-stat strong {{
      font-size: 16px;
    }}
    .section-card {{
      border-top: 1px solid rgba(148,163,184,0.10);
      padding-top: 12px;
    }}
    .section-card:first-child {{
      border-top: 0;
      padding-top: 0;
    }}
    .section-label {{
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 8px;
      text-transform: uppercase;
      letter-spacing: 0.10em;
      font-weight: 800;
    }}
    .list {{
      display: grid;
      gap: 8px;
    }}
    .list-item {{
      border: 1px solid rgba(148,163,184,0.12);
      background:
        linear-gradient(180deg, rgba(255,255,255,0.02), transparent),
        rgba(2,6,23,0.18);
      border-radius: 16px;
      padding: 10px 12px;
    }}
    .list-item button {{
      all: unset;
      cursor: pointer;
      display: block;
      width: 100%;
    }}
    .list-item .title {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      font-weight: 800;
      margin-bottom: 6px;
    }}
    .score {{
      color: var(--accent);
      font-size: 12px;
      font-weight: 800;
    }}
    .pill-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .stat-chip {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 8px 10px;
      border-radius: 999px;
      background: rgba(2,6,23,0.20);
      border: 1px solid rgba(148,163,184,0.14);
      color: #e2e8f0;
      font-size: 12px;
      font-weight: 700;
    }}
    .stat-chip strong {{
      color: #fff;
      font-family: "Space Grotesk", sans-serif;
    }}
    .section-card.compact {{
      padding-top: 10px;
    }}
    .tiny-note {{
      color: var(--muted);
      font-size: 12px;
      margin-top: 2px;
    }}
    .muted {{
      color: var(--muted);
      font-size: 12px;
      line-height: 1.45;
    }}
    .bar {{
      width: 100%;
      height: 8px;
      background: rgba(148,163,184,0.12);
      border-radius: 999px;
      overflow: hidden;
      margin-top: 8px;
    }}
    .bar > div {{
      height: 100%;
      border-radius: 999px;
      background: linear-gradient(90deg, var(--accent), var(--accent-2));
    }}
    .empty-state {{
      border: 1px dashed rgba(148,163,184,0.24);
      border-radius: 18px;
      padding: 16px;
      color: var(--muted);
      line-height: 1.5;
      background: rgba(2,6,23,0.14);
    }}
    .footer-links {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-top: 10px;
    }}
    .footer-links a {{
      color: #dbeafe;
      text-decoration: none;
      border: 1px solid rgba(148,163,184,0.16);
      border-radius: 999px;
      padding: 8px 10px;
      background: rgba(15,23,42,0.44);
      font-size: 12px;
      font-weight: 700;
    }}
    .footer-links a:hover {{
      border-color: rgba(125,211,252,0.55);
    }}
    @media (max-width: 1400px) {{
      .workspace {{ grid-template-columns: 300px minmax(0, 1fr) 320px; }}
      .metrics {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
    }}
    @media (max-width: 1100px) {{
      body {{ overflow: auto; }}
      .app {{ height: auto; min-height: 100vh; }}
      .shell {{ grid-template-rows: auto auto auto; }}
      .workspace {{ grid-template-columns: 1fr; }}
      .metrics {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .hero {{ grid-template-columns: 1fr; }}
      .hero-actions {{ justify-content: flex-start; }}
      .panel {{ min-height: 520px; }}
    }}
  </style>
</head>
<body>
  <div class="app">
    <div class="shell">
      <section class="hero panel">
        <div class="panel-body" style="padding: 12px 16px;">
          <div class="eyebrow">Skill E · Interactive Music Community Atlas</div>
          <h1><span class="hero-title">Music Community Explorer</span></h1>
          <div class="footer-links">
            <a href="final_report.html">Open report</a>
            <a href="network_viz.png">Open PNG</a>
          </div>
        </div>
        <div class="hero-actions" style="padding: 12px 16px 12px 0;">
          <button class="btn" id="resetBtn">Reset</button>
          <button class="btn" id="focusBtn">Focus selected</button>
          <button class="btn" id="fitBtn">Fit graph</button>
          <button class="btn" id="physicsBtn">Physics on</button>
        </div>
      </section>

      <section class="metrics">
        <div class="metric metric-nodes"><span>Total nodes</span><strong id="totalNodes">0</strong></div>
        <div class="metric metric-edges"><span>Total edges</span><strong id="totalEdges">0</strong></div>
        <div class="metric metric-communities"><span>Communities</span><strong id="totalCommunities">0</strong></div>
        <div class="metric metric-visible-nodes"><span>Visible nodes</span><strong id="visibleNodes">0</strong></div>
        <div class="metric metric-visible-edges"><span>Visible edges</span><strong id="visibleEdges">0</strong></div>
        <div class="metric metric-filter"><span>Active filter</span><strong id="activeFilter">All</strong></div>
      </section>

      <section class="workspace">
        <aside class="panel sidebar">
          <div class="panel-header">
            <h2 class="panel-title">Explore</h2>
            <p class="panel-subtitle">Search listeners, filter communities, and surface similar users.</p>
          </div>
          <div class="panel-body control-grid">
            <div class="field">
              <label for="searchInput">Search</label>
              <div class="search-row">
                <input class="input" id="searchInput" placeholder="username, artist, tag, community..." />
                <button class="small-btn" id="searchClearBtn" type="button">Clear</button>
              </div>
            </div>

            <div class="field">
              <label for="communitySelect">Community filter</label>
              <select class="select" id="communitySelect"></select>
            </div>

            <div class="field">
              <label for="weightSlider">Original edge weight threshold: <span id="weightValue">1</span></label>
              <input class="range" id="weightSlider" type="range" min="1" max="1" value="1" step="1" />
            </div>

            <div class="toggle-row">
              <label class="toggle-pill" id="focusModePill"><input type="checkbox" id="focusModeToggle" /> Focus neighborhood</label>
              <label class="toggle-pill" id="bridgeModePill"><input type="checkbox" id="bridgeModeToggle" checked /> Highlight bridges</label>
            </div>

            <div class="divider"></div>

            <div>
              <div class="section-title"><span>Search results</span><span id="searchCount">0</span></div>
              <div class="results" id="searchResults"></div>
            </div>

            <div>
              <div class="section-title"><span>Communities</span><span id="communityCount">0</span></div>
              <div class="community-list" id="communityList"></div>
            </div>
          </div>
        </aside>

        <main class="panel canvas-panel">
          <div class="canvas-toolbar">
            <div class="canvas-caption"><span class="dot" style="display:inline-block;vertical-align:middle;margin-right:8px;"></span><span id="statusText">Dashboard ready</span> · Click a node to unlock recommendations · Drag, zoom, explore</div>
          </div>
          <div class="canvas-stage">
            <div id="network"></div>
          </div>
        </main>

        <aside class="panel sidebar">
          <div class="panel-header">
            <h2 class="panel-title">Recommendations</h2>
            <p class="panel-subtitle">Taste matches, strong ties, and bridge candidates from your current focus.</p>
          </div>
          <div class="panel-body">
            <div class="detail-stack">
              <div class="detail-card" id="nodePanel">
                <div class="detail-head">
                  <h3>No node selected</h3>
                  <p>Pick a node to see its taste profile and recommendations.</p>
                </div>
                <div class="detail-body">
                  <div class="empty-state">
                    Select a listener node in the graph, or search a username/artist/tag from the left panel.
                  </div>
                </div>
              </div>

              <div class="detail-card" id="communityPanel">
                <div class="detail-head">
                  <h3>Community overview</h3>
                  <p>Choose a community to inspect its identity and crossover paths.</p>
                </div>
                <div class="detail-body">
                  <div class="empty-state">
                    The dashboard will show the currently focused community, related communities, and the best entry nodes.
                  </div>
                </div>
              </div>
            </div>
          </div>
        </aside>
      </section>
    </div>
  </div>

  <script id="viz-data" type="application/json">__VIZ_DATA__</script>
  <script>
    const APP = JSON.parse(document.getElementById("viz-data").textContent);
    const state = {{
      community: "all",
      selectedNode: null,
      searchTerm: "",
      minWeight: 1,
      focusMode: false,
      bridgeMode: true,
      physicsOn: true,
      searchMatches: new Set(),
      highlightedNodes: new Set(),
      highlightedEdges: new Set(),
    }};

    const baseNodes = APP.nodes.map(node => Object.assign({{}}, node));
    const baseEdges = APP.edges.map(edge => Object.assign({{}}, edge));
    const nodeMap = new Map();
    const communityMap = new Map();
    const neighborMap = new Map();
    const searchIndex = new Map();

    for (const node of baseNodes) {{
      nodeMap.set(String(node.id), node);
      searchIndex.set(String(node.id), (node.search_text || "").toLowerCase());
    }}
    for (const community of APP.communities) {{
      communityMap.set(String(community.id), community);
    }}
    for (const edge of baseEdges) {{
      const a = String(edge.from);
      const b = String(edge.to);
      if (!neighborMap.has(a)) neighborMap.set(a, []);
      if (!neighborMap.has(b)) neighborMap.set(b, []);
      neighborMap.get(a).push({{ id: b, weight: edge.weight }});
      neighborMap.get(b).push({{ id: a, weight: edge.weight }});
    }}

    const nodes = new vis.DataSet(baseNodes);
    const edges = new vis.DataSet(baseEdges);
    const network = new vis.Network(document.getElementById("network"), {{ nodes, edges }}, {{
      autoResize: true,
      interaction: {{
        hover: true,
        multiselect: false,
        navigationButtons: false,
        keyboard: true,
        tooltipDelay: 90,
      }},
      layout: {{
        improvedLayout: true,
      }},
      edges: {{
        width: 1,
        selectionWidth: 2,
        hoverWidth: 3,
        arrows: {{ to: {{ enabled: false }} }},
      }},
      nodes: {{
        shape: "dot",
        font: {{ color: "#F8FAFC", face: "Manrope", size: 14 }},
      }},
      physics: {{
        enabled: true,
        solver: "forceAtlas2Based",
        forceAtlas2Based: {{
          gravitationalConstant: -68,
          centralGravity: 0.018,
          springLength: 145,
          springConstant: 0.09,
          damping: 0.48,
          avoidOverlap: 1
        }},
        stabilization: {{
          enabled: true,
          iterations: 220,
          fit: true
        }}
      }}
    }});

    const els = {{
      searchInput: document.getElementById("searchInput"),
      searchClearBtn: document.getElementById("searchClearBtn"),
      searchResults: document.getElementById("searchResults"),
      searchCount: document.getElementById("searchCount"),
      communitySelect: document.getElementById("communitySelect"),
      communityList: document.getElementById("communityList"),
      communityCount: document.getElementById("communityCount"),
      weightSlider: document.getElementById("weightSlider"),
      weightValue: document.getElementById("weightValue"),
      focusModeToggle: document.getElementById("focusModeToggle"),
      bridgeModeToggle: document.getElementById("bridgeModeToggle"),
      focusModePill: document.getElementById("focusModePill"),
      bridgeModePill: document.getElementById("bridgeModePill"),
      resetBtn: document.getElementById("resetBtn"),
      focusBtn: document.getElementById("focusBtn"),
      fitBtn: document.getElementById("fitBtn"),
      physicsBtn: document.getElementById("physicsBtn"),
      statusText: document.getElementById("statusText"),
      totalNodes: document.getElementById("totalNodes"),
      totalEdges: document.getElementById("totalEdges"),
      totalCommunities: document.getElementById("totalCommunities"),
      visibleNodes: document.getElementById("visibleNodes"),
      visibleEdges: document.getElementById("visibleEdges"),
      activeFilter: document.getElementById("activeFilter"),
      nodePanel: document.getElementById("nodePanel"),
      communityPanel: document.getElementById("communityPanel"),
    }};

    function escapeHtml(value) {{
      return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
    }}

    function percent(value) {{
      return `${{Math.round((Number(value) || 0) * 100)}}%`;
    }}

    function joinChips(items, cls = "chip soft") {{
      return (items || []).map(item => `<span class="${{cls}}">${{escapeHtml(item)}}</span>`).join("");
    }}

    function listMarkup(items, limit = 6) {{
      return (items || []).slice(0, limit).map(item => `<span class="chip">${{escapeHtml(item)}}</span>`).join("");
    }}

    function communityLookup(cid) {{
      return communityMap.get(String(cid)) || null;
    }}

    function nodeText(node) {{
      const community = communityLookup(node.community_id);
      return [
        node.label,
        node.username,
        node.community_label,
        (community && community.description) || "",
        (node.top_artists || []).join(" "),
        (node.top_tags || []).join(" "),
      ].join(" ").toLowerCase();
    }}

    function sortedNodesByImportance() {{
      return baseNodes.slice().sort((a, b) => (b.importance - a.importance) || (b.degree - a.degree) || a.label.localeCompare(b.label));
    }}

    function searchNodes(term) {{
      const q = term.trim().toLowerCase();
      if (!q) return [];
      const scored = [];
      for (const node of baseNodes) {{
        const text = searchIndex.get(String(node.id)) || nodeText(node);
        if (!text.includes(q)) continue;
        let score = 0;
        if (node.username.toLowerCase() === q) score += 4;
        if ((node.label || "").toLowerCase().includes(q)) score += 2.5;
        if ((node.community_label || "").toLowerCase().includes(q)) score += 1.4;
        if ((node.top_artists || []).some(a => a.toLowerCase().includes(q))) score += 1.1;
        if ((node.top_tags || []).some(t => t.toLowerCase().includes(q))) score += 1.1;
        score += node.importance;
        scored.push({{ node, score }});
      }}
      scored.sort((a, b) => (b.score - a.score) || (b.node.degree - a.node.degree) || a.node.label.localeCompare(b.node.label));
      return scored.slice(0, 12).map(entry => entry.node);
    }}

    function setStatus(text) {{
      els.statusText.textContent = text;
    }}

    function currentCommunityLabel() {{
      if (state.community === "all") return "All communities";
      const item = communityLookup(state.community);
      return item ? item.label : `Community ${{state.community}}`;
    }}

    function edgeWeightThreshold() {{
      return state.minWeight;
    }}

    function computeVisibleIds() {{
      const visibleNodes = new Set();
      const selected = state.selectedNode ? String(state.selectedNode) : null;
      const neighborhood = state.focusMode && selected
        ? new Set([selected, ...((neighborMap.get(selected) || []).map(item => String(item.id)))])
        : null;

      for (const node of baseNodes) {{
        let visible = true;
        if (state.community !== "all" && String(node.community_id) !== String(state.community)) visible = false;
        if (neighborhood && !neighborhood.has(String(node.id))) visible = false;
        if (visible) visibleNodes.add(String(node.id));
      }}

      const visibleEdges = new Set();
      const threshold = edgeWeightThreshold();
      for (const edge of baseEdges) {{
        if (edge.weight < threshold) continue;
        if (!visibleNodes.has(String(edge.from)) || !visibleNodes.has(String(edge.to))) continue;
        if (state.focusMode && selected) {{
          if (!(String(edge.from) === selected || String(edge.to) === selected)) continue;
        }}
        visibleEdges.add(String(edge.id));
      }}

      return {{ visibleNodes, visibleEdges }};
    }}

    function refreshGraph(fit = false) {{
      const selected = state.selectedNode ? String(state.selectedNode) : null;
      const neighborhood = state.focusMode && selected
        ? new Set([selected, ...((neighborMap.get(selected) || []).map(item => String(item.id)))])
        : null;
      const {{ visibleNodes, visibleEdges }} = computeVisibleIds();

      const nodeUpdates = [];
      for (const node of baseNodes) {{
        const nodeId = String(node.id);
        const visible = visibleNodes.has(nodeId);
        const isSelected = selected && nodeId === selected;
        const isMatch = state.searchMatches.has(nodeId);
        const isNeighbor = neighborhood && neighborhood.has(nodeId) && !isSelected;
        const highlight = isSelected || isMatch || isNeighbor;
        const color = Object.assign({{}}, node.color);
        if (isSelected) {{
          color.border = "#F8FAFC";
          color.highlight = {{ background: "#FDE68A", border: "#FFFFFF" }};
        }} else if (isMatch) {{
          color.border = "#FBBF24";
          color.highlight = {{ background: "#F59E0B", border: "#FFFFFF" }};
        }} else if (isNeighbor) {{
          color.border = "#7DD3FC";
          color.highlight = {{ background: "#38BDF8", border: "#FFFFFF" }};
        }}
        nodeUpdates.push({{
          id: nodeId,
          hidden: !visible,
          borderWidth: isSelected ? 5 : highlight ? 3.4 : 2,
          color: color,
          value: node.value,
          size: node.size,
          shadow: {{
            enabled: highlight,
            size: highlight ? 20 : 14,
            color: highlight ? "rgba(14, 165, 233, 0.34)" : "rgba(2, 6, 23, 0.22)",
            x: 0,
            y: 0
          }}
        }});
      }}

      const edgeUpdates = [];
      for (const edge of baseEdges) {{
        const edgeId = String(edge.id);
        const visible = visibleEdges.has(edgeId);
        const isSelectedEdge = selected && (String(edge.from) === selected || String(edge.to) === selected);
        edgeUpdates.push({{
          id: edgeId,
          hidden: !visible,
          width: isSelectedEdge ? Math.max(2.8, edge.width + 0.8) : edge.width,
          color: isSelectedEdge ? {{ color: "rgba(248,250,252,0.92)", highlight: "#F8FAFC", hover: "#F8FAFC" }} : edge.color,
        }});
      }}

      nodes.update(nodeUpdates);
      edges.update(edgeUpdates);

      els.visibleNodes.textContent = visibleNodes.size.toLocaleString();
      els.visibleEdges.textContent = visibleEdges.size.toLocaleString();
      els.activeFilter.textContent = state.community === "all" ? (state.focusMode && selected ? "Neighborhood focus" : "All") : currentCommunityLabel();
      els.focusModePill.classList.toggle("active", state.focusMode);
      els.bridgeModePill.classList.toggle("active", state.bridgeMode);
      els.focusModeToggle.checked = state.focusMode;
      els.bridgeModeToggle.checked = state.bridgeMode;

      if (fit) {{
        network.fit({{ animation: {{ duration: 420, easingFunction: "easeInOutCubic" }} }});
      }}
      network.redraw();
    }}

    function renderSearchResults(term) {{
      els.searchResults.innerHTML = "";
      if (!term.trim()) {{
        els.searchCount.textContent = "0";
        state.searchMatches = new Set();
        refreshGraph(false);
        return;
      }}

      const matches = searchNodes(term);
      state.searchMatches = new Set(matches.map(node => String(node.id)));
      els.searchCount.textContent = String(matches.length);
      if (!matches.length) {{
        els.searchResults.innerHTML = `<div class="empty-state">No results for <b>${{escapeHtml(term)}}</b>. Try a shorter artist, tag, or username.</div>`;
        refreshGraph(false);
        return;
      }}

      els.searchResults.innerHTML = matches.map(node => {{
        const community = communityLookup(node.community_id);
        return `
          <button class="result" type="button" data-node="${{escapeHtml(node.id)}}">
            <strong>${{escapeHtml(node.label)}}</strong>
            <span>${{escapeHtml(node.community_label)}} · playcount ${{Number(node.playcount).toLocaleString()}} · degree ${{node.degree}}</span>
            <span>${{escapeHtml((node.top_artists || []).slice(0, 3).join(" • "))}}</span>
          </button>`;
      }}).join("");
      refreshGraph(false);
    }}

    function communitySummaryCard(community, active = false) {{
      const chipArtists = listMarkup(community.top_artists || [], 3);
      const chipTags = listMarkup(community.top_tags || [], 3);
      const related = (community.related_communities || []).map(item => `<span class="chip soft">${{escapeHtml(item.label)}} · ${{percent(item.score)}} </span>`).join("");
      const accent = community.color || "#7dd3fc";
      return `
        <article class="community-card" data-community="${{escapeHtml(community.id)}}" style="--community-color: linear-gradient(90deg, ${{accent}}, ${{community.secondary_color || "#c084fc"}}); ${{active ? "border-color: rgba(125,211,252,0.55);" : ""}}">
          <div class="community-top"></div>
          <div class="community-body">
            <h4>${{escapeHtml(community.label)}}</h4>
            <div class="community-meta">
              <span>${{community.size}} members</span>
              <span>density ${{community.density.toFixed(3)}}</span>
              <span>avg degree ${{community.avg_degree.toFixed(2)}}</span>
            </div>
            <div class="chip-row">${{chipArtists}}${{chipTags}}</div>
            <div class="chip-row" style="margin-top:8px;">${{related}}</div>
          </div>
        </article>`;
    }}

    function renderCommunityList() {{
      els.communityCount.textContent = String(APP.communities.length);
      els.communityList.innerHTML = APP.communities.map(c => communitySummaryCard(c, String(c.id) === String(state.community))).join("");
    }}

    function nodeListMarkup(items, type) {{
      if (!items || !items.length) return '<div class="empty-state">No recommendations available.</div>';
      return `<div class="list">${
        items.map(item => {{
          const community = communityLookup(item.community_id);
          const title = item.id;
          const score = type === "neighbor" ? `${{item.weight.toFixed(2)}}` : percent(item.score);
          const detail = type === "neighbor"
            ? `weight ${{item.weight.toFixed(2)}} · score ${{percent(item.score)}}`
            : `score ${{percent(item.score)}}`;
          const arts = (item.shared_artists || []).length ? item.shared_artists.join(" • ") : "";
          const tags = (item.shared_tags || []).length ? item.shared_tags.join(" • ") : "";
          return `
            <div class="list-item">
              <button type="button" data-node="${{escapeHtml(item.id)}}">
                <div class="title">
                  <span>${{escapeHtml(title)}}</span>
                  <span class="score">${{escapeHtml(score)}}</span>
                </div>
                <div class="muted">${{escapeHtml(community ? community.label : `Community ${{item.community_id}}`)}} · ${{escapeHtml(detail)}}</div>
                ${{arts ? `<div class="muted">Shared artists: ${{escapeHtml(arts)}}</div>` : ""}}
                ${{tags ? `<div class="muted">Shared tags: ${{escapeHtml(tags)}}</div>` : ""}}
              </button>
            </div>`;
        }}).join("")
      }</div>`;
    }}

    function renderNodePanel(nodeId) {{
      const node = nodeMap.get(String(nodeId));
      if (!node) return;
      const rec = (APP.recommendations[node.id]) || {{ similar: [], bridges: [], neighbors: [] }};
      const community = communityLookup(node.community_id);
      const communityLabel = community ? community.label : node.community_label;
      const headlineArtists = (node.top_artists || []).slice(0, 4);
      const headlineTags = (node.top_tags || []).slice(0, 4);
      const recommendationCount = rec.similar.length + rec.neighbors.length + (state.bridgeMode ? rec.bridges.length : 0);

      els.nodePanel.innerHTML = `
        <div class="detail-head">
          <div class="node-badge"><span class="node-dot"></span>Listener profile</div>
          <div class="profile-hero">
            <h3>${{escapeHtml(node.label)}}</h3>
            <p>${{escapeHtml(communityLabel)}} · playcount ${{Number(node.playcount).toLocaleString()}} · ${{recommendationCount}} recommendation signals</p>
            <div class="pill-row">
              <span class="stat-chip">Degree <strong>${{node.degree}}</strong></span>
              <span class="stat-chip">Bridge <strong>${{node.bridge_score.toFixed(3)}}</strong></span>
              <span class="stat-chip">PageRank <strong>${{node.pagerank.toFixed(4)}}</strong></span>
              <span class="stat-chip">Community <strong>${{node.community_size}}</strong></span>
            </div>
          </div>
        </div>
        <div class="detail-body">
          <div class="stats-grid">
            <div class="mini-stat"><span>Closeness</span><strong>${{node.closeness.toFixed(4)}}</strong></div>
            <div class="mini-stat"><span>Clustering</span><strong>${{node.clustering.toFixed(4)}}</strong></div>
            <div class="mini-stat"><span>Importance</span><strong>${{node.importance.toFixed(3)}}</strong></div>
            <div class="mini-stat"><span>Cross-community</span><strong>${{node.cross_community_neighbors || 0}}</strong></div>
          </div>

          <div class="section-card compact">
            <div class="section-label">Taste signature</div>
            <div class="chip-row">${{headlineArtists.length ? joinChips(headlineArtists) : '<span class="muted">No artist data</span>'}}</div>
            <div class="tiny-note">${{headlineTags.length ? escapeHtml(headlineTags.join(" • ")) : "No tag data"}}</div>
          </div>

          <div class="section-card">
            <div class="section-label">Top artists</div>
            <div class="chip-row">${{joinChips(node.top_artists || []) || '<span class="muted">No artist data</span>'}}</div>
          </div>

          <div class="section-card">
            <div class="section-label">Top tags</div>
            <div class="chip-row">${{joinChips(node.top_tags || []) || '<span class="muted">No tag data</span>'}}</div>
          </div>

          <div class="section-card">
            <div class="section-label">Taste matches</div>
            <div class="tiny-note">Users with similar artists and tags.</div>
            ${{nodeListMarkup(rec.similar, "similar")}}
          </div>

          <div class="section-card">
            <div class="section-label">Strong ties</div>
            <div class="tiny-note">Neighbors with stronger graph connections.</div>
            ${{nodeListMarkup(rec.neighbors, "neighbor")}}
          </div>

          <div class="section-card">
            <div class="section-label">Cross-community bridges</div>
            <div class="tiny-note">Useful nodes for discovering adjacent scenes.</div>
            ${{nodeListMarkup(state.bridgeMode ? rec.bridges : [], "bridge")}}
          </div>
        </div>`;
      els.nodePanel.classList.add("hero-card");
    }}

    function renderCommunityPanel() {{
      const selectedCommunity = state.community === "all" ? null : communityLookup(state.community);
      if (!selectedCommunity) {{
        const ranked = APP.communities.slice().sort((a, b) => (b.size - a.size) || (b.density - a.density));
        const focus = ranked.slice(0, 3);
        els.communityPanel.innerHTML = `
          <div class="detail-head">
            <h3>Community overview</h3>
            <p>All communities are visible. Select one to drill into identity, bridges, and related clusters.</p>
          </div>
          <div class="detail-body">
            <div class="stats-grid">
              <div class="mini-stat"><span>Communities</span><strong>${{APP.communities.length}}</strong></div>
              <div class="mini-stat"><span>Largest</span><strong>${{ranked[0] ? ranked[0].size : 0}}</strong></div>
              <div class="mini-stat"><span>Densest</span><strong>${{ranked[0] ? ranked[0].density.toFixed(3) : "0.000"}}</strong></div>
              <div class="mini-stat"><span>Active filter</span><strong>All</strong></div>
            </div>
            <div class="section-card">
              <div class="section-label">Communities to explore</div>
              <div class="list">
                ${{focus.map(c => `
                  <div class="list-item">
                    <button type="button" data-community="${{escapeHtml(c.id)}}">
                      <div class="title"><span>${{escapeHtml(c.label)}}</span><span class="score">${{c.size}} users</span></div>
                      <div class="muted">density ${{c.density.toFixed(3)}} · avg degree ${{c.avg_degree.toFixed(2)}}</div>
                    </button>
                  </div>
                `).join("")}}
              </div>
            </div>
          </div>`;
        return;
      }}

      const related = selectedCommunity.related_communities || [];
      const topNodes = selectedCommunity.top_nodes || [];
      const bridgeNodes = selectedCommunity.bridge_nodes || [];
      els.communityPanel.innerHTML = `
        <div class="detail-head">
          <h3>${{escapeHtml(selectedCommunity.label)}}</h3>
          <p>${{escapeHtml(selectedCommunity.description || "No description available.")}}</p>
        </div>
        <div class="detail-body">
          <div class="stats-grid">
            <div class="mini-stat"><span>Members</span><strong>${{selectedCommunity.size}}</strong></div>
            <div class="mini-stat"><span>Density</span><strong>${{selectedCommunity.density.toFixed(3)}}</strong></div>
            <div class="mini-stat"><span>Avg degree</span><strong>${{selectedCommunity.avg_degree.toFixed(2)}}</strong></div>
            <div class="mini-stat"><span>Related</span><strong>${{related.length}}</strong></div>
          </div>

          <div class="section-card">
            <div class="section-label">Top artists</div>
            <div class="chip-row">${{joinChips(selectedCommunity.top_artists || []) || '<span class="muted">No artist data</span>'}}</div>
          </div>

          <div class="section-card">
            <div class="section-label">Top tags</div>
            <div class="chip-row">${{joinChips(selectedCommunity.top_tags || []) || '<span class="muted">No tag data</span>'}}</div>
          </div>

          <div class="section-card">
            <div class="section-label">Best entry nodes</div>
            <div class="list">
              ${{topNodes.map(item => `
                <div class="list-item">
                  <button type="button" data-node="${{escapeHtml(item.id)}}">
                    <div class="title"><span>${{escapeHtml(item.id)}}</span><span class="score">${{item.degree}} deg</span></div>
                    <div class="muted">PageRank ${{item.pagerank.toFixed(4)}} · betweenness ${{item.betweenness.toFixed(4)}}</div>
                  </button>
                </div>
              `).join("")}}
            </div>
          </div>

          <div class="section-card">
            <div class="section-label">Bridge nodes</div>
            <div class="list">
              ${{bridgeNodes.length ? bridgeNodes.map(item => `
                <div class="list-item">
                  <button type="button" data-node="${{escapeHtml(item.id)}}">
                    <div class="title"><span>${{escapeHtml(item.id)}}</span><span class="score">${{percent(item.bridge_score)}}</span></div>
                    <div class="muted">${{item.cross_community_neighbors}} external communities · cross fraction ${{percent(item.cross_fraction)}}</div>
                  </button>
                </div>
              `).join("") : '<div class="empty-state">No bridge nodes surfaced for this community.</div>'}}
            </div>
          </div>

          <div class="section-card">
            <div class="section-label">Related communities</div>
            <div class="chip-row">
              ${{related.length ? related.map(item => `<button class="toggle-pill" type="button" data-community="${{escapeHtml(item.id)}}">${{escapeHtml(item.label)}} · ${{percent(item.score)}}</button>`).join("") : '<span class="muted">No overlap detected.</span>'}}
            </div>
          </div>
        </div>`;
    }}

    function renderAllPanels() {{
      if (state.selectedNode) {{
        renderNodePanel(state.selectedNode);
      }} else if (state.community !== "all") {{
        const selectedCommunity = communityLookup(state.community);
        if (selectedCommunity) {{
          renderCommunityPanel();
        }}
      }} else {{
        renderCommunityPanel();
      }}
    }}

    function applyCommunityFilter(communityId, fit = true) {{
      state.community = String(communityId);
      if (state.community === "all") {{
        els.communitySelect.value = "all";
      }} else {{
        els.communitySelect.value = String(communityId);
      }}
      setStatus(state.community === "all" ? "Showing all communities" : `Focused on ${{currentCommunityLabel()}}`);
      renderCommunityList();
      renderAllPanels();
      refreshGraph(fit);
    }}

    function clearSelection() {{
      state.selectedNode = null;
      state.focusMode = false;
      state.searchTerm = "";
      state.searchMatches = new Set();
      els.searchInput.value = "";
      setStatus("Reset view");
      renderSearchResults("");
      renderAllPanels();
      refreshGraph(true);
    }}

    function selectNode(nodeId, fit = true) {{
      const node = nodeMap.get(String(nodeId));
      if (!node) return;
      state.selectedNode = String(nodeId);
      if (state.community !== "all" && String(node.community_id) !== String(state.community)) {{
        state.community = String(node.community_id);
        els.communitySelect.value = state.community;
      }}
      state.focusMode = false;
      els.focusModeToggle.checked = false;
      setStatus(`Selected ${{node.label}}`);
      renderCommunityList();
      renderNodePanel(String(nodeId));
      renderCommunityPanel();
      refreshGraph(fit);
      network.selectNodes([String(nodeId)]);
      network.focus(String(nodeId), {{ animation: {{ duration: 380, easingFunction: "easeInOutCubic" }}, scale: 1.28 }});
    }}

    function selectCommunityFromPanel(communityId) {{
      state.selectedNode = null;
      state.focusMode = false;
      els.focusModeToggle.checked = false;
      applyCommunityFilter(String(communityId), true);
    }}

    function updateCommunityDropdown() {{
      const options = [
        `<option value="all">All communities</option>`,
        ...APP.communities.map(c => `<option value="${{escapeHtml(c.id)}}">${{escapeHtml(c.label)}} (${{c.size}})</option>`)
      ];
      els.communitySelect.innerHTML = options.join("");
      els.communitySelect.value = "all";
    }}

    function updateMetrics() {{
      els.totalNodes.textContent = APP.stats.nodes.toLocaleString();
      els.totalEdges.textContent = APP.stats.edges.toLocaleString();
      els.totalCommunities.textContent = APP.stats.communities.toLocaleString();
    }}

    function installEventHandlers() {{
      els.searchInput.addEventListener("input", (event) => {{
        state.searchTerm = event.target.value;
        renderSearchResults(state.searchTerm);
        setStatus(state.searchTerm.trim() ? `Searching for "${{state.searchTerm.trim()}}"` : "Search cleared");
      }});

      els.searchClearBtn.addEventListener("click", () => {{
        state.searchTerm = "";
        els.searchInput.value = "";
        renderSearchResults("");
        setStatus("Search cleared");
      }});

      els.communitySelect.addEventListener("change", (event) => {{
        const value = event.target.value;
        state.selectedNode = null;
        renderAllPanels();
        applyCommunityFilter(value, true);
      }});

      els.weightSlider.max = "2";
      els.weightSlider.value = String(state.minWeight);
      els.weightValue.textContent = String(state.minWeight);
      els.weightSlider.addEventListener("input", (event) => {{
        state.minWeight = Number(event.target.value);
        els.weightValue.textContent = String(state.minWeight);
        setStatus(`Original edge weight threshold: ${{state.minWeight}}`);
        refreshGraph(false);
      }});

      els.focusModeToggle.addEventListener("change", (event) => {{
        state.focusMode = event.target.checked && !!state.selectedNode;
        if (event.target.checked && !state.selectedNode) {{
          event.target.checked = false;
          state.focusMode = false;
          setStatus("Select a node first to focus its neighborhood");
          return;
        }}
        setStatus(state.focusMode ? "Neighborhood focus enabled" : "Neighborhood focus disabled");
        refreshGraph(true);
      }});

      els.bridgeModeToggle.addEventListener("change", (event) => {{
        state.bridgeMode = event.target.checked;
        renderAllPanels();
        setStatus(state.bridgeMode ? "Bridge recommendations on" : "Bridge recommendations off");
      }});

      els.resetBtn.addEventListener("click", () => {{
        state.community = "all";
        state.selectedNode = null;
        state.searchTerm = "";
        state.minWeight = 1;
        state.focusMode = false;
        state.bridgeMode = true;
        els.searchInput.value = "";
        els.searchCount.textContent = "0";
        els.searchResults.innerHTML = "";
        els.communitySelect.value = "all";
        els.weightSlider.value = "1";
        els.weightValue.textContent = "1";
        els.focusModeToggle.checked = false;
        els.bridgeModeToggle.checked = true;
        state.searchMatches = new Set();
        renderCommunityList();
        renderCommunityPanel();
        setStatus("Reset view");
        refreshGraph(true);
      }});

      els.focusBtn.addEventListener("click", () => {{
        if (!state.selectedNode) {{
          setStatus("Pick a node before focusing");
          return;
        }}
        state.focusMode = !state.focusMode;
        els.focusModeToggle.checked = state.focusMode;
        setStatus(state.focusMode ? "Neighborhood focus enabled" : "Neighborhood focus disabled");
        refreshGraph(true);
        renderAllPanels();
      }});

      els.fitBtn.addEventListener("click", () => {{
        network.fit({{ animation: {{ duration: 420, easingFunction: "easeInOutCubic" }} }});
        setStatus("Graph fitted to view");
      }});

      els.physicsBtn.addEventListener("click", () => {{
        state.physicsOn = !state.physicsOn;
        network.setOptions({{ physics: {{ enabled: state.physicsOn }} }});
        els.physicsBtn.textContent = state.physicsOn ? "Physics on" : "Physics off";
        setStatus(state.physicsOn ? "Physics enabled" : "Physics disabled");
      }});

      document.body.addEventListener("click", (event) => {{
        const nodeButton = event.target.closest("[data-node]");
        if (nodeButton) {{
          const id = nodeButton.getAttribute("data-node");
          selectNode(id, true);
          return;
        }}

        const communityButton = event.target.closest("[data-community]");
        if (communityButton) {{
          const cid = communityButton.getAttribute("data-community");
          state.selectedNode = null;
          els.focusModeToggle.checked = false;
          applyCommunityFilter(cid, true);
          return;
        }}
      }});
    }}

    function renderInitialCommunitySelection() {{
      const densest = APP.communities.slice().sort((a, b) => (b.density - a.density) || (b.size - a.size))[0];
      if (densest) {{
        applyCommunityFilter("all", false);
      }}
    }}

    function initialize() {{
      updateMetrics();
      updateCommunityDropdown();
      renderCommunityList();
      renderSearchResults("");
      renderCommunityPanel();
      refreshGraph(false);
      installEventHandlers();
      renderInitialCommunitySelection();

      network.once("stabilizationIterationsDone", () => {{
        network.fit({{ animation: {{ duration: 260, easingFunction: "easeInOutCubic" }} }});
      }});

      network.on("selectNode", (params) => {{
        if (params.nodes && params.nodes.length) {{
          selectNode(params.nodes[0], true);
        }}
      }});

      network.on("deselectNode", () => {{
        if (state.focusMode && state.selectedNode) return;
      }});

      setStatus("Dashboard ready");
    }}

    initialize();
  </script>
</body>
</html>
"""
    template = template.replace("{{", "{").replace("}}", "}")
    return (
        template.replace("__VIZ_DATA__", to_script_json(data))
    )


def draw_static(G, partition, out_path):
    """Draw a polished static PNG overview of the network."""
    if G.number_of_nodes() == 0:
        fig = plt.figure(figsize=(10, 6))
        plt.text(0.5, 0.5, "No graph data available", ha="center", va="center")
        plt.axis("off")
        plt.savefig(out_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return

    community_ids = sorted(set(partition.values()), key=str)
    if not community_ids:
        community_ids = ["0"]

    palette = color_palette(community_ids)
    color_lookup = {cid: i for i, cid in enumerate(community_ids)}
    cmap = plt.get_cmap("tab20", max(len(community_ids), 1))

    colors = []
    sizes = []
    degree = dict(G.degree())
    max_degree = max(degree.values(), default=1)
    for node in G.nodes():
        cid = partition.get(node, community_ids[0])
        colors.append(cmap(color_lookup.get(cid, 0)))
        sizes.append(70 + 380 * (degree.get(node, 0) / max_degree if max_degree else 0))

    pos = nx.spring_layout(G, seed=42, k=0.45 if G.number_of_nodes() < 220 else 0.20)

    fig, ax = plt.subplots(figsize=(17, 11.5), facecolor="#050816")
    ax.set_facecolor("#050816")
    ax.text(
        0.02,
        0.965,
        "Music Community Network",
        transform=ax.transAxes,
        fontsize=24,
        fontweight="bold",
        color="#e5eefb",
        ha="left",
        va="top",
    )
    ax.text(
        0.02,
        0.93,
        "Static overview with community grouping, node prominence, and social links",
        transform=ax.transAxes,
        fontsize=11,
        color="#97a6c6",
        ha="left",
        va="top",
    )

    nx.draw_networkx_edges(
        G,
        pos,
        ax=ax,
        edge_color="#7c93b8",
        width=0.55,
        alpha=0.22,
    )
    nx.draw_networkx_nodes(
        G,
        pos,
        ax=ax,
        node_color=colors,
        node_size=sizes,
        linewidths=0.8,
        edgecolors="#dbeafe",
        alpha=0.95,
    )

    top_nodes = sorted(degree.items(), key=lambda item: (-item[1], str(item[0])))[:8]
    for node, _ in top_nodes:
        x, y = pos[node]
        ax.text(
            x,
            y,
            str(node),
            fontsize=8.5,
            color="#f8fafc",
            ha="center",
            va="center",
            bbox=dict(
                boxstyle="round,pad=0.22",
                facecolor=(5 / 255, 8 / 255, 22 / 255, 0.78),
                edgecolor=(125 / 255, 211 / 255, 252 / 255, 0.22),
                linewidth=0.7,
            ),
            zorder=5,
        )

    legend_items = []
    for cid in community_ids[:6]:
        legend_items.append(
            Line2D(
                [0],
                [0],
                marker="o",
                linestyle="",
                label=f"Community {cid}",
                markerfacecolor=palette.get(cid, "#7dd3fc"),
                markeredgecolor="#dbeafe",
                markeredgewidth=0.8,
                markersize=9,
            )
        )
    if legend_items:
        legend = ax.legend(
            handles=legend_items,
            loc="lower left",
            bbox_to_anchor=(0.015, 0.02),
            frameon=True,
            facecolor="#0f172a",
            edgecolor="#334155",
            fontsize=9,
            labelcolor="#e5eefb",
            ncol=min(3, len(legend_items)),
        )
        legend.get_frame().set_alpha(0.84)

    ax.text(
        0.985,
        0.035,
        f"Nodes: {G.number_of_nodes()}   Links: {G.number_of_edges()}",
        transform=ax.transAxes,
        fontsize=10,
        color="#cbd5e1",
        ha="right",
        va="bottom",
        bbox=dict(
            boxstyle="round,pad=0.35",
            facecolor=(15 / 255, 23 / 255, 42 / 255, 0.82),
            edgecolor=(148 / 255, 163 / 255, 184 / 255, 0.20),
            linewidth=0.8,
        ),
    )

    ax.axis("off")
    fig.savefig(out_path, dpi=220, bbox_inches="tight", facecolor="#050816")
    plt.close(fig)


def generate_report(payload, out_path):
    """Generate the markdown report summarizing the analysis results."""
    stats = payload["stats"]
    communities = payload["communities"]
    insights = payload["insights"]
    top_hubs = insights.get("top_hubs", [])
    top_bridges = insights.get("top_bridges", [])

    lines = [
        "## Network Overview",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Nodes | {stats['nodes']} |",
        f"| Edges | {stats['edges']} |",
        f"| Communities | {stats['communities']} |",
        f"| Density | {stats['density']:.4f} |",
        f"| Average degree | {stats['avg_degree']:.2f} |",
        f"| Average clustering | {stats['avg_clustering']:.4f} |",
        f"| Largest connected component | {stats['largest_cc']} |",
        "",
        "## Global Insights",
        "",
        f"- Largest community: {insights.get('largest_community', {}).get('label', 'N/A')}",
        f"- Densest community: {insights.get('densest_community', {}).get('label', 'N/A')}",
        f"- Top hub: {insights.get('top_hub', {}).get('id', 'N/A')}",
        f"- Best bridge: {insights.get('top_bridge', {}).get('id', 'N/A')}",
        "",
        "## Community Snapshot",
        "",
        "| Community | Size | Density | Avg degree | Top artists |",
        "| --- | ---: | ---: | ---: | --- |",
    ]

    for community in sorted(communities, key=lambda c: (-c["size"], c["label"])):
        lines.append(
            f"| {community['label']} | {community['size']} | {community['density']:.3f} | "
            f"{community['avg_degree']:.2f} | {', '.join(community.get('top_artists', [])[:4])} |"
        )

    lines.extend(
        [
            "",
            "## Top Hubs",
            "",
            "| Node | Community | Degree | PageRank |",
            "| --- | --- | ---: | ---: |",
        ]
    )
    for item in top_hubs[:10]:
        lines.append(
            f"| {item['id']} | {item['community_label']} | {item['degree']} | {item['pagerank']:.4f} |"
        )

    lines.extend(
        [
            "",
            "## Bridge Nodes",
            "",
            "| Node | Community | Bridge score | External communities |",
            "| --- | --- | ---: | ---: |",
        ]
    )
    for item in top_bridges[:10]:
        lines.append(
            f"| {item['id']} | {item['community_label']} | {item['bridge_score']:.4f} | {item['cross_community_neighbors']} |"
        )

    lines.extend(
        [
            "",
            "## Visualization Outputs",
            "",
            "- `network_viz.html` interactive dashboard",
            "- `network_viz.png` static overview",
            "",
            "*Report auto-generated by Skill E.*",
        ]
    )

    Path(out_path).write_text("\n".join(lines), encoding="utf-8")


def markdown_table_to_html(lines):
    """Convert a markdown table block into HTML table markup."""
    if len(lines) < 2:
        return ""
    headers = [cell.strip() for cell in lines[0].strip("|").split("|")]
    body_lines = lines[2:]
    rows = []
    for line in body_lines:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != len(headers):
            continue
        rows.append(cells)

    thead = "".join(f"<th>{html_lib.escape(cell)}</th>" for cell in headers)
    tbody_rows = []
    for row in rows:
        tbody_rows.append(
            "<tr>" + "".join(f"<td>{html_lib.escape(cell)}</td>" for cell in row) + "</tr>"
        )
    return f"<table><thead><tr>{thead}</tr></thead><tbody>{''.join(tbody_rows)}</tbody></table>"


def markdown_to_html(markdown_text: str, skip_first_h1: bool = False) -> str:
    """Convert a small subset of markdown syntax into styled HTML."""
    lines = markdown_text.splitlines()
    parts = []
    i = 0
    skipped_h1 = False
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue

        if stripped.startswith("# "):
            if skip_first_h1 and not skipped_h1:
                skipped_h1 = True
                i += 1
                continue
            parts.append(f"<h1>{html_lib.escape(stripped[2:].strip())}</h1>")
            i += 1
            continue
        if stripped.startswith("## "):
            parts.append(f"<h2>{html_lib.escape(stripped[3:].strip())}</h2>")
            i += 1
            continue
        if stripped.startswith("*") and stripped.endswith("*") and len(stripped) > 2:
            parts.append(f"<p class=\"note\">{html_lib.escape(stripped[1:-1].strip())}</p>")
            i += 1
            continue
        if stripped.startswith("|") and i + 1 < len(lines) and lines[i + 1].strip().startswith("| ---"):
            table_lines = [lines[i], lines[i + 1]]
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i])
                i += 1
            parts.append(markdown_table_to_html(table_lines))
            continue
        if stripped.startswith("- "):
            items = []
            while i < len(lines) and lines[i].strip().startswith("- "):
                items.append(lines[i].strip()[2:].strip())
                i += 1
            parts.append(
                "<ul>" + "".join(f"<li>{html_lib.escape(item)}</li>" for item in items) + "</ul>"
            )
            continue
        if stripped.startswith("**") and stripped.endswith("**") and stripped.count("**") == 2:
            parts.append(f"<p><strong>{html_lib.escape(stripped[2:-2].strip())}</strong></p>")
            i += 1
            continue

        paragraph_lines = [stripped]
        i += 1
        while i < len(lines) and lines[i].strip() and not lines[i].strip().startswith(("#", "##", "- ", "|", "*")):
            paragraph_lines.append(lines[i].strip())
            i += 1
        paragraph = " ".join(paragraph_lines)
        paragraph = html_lib.escape(paragraph).replace("&lt;br&gt;", "<br>")
        paragraph = paragraph.replace("**", "")
        parts.append(f"<p>{paragraph}</p>")
    return "\n".join(parts)


def render_report_html(markdown_text: str, payload) -> str:
    """Wrap the markdown report content in a complete HTML page."""
    body = markdown_to_html(markdown_text, skip_first_h1=True)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Music Community Analysis Report</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;700;800&family=Space+Grotesk:wght@500;700&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #050816;
      --panel: rgba(10, 15, 30, 0.84);
      --stroke: rgba(148, 163, 184, 0.18);
      --text: #e5eefb;
      --muted: #97a6c6;
      --accent: #7dd3fc;
      --accent-2: #c084fc;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--text);
      font-family: "Manrope", system-ui, sans-serif;
      background:
        radial-gradient(circle at 14% 18%, rgba(125, 211, 252, 0.16), transparent 28%),
        radial-gradient(circle at 84% 12%, rgba(192, 132, 252, 0.15), transparent 26%),
        linear-gradient(180deg, #050816 0%, #070b18 50%, #02040b 100%);
    }}
    .page {{
      max-width: 1120px;
      margin: 0 auto;
      padding: 28px 18px 40px;
    }}
    .hero {{
      padding: 24px 26px;
      border: 1px solid var(--stroke);
      border-radius: 26px;
      background: linear-gradient(135deg, rgba(12,16,31,0.92), rgba(11,16,30,0.72));
      box-shadow: 0 24px 80px rgba(2, 6, 23, 0.42);
      margin-bottom: 18px;
    }}
    h1 {{
      margin: 0;
      font-family: "Space Grotesk", sans-serif;
      font-size: clamp(28px, 4vw, 42px);
      line-height: 1.04;
      background: linear-gradient(92deg, #8fe9ff 0%, #7dd3fc 22%, #c084fc 58%, #f9a8d4 100%);
      -webkit-background-clip: text;
      background-clip: text;
      color: transparent;
    }}
    .subtitle {{
      margin-top: 12px;
      color: var(--muted);
      font-size: 15px;
    }}
    .shell {{
      border: 1px solid var(--stroke);
      border-radius: 24px;
      background: var(--panel);
      box-shadow: 0 24px 80px rgba(2, 6, 23, 0.36);
      padding: 24px 26px 28px;
      backdrop-filter: blur(18px);
    }}
    h2 {{
      margin: 28px 0 12px;
      font-family: "Space Grotesk", sans-serif;
      font-size: 22px;
    }}
    p, li {{
      color: #dbe7fb;
      line-height: 1.7;
      font-size: 15px;
    }}
    ul {{
      margin: 8px 0 18px;
      padding-left: 22px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin: 14px 0 22px;
      overflow: hidden;
      border-radius: 16px;
      border: 1px solid rgba(148, 163, 184, 0.16);
      background: rgba(15, 23, 42, 0.62);
    }}
    thead {{
      background: rgba(125, 211, 252, 0.10);
    }}
    th, td {{
      padding: 12px 14px;
      text-align: left;
      border-bottom: 1px solid rgba(148, 163, 184, 0.10);
      font-size: 14px;
    }}
    th {{
      color: #bfe9ff;
      font-weight: 800;
      letter-spacing: 0.03em;
    }}
    td {{
      color: #e8eefb;
    }}
    tr:last-child td {{
      border-bottom: none;
    }}
    .note {{
      color: var(--muted);
      font-size: 13px;
      margin-top: 20px;
    }}
    a {{
      color: #9fe6ff;
    }}
  </style>
</head>
<body>
  <div class="page">
    <section class="hero">
      <h1>Music Community Analysis Report</h1>
      <div class="subtitle">Network overview, community structure, and bridge analysis</div>
    </section>
    <section class="shell">
      {body}
    </section>
  </div>
</body>
</html>
"""


def build_payload(G, clustered_nodes, community_profiles, query):
    """Assemble all computed data into the final visualization payload."""
    partition = build_partition(clustered_nodes)
    profiles = build_profile_lookup(community_profiles)
    degree, closeness, pagerank, clustering, betweenness = compute_centrality_metrics(G)

    node_records = {}
    artists_by_node = {}
    tags_by_node = {}
    community_by_node = {}
    bridge_scores = {}
    cross_neighbor_counts = {}
    cross_fraction_by_node = {}

    for node, data in G.nodes(data=True):
        community_by_node[node] = community_key(partition.get(node, "-1"))
        artists_by_node[node] = clean_list(data.get("top_artists"))
        tags_by_node[node] = clean_list(data.get("top_tags"))

    degree_norm = normalized_map({node: float(value) for node, value in degree.items()})
    betweenness_norm = normalized_map({node: float(value) for node, value in betweenness.items()})
    closeness_norm = normalized_map({node: float(value) for node, value in closeness.items()})
    pagerank_norm = normalized_map({node: float(value) for node, value in pagerank.items()})

    node_importance = {}
    max_degree = max(degree.values(), default=1)
    for node in G.nodes():
        node_importance[node] = (
            0.35 * degree_norm.get(node, 0.0)
            + 0.25 * pagerank_norm.get(node, 0.0)
            + 0.20 * betweenness_norm.get(node, 0.0)
            + 0.20 * closeness_norm.get(node, 0.0)
        )

    for node in G.nodes():
        node_comm = community_by_node.get(node, "-1")
        deg = degree.get(node, 0)
        external_neighbor_communities = {
            community_key(partition.get(neighbor, "-1"))
            for neighbor in G.neighbors(node)
            if community_key(partition.get(neighbor, "-1")) != node_comm
        }
        if deg:
            cross_edges = sum(
                1
                for neighbor in G.neighbors(node)
                if community_key(partition.get(neighbor, "-1")) != node_comm
            )
            cross_fraction = cross_edges / deg
        else:
            cross_fraction = 0.0
        cross_neighbor_counts[node] = len(external_neighbor_communities)
        cross_fraction_by_node[node] = cross_fraction
        bridge_scores[node] = (
            0.55 * betweenness_norm.get(node, 0.0)
            + 0.25 * cross_fraction
            + 0.20 * degree_norm.get(node, 0.0)
        )

    palette = color_palette(set(community_by_node.values()))

    communities, community_map = build_community_models(
        G,
        partition,
        profiles,
        artists_by_node,
        tags_by_node,
        degree,
        betweenness,
        closeness,
        pagerank,
        clustering,
    )
    community_map = link_related_communities(communities)

    node_list = list(G.nodes())
    recommendations = build_recommendations(
        G,
        node_list,
        partition,
        artists_by_node,
        tags_by_node,
        community_by_node,
        degree_norm,
        betweenness_norm,
    )

    node_records_list, node_lookup = build_node_records(
        G,
        partition,
        profiles,
        palette,
        degree,
        closeness,
        pagerank,
        clustering,
        betweenness,
        node_importance,
        bridge_scores,
        community_map,
        artists_by_node,
        tags_by_node,
    )

    # Fill recommendation community labels now that community_map exists.
    for node_id, rec in recommendations.items():
        for bucket in ("similar", "bridges", "neighbors"):
            for item in rec[bucket]:
                item["community_label"] = community_map.get(item["community_id"], {}).get("label", f"Community {item['community_id']}")
        if node_id in node_lookup:
            node_lookup[node_id]["recommendations"] = rec

    for node in node_records_list:
        node["recommendations"] = recommendations.get(node["id"], {"similar": [], "bridges": [], "neighbors": []})
        node["cross_community_neighbors"] = cross_neighbor_counts.get(node["id"], 0)
        node["cross_fraction"] = round(cross_fraction_by_node.get(node["id"], 0.0), 6)

    # Rebuild community metadata with normalized related communities and preferred colors.
    sorted_ids = sorted(community_map.keys(), key=lambda x: str(x))
    for idx, cid in enumerate(sorted_ids):
        community = community_map[cid]
        community["color"] = palette.get(cid, "#7dd3fc")
        community["secondary_color"] = palette.get(sorted_ids[(idx + 1) % len(sorted_ids)], "#c084fc") if sorted_ids else "#c084fc"

    if communities:
        largest = max(communities, key=lambda c: c["size"])
        densest = max(communities, key=lambda c: c["density"])
    else:
        largest = {"label": "N/A"}
        densest = {"label": "N/A"}

    if node_records_list:
        top_hub = max(node_records_list, key=lambda n: (n["degree"], n["pagerank"]))
        top_bridge = max(node_records_list, key=lambda n: (n["bridge_score"], n["betweenness"]))
    else:
        top_hub = {}
        top_bridge = {}

    max_weight = max((safe_float(edge_data.get("weight", 1), 1.0) for _, _, edge_data in G.edges(data=True)), default=1.0)
    edges = build_edge_records(G, partition)

    for community in communities:
        related = []
        for rel in community.get("related_communities", []):
            related.append(rel)
        community["related_communities"] = related

    # Extend community nodes with bridge/taste recommendations.
    for community in communities:
        comm_id = community["id"]
        members = [node for node, cid in partition.items() if cid == comm_id]
        community["sample_members"] = sorted(members)[:8]

    payload = {
        "query": clean_text(query),
        "stats": {
            **graph_stats(G),
            "communities": len(communities),
        },
        "insights": {
            "top_hub": {
                "id": top_hub.get("id", "N/A"),
                "community_label": top_hub.get("community_label", "N/A"),
                "degree": top_hub.get("degree", 0),
                "pagerank": top_hub.get("pagerank", 0.0),
            },
            "top_bridge": {
                "id": top_bridge.get("id", "N/A"),
                "community_label": top_bridge.get("community_label", "N/A"),
                "bridge_score": top_bridge.get("bridge_score", 0.0),
                "cross_community_neighbors": top_bridge.get("cross_community_neighbors", 0),
            },
            "largest_community": largest,
            "densest_community": densest,
            "top_hubs": sorted(node_records_list, key=lambda n: (-n["degree"], -n["pagerank"], n["id"]))[:15],
            "top_bridges": sorted(node_records_list, key=lambda n: (-n["bridge_score"], -n["betweenness"], n["id"]))[:15],
        },
        "communities": sorted(
            [
                {
                    **community,
                    "related_communities": sorted(
                        community.get("related_communities", []),
                        key=lambda x: (-x["score"], str(x["id"])),
                    ),
                }
                for community in communities
            ],
            key=lambda c: (-c["size"], c["label"]),
        ),
        "nodes": sorted(node_records_list, key=lambda n: (n["community_id"], -n["value"], n["label"])),
        "edges": edges,
        "recommendations": recommendations,
        "edge_weight_max": max_weight,
    }
    return payload


def main():
    """Parse CLI inputs and generate all Skill E output files."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", required=True)
    parser.add_argument("--clustered_nodes", required=True)
    parser.add_argument("--community_profiles", required=True)
    parser.add_argument("--query", default="")
    parser.add_argument("--out_dir", required=True)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    G = nx.read_gml(args.graph)
    clustered_nodes = load_json(args.clustered_nodes)
    community_profiles = load_json(args.community_profiles)

    payload = build_payload(G, clustered_nodes, community_profiles, args.query)

    png_path = out_dir / "network_viz.png"
    html_path = out_dir / "network_viz.html"
    report_path = out_dir / "final_report.md"
    report_html_path = out_dir / "final_report.html"

    partition = build_partition(clustered_nodes)
    draw_static(G, partition, png_path)
    html_path.write_text(build_dashboard_html(payload), encoding="utf-8")
    generate_report(payload, report_path)
    report_markdown = report_path.read_text(encoding="utf-8")
    report_html_path.write_text(render_report_html(report_markdown, payload), encoding="utf-8")

    print(f"Static graph saved: {png_path}")
    print(f"Interactive graph saved: {html_path}")
    print(f"Report saved: {report_path}")
    print(f"Rendered report saved: {report_html_path}")


if __name__ == "__main__":
    main()
