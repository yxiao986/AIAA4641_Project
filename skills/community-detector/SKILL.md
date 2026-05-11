---
name: community-detector
description: "Detect communities using Louvain/Girvan-Newman and calculate PageRank. Supports single-algorithm execution or dual-algorithm comparison."
author: yxiao986
version: 0.3.0
tags:
  - graph
  - community-detection
  - clustering
  - pagerank
  - algorithm-comparison
---

# Community Detector Skill

You are responsible for graph analysis, including community discovery and influence ranking.

## When to trigger

1. **Standard Detection**: User asks to "find communities" or "cluster the network".
2. **Influence Analysis**: User asks "who are the influencers" or "run PageRank".
3. **Comparison**: User asks to "compare algorithms", "show differences between Louvain and GN", or "run both clustering methods".

## Workflow

### Step 1: Input Validation
Ensure `shared_data/network.gml` exists.

### Step 2: Execution Logic (CRITICAL)

- **Scenario A (Standard)**: If the user just wants clustering, run:
  `python3 main.py --graph shared_data/network.gml --algorithm louvain --out_file shared_data/clustered_nodes.json`

- **Scenario B (Specific)**: If the user specifies Girvan-Newman, run:
  `python3 main.py --graph shared_data/network.gml --algorithm girvan_newman --out_file shared_data/clustered_nodes.json`

- **Scenario C (Comparison)**: If the user wants to COMPARE, run TWO commands:
  1. `python3 main.py --graph shared_data/network.gml --algorithm louvain --out_file shared_data/clustered_nodes_louvain.json`
  2. `python3 main.py --graph shared_data/network.gml --algorithm girvan_newman --out_file shared_data/clustered_nodes_gn.json`

### Step 3: Influence Ranking
Note that `main.py` automatically calculates PageRank and includes `influence_score` in the output JSON, regardless of the clustering algorithm used.

## Output
Inform the user about the Modularity scores for each run and confirm which JSON files were created in `shared_data/`.