"""Skill A - Last.fm music data scraper.

Two interchangeable modes selected by --source:

    hetrec : load from local HetRec 2011 Last.fm dataset (offline, default)
             Supports three seed types: artist / tag / none (whole network)
    api    : crawl live Last.fm REST API (online)
             Supports only seed_user as starting point - see note below

Note on API limitations:
    Last.fm Public API removed all "reverse lookup" endpoints around 2013
    (artist.getTopFans, tag.getTopFans, etc). All remaining endpoints require
    a known username first. So API mode can only BFS from a seed user, not
    from an artist or tag. Use --source hetrec for artist- or tag-driven
    community analysis.

Outputs (always identical schema, regardless of mode):

    <out_dir>/raw_users.json
    <out_dir>/raw_interactions.json

Additional output in api mode only:

    <out_dir>/raw_users_extended.json

    Written automatically when --source api is used. Not produced in hetrec
    mode (HetRec data lacks the demographic and behavioural fields that make
    this file useful). Consumed by Skill D for community demographic analysis.

    Schema:
        data_source        "api"
        users[]
          username         str   matches raw_users.json (join key)
          total_playcount  int | null   lifetime scrobble count
          country          str   e.g. "United Kingdom", "" if not set
          registered_year  int | null
          age              int | null   0 = not disclosed by user
          gender           str | null   "m" / "f" / null
          artist_count     int | null   distinct artists ever scrobbled
          subscriber       bool | null  true = Last.fm Pro subscriber
          loved_tracks_count   int | null
          recent_track_count   int | null   tracks in last 50 fetched

Usage:

    # Offline mode, artist seed (default)
    python main.py --source hetrec --data_dir data/hetrec2011-lastfm-2k/ \
        --seed_type artist --seed_value "Radiohead" --max_users 200

    # Offline mode, tag seed
    python main.py --source hetrec --data_dir data/hetrec2011-lastfm-2k/ \
        --seed_type tag --seed_value "trip-hop" --max_users 200

    # Offline mode, no seed (most-active users across the whole network)
    python main.py --source hetrec --data_dir data/hetrec2011-lastfm-2k/ \
        --seed_type none --max_users 200

    # Online mode — also writes raw_users_extended.json automatically
    python main.py --source api --seed_user "RJ" --max_users 200 \
        --api_key $LASTFM_API_KEY
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

try:
    import requests
except ImportError:
    requests = None  # only required for --source api


# ---------------------------------------------------------------------------
# Shared data contract  (DO NOT MODIFY — downstream skills depend on this)
# ---------------------------------------------------------------------------

@dataclass
class UserRecord:
    """One row of raw_users.json."""
    username: str
    playcount: int
    top_artists: list[str]
    top_tags: list[str]
    friends: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class InteractionRecord:
    """One edge of raw_interactions.json.

    type='friend'   -> source and target are both users
    type='listener' -> source is a user, target is an artist, weight = playcount
    """
    source: str
    target: str
    type: Literal["friend", "listener"]
    weight: int = 1

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.type == "friend" and self.weight == 1:
            d.pop("weight")
        return d


# ---------------------------------------------------------------------------
# Extended record — api mode only, written to raw_users_extended.json
# ---------------------------------------------------------------------------
# DESIGN NOTE FOR SKILL D:
#   Only produced in api mode. Join on "username" with raw_users.json.
#   All fields always present (null when unavailable from API).

@dataclass
class ExtendedUserRecord:
    """One entry inside raw_users_extended.json["users"]. Api mode only."""

    username: str                          # join key -> raw_users.json

    # From user.getInfo
    total_playcount: int | None = None     # lifetime scrobble count
    country: str | None = None            # "United Kingdom" / "" if not set
    registered_year: int | None = None    # year from Unix registration timestamp
    age: int | None = None                # self-reported; 0 = not disclosed
    gender: str | None = None            # "m" / "f" / null
    artist_count: int | None = None       # distinct artists ever scrobbled
    subscriber: bool | None = None        # True = Last.fm Pro subscriber

    # From user.getLovedTracks
    loved_tracks_count: int | None = None

    # From user.getRecentTracks
    recent_track_count: int | None = None  # count of tracks in last 50 fetched

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Validators (unchanged)
# ---------------------------------------------------------------------------

def validate_users(users: list[dict]) -> None:
    assert isinstance(users, list) and len(users) > 0, "users must be a non-empty list"
    required = {"username", "playcount", "top_artists", "top_tags", "friends"}
    for i, u in enumerate(users):
        missing = required - u.keys()
        assert not missing, f"user[{i}] missing fields: {missing}"
        assert isinstance(u["top_artists"], list), f"user[{i}].top_artists must be list"
        assert isinstance(u["friends"], list), f"user[{i}].friends must be list"


def validate_interactions(interactions: list[dict]) -> None:
    assert isinstance(interactions, list) and len(interactions) > 0, \
        "interactions must be a non-empty list"
    valid_types = {"friend", "listener"}
    for i, e in enumerate(interactions):
        assert "source" in e and "target" in e and "type" in e, \
            f"interaction[{i}] missing source/target/type"
        assert e["type"] in valid_types, \
            f"interaction[{i}].type invalid: {e['type']}"


# ---------------------------------------------------------------------------
# Offline mode: HetRec 2011 dataset loader
# ---------------------------------------------------------------------------
# Dataset: https://grouplens.org/datasets/hetrec-2011/
# Files used (tab-separated, header row):
#   artists.dat              id  name  url  pictureURL
#   tags.dat                 tagID  tagValue
#   user_friends.dat         userID  friendID
#   user_artists.dat         userID  artistID  weight   <- weight = playcount
#   user_taggedartists.dat   userID  artistID  tagID  day  month  year

def _hetrec_load_artists(data_dir: Path) -> dict[str, str]:
    artists: dict[str, str] = {}
    with open(data_dir / "artists.dat", encoding="utf-8", errors="ignore") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            artists[row["id"]] = row["name"]
    return artists


def _hetrec_load_tags(data_dir: Path) -> dict[str, str]:
    tags: dict[str, str] = {}
    with open(data_dir / "tags.dat", encoding="utf-8", errors="ignore") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            tags[row["tagID"]] = row["tagValue"]
    return tags


def _hetrec_load_friendships(data_dir: Path) -> dict[str, list[str]]:
    friends: dict[str, list[str]] = defaultdict(list)
    with open(data_dir / "user_friends.dat", encoding="utf-8", errors="ignore") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            friends[row["userID"]].append(row["friendID"])
    return dict(friends)


def _hetrec_load_user_artists(data_dir: Path,
                              artists: dict[str, str]
                              ) -> dict[str, list[tuple[str, int]]]:
    """Returns {user_id: [(artist_name, playcount), ...]} sorted by playcount desc."""
    out: dict[str, list[tuple[str, int]]] = defaultdict(list)
    with open(data_dir / "user_artists.dat", encoding="utf-8", errors="ignore") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            name = artists.get(row["artistID"])
            if not name:
                continue
            try:
                out[row["userID"]].append((name, int(row["weight"])))
            except (ValueError, KeyError):
                continue
    for uid in out:
        out[uid].sort(key=lambda x: -x[1])
    return dict(out)


def _hetrec_load_user_tags(data_dir: Path,
                           tags: dict[str, str]) -> dict[str, list[str]]:
    """Returns {user_id: [top tag names]} (top 10 by frequency)."""
    counter: dict[str, Counter] = defaultdict(Counter)
    with open(data_dir / "user_taggedartists.dat",
              encoding="utf-8", errors="ignore") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            tag = tags.get(row["tagID"])
            if tag:
                counter[row["userID"]][tag] += 1
    return {uid: [t for t, _ in c.most_common(10)] for uid, c in counter.items()}


def _hetrec_pick_seeds(seed_type: str,
                       seed_value: str | None,
                       user_artists: dict[str, list[tuple[str, int]]],
                       user_tags: dict[str, list[str]],
                       n_seeds: int = 50) -> list[str]:
    """Pick BFS starting users based on seed type.

    seed_type='artist' : users who rank seed_value in their top 30 artists
    seed_type='tag'    : users whose top tags include seed_value
    seed_type='none'   : most-active users by total playcount (whole-network)

    Falls back to most-active users if a typed seed yields no matches.
    """
    if seed_type == "artist" and seed_value:
        target = seed_value.lower().strip()
        candidates = [
            uid for uid, alist in user_artists.items()
            if any(name.lower() == target for name, _ in alist[:30])
        ]
        if candidates:
            return candidates[:n_seeds]

    if seed_type == "tag" and seed_value:
        target = seed_value.lower().strip()
        candidates = [
            uid for uid, tlist in user_tags.items()
            if any(t.lower() == target for t in tlist)
        ]
        if candidates:
            return candidates[:n_seeds]

    most_active = sorted(
        user_artists.items(),
        key=lambda kv: -sum(c for _, c in kv[1]),
    )
    return [uid for uid, _ in most_active[:n_seeds]]


def _hetrec_bfs(seed_users: list[str],
                friendships: dict[str, list[str]],
                user_artists: dict[str, list[tuple[str, int]]],
                user_tags: dict[str, list[str]],
                max_users: int,
                ) -> tuple[list[UserRecord], list[InteractionRecord]]:
    """BFS expansion across the friend graph.

    Usernames are prefixed with 'user_' to keep node IDs string-typed
    (NetworkX has edge cases with purely-numeric node IDs in GML).
    """
    visited: set[str] = set()
    queue: list[str] = list(seed_users)
    users_out: list[UserRecord] = []
    edges_out: list[InteractionRecord] = []

    while queue and len(visited) < max_users:
        uid = queue.pop(0)
        if uid in visited:
            continue
        visited.add(uid)

        artists_with_counts = user_artists.get(uid, [])
        top_names = [n for n, _ in artists_with_counts[:10]]
        friends = friendships.get(uid, [])
        playcount = artists_with_counts[0][1] if artists_with_counts else 0

        users_out.append(UserRecord(
            username=f"user_{uid}",
            playcount=playcount,
            top_artists=top_names,
            top_tags=user_tags.get(uid, []),
            friends=[f"user_{fid}" for fid in friends[:20]],
        ))

        for fid in friends[:10]:
            edges_out.append(InteractionRecord(
                source=f"user_{uid}", target=f"user_{fid}", type="friend",
            ))
            if fid not in visited:
                queue.append(fid)

        for name, pcount in artists_with_counts[:5]:
            edges_out.append(InteractionRecord(
                source=f"user_{uid}", target=name, type="listener", weight=pcount,
            ))

    return users_out, edges_out


def run_hetrec(data_dir: Path,
               max_users: int,
               seed_type: str,
               seed_value: str | None,
               ) -> tuple[list[dict], list[dict]]:
    """Run hetrec mode. Returns (users, interactions) — no extended output."""
    if not data_dir.exists():
        raise FileNotFoundError(
            f"HetRec data directory not found: {data_dir}\n"
            f"Download from https://grouplens.org/datasets/hetrec-2011/ "
            f"and unzip into this path."
        )
    artists = _hetrec_load_artists(data_dir)
    tags = _hetrec_load_tags(data_dir)
    friendships = _hetrec_load_friendships(data_dir)
    user_artists = _hetrec_load_user_artists(data_dir, artists)
    user_tags = _hetrec_load_user_tags(data_dir, tags)
    seeds = _hetrec_pick_seeds(seed_type, seed_value, user_artists, user_tags)
    users, edges = _hetrec_bfs(seeds, friendships, user_artists, user_tags, max_users)
    return [u.to_dict() for u in users], [e.to_dict() for e in edges]


# ---------------------------------------------------------------------------
# Online mode: Last.fm REST API client
# ---------------------------------------------------------------------------
# Register an API key at https://www.last.fm/api/account/create
# Docs: https://www.last.fm/api
#
# IMPORTANT: Last.fm removed all reverse-lookup endpoints (artist.getTopFans,
# tag.getTopFans, etc) around 2013. All remaining endpoints require a known
# username, so API mode must start BFS from a seed user, not an artist/tag.

_LASTFM_BASE = "http://ws.audioscrobbler.com/2.0/"


class _LastfmClient:
    """Minimal rate-limited Last.fm REST client."""

    def __init__(self, api_key: str, rate_limit: float = 0.3):
        if requests is None:
            raise ImportError(
                "Online mode requires the 'requests' package. "
                "Install with: pip install requests"
            )
        self.api_key = api_key
        self.rate_limit = rate_limit
        self._last_call = 0.0

    def _get(self, params: dict) -> dict:
        gap = time.time() - self._last_call
        if gap < self.rate_limit:
            time.sleep(self.rate_limit - gap)
        full = {**params, "api_key": self.api_key, "format": "json"}
        try:
            r = requests.get(_LASTFM_BASE, params=full, timeout=10)
            self._last_call = time.time()
            r.raise_for_status()
            data = r.json()
            return {} if "error" in data else data
        except requests.RequestException:
            return {}

    def friends(self, username: str, limit: int = 50) -> list[str]:
        data = self._get({"method": "user.getFriends",
                          "user": username, "limit": limit})
        users = data.get("friends", {}).get("user", [])
        return [u["name"] for u in users] if isinstance(users, list) else []

    def top_artists(self, username: str, limit: int = 20) -> list[dict]:
        data = self._get({"method": "user.getTopArtists",
                          "user": username, "limit": limit, "period": "overall"})
        artists = data.get("topartists", {}).get("artist", [])
        return artists if isinstance(artists, list) else []

    def artist_top_tags(self, artist: str, top_k: int = 5) -> list[str]:
        data = self._get({"method": "artist.getTopTags", "artist": artist})
        tags = data.get("toptags", {}).get("tag", [])
        if not isinstance(tags, list):
            return []
        return [t["name"] for t in tags[:top_k]]

    def infer_user_tags(self, top_artist_names: list[str]) -> list[str]:
        """user.getTopTags is often empty, so aggregate artist tags instead."""
        c: Counter = Counter()
        for a in top_artist_names[:5]:
            c.update(self.artist_top_tags(a))
        return [t for t, _ in c.most_common(10)]

    def user_info(self, username: str) -> dict[str, Any]:
        """Call user.getInfo. Always returns all keys (null/'' on failure).

        Keys: total_playcount, country, registered_year, age, gender,
              artist_count, subscriber
        """
        data = self._get({"method": "user.getInfo", "user": username})
        info = data.get("user", {})

        country = info.get("country", "") or ""

        registered_year: int | None = None
        try:
            ts_raw = info.get("registered", {})
            ts = int(ts_raw.get("#text", 0) if isinstance(ts_raw, dict) else ts_raw)
            if ts:
                registered_year = time.gmtime(ts).tm_year
        except (ValueError, TypeError, AttributeError):
            pass

        total_playcount: int | None = None
        try:
            total_playcount = int(info.get("playcount", 0)) or None
        except (ValueError, TypeError):
            pass

        age: int | None = None
        try:
            age = int(info.get("age", 0))
        except (ValueError, TypeError):
            pass

        gender_raw = info.get("gender", "") or ""
        gender: str | None = gender_raw if gender_raw in ("m", "f") else None

        artist_count: int | None = None
        try:
            artist_count = int(info.get("artist_count", 0)) or None
        except (ValueError, TypeError):
            pass

        subscriber: bool | None = None
        try:
            subscriber = bool(int(info.get("subscriber", 0)))
        except (ValueError, TypeError):
            pass

        return {
            "total_playcount": total_playcount,
            "country": country,
            "registered_year": registered_year,
            "age": age,
            "gender": gender,
            "artist_count": artist_count,
            "subscriber": subscriber,
        }

    def loved_tracks_count(self, username: str) -> int | None:
        """Return total loved tracks via user.getLovedTracks @attr.total."""
        data = self._get({"method": "user.getLovedTracks",
                          "user": username, "limit": 1})
        try:
            return int(data.get("lovedtracks", {})
                           .get("@attr", {})
                           .get("total", 0))
        except (ValueError, TypeError):
            return None

    def recent_track_count(self, username: str, limit: int = 50) -> int | None:
        """Return count of tracks in last `limit` fetched (activity proxy)."""
        data = self._get({"method": "user.getRecentTracks",
                          "user": username, "limit": limit})
        tracks = data.get("recenttracks", {}).get("track", [])
        if not isinstance(tracks, list):
            return None
        return len(tracks)


def run_api(api_key: str,
            seed_user: str,
            max_users: int,
            rate_limit: float,
            ) -> tuple[list[dict], list[dict], list[dict]]:
    """Run API mode. Returns (users, interactions, extended_users).

    Five API calls are made per user:
      user.getTopArtists, user.getFriends, user.getInfo,
      user.getLovedTracks, user.getRecentTracks
    """
    client = _LastfmClient(api_key=api_key, rate_limit=rate_limit)

    visited: set[str] = set()
    queue: list[str] = [seed_user]
    users_out: list[UserRecord] = []
    edges_out: list[InteractionRecord] = []
    extended_out: list[ExtendedUserRecord] = []

    while queue and len(visited) < max_users:
        username = queue.pop(0)
        if username in visited:
            continue
        visited.add(username)

        top_artists_raw = client.top_artists(username)
        top_names = [a["name"] for a in top_artists_raw[:10]]
        friends = client.friends(username)
        top_tags = client.infer_user_tags(top_names)

        playcount = 0
        if top_artists_raw:
            try:
                playcount = int(top_artists_raw[0].get("playcount", 0))
            except (ValueError, TypeError):
                pass

        # ---- core records (schema unchanged) ----
        users_out.append(UserRecord(
            username=username,
            playcount=playcount,
            top_artists=top_names,
            top_tags=top_tags,
            friends=friends[:20],
        ))

        for f in friends[:10]:
            edges_out.append(InteractionRecord(
                source=username, target=f, type="friend",
            ))
            if f not in visited:
                queue.append(f)

        for a in top_artists_raw[:5]:
            try:
                w = int(a.get("playcount", 1))
            except (ValueError, TypeError):
                w = 1
            edges_out.append(InteractionRecord(
                source=username, target=a["name"], type="listener", weight=w,
            ))

        # ---- extended record (always collected in api mode) ----
        info = client.user_info(username)
        loved = client.loved_tracks_count(username)
        recent = client.recent_track_count(username)
        extended_out.append(ExtendedUserRecord(
            username=username,
            total_playcount=info["total_playcount"],
            country=info["country"],
            registered_year=info["registered_year"],
            age=info["age"],
            gender=info["gender"],
            artist_count=info["artist_count"],
            subscriber=info["subscriber"],
            loved_tracks_count=loved,
            recent_track_count=recent,
        ))

    return (
        [u.to_dict() for u in users_out],
        [e.to_dict() for e in edges_out],
        [x.to_dict() for x in extended_out],
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Skill A - Last.fm music data scraper "
                    "(dual-mode: HetRec dataset OR Last.fm API)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--source", choices=["hetrec", "api"], default="hetrec",
                   help="Data source")
    p.add_argument("--seed_type", choices=["artist", "tag", "none"], default="artist",
                   help="(hetrec mode) Seed type: "
                        "artist=artist name, tag=genre tag, none=whole network")
    p.add_argument("--seed_value", default=None,
                   help="(hetrec mode) Seed value "
                        "(artist name / tag string / ignored when none)")
    p.add_argument("--seed_user", default=None,
                   help="(api mode) Starting username")
    p.add_argument("--max_users", type=int, default=200,
                   help="Maximum users to collect")
    p.add_argument("--out_dir", default="shared_data/",
                   help="Output directory")
    p.add_argument("--data_dir", default="data/hetrec2011-lastfm-2k/",
                   help="(hetrec mode) Path to extracted dataset")
    p.add_argument("--api_key", default=os.environ.get("LASTFM_API_KEY"),
                   help="(api mode) Last.fm API key, or set LASTFM_API_KEY env var")
    p.add_argument("--rate_limit", type=float, default=0.3,
                   help="(api mode) Min seconds between API calls")

    args = p.parse_args()

    if args.source == "hetrec" and args.seed_type == "artist" and not args.seed_value:
        args.seed_value = "Radiohead"

    return args


def main() -> int:
    args = parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.source == "hetrec":
        users, interactions = run_hetrec(
            data_dir=Path(args.data_dir),
            max_users=args.max_users,
            seed_type=args.seed_type,
            seed_value=args.seed_value,
        )
        extended = None  # hetrec mode: no extended output

    else:
        if not args.api_key:
            print("error: --source api requires --api_key or LASTFM_API_KEY",
                  file=sys.stderr)
            return 2
        if not args.seed_user:
            print("error: --source api requires --seed_user (Last.fm API does "
                  "not support reverse lookup from artist/tag; use --source "
                  "hetrec for artist- or tag-driven analysis)", file=sys.stderr)
            return 2
        users, interactions, extended = run_api(
            api_key=args.api_key,
            seed_user=args.seed_user,
            max_users=args.max_users,
            rate_limit=args.rate_limit,
        )

    # ---- validate + write raw_users / raw_interactions (always) ----
    validate_users(users)
    validate_interactions(interactions)

    users_path = out_dir / "raw_users.json"
    edges_path = out_dir / "raw_interactions.json"
    users_path.write_text(
        json.dumps(users, indent=2, ensure_ascii=False), encoding="utf-8")
    edges_path.write_text(
        json.dumps(interactions, indent=2, ensure_ascii=False), encoding="utf-8")

    n_friend = sum(1 for e in interactions if e["type"] == "friend")
    n_listener = sum(1 for e in interactions if e["type"] == "listener")
    print(f"users: {len(users)} -> {users_path}")
    print(f"edges: {len(interactions)} ({n_friend} friend, {n_listener} listener) "
          f"-> {edges_path}")

    # ---- write raw_users_extended (api mode only) ----
    if extended:
        ext_path = out_dir / "raw_users_extended.json"
        envelope = {
            "data_source": "api",
            "users": extended,
        }
        ext_path.write_text(
            json.dumps(envelope, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"extended: {len(extended)} users -> {ext_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())