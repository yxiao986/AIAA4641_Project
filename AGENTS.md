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
## When to Use / Trigger Keywords

The Agent accepts natural-language user queries and maps them to a high-level analysis task.  
The trigger keywords below are only suggestions. Users do not need to type exact commands.

Detailed Skill-level execution logic is documented separately in each Skill's own `SKILL.md`.  
This README only explains when the Agent should choose each high-level task.

If a downstream task depends on files that do not exist yet, the Agent may automatically run the required previous steps first.  
For example, if the user asks for community profiling but the clustered community file has not been generated yet, the Agent should first prepare the required graph and community detection outputs.

However, `visualize_existing` is different: it is designed to reuse existing results only. If required files are missing, the Agent should report the missing files rather than rerun the full pipeline.

---

### Supported Agent Tasks

| Agent Task | When to Use | Example User Queries / Trigger Keywords |
|---|---|---|
| `community_analysis` | Use this when the user wants to detect, inspect, or understand the community structure of a music/social network. This is the normal single-analysis mode. | `analyze communities`, `detect communities`, `show community structure`, `analyze the indie rock community`, `analyze users around Radiohead`, `community analysis`, `社区分析`, `社区结构`, `分析音乐社区` |
| `algorithm_comparison` | Use this when the user wants to compare different community detection methods or generate two sets of community results. | `compare algorithms`, `compare Louvain and Girvan-Newman`, `two methods`, `two results`, `algorithm comparison`, `generate two community results`, `对比算法`, `比较 Louvain 和 Girvan-Newman`, `生成两种结果` |
| `full_analysis` | Use this when the user wants a complete end-to-end analysis, including graph construction, community detection, comparison, influence ranking, profiling, and visualization/report outputs. | `full analysis`, `complete analysis`, `comprehensive analysis`, `end-to-end analysis`, `run everything`, `all results`, `完整分析`, `全面分析`, `完整流程`, `全部跑一遍` |
| `influence_ranking` | Use this when the user wants to find important, central, influential, or bridge users in the network. | `top influencers`, `influence ranking`, `most influential users`, `central users`, `key users`, `important users`, `hub users`, `bridge users`, `核心用户`, `关键用户`, `最有影响力的用户` |
| `visualize_existing` | Use this when the user only wants to visualize or report on existing outputs without rerunning earlier analysis steps. | `visualize existing`, `only visualize`, `reuse existing results`, `regenerate dashboard`, `show existing results`, `只可视化已有结果`, `复用已有文件`, `重新生成图表` |

---

### Task Selection Notes

The Agent should choose the task based on the user's intent rather than only matching exact keywords.

For example:

```text
User query:
"Find the most important users in this music network."

Selected task:
influence_ranking

User query:
"Generate two community detection results and compare them."

Selected task:
algorithm_comparison

User query:
"Give me a full report with community structure, profiles, influencers, and visualizations."

Selected task:
full_analysis

User query:
"I already have the result files. Just regenerate the visualization."

Selected task:
visualize_existing
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
