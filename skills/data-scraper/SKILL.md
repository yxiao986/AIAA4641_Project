---
name: data-scraper
description: Collects a Last.fm music listener social graph via BFS expansion. Use when the user asks to scrape, crawl, or collect music listener data, build a music fan dataset, or gather social connections and listening histories from Last.fm. Supports two modes - offline (HetRec 2011 dataset, recommended) and online (live Last.fm REST API) - and three offline seed types (artist, tag, or whole-network). Emits two standardized JSON files (raw_users.json, raw_interactions.json) that downstream community detection and profiling skills consume. In api mode, also emits raw_users_extended.json with demographic and behavioural fields for Skill D. Trigger phrases include "scrape Last.fm", "build a music listener graph", "collect fans of an artist", "build a community around a genre tag", "Skill A", and any request to seed a music community analysis pipeline.
version: 1.1.0
author: ywu044
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
social graph from Last.fm via breadth-first search (BFS) and emits standardized
JSON files for downstream skills.

Two interchangeable data sources (selected by `--source`):

| Mode      | Source                               | Needs API key | Seed types supported     | Extended output |
|-----------|--------------------------------------|---------------|--------------------------|-----------------|
| `hetrec`  | Local HetRec 2011 Last.fm-2K dataset | No            | `artist`, `tag`, `none`  | No              |
| `api`     | Live Last.fm REST API                | Yes           | `seed_user` only         | Yes (automatic) |

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
| `--data_dir`     | str    | `data/hetrec2011-lastfm-2k/`     | hetrec     | Path to the extracted HetRec dataset                   |
| `--seed_user`    | str    | `None`                           | api        | Starting Last.fm username (required)                   |
| `--api_key`      | str    | `$LASTFM_API_KEY`                | api        | Last.fm API key                                        |
| `--rate_limit`   | float  | `0.3`                            | api        | Min seconds between API requests                       |

### Offline seed types

- **`artist`** — picks users who rank `seed_value` in their top-30 most-played artists. Falls back to most-active users if the artist has no listeners in the dataset.
- **`tag`** — picks users whose top tags include `seed_value` (case-insensitive). Falls back to most-active users if no match.
- **`none`** — picks the most-active users by total playcount across the entire network. Useful for whole-network baselines.

## Outputs

### Always produced (both modes)

#### `raw_users.json`

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

#### `raw_interactions.json`

```json
[
  { "source": "user_2", "target": "user_275", "type": "friend" },
  { "source": "user_2", "target": "Radiohead", "type": "listener", "weight": 13883 }
]
```

Schema is enforced by `validate_users()` and `validate_interactions()` before
writing — invalid records cause an immediate `AssertionError`.

---

### api mode only

#### `raw_users_extended.json`

Written automatically whenever `--source api` is used. **Not produced in hetrec
mode** — the HetRec dataset does not contain the demographic and behavioural
fields that make this file useful.

Consumed by **Skill B (Community Linker)**.

```json
{
  "data_source": "api",
  "users": [
    {
      "username": "RJ",
      "total_playcount": 157114,
      "country": "United Kingdom",
      "registered_year": 2002,
      "age": 0,
      "gender": "m",
      "artist_count": 4023,
      "subscriber": true,
      "loved_tracks_count": 700,
      "recent_track_count": 50
    }
  ]
}
```

Field reference:

| Field                | Type         | Source API call          | Notes                                      |
|----------------------|--------------|--------------------------|--------------------------------------------|
| `username`           | str          | —                        | Join key; matches `raw_users.json` exactly |
| `total_playcount`    | int \| null  | `user.getInfo`           | Lifetime scrobble count                    |
| `country`            | str          | `user.getInfo`           | Empty string if not set by user            |
| `registered_year`    | int \| null  | `user.getInfo`           | Year extracted from Unix timestamp         |
| `age`                | int \| null  | `user.getInfo`           | Self-reported; `0` means not disclosed     |
| `gender`             | str \| null  | `user.getInfo`           | `"m"` / `"f"` / `null` if not disclosed   |
| `artist_count`       | int \| null  | `user.getInfo`           | Distinct artists ever scrobbled            |
| `subscriber`         | bool \| null | `user.getInfo`           | `true` = Last.fm Pro subscriber            |
| `loved_tracks_count` | int \| null  | `user.getLovedTracks`    | Total loved tracks (`@attr.total`)         |
| `recent_track_count` | int \| null  | `user.getRecentTracks`   | Count of tracks in last 50 fetched; activity proxy |

All fields are always present. Fields that could not be retrieved from the API
are set to `null` (or `""` for `country`) rather than omitted, so Skill D can
read all keys without defensive `.get()` calls.

**API call overhead:** api mode makes 5 calls per user
(`user.getTopArtists`, `user.getFriends`, `user.getInfo`,
`user.getLovedTracks`, `user.getRecentTracks`), compared to 3 calls without
extended data. Budget approximately 1.5 s per user at the default rate limit.

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
    --seed_user "RJ" \
    --max_users 200 --out_dir shared_data/
```

Output (api mode):
```
users: 200 -> shared_data/raw_users.json
edges: 612 (401 friend, 211 listener) -> shared_data/raw_interactions.json
extended: 200 users -> shared_data/raw_users_extended.json
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
- **Extended output resilience:** all `user_info()`, `loved_tracks_count()`, and `recent_track_count()` calls are individually wrapped in try/except. A failed API call for one user sets that field to `null` and never interrupts the BFS loop.

## File Layout

```
data-scraper/
├── SKILL.md     # This file (registry metadata + docs)
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
- `raw_users_extended.json` is only available in api mode. Skill D must check `data_source` before accessing extended fields and should handle gracefully the case where the file does not exist (hetrec runs).
- Some Last.fm users do not disclose age or gender; these fields will be `null` or `0` for age. Skill D should filter `age == 0` as "not disclosed".
