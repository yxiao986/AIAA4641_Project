---
name: lastfm-music-scraper
description: Collects a Last.fm music listener social graph via BFS expansion. Use when the user asks to scrape, crawl, or collect music listener data, build a music fan dataset, or gather social connections and listening histories from Last.fm. Supports two modes - offline (HetRec 2011 dataset, recommended) and online (live Last.fm REST API) - and three offline seed types (artist, tag, or whole-network). Emits two standardized JSON files (raw_users.json, raw_interactions.json) that downstream community detection and profiling skills consume. Trigger phrases include "scrape Last.fm", "build a music listener graph", "collect fans of an artist", "build a community around a genre tag", "Skill A", and any request to seed a music community analysis pipeline.
author: your-github-username
version: 2.0.0
tags:
  - data-collection
  - lastfm
  - social-network
  - music
  - scraper
  - bfs
---
 
# Last.fm Music Scraper (Skill A)
 
Skill A of the **Music Community Analysis Agent**. Collects a music listener
social graph from Last.fm via breadth-first search (BFS) and emits two
standardized JSON files for downstream skills.
 
## Functionality
 
This skill solves the **data collection** stage of the pipeline:
 
```
[Skill A: Scraper] --> raw_users.json + raw_interactions.json --> [Skill B: Linker]
```
 
Two interchangeable data sources (selected by `--source`):
 
| Mode      | Source                               | Needs API key | Seed types supported     |
|-----------|--------------------------------------|---------------|--------------------------|
| `hetrec`  | Local HetRec 2011 Last.fm-2K dataset | No            | `artist`, `tag`, `none`  |
| `api`     | Live Last.fm REST API                | Yes           | `seed_user` only         |
 
Both modes produce **bit-for-bit compatible output** conforming to the
`UserRecord` and `InteractionRecord` schemas defined in `main.py`, so
downstream skills do not need to know which source was used.
 
### Why API mode only supports `seed_user`
 
Last.fm removed all reverse-lookup endpoints (`artist.getTopFans`,
`tag.getTopFans`, etc.) around 2013. All remaining public endpoints require a
known username first, so the online crawler must start from a seed user. Use
`--source hetrec` for artist- or tag-driven analysis.
 
## Inputs
 
| Flag             | Type   | Default                          | Applies to | Description                                            |
|------------------|--------|----------------------------------|------------|--------------------------------------------------------|
| `--source`       | str    | `hetrec`                         | both       | `hetrec` or `api`                                      |
| `--max_users`    | int    | `200`                            | both       | Maximum users to collect                               |
| `--out_dir`      | str    | `shared_data/`                   | both       | Output directory                                       |
| `--seed_type`    | str    | `artist`                         | hetrec     | One of `artist`, `tag`, `none`                         |
| `--seed_value`   | str    | `Radiohead` (when type=artist)   | hetrec     | Artist name or tag string; ignored when type=`none`    |
| `--seed_artist`  | str    | `None`                           | hetrec     | Legacy alias for `--seed_type artist --seed_value ...` |
| `--data_dir`     | str    | `data/hetrec2011-lastfm-2k/`     | hetrec     | Path to the extracted HetRec dataset                   |
| `--seed_user`    | str    | `None`                           | api        | Starting Last.fm username (required)                   |
| `--api_key`      | str    | `$LASTFM_API_KEY`                | api        | Last.fm API key                                        |
| `--rate_limit`   | float  | `0.3`                            | api        | Min seconds between API requests                       |
 
### Offline seed types
 
- **`artist`** — picks users who rank `seed_value` in their top-30 most-played artists. Falls back to most-active users if the artist has no listeners in the dataset.
- **`tag`** — picks users whose top tags include `seed_value` (case-insensitive). Falls back to most-active users if no match.
- **`none`** — picks the most-active users by total playcount across the entire network. Useful for whole-network baselines.
## Outputs
 
Two JSON files written to `--out_dir`:
 
### `raw_users.json`
 
```json
[
  {
    "username": "user_2",
    "playcount": 13883,
    "top_artists": ["Radiohead", "Portishead", "Massive Attack"],
    "top_tags": ["alternative", "trip-hop", "electronic"],
    "friends": ["user_275", "user_428"]
  }
]
```
 
### `raw_interactions.json`
 
```json
[
  { "source": "user_2", "target": "user_275", "type": "friend" },
  { "source": "user_2", "target": "Radiohead", "type": "listener", "weight": 13883 }
]
```
 
Schema is enforced by `validate_users()` and `validate_interactions()` before
writing — invalid records cause an immediate `AssertionError`.
 
## Usage
 
### Offline mode, artist seed (most common)
 
```bash
python main.py --source hetrec \
    --data_dir data/hetrec2011-lastfm-2k/ \
    --seed_type artist --seed_value "Radiohead" \
    --max_users 200 --out_dir shared_data/
```
 
### Offline mode, tag seed
 
```bash
python main.py --source hetrec \
    --data_dir data/hetrec2011-lastfm-2k/ \
    --seed_type tag --seed_value "trip-hop" \
    --max_users 200 --out_dir shared_data/
```
 
### Offline mode, whole-network (no seed)
 
```bash
python main.py --source hetrec \
    --data_dir data/hetrec2011-lastfm-2k/ \
    --seed_type none \
    --max_users 200 --out_dir shared_data/
```
 
### Online mode
 
```bash
# Get a free API key at https://www.last.fm/api/account/create
export LASTFM_API_KEY="your_key_here"
 
python main.py --source api \
    --api_key {Your last.fm API key} \
    --seed_user "RJ" \
    --max_users 200 --out_dir shared_data/
```
 
## Implementation Notes
 
- **BFS strategy:** seed users are picked according to `--seed_type`, then expanded along the friend graph until `--max_users` is reached.
- **Username convention (offline):** numeric HetRec IDs are prefixed with `user_` (e.g., `user_2`) so node IDs stay string-typed and never collide with artist names.
- **Username convention (online):** real Last.fm usernames are kept as-is.
- **Listener edges:** each user contributes weighted edges to their top 5 artists; edge weight equals raw playcount.
- **Friend edges:** first 10 friends per user become BFS expansion candidates and contribute friend edges (default weight 1, which is dropped from the JSON to keep it compact).
- **Tag inference (online):** `user.getTopTags` is often empty in the live API, so the online crawler aggregates the top tags of the user's top 5 artists instead.
- **Rate limiting (online):** 0.3 s between calls, well under Last.fm's 5 req/s ceiling.
- **Encoding:** HetRec files are read with `errors='ignore'` because some artist names contain non-UTF-8 bytes.
- **Single-file design:** the schema, offline loader, online client, and CLI are all in `main.py`. The `requests` import is wrapped in `try/except ImportError`, so the offline mode runs even when `requests` is not installed.
## File Layout
 
```
skill_a_scraper/
├── skill.md     # This file (registry metadata + docs)
└── main.py      # CLI, schema, offline loader, online client - all in one file
```
 
## References
 
- **HetRec 2011 dataset.** Cantador, Brusilovsky, Kuflik (2011).
  *Second Workshop on Information Heterogeneity and Fusion in Recommender
  Systems (HetRec 2011).* In RecSys 2011.
  <https://grouplens.org/datasets/hetrec-2011/>
- **Last.fm API documentation.** <https://www.last.fm/api>
- **BFS for social-network sampling.** Leskovec & Faloutsos (2006).
  *Sampling from Large Graphs.* In KDD 2006.
## Limitations
 
- Maximum graph size is bounded by `--max_users` (BFS terminates at the cap).
- HetRec mode is a static 2011 snapshot; communities reflect listener taste from that era and may not match current charts.
- Online mode cannot start from an artist or tag — see the note in *Functionality*.
- This skill collects only listening counts and friend links; it does not attempt to fetch user-level tag data via `user.getTopTags`, which the live API frequently returns empty.
