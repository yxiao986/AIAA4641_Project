---
name: community-visualization
description: "Build an interactive music community network dashboard with reports and static visual outputs. Use when the user says 'visualize the network', 'generate the music dashboard', or 'create the community report'."
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
      env: []
      bins:
        - python
    primaryEnv: ""
---

# Music Community Explorer

You are helping the user turn music community graph data into an interactive dashboard, a static network PNG, and a rendered analysis report.

## When to trigger

Activate when the user asks to visualize the music network, generate an interactive HTML graph, beautify the dashboard, or export a report from community data.

## Workflow

### Step 1: Gather input

Load the graph, clustered node assignments, community profiles, and the requested output directory.

### Step 2: Execute

Compute network statistics, build node and edge records, generate the interactive HTML dashboard, draw the static PNG, and render the markdown report as HTML.

### Step 3: Present results

Write `network_viz.html`, `network_viz.png`, and `final_report.html`, then summarize where each output was saved.

## Error handling

- If any required input file is missing, stop and report the exact missing path.
- If graph parsing or rendering fails, surface the specific stage that failed.
- If HTML, PNG, or report output cannot be written, report the destination path and the error message.
