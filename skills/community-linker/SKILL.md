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



# Graph Linker

You are helping the user build a clean, analysis-ready social network graph from raw JSON data produced by the Data Scraper skill.

## When to trigger

Activate when the user says "build graph", "link nodes", "construct network", "run graph linker", or when `raw_users.json` and `raw_interactions.json` are available and a `network.gml` is needed.

## Workflow

### Step 1: Verify inputs

Confirm that the following files exist in the working directory:
- `raw_users.json` — list of user objects with `username`, `playcount`, `top_artists`, `top_tags`, `friends`
- `raw_interactions.json` — list of edge objects with `source`, `target`, `type`, and optional `weight`
- `raw_users_extended.json` — extended user attributes including `country`, `registered_year`, `age`, `gender`, `subscriber`, `artist_count`, `loved_tracks_count`, `recent_track_count`

If `raw_users.json` or `raw_interactions.json` is missing, ask the user to run the Data Scraper skill first. `raw_users_extended.json` is optional; if absent, extended node attributes will be omitted.

### Step 2: Run the Graph Linker

```bash
python skill_b_linker/main.py \
  --users_file raw_users.json \
  --interactions_file raw_interactions.json \
  --users_extended_file raw_users_extended.json \
  --out_graph network.gml
```

### Step 3: Present results

Report the graph statistics printed to stdout:
- Number of nodes and edges
- Graph density
- Average degree
- Number of connected components and largest component size
- Average clustering coefficient (unweighted)
- Modularity and number of communities detected
- Number of isolated nodes removed
- Number of edges skipped (target not in user set, e.g. artist nodes) — printed as a warning if any were skipped

Confirm that `network.gml` has been written and is ready for the Community Detector skill.

## Output

- `network.gml` — undirected weighted graph in GML format
  - Node attributes: `playcount` (int), `top_artists` (pipe-delimited string, up to 5), `top_tags` (pipe-delimited string, up to 5), `country` (string), `registered_year` (int), `age` (int), `gender` (string), `subscriber` (0/1), `artist_count` (int), `loved_tracks_count` (int), `recent_track_count` (int)
  - Edge attributes: `weight` (float, playcount-scaled cumulative), `etype` (pipe-delimited string: `friend`, `shared_artist`, or `friend|shared_artist`)

## Edge construction

Two mechanisms create edges:
- **Friend edges**: interactions with `type=friend` where both endpoints are in the user set.
- **Shared-artist edges**: interactions with `type=listener` connect a user to an artist. Since artists are not in the user set, these are not added directly. Instead, pairs of users who both listened to the same artist are connected via an inferred shared-artist edge.

Edge weights are scaled by a playcount factor: `(log1p(pc1) + log1p(pc2)) / (2 * log1p(max_pc))`, mapping weights to `[0, 1]`. Base weights (friend = 5, shared_artist = 1) are selected by hyperparameter search maximizing modularity.

## Error handling

- If `raw_users.json` or `raw_interactions.json` is not found, report the missing file and ask the user to run Skill A first.
- If any edges are skipped because the target is not in the user set (expected for artist nodes from listener interactions), this is normal behavior and not an error.
- If the output graph has zero edges after cleaning, report that no connected users were found and suggest increasing `--max_users` in Skill A.
