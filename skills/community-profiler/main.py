import argparse
import json
import os
import re
import time
from pathlib import Path
from collections import Counter, defaultdict
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
            "top_artists",
            "top_tags",
            "top_tracks",
            "recent_tracks",
            "comments",
            "top_comments",
            "recent_comments",
            "user_comments",
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
    Aggregate top artists, tags, tracks, comments, and influential users
    across all members of a community.
    """
    artist_counter = Counter()
    tag_counter = Counter()
    track_counter = Counter()
    comment_counter = Counter()
    influencers = []

    for member in members:
        artist_counter.update(normalize_name_list(member.get("top_artists")))
        tag_counter.update(normalize_name_list(member.get("top_tags")))
        track_counter.update(normalize_name_list(member.get("top_tracks")))
        track_counter.update(normalize_name_list(member.get("recent_tracks")))

        for field in ["comments", "top_comments", "recent_comments", "user_comments"]:
            comment_counter.update(normalize_text_list(member.get(field)))

        username = (
            member.get("username")
            or member.get("user_name")
            or member.get("user")
            or member.get("user_id")
            or member.get("id")
            or member.get("name")
            or "unknown"
        )

        try:
            influence_score = float(member.get("influence_score", 0))
        except (TypeError, ValueError):
            influence_score = 0.0

        influencers.append({
            "username": str(username),
            "influence_score": influence_score,
        })

    return {
        "top_artists": [a for a, _ in artist_counter.most_common(10)],
        "top_tags": [t for t, _ in tag_counter.most_common(10)],
        "top_tracks": [t for t, _ in track_counter.most_common(10)],
        "size": len(members),
        "top_comments": [c for c, _ in comment_counter.most_common(5)],
        "top_influencers": sorted(
            influencers,
            key=lambda x: x["influence_score"],
            reverse=True,
        )[:5],
    }

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
        f"- {item['username']} (influence_score={item['influence_score']:.4f})"
        for item in agg.get("top_influencers", [])[:5]
    ) or "Unavailable"

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
- Core influential users by influence_score:
{top_influencers}

Task:
Generate a human-readable profile for this music listener community.

Rules:
1. Do not invent facts beyond the provided artists, tags, tracks, and comments.
2. The label should be short, specific, and evocative.
3. The description should summarize the community's musical identity and listening culture.
4. Respond ONLY with a valid JSON object.
5. Do not include markdown, explanation, or code fences.
6. Pay special attention to the users with the highest influence_score when describing the community's core members and culture.  

Required JSON format:
{{
  "label": "<short evocative name, max 5 words>",
  "description": "<2-3 sentences describing this community's musical identity and culture>"
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

    profiles = {}

    for i, cid in enumerate(sorted(communities.keys(), key=lambda x: int(x) if x.isdigit() else x)):
        if args.max_communities is not None and i >= args.max_communities:
            print(f"Stopped after {args.max_communities} communities for testing.")
            break

        members = communities[cid]
        print(f"Profiling community {cid} ({len(members)} members)...")

        agg = aggregate_community(members)

        try:
            llm_result = profile_community(
                community_id=cid,
                agg=agg,
                provider=args.provider,
                model=args.model,
                max_tokens=args.max_tokens,
            )

            label = llm_result.get("label", f"Community {cid}")
            description = llm_result.get("description", "Profile unavailable.")

        except Exception as e:
            print(f"LLM error for community {cid}: {e}")
            fallback = heuristic_profile(cid, agg)
            label = fallback["label"]
            description = fallback["description"]

        profiles[str(cid)] = {
            "label": label,
            "description": description,

            # These fields are not used by the visualization step.
            # The visualization rebuilds top_artists/top_tags from graph.gml,
            # and only reads label/description from community_profiles.json.
            # "top_artists": agg["top_artists"],
            # "top_tags": agg["top_tags"],
            # "top_tracks": agg["top_tracks"],
            # "top_comments": agg["top_comments"],
            # "size": agg["size"],
        }
        
        print(f"  -> {label}")

        if args.sleep > 0:
            time.sleep(args.sleep)

    save_json(profiles, args.out_file)
    print(f"Community profiles saved to {args.out_file}")


if __name__ == "__main__":
    main()