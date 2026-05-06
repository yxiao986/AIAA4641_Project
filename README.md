# 🎵 Music Community Analysis Agent

An end-to-end social network analysis agent that mines Last.fm listener data, constructs a social graph, detects music fan communities, and generates LLM-powered semantic profiles — all from a single natural-language command.

> **Group:** yxiao986, herry-sketch, ZuriZHAO, yyu704, ywu044

---

## Overview

The agent answers queries like:

```
"Analyze the indie rock community around Radiohead"
"Find subgroups in the folk listener network"
```

It does so by coordinating five independent Skills through a shared data layer, following the same pipeline-over-files architecture described in the project guidance.

```
User Query
    │
    ▼
agent.py  (Orchestrator)
    │
    ├─► Skill A · data-scraper             →  raw_users.json + raw_interactions.json
    ├─► Skill B · community-linker         →  network.gml
    ├─► Skill C · community-detector       →  clustered_nodes.json
    ├─► Skill D · community-profiler       →  community_profiles.json
    └─► Skill E · community-visualization  →  network_viz.html + final_report.html
```

---

## Repository Structure

```
Music_Community_Agent/
│
├── agent.py                        # ⭐ Orchestrator — coordinates all five Skills
├── AGENTS.md                       # StudyClawHub agent registry metadata
├── requirements.txt                # Python dependencies
├── README.md                       # This file
│
├── shared_data/                    # ⭐ Shared data layer — all inter-skill communication
│   ├── raw_users.json              # Output of Skill A
│   ├── raw_interactions.json       # Output of Skill A
│   ├── network.gml                 # Output of Skill B
│   ├── clustered_nodes.json        # Output of Skill C
│   ├── community_profiles.json     # Output of Skill D
│   ├── network_viz.html            # Output of Skill E
│   ├── network_viz.png             # Output of Skill E
│   └── final_report.html           # Output of Skill E
│
└── skills/
    ├── __init__.py
    ├── data-scraper/
    │   ├── SKILL.md                # Registry metadata (name: data-scraper)
    │   ├── main.py                 # BFS scraper — HetRec offline or Last.fm API online
    │   └── api_utils.py            # Last.fm REST helpers (online mode)
    ├── community-linker/
    │   ├── SKILL.md                # Registry metadata (name: community-linker)
    │   └── main.py                 # Builds and cleans the NetworkX graph → GML
    ├── community-detector/
    │   ├── SKILL.md                # Registry metadata (name: community-detector)
    │   └── main.py                 # Louvain / Girvan-Newman community detection
    ├── community-profiler/
    │   ├── SKILL.md                # Registry metadata (name: community-profiler)
    │   └── main.py                 # LLM-powered (or heuristic) semantic profiling
    └── community-visualization/
        ├── SKILL.md                # Registry metadata (name: community-visualization)
        └── main.py                 # Interactive HTML dashboard + static PNG + report
```

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Run in offline mode (no API key needed)

Uses the bundled HetRec 2011 Last.fm-2K dataset. Recommended for first runs and testing.

```bash
python agent.py \
  --query "Analyze the folk community" \
  --seed_artist "Bob Dylan" \
  --skip_scrape
```

> `--skip_scrape` reuses existing `shared_data/raw_users.json` if present, or triggers Skill A in offline (`hetrec`) mode.

### 3. Run in online mode (live Last.fm API)

```bash
export LASTFM_API_KEY="your_key_here"

python agent.py \
  --query "Analyze the indie rock community" \
  --seed_artist "Radiohead" \
  --max_users 200 \
  --algorithm louvain
```

### 4. Compare community detection algorithms

```bash
# Louvain (default — fast, high modularity)
python agent.py --query "..." --seed_artist "Radiohead" --algorithm louvain

# Girvan-Newman (slower, coarser partitions)
python agent.py --query "..." --seed_artist "Radiohead" --algorithm girvan_newman
```

### 5. Run any Skill in isolation

Every Skill is independently executable for development and testing:

```bash
# Skill A — scrape data
python skills/data-scraper/main.py \
  --source hetrec --seed_type artist --seed_value "Radiohead" \
  --max_users 200 --out_dir shared_data/

# Skill B — build graph
python skills/community-linker/main.py \
  --users_file shared_data/raw_users.json \
  --interactions_file shared_data/raw_interactions.json \
  --out_graph shared_data/network.gml

# Skill C — detect communities
python skills/community-detector/main.py \
  --graph shared_data/network.gml \
  --algorithm louvain \
  --out_file shared_data/clustered_nodes.json

# Skill D — generate semantic profiles
python skills/community-profiler/main.py \
  --clustered_nodes shared_data/clustered_nodes.json \
  --raw_users shared_data/raw_users.json \
  --out_file shared_data/community_profiles.json \
  --provider anthropic          # or: openai, heuristic

# Skill E — visualise and report
python skills/community-visualization/main.py \
  --graph shared_data/network.gml \
  --clustered_nodes shared_data/clustered_nodes.json \
  --community_profiles shared_data/community_profiles.json \
  --query "Analyze the indie rock community" \
  --out_dir shared_data/
```

---

## Skills

### Skill A — Data Scraper (`data-scraper`)
**Author:** ywu044 · **File:** `skills/data-scraper/main.py`

Collects a music listener social graph via BFS expansion. Supports two interchangeable data sources that produce identical output schemas:

- **Offline (`--source hetrec`)** — reads the local HetRec 2011 Last.fm-2K dataset. No API key required. Supports three seed types: `artist`, `tag`, or `none` (whole-network baseline).
- **Online (`--source api`)** — crawls the live Last.fm REST API starting from a seed username. Note: Last.fm removed reverse-lookup endpoints around 2013, so online mode requires a seed username rather than an artist or tag name.

Outputs `raw_users.json` (user profiles with top artists, tags, and friend lists) and `raw_interactions.json` (friendship and listener edges with weights).

---

### Skill B — Graph Linker (`community-linker`)
**Author:** herry-sketch · **File:** `skills/community-linker/main.py`

Transforms the raw JSON output of Skill A into an analysis-ready social graph. Builds a weighted undirected NetworkX graph, accumulates edge weights for duplicate connections (e.g. a user who appears as both a friend and a listener), removes isolated nodes, and exports to GML format. Prints a statistics summary on completion: node/edge count, density, average degree, number of connected components, largest component size, and average clustering coefficient.

---

### Skill C — Community Detector (`community-detector`)
**Author:** yxiao986 · **File:** `skills/community-detector/main.py`

Partitions the social graph into communities using one of two algorithms, selectable via `--algorithm`:

- **Louvain** — greedy modularity optimisation via `python-louvain`. Runs in O(n log n). Default and recommended for graphs of any practical size.
- **Girvan-Newman** — iterative edge-betweenness removal via NetworkX. Exact but O(m²n); best used on small graphs or for algorithm comparison.

Reports modularity Q and community size statistics (min, max, average). Outputs `clustered_nodes.json` with a `community_id` integer field appended to each node record.

---

### Skill D — Community Profiler (`community-profiler`)
**Author:** ZuriZHAO · **File:** `skills/community-profiler/main.py`

Generates human-readable semantic profiles for each detected community. Aggregates top artists, genre tags, and tracks per community, then calls an LLM to produce a short label and a 2–3 sentence description. Three providers are available via `--provider`:

- `anthropic` — uses Claude (requires `ANTHROPIC_API_KEY`)
- `openai` — uses GPT (requires `OPENAI_API_KEY`)
- `heuristic` — rule-based fallback, no API key needed; safe for local testing

API failures fall back to the heuristic provider automatically so the full pipeline always completes. Use `--max_communities 2` when testing API-based runs to limit cost.

---

### Skill E — Community Visualisation (`community-visualization`)
**Author:** yyu704 · **File:** `skills/community-visualization/main.py`

Produces three output files from the accumulated pipeline results:

- **`network_viz.html`** — interactive network dashboard; nodes are coloured by community and show LLM-generated profile names on hover
- **`network_viz.png`** — static PNG for embedding in reports and presentations
- **`final_report.html`** — rendered analysis report combining network statistics, community profiles, and visualisations

---

## Architecture: Shared Data Layer

Skills communicate exclusively through files in `shared_data/`. No Skill imports code from another Skill. `agent.py` calls each Skill as an independent subprocess, passing only file paths as arguments. This means any Skill can be swapped, updated, or tested without touching the others.

```
raw_users.json          ← written by A, read by B and D
raw_interactions.json   ← written by A, read by B
network.gml             ← written by B, read by C and E
clustered_nodes.json    ← written by C, read by D and E
community_profiles.json ← written by D, read by E
```

---
## Design Philosophy: Code-Driven vs. Prompt-Based Skills

While many agents on StudyClawHub are purely prompt-based (consisting only of markdown files that rely entirely on LLM reasoning), our project utilizes a **code-driven** approach with dedicated Python scripts for each Skill. We chose this architecture for several critical reasons:

- **Algorithmic Precision:** Tasks like graph construction (Skill B) and community detection (Skill C) involve high-density mathematical computations, such as calculating edge-betweenness or optimizing Louvain modularity. LLMs cannot reliably or deterministically execute complex topological math on hundreds of nodes.
- **Performance and Scalability:** Processing large datasets—like the HetRec 2011 dataset or live Last.fm API JSON responses—via LLM context windows is slow, highly token-expensive, and prone to hallucination. Python handles data parsing and graph rendering instantly and accurately.
- **Reproducibility:** Network statistics (density, average degree, clustering coefficients) must be exact. Code execution guarantees consistent, reproducible results every time the pipeline runs.
- **The Best of Both Worlds:** We still leverage LLMs exactly where they excel. After our Python execution engine handles the heavy computational lifting of data collection and graph partitioning, Skill D applies prompt-based LLM calls to generate intuitive, semantic cultural profiles for the mathematically detected communities.
Adding this section directly addresses why your repository has so many .py files and

---
## StudyClawHub Registry

All Skills and the Agent are published on StudyClawHub. Registry metadata lives in each skill's `SKILL.md` and in `AGENTS.md` at the repository root.

| Component | Registry name | Author |
|-----------|--------------|--------|
| Agent | `music-community-analysis-agent` | yxiao986 |
| Skill A | `data-scraper` | ywu044 |
| Skill B | `community-linker` | herry-sketch |
| Skill C | `community-detector` | yxiao986 |
| Skill D | `community-profiler` | ZuriZHAO |
| Skill E | `community-visualization` | yyu704 |

---

## Requirements

```
requests>=2.31
networkx>=3.2
python-louvain>=0.16
matplotlib>=3.8
pyvis>=0.3.2
anthropic>=0.25
openai>=1.0
```

