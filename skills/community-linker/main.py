import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

import networkx as nx

FRIEND_WEIGHT = 5
LISTENER_WEIGHT = 2
SHARED_ARTIST_WEIGHT = 1


def _pc_factor(pc1, pc2, max_pc):
    if max_pc <= 0:
        return 1.0
    return (math.log1p(pc1) + math.log1p(pc2)) / (2 * math.log1p(max_pc))


def load_data(users_file, interactions_file, extended_file=None):
    users = json.loads(Path(users_file).read_text())
    interactions = json.loads(Path(interactions_file).read_text())
    extended = None
    if extended_file:
        raw = json.loads(Path(extended_file).read_text())
        if isinstance(raw, dict) and "users" in raw:
            extended = {u["username"]: u for u in raw["users"]}
        else:
            extended = {u["username"]: u for u in raw}
    return users, interactions, extended


def build_graph(users, interactions, extended=None):
    G = nx.Graph()
    ext = extended or {}
    playcounts = {}

    for u in users:
        name = u["username"]
        ex = ext.get(name, {})
        pc = ex.get("total_playcount") or u.get("playcount") or 0
        playcounts[name] = pc
        top_artists = u.get("top_artists", [])[:5]
        top_tags = u.get("top_tags", [])[:5]
        G.add_node(
            name,
            playcount=int(pc),
            top_artists="|".join(str(a) for a in top_artists),
            top_tags="|".join(str(t) for t in top_tags),
            country=str(ex.get("country") or ""),
            registered_year=int(ex.get("registered_year") or 0),
            age=int(ex.get("age") or 0),
            gender=str(ex.get("gender") or ""),
            subscriber=int(bool(ex.get("subscriber") or False)),
            artist_count=int(ex.get("artist_count") or 0),
            loved_tracks_count=int(ex.get("loved_tracks_count") or 0),
            recent_track_count=int(ex.get("recent_track_count") or 0),
        )

    max_pc = max(playcounts.values()) if playcounts else 1
    user_names = set(G.nodes())

    for edge in interactions:
        if edge.get("type") != "friend":
            continue
        src, tgt = edge["source"], edge["target"]
        if src not in user_names or tgt not in user_names:
            continue
        w = FRIEND_WEIGHT * _pc_factor(playcounts.get(src, 0), playcounts.get(tgt, 0), max_pc)
        if G.has_edge(src, tgt):
            G[src][tgt]["weight"] += w
        else:
            G.add_edge(src, tgt, weight=w, etype="friend")

    artist_fans = defaultdict(set)
    for edge in interactions:
        if edge.get("type") == "listener" and edge["source"] in user_names:
            artist_fans[edge["target"]].add(edge["source"])

    shared_count = 0
    for artist, fans in artist_fans.items():
        fans = sorted(fans)
        for i in range(len(fans)):
            for j in range(i + 1, len(fans)):
                u1, u2 = fans[i], fans[j]
                w = SHARED_ARTIST_WEIGHT * _pc_factor(playcounts.get(u1, 0), playcounts.get(u2, 0), max_pc)
                if G.has_edge(u1, u2):
                    G[u1][u2]["weight"] += w
                    if "shared_artist" not in G[u1][u2]["etype"]:
                        G[u1][u2]["etype"] += "|shared_artist"
                else:
                    G.add_edge(u1, u2, weight=w, etype="shared_artist")
                shared_count += 1

    print(f"Added {shared_count} shared-artist edge increments")
    return G


def clean_graph(G):
    G.remove_nodes_from(list(nx.isolates(G)))
    return G


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--users_file", required=True)
    parser.add_argument("--interactions_file", required=True)
    parser.add_argument("--extended_file", default=None)
    parser.add_argument("--output", default="network.gml")
    args = parser.parse_args()

    users, interactions, extended = load_data(
        args.users_file, args.interactions_file, args.extended_file
    )
    G = build_graph(users, interactions, extended)
    G = clean_graph(G)
    cc = nx.average_clustering(G)
    import networkx.algorithms.community as nx_comm
    communities = nx_comm.greedy_modularity_communities(G, weight='weight')
    modularity = nx_comm.modularity(G, communities, weight='weight')
    print(f"Nodes: {G.number_of_nodes()}, Edges: {G.number_of_edges()}")
    print(f"Avg clustering coefficient (unweighted): {cc:.4f}")
    print(f"Modularity: {modularity:.4f}, Communities: {len(communities)}")
    nx.write_gml(G, args.output)
    print(f"Graph written to {args.output}")


if __name__ == "__main__":
    main()
