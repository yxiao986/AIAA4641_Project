---
name: community-detector
description: "Detect communities in a social network using Louvain/Girvan-Newman. Use when user says 'detect communities', 'run clustering', or 'find subgroups'."
author: yxiao986
version: 0.1.0
tags:
  - graph
  - community-detection
  - clustering
  - python
metadata:
  openclaw:
    requires:
      bins:
        - python3
---

# Community Detector Skill

You are helping the user detect communities and subgroups within a music listener social network.

## When to trigger

Activate when the user says "detect communities", "run louvain", "find subgroups", or when the Agent orchestrator reaches the clustering stage (Stage 3).

## Workflow

### Step 1: Gather input

Check if the input graph file exists at `shared_data/network.gml`. If it does not exist, halt and inform the user.

### Step 2: Execute

Run the clustering Python script. Execute the following command:
`python3 main.py --graph shared_data/network.gml --algorithm louvain --out_file shared_data/clustered_nodes.json`
*(Note: Use `--algorithm girvan_newman` if the user specifically requests it).*

### Step 3: Present results

Read the terminal output to find the number of detected communities and the modularity score. Present these quantitative results to the user and confirm that `shared_data/clustered_nodes.json` has been successfully generated.

## Error handling

- If `shared_data/network.gml` is missing, instruct the user to run the Data Scraper and Graph Linker skills first.
- If the execution fails due to missing packages, tell the user to run `pip install networkx python-louvain`.
- If the graph is too large and Girvan-Newman is taking too long, suggest switching to the `louvain` algorithm for better performance.