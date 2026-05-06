import argparse
import json
import networkx as nx
from pathlib import Path


def load_data(users_file: str, interactions_file: str) -> tuple[list, list]:
    with open(users_file, encoding="utf-8") as f:
        users = json.load(f)
    with open(interactions_file, encoding="utf-8") as f:
        interactions = json.load(f)
    return users, interactions


def build_graph(users: list, interactions: list) -> nx.Graph:
    G = nx.Graph()

    # Add user nodes with attributes (GML doesn't support lists, join as strings)
    for u in users:
        G.add_node(
            u["username"],
            playcount=u.get("playcount", 0),
            top_artists="|".join(u.get("top_artists", [])[:5]),
            top_tags="|".join(u.get("top_tags", [])[:5]),
        )

    # Add edges from interactions
    skipped = 0
    for edge in interactions:
        src, tgt = edge["source"], edge["target"]

        if not G.has_node(src):
            continue
        if not G.has_node(tgt):
            skipped += 1
            continue

        weight = edge.get("weight", 1)
        etype = edge.get("type", "friend")
        if G.has_edge(src, tgt):
            G[src][tgt]["weight"] += weight
            # accumulate all observed edge types as a pipe-delimited string
            existing = set(G[src][tgt]["etype"].split("|"))
            existing.add(etype)
            G[src][tgt]["etype"] = "|".join(sorted(existing))
        else:
            G.add_edge(src, tgt, weight=weight, etype=etype)

    if skipped:
        print(f"Warning: skipped {skipped} edges whose target was not in the user list")

    return G


def clean_graph(G: nx.Graph) -> nx.Graph:
    isolates = list(nx.isolates(G))
    G.remove_nodes_from(isolates)
    print(f"Removed {len(isolates)} isolated nodes")
    return G


def print_stats(G: nx.Graph):
    n = G.number_of_nodes()
    e = G.number_of_edges()
    density = nx.density(G)
    avg_degree = sum(d for _, d in G.degree()) / n if n else 0

    # Largest connected component
    components = list(nx.connected_components(G))
    largest_cc = max(components, key=len)
    lcc_ratio = len(largest_cc) / n if n else 0

    print("\n--- Graph Statistics ---")
    print(f"Nodes:                    {n}")
    print(f"Edges:                    {e}")
    print(f"Density:                  {density:.2e}")
    print(f"Average degree:           {avg_degree:.2f}")
    print(f"Connected components:     {len(components)}")
    print(f"Largest CC size:          {len(largest_cc)} ({lcc_ratio:.1%} of nodes)")

    if n <= 10_000:
        avg_clustering = nx.average_clustering(G)
        print(f"Average clustering coef:  {avg_clustering:.4f}")
    else:
        print("Average clustering coef:  skipped (graph too large)")
    print("------------------------\n")


def main():
    parser = argparse.ArgumentParser(description="Skill B — Graph Linker")
    parser.add_argument("--users_file", required=True)
    parser.add_argument("--interactions_file", required=True)
    parser.add_argument("--out_graph", required=True)
    args = parser.parse_args()

    print(f"Loading data from {args.users_file} and {args.interactions_file}...")
    users, interactions = load_data(args.users_file, args.interactions_file)
    print(f"Loaded {len(users)} users, {len(interactions)} interactions")

    print("Building graph...")
    G = build_graph(users, interactions)
    print(f"Raw graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

    print("Cleaning isolated nodes...")
    G = clean_graph(G)

    print_stats(G)

    Path(args.out_graph).parent.mkdir(parents=True, exist_ok=True)
    nx.write_gml(G, args.out_graph)
    print(f"Graph saved to {args.out_graph}")


if __name__ == "__main__":
    main()
