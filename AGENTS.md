---
name: music-community-analysis-agent
description: "An end-to-end SNA agent that scrapes Last.fm data, builds social graphs, compares fan communities, and generates LLM-powered profiles."
author: yxiao986
version: 0.3.0
tags: [music, social-network-analysis, graph-ml, llm, community-discovery, algorithms]
skills:
  - data-scraper
  - community-linker
  - community-detector
  - community-profiler
  - community-visualization
---

# Music Community Analysis Agent

This project is an Agent specifically designed to analyze Last.fm music listener social networks. It responds to natural language commands, automatically mines listener circles for specific music genres or artists, and generates in-depth profiling reports.

## 1. Core Features
The Agent coordinates five major Skill modules to achieve the following end-to-end pipeline:
* **Hybrid Data Scraping**: Supports Offline mode using the HetRec 2011 dataset and Online mode using the live Last.fm REST API. **Offline** mode can start from an artist or tag, while **Online** mode must start from a known Last.fm username because the public API no longer supports artist-to-user reverse lookup.
* **Network Modeling**: Transforms raw JSON data into a standard GML format social graph.
* **Community Clustering**: Applies Louvain or Girvan-Newman algorithms to partition listeners into communities, and computes a PageRank-based `influence_score` for each node.
* **Influence Ranking**: Automatically calculates PageRank centralities to identify key opinion leaders (KOLs) within each musical subculture.
* **Semantic Profiling**: Uses LLMs (Claude/GPT) when API keys are available, or a heuristic fallback when API calls fail or no key is configured. The profiler also uses `influence_score` to highlight core users in each community.
* **Visual Output**: Generates interactive HTML network graphs.

## 2. When to Use (Trigger Keywords)
This project does not require users to type fixed commands.  
The trigger keywords below are only suggestions. The Agent uses a natural-language planner to infer the user's goal and select the most suitable task and Skill pipeline.

The Agent supports five main task types:

1. `community_analysis`
2. `algorithm_comparison`
3. `full_analysis`
4. `influence_ranking`
5. `visualize_existing`

If the user asks for a downstream Skill but the required input files are not available yet, the Agent will normally run the necessary previous Skills first.  
For example, if the user asks to generate community profiles but there is no `clustered_nodes.json`, the Agent needs to run graph construction and community detection before profiling.

The only exception is `visualize_existing`: this mode is designed to reuse existing files only. If the required existing outputs are missing, the Agent will stop and report which files are missing instead of rerunning the previous pipeline.

---

### Agent Task Triggers

| Agent Task | When to Use | Example Trigger Keywords / Queries | Typical Pipeline |
|---|---|---|---|
| `community_analysis` | Use this when the user wants to analyze the community structure of a music network using one community detection method. This is the default task for normal community analysis. | `analyze communities`, `community structure`, `detect communities`, `analyze the indie rock community`, `analyze users around Radiohead`, `社区分析`, `社区结构`, `分析某个音乐社区` | Skill A → Skill B → Skill C → Skill D, with Skill E only if visualization/report is requested |
| `algorithm_comparison` | Use this when the user wants to compare two community detection algorithms, especially Louvain and Girvan-Newman. | `compare algorithms`, `compare Louvain and Girvan-Newman`, `two methods`, `two results`, `generate two outputs`, `algorithm comparison`, `对比算法`, `比较 Louvain 和 Girvan-Newman`, `生成两种结果`, `两套社区结果` | Skill A → Skill B → Skill C using Louvain + Skill C using Girvan-Newman → comparison metrics; optionally Skill D/E |
| `full_analysis` | Use this when the user wants the complete end-to-end pipeline and all available outputs. | `full analysis`, `complete analysis`, `comprehensive analysis`, `end-to-end analysis`, `run everything`, `all results`, `完整分析`, `全面分析`, `完整流程`, `跑完整`, `全部分析` | Skill A → Skill B → Skill C using both algorithms → algorithm comparison → influence ranking → Skill D → Skill E |
| `influence_ranking` | Use this when the user wants to find important, central, or influential users in the network. | `top influencers`, `influence ranking`, `most influential users`, `central users`, `key users`, `important users`, `hub users`, `bridge users`, `找最有影响力的用户`, `核心用户`, `关键用户` | Skill A → Skill B → Skill C → PageRank-based influence ranking; Skill D/E only if report or visualization is requested |
| `visualize_existing` | Use this when the user only wants to regenerate visualization or reports from existing files, without rerunning scraping, graph construction, clustering, or profiling. | `visualize existing`, `only visualize`, `reuse existing results`, `regenerate dashboard`, `show existing results`, `只可视化已有结果`, `复用已有文件`, `重新生成图表` | Skill E only, using existing `network.gml`, clustered node files, and community profile files |

---

### Skill-Level Trigger Explanation

| Skill | Function | When It Is Triggered | Main Inputs | Main Outputs |
|---|---|---|---|---|
| Skill A — `data-scraper` | Collects or parses user/music interaction data. | Triggered when the Agent needs raw user and interaction data. This happens in most tasks except `visualize_existing`. | `source`, `seed_type`, `seed_value`, `seed_user`, `max_users` | `raw_users.json`, `raw_interactions.json` |
| Skill B — `community-linker` | Builds the social/music network graph. | Triggered when a graph is needed for community detection, influence ranking, comparison, or full analysis. | `raw_users.json`, `raw_interactions.json` | `network.gml` |
| Skill C — `community-detector` | Runs community detection and calculates node-level influence scores. | Triggered when the user asks for community analysis, algorithm comparison, influence ranking, or full analysis. | `network.gml`, selected algorithm | `clustered_nodes.json`, or `clustered_nodes_louvain.json` and `clustered_nodes_girvan_newman.json` in comparison mode |
| Skill D — `community-profiler` | Generates semantic community labels and descriptions. | Triggered when the user asks to describe, label, profile, explain communities, generate a report, or run full analysis. | clustered node file(s), `raw_users.json` | `community_profiles.json`, or `profiles_louvain.json` and `profiles_girvan_newman.json` in comparison mode |
| Skill E — `community-visualization` | Generates visualization and final report outputs. | Triggered when the user asks for visualization, dashboard, graph view, report, explanation, or full analysis. Also used directly in `visualize_existing` mode. | `network.gml`, clustered node file(s), community profile file(s) | `final_report.md`, `final_report.html`, visualization files |

---

### Source Selection Triggers

| Source | When to Use | Trigger Keywords |
|---|---|---|
| `hetrec` | Use the offline HetRec music dataset. This is the default source for artist- or genre-based analysis. | `artist`, `genre`, `tag`, `Radiohead`, `indie rock`, `jazz`, `metal`, `pop`, `hip hop`, `electronic` |
| `api` | Use live Last.fm API mode. This requires a Last.fm API key and a seed user. | `Last.fm`, `lastfm`, `online`, `API`, `user network`, `username`, `around user ...` |

If the query mentions a known music genre such as `indie rock`, `jazz`, `metal`, `pop`, `hip hop`, or `electronic`, the Agent treats it as a tag-based HetRec query.

If the query mentions a specific artist, the Agent treats it as an artist-based HetRec query.

If no seed is provided in offline mode, the Agent uses `Radiohead` as a safe default seed for demo stability.

---

### Algorithm Selection Triggers

| Algorithm | When to Use | Trigger Keywords |
|---|---|---|
| `louvain` | Default algorithm for normal single-method community analysis. | `louvain`, or no specific algorithm mentioned |
| `girvan_newman` | Used when the user explicitly asks for Girvan-Newman. | `girvan`, `girvan-newman`, `edge betweenness` |
| Louvain + Girvan-Newman | Used when the user asks for comparison or multiple results. | `compare`, `comparison`, `two methods`, `two algorithms`, `two results`, `两种方法`, `两个结果`, `对比算法` |

---

### Output Intent Triggers

The Agent does not always generate every possible output.  
It decides whether to run profiling and visualization based on the user's requested output.

| User Intent | Trigger Keywords | Effect |
|---|---|---|
| Community profiling | `profile`, `community profile`, `describe communities`, `label communities`, `semantic`, `社区画像`, `社区描述`, `社区标签` | Runs Skill D |
| Visualization | `visualize`, `visualization`, `dashboard`, `graph view`, `plot`, `chart`, `show me`, `可视化`, `图`, `展示` | Runs Skill E |
| Report generation | `report`, `final report`, `summary report`, `write-up`, `explain`, `analysis report`, `报告`, `总结`, `解释` | Runs Skill D and Skill E |
| Full pipeline | `full analysis`, `complete analysis`, `run everything`, `完整分析`, `全面分析`, `全部分析` | Runs all major stages |

---

### Dependency Rule

The Skills are connected through files in the `shared_data/` directory.

For example:

```text
Skill A produces raw_users.json and raw_interactions.json
Skill B uses those files to produce network.gml
Skill C uses network.gml to produce clustered node files
Skill D uses clustered node files and raw user data to produce community profiles
Skill E uses the graph, clusters, and profiles to produce visual reports
```

## 3. Configuration & API Keys
Because this Agent relies on real-time external data scraping and LLM semantic inference, you need to configure API keys for full functionality.

1.  **Data Collection**: Uses `data-scraper` (Skill A) to gather users and interactions.
2.  **Network Construction**: Uses `community-linker` to transform raw JSON profiles into a GML graph.
3.  **Community Discovery**: Uses `community-detector` to partition the network into distinct sub-communities.
4.  **Semantic Profiling**: Uses `community-profiler` to generate natural language descriptions for each cluster.
5.  **Reporting**: Uses `community-visualization` to produce interactive visualizations and a final Markdown briefing.

**1. Last.fm API Key (Required for Skill A - Online Mode):**
Used to scrape real-time user social networks.
* Mac/Linux: `export LASTFM_API_KEY="your_lastfm_key"`
* Windows (PowerShell): `$env:LASTFM_API_KEY="your_lastfm_key"`

**2. LLM API Key (Required for Skill D - Semantic Profiler):**
Used to generate human-readable cultural profiles for the detected communities. Depending on your configuration in Skill D, export the relevant key:
* Mac/Linux: `export ANTHROPIC_API_KEY="your_claude_key"` (or `OPENAI_API_KEY`)
* Windows (PowerShell): `$env:ANTHROPIC_API_KEY="your_claude_key"`

*(Note: If you do not have a Last.fm API key, you can still run the Agent flawlessly using the offline HetRec dataset.)*


## 4. Architecture
Unlike pure prompt-based agents, this project chooses to retain a complete Python codebase based on the following considerations:
* **Algorithmic Precision**: Community discovery (like Louvain) and graph modeling involve high-density mathematical computations and large-scale node processing, which exceeds the capabilities of pure text prompts.
* **Scalability**: Each Skill is an independently testable tool. This means you can run any single module in isolation to verify data without needing to launch the entire Agent pipeline every time.

## 5. Directory Structure
```text
Music_Community_Agent/
├── AGENTS.md             # This documentation file
├── shared_data/          # Shared Data Layer: Stores JSON and graph files passed between Skills
└── skills/               # Implementation Layer: Contains the specific Python implementations for Skills A-E
```
