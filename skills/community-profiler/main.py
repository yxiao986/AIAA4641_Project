import argparse
from html import parser
import json
import os
import re
import time
from pathlib import Path
from collections import Counter, defaultdict
from statistics import mean, median
from typing import Any


# =========================
# Basic JSON utilities
# =========================

def load_json(path: str) -> Any:
    """Load a JSON file with UTF-8 encoding."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(obj: Any, path: str) -> None:
    """Save object as pretty JSON."""
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def to_record_list(data: Any) -> list[dict]:
    """
    Convert possible JSON formats into a list of dictionaries.

    Supported:
    1. [ {...}, {...} ]
    2. { "users": [ {...}, {...} ] }
    3. { "nodes": [ {...}, {...} ] }
    4. { "username1": {...}, "username2": {...} }
    """
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ["users", "nodes", "data", "items"]:
            if key in data and isinstance(data[key], list):
                return data[key]

        records = []
        for k, v in data.items():
            if isinstance(v, dict):
                item = dict(v)
                item.setdefault("username", k)
                records.append(item)
        return records

    raise ValueError("Unsupported JSON format. Expected list or dict.")


# =========================
# Data normalization
# =========================

def normalize_name_list(value: Any) -> list[str]:
    """
    Normalize artists/tags/tracks into a clean list of strings.

    Handles:
    - ["Radiohead", "Portishead"]
    - [{"name": "Radiohead"}, {"artist": "Portishead"}]
    - "Radiohead, Portishead"
    """
    if value is None:
        return []

    if isinstance(value, str):
        parts = re.split(r"\s*[,;|]\s*|\s+/\s+", value)
        return [p.strip() for p in parts if p.strip()]

    if isinstance(value, list):
        result = []
        for item in value:
            if isinstance(item, str):
                name = item.strip()
            elif isinstance(item, dict):
                name = (
                    item.get("name")
                    or item.get("artist")
                    or item.get("tag")
                    or item.get("title")
                    or item.get("track")
                    or ""
                )
                name = str(name).strip()
            else:
                name = str(item).strip()

            if name:
                result.append(name)
        return result

    return []

def normalize_text_list(value: Any) -> list[str]:
    """Normalize comment/text fields into a clean list of strings."""
    if value is None:
        return []

    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []

    if isinstance(value, list):
        result = []
        for item in value:
            if isinstance(item, str):
                text = item.strip()
            elif isinstance(item, dict):
                text = (
                    item.get("comment")
                    or item.get("text")
                    or item.get("content")
                    or item.get("body")
                    or ""
                )
                text = str(text).strip()
            else:
                text = str(item).strip()

            if text:
                result.append(text)
        return result

    return []

def safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert a value to float."""
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    """Safely convert a value to int."""
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def avg(values: list[float]) -> float:
    """Return average value, or 0 if empty."""
    return round(mean(values), 4) if values else 0.0


def med(values: list[float]) -> float:
    """Return median value, or 0 if empty."""
    return round(median(values), 4) if values else 0.0


def top_counter(counter: Counter, n: int = 10) -> list[dict]:
    """Return Counter result as list of {name, count} dictionaries."""
    return [{"name": k, "count": v} for k, v in counter.most_common(n)]

def get_user_key(record: dict) -> str | None:  # sourcery skip: use-next
    """
    Find the most likely user identifier from a user/node record.
    """
    for key in ["username", "user_name", "user", "user_id", "id", "name"]:
        if key in record and record[key] is not None:
            return str(record[key])
    return None


def build_raw_user_index(raw_users_data: Any) -> dict[str, dict]:
    """
    Build username/user_id -> raw user record index.

    This lets us enrich clustered_nodes if clustered_nodes only contains
    username and community_id but raw_users contains top_artists/top_tags.
    """
    raw_users = to_record_list(raw_users_data)
    index = {}

    for user in raw_users:
        if not isinstance(user, dict):
            continue

        for key in ["username", "user_name", "user", "user_id", "id", "name"]:
            if key in user and user[key] is not None:
                index[str(user[key])] = user

    return index


def enrich_node_with_raw_user(node: dict, raw_user_index: dict[str, dict]) -> dict:
    """
    If clustered node lacks top_artists/top_tags & music or comment fields, fill them from raw_users.json.
    """
    enriched = dict(node)
    user_key = get_user_key(node)

    if user_key and user_key in raw_user_index:
        raw = raw_user_index[user_key]

        for field in [
            # music taste fields
            "top_artists",
            "top_tags",
            "top_tracks",
            "recent_tracks",

            # text / comment fields
            "comments",
            "top_comments",
            "recent_comments",
            "user_comments",

            # behavior / metadata fields
            "friends",
            "playcount",
            "total_playcount",
            "country",
            "registered_year",
            "age",
            "gender",
            "subscriber",
            "artist_count",
            "loved_tracks_count",
            "recent_track_count",
            "influence_score",
            "betweenness_score",
        ]:
            if not enriched.get(field) and raw.get(field):
                enriched[field] = raw[field]

    return enriched


# =========================
# Community aggregation
# =========================

def get_community_id(node: dict) -> str:
    """
    Read community id from common possible field names.
    """
    for key in ["community_id", "cluster_id", "community", "cluster"]:
        if key in node:
            return str(node[key])

    raise KeyError(f"Node does not contain community id: {node}")

def aggregate_community(members: list[dict]) -> dict:
    # sourcery skip: dict-assign-update-to-union
    """
    Aggregate music taste, listening behavior, social behavior, demographic features,
    and influential users across all members of a community.
    """
    artist_counter = Counter()
    tag_counter = Counter()
    track_counter = Counter()
    comment_counter = Counter()

    country_counter = Counter()
    gender_counter = Counter()
    registered_year_counter = Counter()

    playcounts = []
    total_playcounts = []
    artist_counts = []
    loved_tracks_counts = []
    recent_track_counts = []
    friend_counts = []
    ages = []
    subscriber_values = []

    influence_scores = []
    betweenness_scores = []
    influencers = []

    for member in members:
        # ---------- music preference ----------
        artist_counter.update(normalize_name_list(member.get("top_artists")))
        tag_counter.update(normalize_name_list(member.get("top_tags")))
        track_counter.update(normalize_name_list(member.get("top_tracks")))
        track_counter.update(normalize_name_list(member.get("recent_tracks")))

        for field in ["comments", "top_comments", "recent_comments", "user_comments"]:
            comment_counter.update(normalize_text_list(member.get(field)))

        # ---------- user identity ----------
        username = (
            member.get("username")
            or member.get("user_name")
            or member.get("user")
            or member.get("user_id")
            or member.get("id")
            or member.get("name")
            or "unknown"
        )

        # ---------- listening behavior ----------
        playcount = safe_float(member.get("playcount", member.get("total_playcount", 0)))
        total_playcount = safe_float(member.get("total_playcount", playcount))
        artist_count = safe_float(member.get("artist_count", 0))
        loved_tracks_count = safe_float(member.get("loved_tracks_count", 0))
        recent_track_count = safe_float(member.get("recent_track_count", 0))

        if playcount > 0:
            playcounts.append(playcount)
        if total_playcount > 0:
            total_playcounts.append(total_playcount)
        if artist_count > 0:
            artist_counts.append(artist_count)
        if loved_tracks_count > 0:
            loved_tracks_counts.append(loved_tracks_count)
        if recent_track_count > 0:
            recent_track_counts.append(recent_track_count)

        # ---------- social behavior ----------
        friends = member.get("friends", [])
        if isinstance(friends, list):
            friend_count = len(friends)
        else:
            friend_count = 0

        friend_counts.append(friend_count)

        # ---------- demographics / account behavior ----------
        country = str(member.get("country", "")).strip()
        if country:
            country_counter.update([country])

        gender = str(member.get("gender", "")).strip()
        if gender:
            gender_counter.update([gender])

        registered_year = safe_int(member.get("registered_year", 0))
        if registered_year > 0:
            registered_year_counter.update([registered_year])

        age = safe_float(member.get("age", 0))
        # age=0 normally means missing / unknown in this dataset
        if age > 0:
            ages.append(age)

        subscriber = member.get("subscriber", None)
        if isinstance(subscriber, bool):
            subscriber_values.append(1 if subscriber else 0)
        elif str(subscriber).lower() in ["true", "1", "yes"]:
            subscriber_values.append(1)
        elif str(subscriber).lower() in ["false", "0", "no"]:
            subscriber_values.append(0)

        # ---------- influence behavior ----------
        influence_score = safe_float(member.get("influence_score", 0))
        betweenness_score = safe_float(member.get("betweenness_score", 0))

        influence_scores.append(influence_score)
        betweenness_scores.append(betweenness_score)

        influencers.append({
            "username": str(username),
            "influence_score": influence_score,
            "betweenness_score": betweenness_score,
            "playcount": playcount,
            "friend_count": friend_count,
        })

    sorted_influencers = sorted(
        influencers,
        key=lambda x: (
            x["influence_score"],
            x["betweenness_score"],
            x["playcount"],
            x["friend_count"],
        ),
        reverse=True,
    )

    behavior_metrics = {
        "avg_playcount": avg(playcounts),
        "median_playcount": med(playcounts),
        "max_playcount": max(playcounts) if playcounts else 0,
        "avg_total_playcount": avg(total_playcounts),
        "avg_artist_count": avg(artist_counts),
        "avg_loved_tracks_count": avg(loved_tracks_counts),
        "avg_recent_track_count": avg(recent_track_counts),
        "avg_friend_count": avg(friend_counts),
        "median_friend_count": med(friend_counts),
        "subscriber_rate": round(avg(subscriber_values), 4) if subscriber_values else 0.0,
        "avg_age": avg(ages),
        "avg_influence_score": avg(influence_scores),
        "max_influence_score": max(influence_scores) if influence_scores else 0,
        "avg_betweenness_score": avg(betweenness_scores),
        "max_betweenness_score": max(betweenness_scores) if betweenness_scores else 0,
    }

    return {
        # original music profiling fields
        "top_artists": [a for a, _ in artist_counter.most_common(10)],
        "top_tags": [t for t, _ in tag_counter.most_common(10)],
        "top_tracks": [t for t, _ in track_counter.most_common(10)],
        "size": len(members),
        "top_comments": [c for c, _ in comment_counter.most_common(5)],

        # new behavior analysis fields
        "behavior_metrics": behavior_metrics,
        "top_countries": top_counter(country_counter, 5),
        "gender_distribution": top_counter(gender_counter, 5),
        "registered_year_distribution": top_counter(registered_year_counter, 10),

        # richer influencer output
        "top_influencers": sorted_influencers[:5],
        "high_activity_users": sorted(
            influencers,
            key=lambda x: x["playcount"],
            reverse=True,
        )[:5],
        "socially_connected_users": sorted(
            influencers,
            key=lambda x: x["friend_count"],
            reverse=True,
        )[:5],
    }
   
def percentile_level(value: float, values: list[float]) -> str:
    """
    Convert a raw metric into a relative level compared with other communities.
    This avoids asking the LLM to guess whether a number is high or low.
    """
    clean_values = sorted(v for v in values if v is not None and v > 0)

    if not clean_values or value <= 0:
        return "unknown"

    smaller_or_equal = sum(1 for v in clean_values if v <= value)
    rank = smaller_or_equal / len(clean_values)

    if rank >= 0.75:
        return "high"
    if rank >= 0.40:
        return "medium"
    return "low"


def influence_concentration(agg: dict) -> str:
    """
    Detect whether influence is concentrated in a few users or broadly distributed.
    """
    metrics = agg.get("behavior_metrics", {})
    avg_influence = metrics.get("avg_influence_score", 0)
    max_influence = metrics.get("max_influence_score", 0)

    if avg_influence <= 0 or max_influence <= 0:
        return "unknown"

    ratio = max_influence / avg_influence

    if ratio >= 8:
        return "highly concentrated"
    if ratio >= 4:
        return "moderately concentrated"
    return "broadly distributed"


def get_top_names(items: list[dict], key: str = "username", limit: int = 3) -> str:
    """
    Format top users or top categories into a readable phrase.
    """
    names = [str(item.get(key, "")).strip() for item in items[:limit] if item.get(key)]
    return ", ".join(names) if names else "Unavailable"


def build_behavior_pattern(relative: dict) -> str:
    """
    Convert relative behavior levels into a short interpretable pattern.
    """
    activity = relative.get("activity_level", "unknown")
    social = relative.get("social_level", "unknown")
    diversity = relative.get("diversity_level", "unknown")
    influence = relative.get("influence_concentration", "unknown")

    patterns = []

    if activity == "high" and social == "high":
        patterns.append("highly active and socially embedded")
    elif activity == "high" and social in ["low", "unknown"]:
        patterns.append("intensive listeners with weaker visible social ties")
    elif activity == "low" and social == "high":
        patterns.append("socially connected but comparatively lighter listeners")
    elif activity == "low":
        patterns.append("comparatively low-activity listeners")

    if diversity == "high":
        patterns.append("broad music explorers")
    elif diversity == "low":
        patterns.append("more focused or niche listeners")

    if influence == "highly concentrated":
        patterns.append("shaped by a small number of central users")
    elif influence == "broadly distributed":
        patterns.append("without a single dominant influence core")

    return "; ".join(patterns) if patterns else "mixed behavior pattern"


def build_behavior_evidence(agg: dict, relative: dict) -> list[str]:
    """
    Build a small number of natural evidence statements.
    These are used by the LLM as interpretation anchors, not as a checklist.
    """
    metrics = agg.get("behavior_metrics", {})
    evidence = []

    activity = relative.get("activity_level", "unknown")
    social = relative.get("social_level", "unknown")
    diversity = relative.get("diversity_level", "unknown")
    recent = relative.get("recent_activity_level", "unknown")

    if activity != "unknown":
        evidence.append(
            f"Listening activity is {activity} relative to other communities "
            f"(average playcount: {metrics.get('avg_playcount', 0)}, "
            f"median playcount: {metrics.get('median_playcount', 0)})."
        )

    if diversity != "unknown":
        evidence.append(
            f"Artist diversity is {diversity} relative to other communities "
            f"(average artist count: {metrics.get('avg_artist_count', 0)})."
        )

    if social != "unknown":
        evidence.append(
            f"Social connectedness is {social} relative to other communities "
            f"(average friend count: {metrics.get('avg_friend_count', 0)})."
        )

    if recent != "unknown":
        evidence.append(
            f"Recent listening activity is {recent} relative to other communities "
            f"(average recent track count: {metrics.get('avg_recent_track_count', 0)})."
        )

    concentration = relative.get("influence_concentration", "unknown")
    if concentration != "unknown":
        evidence.append(
            f"Influence appears {concentration} based on the gap between average and maximum influence score."
        )

    top_influencers = get_top_names(agg.get("top_influencers", []))
    if top_influencers != "Unavailable":
        evidence.append(f"Representative central users include {top_influencers}.")

    return evidence[:5]


def add_relative_behavior_context(community_aggs: dict[str, dict]) -> None:
    """
    Add relative behavior interpretation to each community.

    This is important because raw values such as avg_playcount=5000 are hard
    to interpret without comparing them against other communities.
    """
    avg_playcounts = [
        agg.get("behavior_metrics", {}).get("avg_playcount", 0)
        for agg in community_aggs.values()
    ]

    avg_friend_counts = [
        agg.get("behavior_metrics", {}).get("avg_friend_count", 0)
        for agg in community_aggs.values()
    ]

    avg_artist_counts = [
        agg.get("behavior_metrics", {}).get("avg_artist_count", 0)
        for agg in community_aggs.values()
    ]

    avg_recent_track_counts = [
        agg.get("behavior_metrics", {}).get("avg_recent_track_count", 0)
        for agg in community_aggs.values()
    ]

    subscriber_rates = [
        agg.get("behavior_metrics", {}).get("subscriber_rate", 0)
        for agg in community_aggs.values()
    ]

    for cid, agg in community_aggs.items():
        metrics = agg.get("behavior_metrics", {})

        relative = {
            "activity_level": percentile_level(
                metrics.get("avg_playcount", 0),
                avg_playcounts,
            ),
            "social_level": percentile_level(
                metrics.get("avg_friend_count", 0),
                avg_friend_counts,
            ),
            "diversity_level": percentile_level(
                metrics.get("avg_artist_count", 0),
                avg_artist_counts,
            ),
            "recent_activity_level": percentile_level(
                metrics.get("avg_recent_track_count", 0),
                avg_recent_track_counts,
            ),
            "subscriber_level": percentile_level(
                metrics.get("subscriber_rate", 0),
                subscriber_rates,
            ),
            "influence_concentration": influence_concentration(agg),
        }

        relative["behavior_pattern"] = build_behavior_pattern(relative)
        relative["behavior_evidence"] = build_behavior_evidence(agg, relative)

        agg["relative_behavior"] = relative 
# =========================
# LLM profiling
# =========================

def build_prompt(community_id: str, agg: dict) -> str:
    """
    Build the prompt sent to the LLM.
    """
    top_artists = ", ".join(agg["top_artists"]) if agg["top_artists"] else "Unknown"
    top_tags = ", ".join(agg["top_tags"]) if agg["top_tags"] else "Unknown"
    top_tracks = ", ".join(agg["top_tracks"]) if agg["top_tracks"] else "Unknown"
    top_comments = "\n".join(f"- {c}" for c in agg.get("top_comments", [])[:5]) or "Unavailable"
    top_influencers = "\n".join(
        f"- {item['username']} "
        f"(influence_score={item['influence_score']:.4f}, "
        f"betweenness_score={item.get('betweenness_score', 0):.6f}, "
        f"playcount={item.get('playcount', 0):.0f}, "
        f"friends={item.get('friend_count', 0)})"
        for item in agg.get("top_influencers", [])[:5]
    ) or "Unavailable"

    high_activity_users = "\n".join(
        f"- {item['username']} (playcount={item.get('playcount', 0):.0f})"
        for item in agg.get("high_activity_users", [])[:5]
    ) or "Unavailable"

    socially_connected_users = "\n".join(
        f"- {item['username']} (friends={item.get('friend_count', 0)})"
        for item in agg.get("socially_connected_users", [])[:5]
    ) or "Unavailable"

    behavior_metrics = agg.get("behavior_metrics", {})

    relative_behavior = agg.get("relative_behavior", {})
    behavior_pattern = relative_behavior.get("behavior_pattern", "mixed behavior pattern")
    behavior_evidence = "\n".join(
        f"- {item}" for item in relative_behavior.get("behavior_evidence", [])
    ) or "Unavailable"

    top_countries = ", ".join(
        f"{item['name']} ({item['count']})"
        for item in agg.get("top_countries", [])
    ) or "Unknown"

    return f"""
You are analyzing a music listener community discovered through social network analysis.

Community ID: {community_id}
Community data:
- Size: {agg["size"]} users
- Top artists: {top_artists}
- Top genre tags: {top_tags}
- Top tracks: {top_tracks}
- Representative comments:
{top_comments}
- Core influential users:
{top_influencers}

- High activity users by playcount:
{high_activity_users}

- Socially connected users by friend count:
{socially_connected_users}

- Interpreted behavior pattern:
{behavior_pattern}

- Behavior evidence:
{behavior_evidence}

- Additional context:
  - Top countries: {top_countries}
  - Average playcount: {behavior_metrics.get("avg_playcount", 0)}
  - Average artist count: {behavior_metrics.get("avg_artist_count", 0)}
  - Average friend count: {behavior_metrics.get("avg_friend_count", 0)}
  - Subscriber rate: {behavior_metrics.get("subscriber_rate", 0)}

Task:
Generate a human-readable profile and behavior analysis for this music listener community.

Rules:
1. Do not invent facts beyond the provided community data.
2. The label should be short, specific, and evocative.
3. The description should mainly describe the community's musical identity and listening culture.
4. The behavior_summary should synthesize the behavior pattern naturally. Do not list metrics one by one.
5. Mention only the most meaningful behavioral signals. Ignore weak or uninformative fields.
6. Connect behavior to music taste when possible, for example whether the community appears exploratory, highly engaged, socially embedded, or driven by a few central users.
7. Do not mechanically repeat field names such as average playcount, average friend count, or subscriber rate unless the number is important evidence.
8. Respond ONLY with a valid JSON object.
9. Do not include markdown, explanation, or code fences.

Required JSON format:
{{
  "label": "<short evocative name, max 5 words>",
  "description": "<2-3 sentences describing this community's musical identity and culture>",
  "behavior_summary": "<1-2 sentences about activity level, social connectedness, and influence pattern>"
}}
""".strip()


def extract_json_object(text: str) -> dict:
    # sourcery skip: reintroduce-else, swap-if-else-branches, use-contextlib-suppress, use-getitem-for-re-match-groups, use-named-expression
    """
    Robustly extract JSON object from LLM output.
    """
    text = text.strip()

    # Remove markdown code fences if the model accidentally returns them.
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fallback: extract the first {...} block.
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in LLM output: {text}")

    return json.loads(match.group(0))


def call_anthropic(prompt: str, model: str, max_tokens: int = 256) -> dict:
    """
    Call Anthropic Claude API.

    Requires:
    pip install anthropic
    export ANTHROPIC_API_KEY=your_key
    """
    import anthropic

    client = anthropic.Anthropic()

    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=0.2,
        messages=[
            {"role": "user", "content": prompt}
        ],
    )

    raw_text = message.content[0].text.strip()

    if (usage := getattr(message, "usage", None)):
        input_tokens = getattr(usage, "input_tokens", 0)
        output_tokens = getattr(usage, "output_tokens", 0)
        print(f"[TOKEN USAGE] input={input_tokens}, output={output_tokens}, total={input_tokens + output_tokens}")

    return extract_json_object(raw_text)


def call_openai(prompt: str, model: str, max_tokens: int = 256) -> dict:
    """
    Optional OpenAI backend.

    Requires:
    pip install openai
    export OPENAI_API_KEY=your_key
    """
    from openai import OpenAI

    client = OpenAI()

    response = client.chat.completions.create(
        model=model,
        temperature=0.2,
        max_tokens=max_tokens,
        messages=[
            {
                "role": "system",
                "content": "You are a music community profiling assistant. Always return valid JSON only.",
            },
            {"role": "user", "content": prompt},
        ],
    )

    raw_text = response.choices[0].message.content.strip()
    return extract_json_object(raw_text)

def call_deepseek(prompt: str, model: str, max_tokens: int = 256) -> dict:
    """
    Call DeepSeek API through OpenAI-compatible interface.

    Requires:
    pip install openai
    export DEEPSEEK_API_KEY=your_key
    """
    from openai import OpenAI

    client = OpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com",
    )

    response = client.chat.completions.create(
        model=model,
        temperature=0.2,
        max_tokens=max_tokens,
        messages=[
            {
                "role": "system",
                "content": "You are a music community profiling assistant. Always return valid JSON only.",
            },
            {"role": "user", "content": prompt},
        ],
    )

    raw_text = response.choices[0].message.content.strip()

    if getattr(response, "usage", None):
        input_tokens = getattr(response.usage, "prompt_tokens", 0)
        output_tokens = getattr(response.usage, "completion_tokens", 0)
        print(f"[TOKEN USAGE] input={input_tokens}, output={output_tokens}, total={input_tokens + output_tokens}")

    return extract_json_object(raw_text)

def heuristic_profile(community_id: str, agg: dict) -> dict:
    """
    Fallback profile when API fails or when --provider heuristic is used.
    This keeps the pipeline runnable without API credits.
    """
    tags = [t.lower() for t in agg.get("top_tags", [])]
    artists = agg.get("top_artists", [])

    tag_text = " ".join(tags)
    tag_text_space = tag_text.replace("-", " ")

    def has_any(keywords: list[str]) -> bool:
        return any(keyword in tag_text or keyword in tag_text_space for keyword in keywords)

    if has_any(["punk", "hardcore"]):
        label = "Punk Revival Circle"
    elif has_any(["metal"]):
        label = "Heavy Metal Loyalists"
    elif has_any(["hip hop", "hip-hop", "hiphop", "rap"]):
        label = "Hip-Hop Beat Seekers"
    elif has_any(["shoegaze", "dream pop"]):
        label = "Shoegaze Dream Listeners"
    elif has_any(["post rock", "post-rock"]):
        label = "Post-Rock Soundscapers"
    elif has_any(["folk", "acoustic"]):
        label = "Folk Acoustic Circle"
    elif has_any(["soul", "r&b", "rnb", "rhythm and blues"]):
        label = "Soul R&B Listeners"
    elif has_any(["k pop", "k-pop", "kpop"]):
        label = "K-Pop Fandom Cluster"
    elif has_any(["experimental", "avant garde", "avant-garde"]):
        label = "Experimental Sound Explorers"
    elif has_any(["electronic", "electronica", "ambient", "trip hop", "trip-hop", "techno", "house"]):
        label = "Atmospheric Electronica Fans"
    elif has_any(["indie", "alternative"]):
        label = "Indie Alternative Explorers"
    elif has_any(["pop"]):
        label = "Pop Melody Listeners"
    elif has_any(["jazz"]):
        label = "Jazz Fusion Listeners"
    elif has_any(["classical"]):
        label = "Classical Sound Admirers"
    elif has_any(["rock"]):
        label = "Rock Music Listeners"
    else:
        label = f"Community {community_id}"

    artist_part = ", ".join(artists[:3]) if artists else "a diverse set of artists"
    tag_part = ", ".join(agg.get("top_tags", [])[:3]) if agg.get("top_tags") else "mixed genres"

    description = (
        f"This community is centered around {artist_part}. "
        f"Their listening profile is strongly associated with {tag_part}, suggesting a shared taste shaped by these musical styles."
    )

    return {
        "label": label,
        "description": description,
    }


def profile_community(
    community_id: str,
    agg: dict,
    provider: str,
    model: str,
    max_tokens: int,
) -> dict:
    """
    Generate profile using selected provider.
    """
    if provider == "heuristic":
        return heuristic_profile(community_id, agg)

    prompt = build_prompt(community_id, agg)

    if provider == "anthropic":
        return call_anthropic(prompt, model=model, max_tokens=max_tokens)

    if provider == "openai":
        return call_openai(prompt, model=model, max_tokens=max_tokens)
    
    if provider == "deepseek":
        return call_deepseek(prompt, model=model, max_tokens=max_tokens)

    raise ValueError(f"Unsupported provider: {provider}")

def profile_community_with_retries(
    community_id: str,
    agg: dict,
    provider: str,
    model: str,
    max_tokens: int,
    llm_retries: int = 3,
    retry_sleep: float = 2.0,
    retry_backoff: float = 2.0,
) -> dict:
    """
    Try LLM profiling multiple times before falling back to heuristic.

    This is useful for temporary API failures, rate limits, unstable network,
    or occasional invalid JSON responses from the LLM.
    """
    if provider == "heuristic":
        return heuristic_profile(community_id, agg)

    attempts = max(1, llm_retries)
    last_error = None

    for attempt in range(1, attempts + 1):
        try:
            print(f"LLM attempt {attempt}/{attempts} for community {community_id}...")
            return profile_community(
                community_id=community_id,
                agg=agg,
                provider=provider,
                model=model,
                max_tokens=max_tokens,
            )

        except Exception as e:
            last_error = e
            print(f"LLM attempt {attempt}/{attempts} failed for community {community_id}: {e}")

            if attempt < attempts:
                sleep_seconds = retry_sleep * (retry_backoff ** (attempt - 1))
                print(f"Retrying after {sleep_seconds:.1f} seconds...")
                time.sleep(sleep_seconds)

    print(
        f"All {attempts} LLM attempts failed for community {community_id}. "
        f"Falling back to heuristic. Last error: {last_error}"
    )
    return heuristic_profile(community_id, agg)
# =========================
# Main pipeline
# =========================

def main():
    parser = argparse.ArgumentParser(
        description="Skill D: Generate semantic profiles for music listener communities."
    )

    parser.add_argument(
        "--clustered_nodes",
        required=True,
        help="Input JSON from Skill C. Each node should contain community_id.",
    )
    parser.add_argument(
        "--raw_users",
        required=False,
        default=None,
        help="Optional raw user JSON from Skill A. Used to fill missing top_artists/top_tags.",
    )
    parser.add_argument(
        "--out_file",
        required=True,
        help="Output path for community_profiles.json.",
    )

    parser.add_argument(
        "--provider",
        choices=["anthropic", "openai", "deepseek", "heuristic"],
        default="anthropic",
        help="LLM provider. Use heuristic to run without API.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model name. If omitted, a default model is selected based on provider.",
    )
    parser.add_argument(
        "--max_communities",
        type=int,
        default=None,
        help="Only profile the first N communities. Useful for API testing.",
    )
    parser.add_argument(
        "--max_tokens",
        type=int,
        default=256,
        help="Maximum tokens for LLM response.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.0,
        help="Seconds to sleep between API calls.",
    )
    parser.add_argument(
        "--llm_retries",
        type=int,
        default=3,
        help="Number of LLM attempts before falling back to heuristic.",
    )

    parser.add_argument(
        "--retry_sleep",
        type=float,
        default=2.0,
        help="Base seconds to sleep between failed LLM retry attempts.",
    )

    parser.add_argument(
        "--retry_backoff",
        type=float,
        default=2.0,
        help="Retry sleep multiplier. Example: 2 means 2s, 4s, 8s...",
    )

    args = parser.parse_args()

    # Check API keys before selecting default models.
    # If the selected API provider is unavailable, fall back to heuristic mode.
    if args.provider == "anthropic" and not os.getenv("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY not found. Falling back to heuristic.")
        args.provider = "heuristic"

    if args.provider == "openai" and not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY not found. Falling back to heuristic.")
        args.provider = "heuristic"
        
    if args.provider == "deepseek" and not os.getenv("DEEPSEEK_API_KEY"):
        print("DEEPSEEK_API_KEY not found. Falling back to heuristic.")
        args.provider = "heuristic"
        
    # Default models
    if args.model is None:
        if args.provider == "anthropic":
            args.model = "claude-sonnet-4-20250514"
        elif args.provider == "openai":
            args.model = "gpt-4o-mini"
        elif args.provider == "deepseek":
            args.model = "deepseek-v4-pro"
        else:
            args.model = "heuristic"

    # Load clustered nodes
    clustered_data = load_json(args.clustered_nodes)
    clustered_nodes = to_record_list(clustered_data)

    # Load raw users if provided
    raw_user_index = {}
    if args.raw_users:
        raw_users_data = load_json(args.raw_users)
        raw_user_index = build_raw_user_index(raw_users_data)

    # Group nodes by community
    communities = defaultdict(list)

    for node in clustered_nodes:
        if not isinstance(node, dict):
            continue

        enriched_node = enrich_node_with_raw_user(node, raw_user_index)
        cid = get_community_id(enriched_node)
        communities[cid].append(enriched_node)

    print(f"Found {len(communities)} communities.")
    
    # Aggregate all communities first, so that behavior can be interpreted relatively.
    community_aggs = {}

    for cid in communities:
        community_aggs[cid] = aggregate_community(communities[cid])

    add_relative_behavior_context(community_aggs)
    
    profiles = {}

    for i, cid in enumerate(sorted(communities.keys(), key=lambda x: int(x) if x.isdigit() else x)):
        if args.max_communities is not None and i >= args.max_communities:
            print(f"Stopped after {args.max_communities} communities for testing.")
            break

        members = communities[cid]
        print(f"Profiling community {cid} ({len(members)} members)...")

        agg = community_aggs[cid]

        try:
            llm_result = profile_community_with_retries(
                community_id=cid,
                agg=agg,
                provider=args.provider,
                model=args.model,
                max_tokens=args.max_tokens,
                llm_retries=args.llm_retries,
                retry_sleep=args.retry_sleep,
                retry_backoff=args.retry_backoff,
            )

            label = llm_result.get("label", f"Community {cid}")
            description = llm_result.get("description", "Profile unavailable.")
            behavior_summary = llm_result.get("behavior_summary", "Behavior summary unavailable.")

        except Exception as e:
            print(f"Unexpected profiling error for community {cid}: {e}")
            fallback = heuristic_profile(cid, agg)
            label = fallback["label"]
            description = fallback["description"]
            behavior_summary = "This behavior summary was not generated because the LLM call failed."

        profiles[str(cid)] = {
            "label": label,
            "description": description,
            "behavior_summary": behavior_summary,

            # music profile
            "size": agg["size"],
            "top_artists": agg["top_artists"],
            "top_tags": agg["top_tags"],
            "top_tracks": agg["top_tracks"],
            "top_comments": agg["top_comments"],

            # behavior analysis
            "behavior_metrics": agg["behavior_metrics"],
            "top_countries": agg["top_countries"],
            "gender_distribution": agg["gender_distribution"],
            "registered_year_distribution": agg["registered_year_distribution"],
            "top_influencers": agg["top_influencers"],
            "high_activity_users": agg["high_activity_users"],
            "socially_connected_users": agg["socially_connected_users"],
            "relative_behavior": agg.get("relative_behavior", {}),
        }
                
        print(f"  -> {label}")

        if args.sleep > 0:
            time.sleep(args.sleep)

    save_json(profiles, args.out_file)
    print(f"Community profiles saved to {args.out_file}")


if __name__ == "__main__":
    main()