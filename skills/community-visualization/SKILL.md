---
name: community-visualization
description: "Build an interactive music community dashboard, static PNG, and rendered report from a network graph. Use when the user says 'visualize the network', 'generate the dashboard', or 'create the report'."
author: Yue Yu
version: 1.0.0
tags:
  - visualization
  - dashboard
  - network-analysis
  - report
metadata:
  openclaw:
    requires:
      bins:
        - python
    primaryEnv: ""
---

# Community Visualization

You are helping the user turn music community graph data into an interactive dashboard, a static network PNG, and a rendered analysis report.

## When to trigger

Activate when the user asks to visualize a social graph, explore community structure, build an interactive HTML network, or export a polished report.

## Workflow

### Step 1: Verify inputs

Confirm that the following files exist before running the visualization skill:

- `shared_data/network.gml`
- `shared_data/clustered_nodes.json`
- `shared_data/community_profiles.json`

If any file is missing, stop and tell the user which upstream skill needs to be run first.

### Step 2: Run the Community Visualization

Run the visualization pipeline with the following command:

```bash
python skills\community-visualization\main.py --graph shared_data\network.gml --clustered_nodes shared_data\clustered_nodes.json --community_profiles shared_data\community_profiles.json --query "Analyze the indie rock community" --out_dir shared_data\
```

This command generates the interactive dashboard, static PNG, markdown report, and rendered HTML report.

### Step 3: Present results

Tell the user that the visualization has been generated and report the saved output files. If available, summarize key graph statistics or generated artifacts.

## Output

- `network_viz.html` interactive dashboard
- `network_viz.png` static overview
- `final_report.html` rendered report

## Error handling

- If a required input file is missing, report the exact missing path.
- If graph parsing fails, stop and report the stage that failed.
- If HTML, PNG, or report writing fails, include the destination path and the filesystem error.
