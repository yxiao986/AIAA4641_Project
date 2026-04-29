"""
Music Community Analysis Agent
================================
Orchestration layer for the Music_Community_Agent project.
Coordinates five Skills via the shared_data/ directory.

Usage:
    python agent.py --query "Analyze the indie rock community" --seed_artist "Radiohead"
    python agent.py --query "Find top influencers in jazz" --seed_artist "Miles Davis" --max_users 200
"""

import argparse
import json
import os
import sys
import time
import subprocess
from datetime import datetime
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT_DIR      = Path(__file__).parent
SHARED_DATA   = ROOT_DIR / "shared_data"
SKILLS_DIR    = ROOT_DIR / "skills"

RAW_USERS_FILE       = SHARED_DATA / "raw_users.json"
RAW_INTERACTIONS     = SHARED_DATA / "raw_interactions.json"
NETWORK_FILE         = SHARED_DATA / "network.gml"
CLUSTERED_NODES_FILE = SHARED_DATA / "clustered_nodes.json"
COMMUNITY_PROFILES   = SHARED_DATA / "community_profiles.json"
FINAL_REPORT         = SHARED_DATA / "final_report.md"

# ── Helpers ───────────────────────────────────────────────────────────────────

def log(stage: str, msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{stage}] {msg}")

def ensure_shared_data():
    SHARED_DATA.mkdir(exist_ok=True)

def run_skill(skill_name: str, args: list[str]) -> int:
    """
    Invoke a skill's main.py as a subprocess, passing extra CLI args.
    Returns the process exit code.
    """
    skill_main = SKILLS_DIR / skill_name / "main.py"
    if not skill_main.exists():
        log("AGENT", f"⚠️  Skill not found: {skill_main}  — skipping.")
        return 1

    cmd = [sys.executable, str(skill_main)] + args
    log("AGENT", f"▶ Running {skill_name}:  {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=False)
    return result.returncode

def check_output(path: Path, label: str) -> bool:
    if path.exists() and path.stat().st_size > 0:
        log("AGENT", f"✅ {label} → {path.name}")
        return True
    log("AGENT", f"❌ {label} missing or empty — pipeline may be incomplete.")
    return False

# ── Pipeline stages ───────────────────────────────────────────────────────────

def stage_scrape(seed_artist: str, max_users: int, lastfm_api_key: str):
    """
    Skill A — Data Scraper
    Input : seed artist name, max_users, Last.fm API key
    Output: shared_data/raw_users.json, shared_data/raw_interactions.json
    """
    log("STAGE 1/5", "Data scraping via Last.fm API  (Skill A)")
    rc = run_skill("skill_a_scraper", [
        "--seed_artist", seed_artist,
        "--max_users",   str(max_users),
        "--api_key",     lastfm_api_key,
        "--out_dir",     str(SHARED_DATA),
    ])
    if rc != 0:
        log("STAGE 1/5", "Scraper exited with errors — continuing with existing data if any.")
    check_output(RAW_USERS_FILE, "raw_users.json")
    check_output(RAW_INTERACTIONS, "raw_interactions.json")


def stage_build_graph():
    """
    Skill B — Graph Linker
    Input : shared_data/raw_users.json, shared_data/raw_interactions.json
    Output: shared_data/network.gml
    """
    log("STAGE 2/5", "Building social graph  (Skill B)")
    rc = run_skill("skill_b_linker", [
        "--users_file",        str(RAW_USERS_FILE),
        "--interactions_file", str(RAW_INTERACTIONS),
        "--out_graph",         str(NETWORK_FILE),
    ])
    if rc != 0:
        log("STAGE 2/5", "Graph builder exited with errors.")
    check_output(NETWORK_FILE, "network.gml")


def stage_cluster(algorithm: str = "louvain"):
    """
    Skill C — Community Detection
    Input : shared_data/network.gml
    Output: shared_data/clustered_nodes.json
    """
    log("STAGE 3/5", f"Community detection [{algorithm}]  (Skill C)")
    rc = run_skill("skill_c_cluster", [
        "--graph",      str(NETWORK_FILE),
        "--algorithm",  algorithm,
        "--out_file",   str(CLUSTERED_NODES_FILE),
    ])
    if rc != 0:
        log("STAGE 3/5", "Clustering exited with errors.")
    check_output(CLUSTERED_NODES_FILE, "clustered_nodes.json")


def stage_profile():
    """
    Skill D — Semantic Profiler (LLM-powered)
    Input : shared_data/clustered_nodes.json, shared_data/raw_users.json
    Output: shared_data/community_profiles.json
    """
    log("STAGE 4/5", "LLM semantic profiling  (Skill D)")
    rc = run_skill("skill_d_profiler", [
        "--clustered_nodes", str(CLUSTERED_NODES_FILE),
        "--raw_users",       str(RAW_USERS_FILE),
        "--out_file",        str(COMMUNITY_PROFILES),
    ])
    if rc != 0:
        log("STAGE 4/5", "Profiler exited with errors.")
    check_output(COMMUNITY_PROFILES, "community_profiles.json")


def stage_visualize(query: str):
    """
    Skill E — Visualisation & Report
    Input : shared_data/network.gml, shared_data/clustered_nodes.json,
            shared_data/community_profiles.json
    Output: shared_data/network_viz.html (or .png), shared_data/final_report.md
    """
    log("STAGE 5/5", "Visualisation & report generation  (Skill E)")
    rc = run_skill("skill_e_viz", [
        "--graph",             str(NETWORK_FILE),
        "--clustered_nodes",   str(CLUSTERED_NODES_FILE),
        "--community_profiles",str(COMMUNITY_PROFILES),
        "--query",             query,
        "--out_dir",           str(SHARED_DATA),
    ])
    if rc != 0:
        log("STAGE 5/5", "Visualisation exited with errors.")
    check_output(FINAL_REPORT, "final_report.md")

# ── Summary ────────────────────────────────────────────────────────────────────

def print_summary():
    print("\n" + "═" * 60)
    print("  MUSIC COMMUNITY AGENT — PIPELINE COMPLETE")
    print("═" * 60)
    outputs = [
        (RAW_USERS_FILE,       "Raw user data"),
        (RAW_INTERACTIONS,     "Raw interactions"),
        (NETWORK_FILE,         "Social graph (GML)"),
        (CLUSTERED_NODES_FILE, "Clustered nodes"),
        (COMMUNITY_PROFILES,   "LLM community profiles"),
        (FINAL_REPORT,         "Final Markdown report"),
    ]
    for path, label in outputs:
        status = "✅" if (path.exists() and path.stat().st_size > 0) else "❌"
        print(f"  {status}  {label:<28} {path.relative_to(ROOT_DIR)}")

    if FINAL_REPORT.exists():
        print(f"\n  📄 Open the report:  {FINAL_REPORT}")
    print("═" * 60 + "\n")

# ── Entry point ────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Music Community Analysis Agent — orchestrates Skills A–E."
    )
    parser.add_argument(
        "--query", required=True,
        help='Natural-language analysis goal, e.g. "Analyze indie rock community"'
    )
    parser.add_argument(
        "--seed_artist", required=True,
        help="Seed artist name for Last.fm scraping, e.g. \"Radiohead\""
    )
    parser.add_argument(
        "--max_users", type=int, default=150,
        help="Maximum number of users to scrape (default: 150)"
    )
    parser.add_argument(
        "--algorithm", default="louvain", choices=["louvain", "girvan_newman"],
        help="Community detection algorithm (default: louvain)"
    )
    parser.add_argument(
        "--lastfm_api_key", default=os.environ.get("LASTFM_API_KEY", ""),
        help="Last.fm API key (or set LASTFM_API_KEY env var)"
    )
    parser.add_argument(
        "--skip_scrape", action="store_true",
        help="Skip Stage 1 (use existing raw_users.json / raw_interactions.json)"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if not args.lastfm_api_key and not args.skip_scrape:
        print("ERROR: Last.fm API key is required. Set --lastfm_api_key or export LASTFM_API_KEY.")
        sys.exit(1)

    print("\n" + "═" * 60)
    print("  MUSIC COMMUNITY ANALYSIS AGENT")
    print(f"  Query      : {args.query}")
    print(f"  Seed artist: {args.seed_artist}")
    print(f"  Max users  : {args.max_users}")
    print(f"  Algorithm  : {args.algorithm}")
    print("═" * 60 + "\n")

    ensure_shared_data()
    t0 = time.time()

    # ── Stage 1: Scrape ──────────────────────────────────────────────────────
    if args.skip_scrape:
        log("STAGE 1/5", "Skipping scrape (--skip_scrape flag set)")
    else:
        stage_scrape(args.seed_artist, args.max_users, args.lastfm_api_key)

    # ── Stage 2: Build Graph ─────────────────────────────────────────────────
    if not RAW_USERS_FILE.exists():
        log("AGENT", "raw_users.json not found — cannot continue. Run without --skip_scrape.")
        sys.exit(1)
    stage_build_graph()

    # ── Stage 3: Cluster ─────────────────────────────────────────────────────
    if not NETWORK_FILE.exists():
        log("AGENT", "network.gml not found — cannot continue.")
        sys.exit(1)
    stage_cluster(algorithm=args.algorithm)

    # ── Stage 4: Profile (LLM) ───────────────────────────────────────────────
    stage_profile()

    # ── Stage 5: Visualise & Report ──────────────────────────────────────────
    stage_visualize(query=args.query)

    elapsed = time.time() - t0
    log("AGENT", f"Total pipeline time: {elapsed:.1f}s")
    print_summary()


if __name__ == "__main__":
    main()
