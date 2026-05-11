---
name: music-community-analysis-agent
description: "An end-to-end SNA agent that scrapes Last.fm data, builds social graphs, detects fan communities, and generates LLM-powered profiles."
author: yxiao986
version: 0.1.0
tags: [music, social-network-analysis, graph-ml, llm, community-discovery]
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
* **Hybrid Data Scraping**: Supports two interchangeable modes for data collection—**Offline** (using the HetRec 2011 dataset for speed and stability) or **Online** (using live Last.fm REST API for real-time data).
* **Network Modeling**: Transforms raw JSON data into a standard GML format social graph.
* **Community Clustering**: Applies Louvain or Girvan-Newman algorithms to partition listeners into communities.
* **Semantic Profiling**: Uses LLMs (Claude/GPT) to automatically analyze the listening preferences of each community, generating human-readable community descriptions.
* **Visual Output**: Generates interactive HTML network graphs and Markdown analysis reports.

## 2. Workflow Orchestration

The Agent orchestrates 5 modular skills through a shared data layer (`shared_data/`):

1.  **Data Collection**: Uses `lastfm-music-scraper` (Skill A) to gather users and interactions.
2.  **Network Construction**: Uses `community-linker` to transform raw JSON profiles into a GML graph.
3.  **Community Discovery**: Uses `community-detector` to partition the network into distinct sub-communities.
4.  **Semantic Profiling**: Uses `community-profiler` to generate natural language descriptions for each cluster.
5.  **Reporting**: Uses `community-visualization` to produce interactive visualizations and a final Markdown briefing.

## 3. Repository Architecture: A Pipeline Based on "Shared Data"
This Agent adopts a **"Shared Data Layer"** architecture design:
* **Independence**: Each Skill is housed within the `skills/` directory and has an independent `main.py`.
* **Communication Mechanism**: Skills **do not cross-import code**. All information exchange is handled via intermediate files (e.g., `network.gml`, `clustered_nodes.json`) located in the `shared_data/` directory.
* **Orchestration Logic**: `agent.py` in the root directory acts as the "conductor", sequentially invoking each Skill via subprocesses to ensure fully isolated environments.

## 4. Technical Characteristics: Why Do We Have Python Files?
On StudyClawHub, many Agents only consist of an `AGENTS.md` (purely prompt-driven). However, this project chooses to retain a complete Python codebase based on the following considerations:
* **Algorithmic Precision**: Community discovery (like Louvain) and graph modeling involve high-density mathematical computations and large-scale node processing, which exceeds the capabilities of pure text prompts.
* **Code-Driven Agent**: `agent.py` provides a robust execution engine capable of leveraging professional libraries like NetworkX for precise topological analysis, rather than relying solely on LLM logical deduction.
* **Scalability**: Each Skill is an independently testable tool. This means you can run any single module in isolation to verify data without needing to launch the entire Agent pipeline every time.

## 5. Directory Structure
```text
Music_Community_Agent/
├── agent.py              # Core Orchestration: Handles logic routing and scheduling
├── AGENTS.md             # This documentation file
├── shared_data/          # Shared Data Layer: Stores JSON and graph files passed between Skills
└── skills/               # Implementation Layer: Contains the specific Python implementations for Skills A-E
```

## 6. Quick Start
By default, the Agent can run in Offline Mode without an API key using pre-loaded datasets:
`python agent.py --source hetrec --query "Analyze the indie rock community" --seed_artist "Radiohead"`

For Online Mode (Live API), set your key and run:
`python agent.py --source api --query "Analyze the listener network around RJ" --seed_user "RJ"`