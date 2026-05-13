"""
Skill C — Community Detector
=============================
Partitions the social graph into communities using Louvain or Girvan-Newman.
And calculates the influence score (PageRank) for each node.

Input:  shared_data/network.gml (from Skill B)
Output: shared_data/clustered_nodes.json

CLI interface:
    python skills/skill_c_cluster/main.py \
      --graph shared_data/network.gml \
      --algorithm louvain \
      --out_file shared_data/clustered_nodes.json
"""

import argparse
import json
from pathlib import Path
from datetime import datetime

import networkx as nx

# Community detection imports
try:
    from community import best_partition  # pip install python-louvain
    HAS_LOUVAIN = True
except ImportError:
    HAS_LOUVAIN = False

from networkx.algorithms.community import girvan_newman
from networkx.algorithms.community.quality import modularity


# ── Utilities ────────────────────────────────────────────────────────────────

def log(msg: str):
    """Print timestamped log message."""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def detect_louvain(G: nx.Graph) -> dict:
    """
    Detect communities using Louvain algorithm.
    Returns: {node_id: community_id}
    """
    if not HAS_LOUVAIN:
        raise ImportError("python-louvain not installed. Install with: pip install python-louvain")
    
    log("  Running Louvain algorithm...")
    partition = best_partition(G, weight="weight")
    return partition


def detect_girvan_newman(G: nx.Graph, k: int = 5) -> dict:
    """
    Detect communities using Girvan-Newman algorithm.
    Returns top k communities as {node_id: community_id}
    
    Args:
        G: NetworkX graph
        k: Target number of communities (algorithm stops when >= k communities found)
    
    Returns:
        Dictionary mapping node → community_id
    """
    log(f"  Running Girvan-Newman algorithm (target {k} communities)...")
    
    # girvan_newman is a generator that yields communities at each step
    # We take the first partition with >= k communities
    comp_gen = girvan_newman(G)
    communities = None
    
    for i, communities in enumerate(comp_gen):
        if len(communities) >= k:
            log(f"    Found {len(communities)} communities after {i} iterations")
            break
    
    if communities is None:
        log(f"    Could not reach {k} communities, using final partition")
        communities = [set(G.nodes())]  # fallback: single community
    
    # Convert generator of sets to {node: community_id}
    partition = {}
    for comm_id, comm_nodes in enumerate(communities):
        for node in comm_nodes:
            partition[node] = comm_id
    
    return partition


def compute_modularity(G: nx.Graph, partition: dict) -> float:
    """
    Compute modularity score for a partition.
    Higher is better (typically 0.3–0.7 is good, max ~0.95).
    """
    # Group nodes by community
    communities_grouped = {}
    for node, comm_id in partition.items():
        communities_grouped.setdefault(comm_id, set()).add(node)
    
    # Compute modularity
    communities_list = list(communities_grouped.values())
    mod_score = modularity(G, communities_list)
    return mod_score


def main():
    parser = argparse.ArgumentParser(
        description="Community detection on social graph (Skill C)"
    )
    parser.add_argument(
        "--graph", required=True,
        help="Path to input GML graph file (from Skill B)"
    )
    parser.add_argument(
        "--algorithm", default="louvain", choices=["louvain", "girvan_newman"],
        help="Community detection algorithm (default: louvain)"
    )
    parser.add_argument(
        "--out_file", required=True,
        help="Path to output JSON file with clustered nodes"
    )
    args = parser.parse_args()

    # ── Validate inputs ──────────────────────────────────────────────────────
    log(f"Skill C — Community Detector started")
    log(f"Input graph:  {args.graph}")
    log(f"Algorithm:    {args.algorithm}")
    log(f"Output file:  {args.out_file}")
    log("")

    graph_path = Path(args.graph)
    if not graph_path.exists():
        log(f"ERROR: Graph file not found: {graph_path}")
        return 1

    # ── Load graph ───────────────────────────────────────────────────────────
    log(f"Loading graph from {graph_path.name}...")
    try:
        G = nx.read_gml(str(graph_path))
    except Exception as e:
        log(f"ERROR: Failed to load graph: {e}")
        return 1

    n_nodes = G.number_of_nodes()
    n_edges = G.number_of_edges()
    log(f"  Loaded: {n_nodes} nodes, {n_edges} edges")
    
    # Check connectivity
    if nx.is_connected(G):
        log(f"  Graph is connected")
    else:
        n_components = nx.number_connected_components(G)
        largest_cc = max(nx.connected_components(G), key=len)
        log(f"  Graph has {n_components} connected components")
        log(f"     Largest component: {len(largest_cc)} nodes")

    # ── Detect communities ───────────────────────────────────────────────────
    log("")
    log(f"Running community detection...")
    
    try:
        if args.algorithm == "louvain":
            partition = detect_louvain(G)
        else:  # girvan_newman
            partition = detect_girvan_newman(G, k=5)
    except Exception as e:
        log(f"ERROR: Community detection failed: {e}")
        return 1

    n_communities = len(set(partition.values()))
    log(f"  Detected {n_communities} communities")

    # ── Compute quality metrics ──────────────────────────────────────────────
    log("")
    log(f"Computing community quality metrics...")
    
    try:
        mod_score = compute_modularity(G, partition)
        log(f"  Modularity score: {mod_score:.4f}")
        if mod_score < 0.3:
            log(f"     Low modularity — communities may be weak")
        elif mod_score > 0.7:
            log(f"     High modularity — strong community structure")
    except Exception as e:
        log(f"  Could not compute modularity: {e}")
        mod_score = None

    # Community size statistics
    community_sizes = {}
    for node, cid in partition.items():
        community_sizes[cid] = community_sizes.get(cid, 0) + 1

    min_size = min(community_sizes.values()) if community_sizes else 0
    max_size = max(community_sizes.values()) if community_sizes else 0
    avg_size = sum(community_sizes.values()) / len(community_sizes) if community_sizes else 0

    log(f"  Community sizes: min={min_size}, max={max_size}, avg={avg_size:.1f}")

    # ── Compute Influence (PageRank) ─────────────────────────────────────────
    log("")
    log(f"Computing node influence (PageRank)...")
    try:
        # PageRank considers the edge weights by default if 'weight' attribute exists
        pagerank_scores = nx.pagerank(G, weight='weight')
        log(f"  Influence scores computed for {len(pagerank_scores)} nodes")
    except Exception as e:
        log(f"  Could not compute PageRank: {e}")
        pagerank_scores = {}

    # ── Compute Influence (Betweenness) ──────────────────────────────────────
    log(f"Computing betweenness centrality (Bridge users)...")
    try:
        betweenness_scores = nx.betweenness_centrality(G, weight='weight')
        log(f"  Betweenness scores computed for {len(betweenness_scores)} nodes")
    except Exception as e:
        log(f"  Could not compute Betweenness: {e}")
        betweenness_scores = {}

    # ── Build output JSON ────────────────────────────────────────────────────
    log("")
    log(f"Building output JSON...")
    
    result = []
    for node, data in G.nodes(data=True):
        community_id = partition.get(node, -1)
        
        # Parse pipe-delimited strings back to lists (GML format constraint)
        top_artists = data.get("top_artists", "").split("|") if data.get("top_artists") else []
        top_tags = data.get("top_tags", "").split("|") if data.get("top_tags") else []
        
        # Remove empty strings
        top_artists = [a for a in top_artists if a]
        top_tags = [t for t in top_tags if t]

        username = str(data.get("label", node))
        playcount = int(data.get("playcount", 0))
        total_playcount = int(data.get("total_playcount", playcount))
        
        result.append({
            "username": username,
            "community_id": community_id,
            "top_artists": top_artists,
            "top_tags": top_tags,
            "playcount": playcount,
            "country": str(data.get("country", "Unknown")),
            "registered_year": int(data.get("registered_year", 0)),
            "age": int(data.get("age", 0)),
            "gender": str(data.get("gender", "unknown")),
            "subscriber": bool(data.get("subscriber", 0)),
            "artist_count": int(data.get("artist_count", 0)),
            "loved_tracks_count": int(data.get("loved_tracks_count", 0)),
            "recent_track_count": int(data.get("recent_track_count", 0)),
            "total_playcount": total_playcount,
            "influence_score": pagerank_scores.get(node, 0.0),
            "betweenness_score": betweenness_scores.get(node, 0.0)
        })

    log(f"  Prepared {len(result)} nodes with community assignments and influence scores")

    # ── Write output ─────────────────────────────────────────────────────────
    log("")
    log(f"Writing output to {args.out_file}...")
    
    try:
        out_path = Path(args.out_file)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        log(f"  Output saved: {out_path}")
    except Exception as e:
        log(f"ERROR: Failed to write output: {e}")
        return 1

    # ── Summary ──────────────────────────────────────────────────────────────
    log("")
    log("=" * 60)
    log(f"Skill C completed successfully")
    log(f"   Communities detected: {n_communities}")
    if mod_score is not None:
        log(f"   Modularity score:     {mod_score:.4f}")
    log(f"   Influence algorithm:  PageRank")
    log(f"   Output file:          {args.out_file}")
    log("=" * 60)

    return 0


if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)