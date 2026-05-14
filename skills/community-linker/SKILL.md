---
name: community-linker
description: "Builds a clean NetworkX graph from raw social network JSON and exports it as GML. Use when user says 'build graph', 'link nodes', 'construct network', or 'run graph linker'."
author: herry-sketch
version: 1.0.0
tags:
  - social-network
  - graph
  - networkx
  - data-processing
metadata:
  openclaw:
    requires:
      bins:
        - python3
---



## Workflow

# Graph Linker

You are helping the user build a clean, analysis-ready social network graph from raw JSON data produced by the Data Scraper skill.


### Step 1: Verify inputs

Confirm that the following files exist in the working directory:
- `raw_users.json` — list of user objects with `username`, `playcount`, `top_artists`, `top_tags`, `friends`
- `raw_interactions.json` — list of edge objects with `source`, `target`, `type`, and optional `weight`

If either file is missing, ask the user to run the Data Scraper skill first.

### Step 2: Run the Graph Linker

```bash
python skill_b_linker/main.py \
  --users_file raw_users.json \
  --interactions_file raw_interactions.json \
  --out_graph network.gml
```

### Step 3: Present results

Report the graph statistics printed to stdout:
- Number of nodes and edges
- Graph density
- Average degree
- Number of connected components and largest component size
- Average clustering coefficient (skipped automatically if graph has >10,000 nodes)
- Number of isolated nodes removed
- Number of edges skipped (target not in user list) — printed as a warning if any were skipped

Confirm that `network.gml` has been written and is ready for the Community Detector skill.

## Output

- `network.gml` — undirected weighted graph in GML format
  - Node attributes: `playcount` (int), `top_artists` (pipe-delimited string, up to 5 entries), `top_tags` (pipe-delimited string, up to 5 entries)
  - Edge attributes: `weight` (int, cumulative), `etype` (pipe-delimited string of observed edge types)

## Error handling

- If `raw_users.json` or `raw_interactions.json` is not found, report the missing file and ask the user to run Skill A first.
- If any edges are skipped (target username not in user list), the script prints a warning automatically. If the skipped count is large (e.g. >50% of total interactions), suggest the user increase the scrape coverage in Skill A.
- If the output graph has zero edges after cleaning, report that no connected users were found and suggest increasing `--max_users` in Skill A.
