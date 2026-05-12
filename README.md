# 🎵 Music Community Analysis Agent

An end-to-end social network analysis agent that mines Last.fm listener data, constructs a social graph, detects music fan communities, and generates LLM-powered semantic profiles — all from a single natural-language command.

> **Group:** yxiao986, herry-sketch, ZuriZHAO, yyu704, ywu044

---

## Overview


By reading the `AGENTS.md` and individual `SKILL.md` manifests, the AI automatically understands the user's intent and selectively executes the necessary Python skills.

```text
🗣️ User Natural Language Query ("Compare Jazz community clustering...")
    │
    ▼
🤖 AI Assistant (Workbuddy / OpenClaw) reads AGENTS.md & SKILL.md
    │
    ├── 🔍 Intention 1: Needs Data  ─► Skill A (data-scraper)
    ├── 🕸️ Intention 2: Build Graph ─► Skill B (community-linker)
    ├── 🧮 Intention 3: Clustering  ─► Skill C (community-detector)
    ├── 🧠 Intention 4: Profiling   ─► Skill D (community-profiler)
    └── 📊 Intention 5: Report      ─► Skill E (community-visualization)
```
---

## Repository Structure

```
Music_Community_Agent/
│
├── AGENTS.md                       # ⭐ Agent Registry Metadata (The "Brain" mapping)
├── requirements.txt                # Python dependencies
├── README.md                       # This file
│
├── shared_data/                    # ⭐ Shared Data Layer (JSON/GML files passed between Skills)
│
└── skills/                         # Implementation Layer
    ├── data-scraper/               # Hybrid BFS scraper (Live API & Offline Dataset)
    ├── community-linker/           # NetworkX graph builder
    ├── community-detector/         # Louvain / Girvan-Newman & PageRank algorithms
    ├── community-profiler/         # LLM-based semantic cultural profiling
    └── community-visualization/    # PyVis / HTML report generation
```

---

## Quick Start

Since this is an AI-Native Agent, you do not run a central Python script. You interact with it via a compatible terminal AI assistant (like Workbuddy) using the StudyClawHub registry.

### Step 1: Environment Setup
Ensure all dependencies are installed:

```Bash
pip install -r requirements.txt
```
### Step 2: Configure API Keys (Terminal Environment)

Our agent requires keys for live data fetching and LLM profiling. Set them in your terminal before waking up the AI assistant:

Mac/Linux:

```Bash
export LASTFM_API_KEY="your_lastfm_key"
export ANTHROPIC_API_KEY="your_claude_key"
```
Windows (PowerShell):

```PowerShell
$env:LASTFM_API_KEY="your_lastfm_key"
(Note: If you lack a Last.fm key, the agent will autonomously decide to use the offline HetRec 2011 dataset).
```
### Step 3: Wake Up the Agent
In your AI terminal assistant, install the agent from the registry (assuming StudyClawHub integration):

```Plaintext
/sch-install music-community-analysis-agent
```
### Step 4: Just Ask!
Now, give it natural language commands. The AI will parse your request and run the specific skills needed:

Full Pipeline: "Analyze the folk community around Bob Dylan."

Compare Algorithms: "Run both Louvain and Girvan-Newman clustering on the current network and compare the modularity."

Find Influencers: "Calculate the PageRank for the existing graph and tell me the top influencers."

Skip Scrape (Re-run): "Generate a new visualization report based on the existing shared_data without re-scraping."

### 5. Run any Skill in isolation

Every Skill is independently executable for development and testing:

```bash
# Skill A — scrape data
python skills/data-scraper/main.py --source hetrec --data_dir data/hetrec2011-lastfm-2k/ --seed_type artist --seed_value "Radiohead" --max_users 50 --out_dir shared_data/

# Skill B — build graph
python skills/community-linker/main.py --users_file shared_data/raw_users.json --interactions_file shared_data/raw_interactions.json --out_graph shared_data/network.gml   

# Skill C — detect communities
python skills/community-detector/main.py --graph shared_data/network.gml --algorithm louvain --out_file shared_data/clustered_nodes.json  

# Skill D — generate semantic profiles
# Make sure to set your API key if using an LLM provider:
$env:ANTHROPIC_API_KEY="your_key_here"          # for Claude
python skills/community-profiler/main.py --clustered_nodes shared_data/clustered_nodes.json --raw_users shared_data/raw_users.json --out_file shared_data/community_profiles.json --provider anthropic          #or: openai, heuristic   
# Heuristic provider example (no API key needed):
python skills/community-profiler/main.py --clustered_nodes shared_data/clustered_nodes.json --raw_users shared_data/raw_users.json --out_file shared_data/community_profiles.json --provider anthropic --model claude-sonnet-4-6   

# Skill E — visualise and report
python skills/community-visualization/main.py --graph shared_data/network.gml --clustered_nodes shared_data/clustered_nodes.json --community_profiles shared_data/community_profiles.json --query "Analyze the indie rock community" --out_dir shared_data/   
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

Reports modularity Q and community size statistics (min, max, average). Outputs `clustered_nodes.json` with a `community_id` field and an `influence_score` field for each node. The influence score is computed using PageRank and is later used by the community profiler to identify core users within each community.

---

### Skill D — Community Profiler (`community-profiler`)
**Author:** ZuriZHAO · **File:** `skills/community-profiler/main.py`

Generates human-readable semantic profiles for each detected community. It aggregates top artists, genre tags, tracks, and the most influential users within each community. If `influence_score` is available in `clustered_nodes.json`, the profiler highlights the highest-influence users in the LLM prompt so that the generated description reflects both musical taste and core community members.   
Three providers are available via `--provider`:

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
scipy>=1.10
openai>=1.0.0
```

