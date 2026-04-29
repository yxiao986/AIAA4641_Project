# 🎵 Music Community Analysis Agent

> A Social Network Analysis final project for Spring 2026.
> Five modular Skills orchestrated by a single Agent to discover and profile music fan communities from Last.fm data.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Repository Structure](#repository-structure)
4. [Quick Start](#quick-start)
5. [Skill Implementation Guides](#skill-implementation-guides)
   - [Skill A — Data Scraper](#skill-a--data-scraper-member-a)
   - [Skill B — Graph Linker](#skill-b--graph-linker-member-b)
   - [Skill C — Community Detector](#skill-c--community-detector-member-c)
   - [Skill D — Semantic Profiler](#skill-d--semantic-profiler-member-d)
   - [Skill E — Visualiser & Reporter](#skill-e--visualiser--reporter-member-e)
6. [Shared Data Contract](#shared-data-contract)
7. [Agent Workflow](#agent-workflow)
8. [Evaluation](#evaluation)
9. [Submission Checklist](#submission-checklist)

---

## Project Overview

This agent answers queries like:

```
"Analyze the indie rock community on Last.fm"
"Find the top influencers in the jazz listener network"
"Show me the community structure around Radiohead fans"
```

It does so by chaining five independent Skills in a pipeline:

```
Last.fm API → [A] Scrape → [B] Build Graph → [C] Cluster → [D] LLM Profile → [E] Visualise + Report
```

All inter-skill communication is done through **files in `shared_data/`** — no Skill imports from another.

---

## Architecture

```
User Query
    │
    ▼
agent.py  (Orchestrator — reads intent, calls Skills in order)
    │
    ├─► skill_a_scraper/main.py   →  shared_data/raw_users.json
    │                                shared_data/raw_interactions.json
    │
    ├─► skill_b_linker/main.py    →  shared_data/network.gml
    │
    ├─► skill_c_cluster/main.py   →  shared_data/clustered_nodes.json
    │
    ├─► skill_d_profiler/main.py  →  shared_data/community_profiles.json
    │
    └─► skill_e_viz/main.py       →  shared_data/network_viz.html
                                     shared_data/final_report.md
```

Each Skill is **independently runnable** and testable. The Agent simply calls them as subprocesses, passing file paths as arguments.

---

## Repository Structure

```
Music_Community_Agent/
├── agent.py                    # ⭐ Agent orchestrator (main entry point)
├── requirements.txt            # All Python dependencies
├── README.md                   # This file
│
├── shared_data/                # ⭐ Shared data layer (git-ignored large files)
│   ├── raw_users.json          # Output of Skill A
│   ├── raw_interactions.json   # Output of Skill A
│   ├── network.gml             # Output of Skill B
│   ├── clustered_nodes.json    # Output of Skill C
│   ├── community_profiles.json # Output of Skill D
│   ├── network_viz.html        # Output of Skill E
│   └── final_report.md         # Output of Skill E
│
└── skills/
    ├── __init__.py
    ├── skill_a_scraper/
    │   ├── main.py
    │   └── api_utils.py
    ├── skill_b_linker/
    │   └── main.py
    ├── skill_c_cluster/
    │   └── main.py
    ├── skill_d_profiler/
    │   └── main.py
    └── skill_e_viz/
        └── main.py
```

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Get a Last.fm API key

Sign up at https://www.last.fm/api/account/create — it's free and instant.

```bash
export LASTFM_API_KEY="your_key_here"
```

### 3. Run the full pipeline

```bash
python agent.py \
  --query "Analyze the indie rock community" \
  --seed_artist "Radiohead" \
  --max_users 200 \
  --algorithm louvain
```

### 4. Run individual Skills (for development / testing)

```bash
# Test Skill A only
python skills/skill_a_scraper/main.py \
  --seed_artist "Radiohead" --max_users 50 \
  --api_key $LASTFM_API_KEY --out_dir shared_data/

# Test Skill B (requires Skill A output)
python skills/skill_b_linker/main.py \
  --users_file shared_data/raw_users.json \
  --interactions_file shared_data/raw_interactions.json \
  --out_graph shared_data/network.gml

# Skip scraping (reuse existing data)
python agent.py --query "..." --seed_artist "..." --skip_scrape
```

---

## Shared Data Contract

> **Rule:** Skills communicate **only** through files in `shared_data/`. Never import from another skill's module.

### `raw_users.json` — written by A, read by B & D

```json
[
  {
    "username": "lastfm_user_123",
    "playcount": 14200,
    "top_artists": ["Radiohead", "Portishead", "Massive Attack"],
    "top_tags": ["alternative", "electronic", "trip-hop"],
    "friends": ["user_456", "user_789"]
  }
]
```

### `raw_interactions.json` — written by A, read by B

```json
[
  { "source": "lastfm_user_123", "target": "user_456", "type": "friend" },
  { "source": "lastfm_user_123", "target": "Radiohead",  "type": "listener", "weight": 142 }
]
```

### `network.gml` — written by B, read by C & E

Standard GML graph file. Use `networkx.write_gml()` to produce it.
Node attributes must include: `id`, `username`, `playcount`.
Edge attributes: `weight` (listen count or friendship strength).

### `clustered_nodes.json` — written by C, read by D & E

```json
[
  {
    "username": "lastfm_user_123",
    "community_id": 2,
    "top_artists": ["Radiohead", "Portishead"],
    "top_tags": ["alternative", "trip-hop"]
  }
]
```

### `community_profiles.json` — written by D, read by E

```json
{
  "0": {
    "label": "Hardcore Punk Purists",
    "description": "Tight-knit community centered around 90s post-hardcore...",
    "top_artists": ["Fugazi", "Minor Threat"],
    "top_tags": ["hardcore", "punk", "post-hardcore"],
    "size": 34
  },
  "2": {
    "label": "Atmospheric Electronica Wanderers",
    "description": "Fans of ambient and trip-hop who often cross into jazz...",
    "top_artists": ["Portishead", "Massive Attack"],
    "top_tags": ["trip-hop", "electronic", "ambient"],
    "size": 51
  }
}
```

---

## Skill Implementation Guides

---

### Skill A — Data Scraper (Member A)

**Goal:** Collect a social graph seed from Last.fm using BFS (breadth-first search) starting from fans of a seed artist.

**Files:** `skills/skill_a_scraper/main.py`, `skills/skill_a_scraper/api_utils.py`

**CLI interface your `main.py` must support:**

```bash
python skills/skill_a_scraper/main.py \
  --seed_artist "Radiohead" \
  --max_users 200 \
  --api_key "YOUR_KEY" \
  --out_dir shared_data/
```

**Implementation steps:**

```python
# api_utils.py — wrap Last.fm REST calls
import requests

BASE = "http://ws.audioscrobbler.com/2.0/"

def get_artist_listeners(artist: str, api_key: str, limit=50) -> list[str]:
    """Return top listener usernames for an artist."""
    r = requests.get(BASE, params={
        "method": "artist.getTopFans", "artist": artist,
        "api_key": api_key, "format": "json", "limit": limit
    })
    return [u["name"] for u in r.json().get("topfans", {}).get("user", [])]

def get_user_friends(username: str, api_key: str) -> list[str]:
    """Return a user's Last.fm friends."""
    r = requests.get(BASE, params={
        "method": "user.getFriends", "user": username,
        "api_key": api_key, "format": "json", "limit": 50
    })
    return [u["name"] for u in r.json().get("friends", {}).get("user", [])]

def get_user_top_artists(username: str, api_key: str) -> list[dict]:
    """Return a user's top artists with playcount."""
    r = requests.get(BASE, params={
        "method": "user.getTopArtists", "user": username,
        "api_key": api_key, "format": "json", "limit": 20, "period": "overall"
    })
    return r.json().get("topartists", {}).get("artist", [])

def get_user_top_tags(username: str, api_key: str) -> list[str]:
    """Return genre tags from user's top artists."""
    # Aggregate tags from top artists
    ...
```

```python
# main.py — BFS expansion
import argparse, json, time
from pathlib import Path
from api_utils import get_artist_listeners, get_user_friends, get_user_top_artists

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed_artist"); parser.add_argument("--max_users", type=int)
    parser.add_argument("--api_key");    parser.add_argument("--out_dir")
    args = parser.parse_args()

    visited, queue = set(), []

    # Seed: get initial users from the seed artist's top fans
    seeds = get_artist_listeners(args.seed_artist, args.api_key)
    queue.extend(seeds)

    users, interactions = [], []

    while queue and len(visited) < args.max_users:
        username = queue.pop(0)
        if username in visited:
            continue
        visited.add(username)

        top_artists = get_user_top_artists(username, args.api_key)
        friends     = get_user_friends(username, args.api_key)

        users.append({
            "username": username,
            "top_artists": [a["name"] for a in top_artists[:10]],
            "playcount": int(top_artists[0].get("playcount", 0)) if top_artists else 0,
            "friends": friends[:20],
            "top_tags": []  # populate via get_user_top_tags if time allows
        })

        for friend in friends[:10]:
            interactions.append({"source": username, "target": friend, "type": "friend"})
            if friend not in visited:
                queue.append(friend)

        time.sleep(0.25)  # respect Last.fm rate limits (5 req/s)
        print(f"  Scraped {len(visited)}/{args.max_users}: {username}")

    out = Path(args.out_dir)
    out.mkdir(exist_ok=True)
    (out / "raw_users.json").write_text(json.dumps(users, indent=2))
    (out / "raw_interactions.json").write_text(json.dumps(interactions, indent=2))
    print(f"Done. {len(users)} users, {len(interactions)} interactions.")

if __name__ == "__main__":
    main()
```

**Key Last.fm API endpoints to use:**
- `artist.getTopFans` — seed users
- `user.getFriends` — social edges
- `user.getTopArtists` — taste profile
- `user.getTopTags` — genre tags

**Rate limit:** 5 requests/second. Add `time.sleep(0.25)` between calls.

**Test it standalone:**
```bash
python skills/skill_a_scraper/main.py \
  --seed_artist "Radiohead" --max_users 30 \
  --api_key $LASTFM_API_KEY --out_dir shared_data/
```

---

### Skill B — Graph Linker (Member B)

**Goal:** Build a clean NetworkX graph from the raw JSON and export it as GML.

**CLI interface:**

```bash
python skills/skill_b_linker/main.py \
  --users_file shared_data/raw_users.json \
  --interactions_file shared_data/raw_interactions.json \
  --out_graph shared_data/network.gml
```

**Implementation:**

```python
import argparse, json
import networkx as nx

def build_graph(users: list, interactions: list) -> nx.Graph:
    G = nx.Graph()

    # Add nodes with attributes
    for u in users:
        G.add_node(u["username"],
                   playcount=u.get("playcount", 0),
                   top_artists="|".join(u.get("top_artists", [])[:5]),  # GML: no lists
                   top_tags="|".join(u.get("top_tags", [])[:5]))

    # Add edges
    for edge in interactions:
        src, tgt = edge["source"], edge["target"]
        if G.has_node(src) and G.has_node(tgt):
            weight = edge.get("weight", 1)
            if G.has_edge(src, tgt):
                G[src][tgt]["weight"] += weight
            else:
                G.add_edge(src, tgt, weight=weight, etype=edge.get("type", "friend"))

    # Remove isolated nodes (no connections)
    isolates = list(nx.isolates(G))
    G.remove_nodes_from(isolates)
    print(f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges "
          f"(removed {len(isolates)} isolates)")
    return G

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--users_file"); parser.add_argument("--interactions_file")
    parser.add_argument("--out_graph")
    args = parser.parse_args()

    users        = json.loads(open(args.users_file).read())
    interactions = json.loads(open(args.interactions_file).read())

    G = build_graph(users, interactions)
    nx.write_gml(G, args.out_graph)
    print(f"Graph saved to {args.out_graph}")

if __name__ == "__main__":
    main()
```

**Tips:**
- GML format does not support Python lists as node attributes — join them as pipe-delimited strings: `"Radiohead|Portishead|Massive Attack"`
- Use `nx.is_connected(G)` to check connectivity; report the largest connected component size
- Compute and print basic stats: average degree, density, clustering coefficient

---

### Skill C — Community Detector (Member C)

**Goal:** Partition the graph into communities using Louvain or Girvan-Newman. Write results with community labels.

**CLI interface:**

```bash
python skills/skill_c_cluster/main.py \
  --graph shared_data/network.gml \
  --algorithm louvain \
  --out_file shared_data/clustered_nodes.json
```

**Implementation:**

```python
import argparse, json
import networkx as nx
from community import best_partition          # pip install python-louvain
# from networkx.algorithms.community import girvan_newman  # built-in alternative

def detect_louvain(G: nx.Graph) -> dict:
    """Returns {node: community_id}"""
    partition = best_partition(G, weight="weight")
    return partition

def detect_girvan_newman(G: nx.Graph, k: int = 5) -> dict:
    """Returns {node: community_id} for first k communities."""
    from networkx.algorithms.community import girvan_newman
    comp = girvan_newman(G)
    for communities in comp:
        if len(communities) >= k:
            break
    return {node: i for i, comm in enumerate(communities) for node in comm}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph"); parser.add_argument("--algorithm", default="louvain")
    parser.add_argument("--out_file")
    args = parser.parse_args()

    G = nx.read_gml(args.graph)

    if args.algorithm == "louvain":
        partition = detect_louvain(G)
    else:
        partition = detect_girvan_newman(G)

    n_communities = len(set(partition.values()))
    print(f"Found {n_communities} communities using {args.algorithm}")

    # Attach community labels back to node attributes
    result = []
    for node, data in G.nodes(data=True):
        result.append({
            "username":     node,
            "community_id": partition.get(node, -1),
            "top_artists":  data.get("top_artists", "").split("|"),
            "top_tags":     data.get("top_tags", "").split("|"),
            "playcount":    data.get("playcount", 0),
        })

    # Print modularity score
    communities_grouped = {}
    for node, cid in partition.items():
        communities_grouped.setdefault(cid, set()).add(node)
    from networkx.algorithms.community.quality import modularity
    mod = modularity(G, list(communities_grouped.values()))
    print(f"Modularity score: {mod:.4f}")

    with open(args.out_file, "w") as f:
        json.dump(result, f, indent=2)
    print(f"Clustered nodes saved to {args.out_file}")

if __name__ == "__main__":
    main()
```

**Key metrics to report:**
- Number of communities detected
- Modularity score (higher = better separation, typically 0.3–0.7 is good)
- Largest and smallest community sizes
- Compare Louvain vs Girvan-Newman results in your individual report

---

### Skill D — Semantic Profiler (Member D)

**Goal:** Use an LLM to give each numeric community a human-readable name and description, based on its members' listening habits.

**CLI interface:**

```bash
python skills/skill_d_profiler/main.py \
  --clustered_nodes shared_data/clustered_nodes.json \
  --raw_users shared_data/raw_users.json \
  --out_file shared_data/community_profiles.json
```

**Implementation:**

```python
import argparse, json, os
from collections import Counter
import anthropic  # pip install anthropic

def aggregate_community(members: list[dict]) -> dict:
    """Aggregate top artists and tags across all members of a community."""
    artist_counter = Counter()
    tag_counter    = Counter()
    for m in members:
        artist_counter.update(m.get("top_artists", []))
        tag_counter.update(m.get("top_tags", []))
    return {
        "top_artists": [a for a, _ in artist_counter.most_common(10)],
        "top_tags":    [t for t, _ in tag_counter.most_common(10)],
        "size":        len(members),
    }

def profile_community_with_llm(community_id: int, agg: dict) -> dict:
    """Call Claude to generate a label and description for a community."""
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

    prompt = f"""You are analyzing a music listener community discovered via social network analysis.

Community data:
- Size: {agg['size']} users
- Top artists: {', '.join(agg['top_artists'])}
- Top genre tags: {', '.join(agg['top_tags'])}

Respond ONLY with a JSON object (no markdown) with these exact keys:
{{
  "label": "<short evocative name, max 5 words>",
  "description": "<2–3 sentences describing this community's musical identity and culture>"
}}"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = message.content[0].text.strip()
    return json.loads(raw)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--clustered_nodes"); parser.add_argument("--raw_users")
    parser.add_argument("--out_file")
    args = parser.parse_args()

    nodes = json.loads(open(args.clustered_nodes).read())

    # Group nodes by community
    communities: dict[int, list] = {}
    for node in nodes:
        cid = node["community_id"]
        communities.setdefault(cid, []).append(node)

    profiles = {}
    for cid, members in sorted(communities.items()):
        print(f"  Profiling community {cid} ({len(members)} members)...")
        agg = aggregate_community(members)
        try:
            llm_result = profile_community_with_llm(cid, agg)
        except Exception as e:
            print(f"  LLM error for community {cid}: {e}")
            llm_result = {"label": f"Community {cid}", "description": "Profile unavailable."}

        profiles[str(cid)] = {**agg, **llm_result}
        print(f"  → {llm_result['label']}")

    with open(args.out_file, "w") as f:
        json.dump(profiles, f, indent=2, ensure_ascii=False)
    print(f"Community profiles saved to {args.out_file}")

if __name__ == "__main__":
    main()
```

**Tips:**
- Set `ANTHROPIC_API_KEY` in your environment
- Test with just 2–3 communities first to conserve API credits
- You can alternatively use OpenAI (`openai` package) — just change the client call
- For your individual report: discuss your prompt engineering choices and how the LLM labels compared to manual inspection

---

### Skill E — Visualiser & Reporter (Member E)

**Goal:** Generate a network visualisation and a complete Markdown analysis report.

**CLI interface:**

```bash
python skills/skill_e_viz/main.py \
  --graph shared_data/network.gml \
  --clustered_nodes shared_data/clustered_nodes.json \
  --community_profiles shared_data/community_profiles.json \
  --query "Analyze the indie rock community" \
  --out_dir shared_data/
```

**Implementation:**

```python
import argparse, json
from pathlib import Path
from collections import Counter
import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

# Optional interactive viz — install with: pip install pyvis
try:
    from pyvis.network import Network
    HAS_PYVIS = True
except ImportError:
    HAS_PYVIS = False

def draw_static(G, partition, out_path):
    """Draw static PNG with matplotlib, nodes coloured by community."""
    cmap = plt.cm.get_cmap("tab20", max(partition.values()) + 1)
    colors = [cmap(partition.get(n, 0)) for n in G.nodes()]
    pos = nx.spring_layout(G, seed=42, k=0.5)

    plt.figure(figsize=(14, 10))
    nx.draw_networkx(G, pos,
        node_color=colors, node_size=40,
        with_labels=False, edge_color="#cccccc", width=0.3, alpha=0.85)
    plt.title("Music Listener Social Network — Community Structure")
    plt.axis("off")
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Static graph saved: {out_path}")

def draw_interactive(G, partition, profiles, out_path):
    """Draw interactive HTML with PyVis."""
    net = Network(height="750px", width="100%", bgcolor="#1a1a2e", font_color="white")
    net.barnes_hut()

    cmap = plt.cm.get_cmap("tab20", max(partition.values()) + 1)
    for node in G.nodes():
        cid  = partition.get(node, 0)
        rgba = cmap(cid)
        hex_color = mcolors.to_hex(rgba)
        label = profiles.get(str(cid), {}).get("label", f"Community {cid}")
        net.add_node(node, label=node, title=f"{node}\n{label}", color=hex_color, size=8)

    for src, tgt, data in G.edges(data=True):
        net.add_edge(src, tgt, width=0.5)

    net.save_graph(str(out_path))
    print(f"Interactive graph saved: {out_path}")

def generate_report(query, profiles, G, partition, out_path):
    """Assemble the Markdown final report."""
    n_nodes = G.number_of_nodes()
    n_edges = G.number_of_edges()
    density = nx.density(G)
    avg_deg = sum(d for _, d in G.degree()) / n_nodes if n_nodes else 0
    n_communities = len(set(partition.values()))

    lines = [
        f"# Music Community Analysis Report",
        f"",
        f"**Query:** {query}  ",
        f"**Generated by:** Music_Community_Agent  ",
        f"",
        f"---",
        f"",
        f"## Network Overview",
        f"",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Nodes (users) | {n_nodes} |",
        f"| Edges (connections) | {n_edges} |",
        f"| Communities detected | {n_communities} |",
        f"| Graph density | {density:.4f} |",
        f"| Average degree | {avg_deg:.2f} |",
        f"",
        f"---",
        f"",
        f"## Community Profiles",
        f"",
    ]

    for cid, profile in sorted(profiles.items(), key=lambda x: -x[1].get("size", 0)):
        lines += [
            f"### 🎵 {profile.get('label', f'Community {cid}')}",
            f"",
            f"- **Size:** {profile.get('size', '?')} members",
            f"- **Top Artists:** {', '.join(profile.get('top_artists', [])[:6])}",
            f"- **Genre Tags:** {', '.join(profile.get('top_tags', [])[:6])}",
            f"",
            f"{profile.get('description', '')}",
            f"",
        ]

    lines += [
        f"---",
        f"",
        f"## Visualisation",
        f"",
        f"See `network_viz.html` (interactive) or `network_viz.png` (static) in `shared_data/`.",
        f"",
        f"---",
        f"",
        f"*Report auto-generated by Music Community Analysis Agent.*",
    ]

    Path(out_path).write_text("\n".join(lines), encoding="utf-8")
    print(f"Report saved: {out_path}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph"); parser.add_argument("--clustered_nodes")
    parser.add_argument("--community_profiles"); parser.add_argument("--query", default="")
    parser.add_argument("--out_dir")
    args = parser.parse_args()

    out = Path(args.out_dir)
    out.mkdir(exist_ok=True)

    G        = nx.read_gml(args.graph)
    nodes    = json.loads(open(args.clustered_nodes).read())
    profiles = json.loads(open(args.community_profiles).read())

    partition = {n["username"]: n["community_id"] for n in nodes}

    # Static PNG
    draw_static(G, partition, out / "network_viz.png")

    # Interactive HTML (if PyVis available)
    if HAS_PYVIS:
        draw_interactive(G, partition, profiles, out / "network_viz.html")

    # Markdown report
    generate_report(args.query, profiles, G, partition, out / "final_report.md")

if __name__ == "__main__":
    main()
```

**Tips:**
- PyVis produces much more impressive interactive HTML graphs — worth installing (`pip install pyvis`)
- Colour-code nodes by community and add hover labels showing the community name
- For your individual report, include the static PNG and discuss what visual patterns you observe

---

## Agent Workflow

Full flow when you run `python agent.py --query "..." --seed_artist "Radiohead"`:

```
1. Agent parses CLI args, verifies API key
2. Creates shared_data/ directory
3. Calls skill_a_scraper → produces raw_users.json + raw_interactions.json
4. Calls skill_b_linker  → produces network.gml
5. Calls skill_c_cluster → produces clustered_nodes.json
6. Calls skill_d_profiler→ produces community_profiles.json
7. Calls skill_e_viz     → produces network_viz.html + final_report.md
8. Prints summary of all output files
```

Each skill is called as a **subprocess**, so they are completely independent — no Python imports cross skill boundaries.

---

## Evaluation

For your group report, evaluate the agent on these metrics:

| Metric | How to measure |
|--------|----------------|
| Modularity | `networkx.algorithms.community.quality.modularity()` |
| Community coherence | Manual inspection: do top artists make sense together? |
| LLM label accuracy | Compare LLM-generated labels to ground-truth genre knowledge |
| Coverage | % of seed users successfully scraped |
| Visualisation clarity | Subjective, include in report |

Run with both `--algorithm louvain` and `--algorithm girvan_newman` and compare results.

---

## Requirements

```
# requirements.txt
requests>=2.31
networkx>=3.2
python-louvain>=0.16
matplotlib>=3.8
pyvis>=0.3.2
anthropic>=0.25
```

---

## Submission Checklist

- [ ] All 5 `skills/skill_*/main.py` files are implemented and individually testable
- [ ] `agent.py` runs end-to-end with a real Last.fm API key
- [ ] `shared_data/final_report.md` is generated correctly
- [ ] Each Skill published to StudyClawHub individually
- [ ] Agent published to StudyClawHub
- [ ] Group Report (4 pages, NeurIPS format) written
- [ ] Individual Reports (3 pages each, NeurIPS format) written
- [ ] Presentation prepared for Week 14

**Deadline: May 15, 2026**
