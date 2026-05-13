---
name: community-visualization
description: "Build interactive music community dashboards, static PNGs, and rendered reports from a network graph. Supports single-algorithm visualization and Louvain vs Girvan-Newman comparison mode."
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

You are helping the user turn music community graph data into interactive dashboards, static PNGs, and rendered analysis reports. The skill supports both a single community-detection result and a comparison run with multiple clustered/profile JSON pairs.

## When to trigger

Activate when the user asks to visualize a social graph, explore community structure, build an interactive HTML network, export a polished report, or compare community-detection algorithms.

## Workflow

### Step 1: Verify inputs

For a single-algorithm run, confirm that the following files exist before running the visualization skill:

- `shared_data/network.gml`
- `shared_data/clustered_nodes.json`
- `shared_data/community_profiles.json`

For comparison mode, confirm that each clustered-node file has a matching community-profile file. The standard compare-mode inputs are:

- `shared_data/clustered_nodes_louvain.json`
- `shared_data/clustered_nodes_gn.json`
- `shared_data/profiles_louvain.json`
- `shared_data/profiles_gn.json`

The clustered-node JSON should include `username`, `community_id`, `top_artists`, `top_tags`, `playcount`, and preferably `influence_score`. If `influence_score` is present, the visualization uses it to scale node prominence and report the top influence user.

If any file is missing, stop and tell the user which upstream skill needs to be run first.

### Step 2: Run the Community Visualization

Run the single-algorithm visualization pipeline with:

```bash
python skills/community-visualization/main.py --graph shared_data/network.gml --clustered_nodes shared_data/clustered_nodes.json --community_profiles shared_data/community_profiles.json --query "Analyze the indie rock community" --out_dir shared_data/
```

For Louvain vs Girvan-Newman comparison, pass comma-separated clustered/profile paths and enable `--compare`:

```bash
python skills/community-visualization/main.py --graph shared_data/network.gml --clustered_nodes shared_data/clustered_nodes_louvain.json,shared_data/clustered_nodes_gn.json --community_profiles shared_data/profiles_louvain.json,shared_data/profiles_gn.json --query "Compare Louvain and Girvan-Newman music communities" --out_dir shared_data/ --compare
```

Do not put spaces around the commas in the comma-separated path lists.

### Step 3: What the pipeline computes

For each algorithm payload, the skill computes and embeds:

- Global graph metrics: node count, edge count, density, average degree, average clustering, largest connected component.
- Partition quality: community count and weighted modularity.
- Node metrics: degree, closeness, PageRank, local clustering coefficient, betweenness, influence score, importance, bridge score, cross-community neighbor count, and cross fraction.
- Community summaries: size, internal density, average degree, top artists, top tags, representative top nodes, bridge nodes, related communities, and sample members.
- Recommendation data: similar listeners, cross-community bridge recommendations, and strongest graph neighbors.

In comparison mode, the final report starts with an algorithm comparison table and then writes separate detailed sections for each algorithm, rather than only expanding the best-modularity result.

### Step 4: Present results

Tell the user that the visualization has been generated and report the saved output files. If available, summarize key graph statistics or generated artifacts.

## Output

- `network_viz.html` interactive dashboard
- `network_viz.png` static overview
- `final_report.md` markdown report
- `final_report.html` rendered report

Comparison mode additionally writes:

- `viz_louvain.html`
- `viz_louvain.png`
- `viz_gn.html`
- `viz_gn.png`
- `final_report.md` / `final_report.html` with:
  - an algorithm comparison table for community count and modularity
  - a comparison summary highlighting the highest-modularity algorithm
  - detailed Louvain sections
  - detailed Girvan-Newman sections

## Report Structure

In single mode, the report contains:

- `Network Overview`
- `Global Insights`
- `Community Snapshot`
- `Top Hubs`
- `Bridge Nodes`
- `Visualization Outputs`

In comparison mode, the report contains:

- `Algorithm Comparison`
- `Comparison Summary`
- `<Algorithm> Network Overview`
- `<Algorithm> Global Insights`
- `<Algorithm> Community Snapshot`
- `<Algorithm> Top Hubs`
- `<Algorithm> Bridge Nodes`
- `Visualization Outputs`

## Notes

- Algorithm names are inferred from clustered-node filenames. Filenames containing `louvain` are labeled `Louvain`; filenames containing `girvan`, `_gn`, or `-gn` are labeled `Girvan-Newman`; otherwise they are labeled `Algorithm 1`, `Algorithm 2`, and so on.
- In comparison mode, the output file suffixes are similarly inferred: `viz_louvain.*`, `viz_gn.*`, or fallback names such as `viz_algo1.*`.
- `modularity` is computed from the graph and the community partition with `weight="weight"`.
- `influence_score` is read from Skill C output. It is not recomputed in this skill, but it is used in node sizing, tooltips, and top influence reporting.

## Error handling

- If a required input file is missing, report the exact missing path.
- If `--compare` is enabled with fewer than two clustered/profile file pairs, stop and report the invalid compare input.
- If the number of clustered-node paths and profile paths differs, stop and report that both comma-separated lists must have the same length.
- If graph parsing fails, stop and report the stage that failed.
- If HTML, PNG, or report writing fails, include the destination path and the filesystem error.
