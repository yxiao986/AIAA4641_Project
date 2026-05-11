"""
Music Community Analysis Agent
================================
Orchestration layer for the Music_Community_Agent project.
Coordinates five Skills via the shared_data/ directory.

Usage:
    python agent.py --query "Analyze the indie rock community" --seed_artist "Radiohead"
    python agent.py --query "Compare network clusters" --seed_artist "Radiohead" --compare
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

def stage_scrape(
    source: str,
    seed_artist: str | None,
    seed_user: str | None,
    max_users: int,
    lastfm_api_key: str,
):
    log("STAGE 1/5", f"Data scraping [{source}]  (Skill A)")

    if source == "hetrec":
        rc = run_skill("data-scraper", [
            "--source", "hetrec",
            "--seed_type", "artist",
            "--seed_value", seed_artist or "Radiohead",
            "--max_users", str(max_users),
            "--out_dir", str(SHARED_DATA),
        ])
    elif source == "api":
        rc = run_skill("data-scraper", [
            "--source", "api",
            "--seed_user", seed_user,
            "--max_users", str(max_users),
            "--api_key", lastfm_api_key,
            "--out_dir", str(SHARED_DATA),
        ])
    else:
        raise ValueError(f"Unsupported source: {source}")

    if rc != 0:
        log("STAGE 1/5", "Scraper exited with errors — continuing with existing data if any.")

    check_output(RAW_USERS_FILE, "raw_users.json")
    check_output(RAW_INTERACTIONS, "raw_interactions.json")
    
def stage_build_graph():
    log("STAGE 2/5", "Building social graph  (Skill B)")
    rc = run_skill("community-linker", [
        "--users_file",        str(RAW_USERS_FILE),
        "--interactions_file", str(RAW_INTERACTIONS),
        "--out_graph",         str(NETWORK_FILE),
    ])
    if rc != 0:
        log("STAGE 2/5", "Graph builder exited with errors.")
    check_output(NETWORK_FILE, "network.gml")


def stage_cluster(algorithm: str = "louvain", compare: bool = False):
    """
    Skill C — Community Detection
    If compare=True, runs both Louvain and Girvan-Newman algorithms.
    Returns a list of generated clustered_nodes JSON paths.
    """
    if compare:
        log("STAGE 3/5", "Community detection [COMPARE MODE: Louvain & Girvan-Newman] (Skill C)")
        out_louvain = SHARED_DATA / "clustered_nodes_louvain.json"
        out_gn = SHARED_DATA / "clustered_nodes_gn.json"
        
        # Run 1: Louvain
        run_skill("community-detector", [
            "--graph",      str(NETWORK_FILE),
            "--algorithm",  "louvain",
            "--out_file",   str(out_louvain)
        ])
        
        # Run 2: Girvan-Newman
        run_skill("community-detector", [
            "--graph",      str(NETWORK_FILE),
            "--algorithm",  "girvan_newman",
            "--out_file",   str(out_gn)
        ])
        return [out_louvain, out_gn]
    else:
        log("STAGE 3/5", f"Community detection [{algorithm}]  (Skill C)")
        rc = run_skill("community-detector", [
            "--graph",      str(NETWORK_FILE),
            "--algorithm",  algorithm,
            "--out_file",   str(CLUSTERED_NODES_FILE),
        ])
        if rc != 0:
            log("STAGE 3/5", "Clustering exited with errors.")
        check_output(CLUSTERED_NODES_FILE, "clustered_nodes.json")
        return [CLUSTERED_NODES_FILE]


def stage_profile(cluster_files: list):
    """
    Skill D — Semantic Profiler (LLM-powered)
    Handles multiple clustering files if in compare mode.
    Returns a list of generated profiles.
    """
    log("STAGE 4/5", f"LLM semantic profiling for {len(cluster_files)} cluster file(s)  (Skill D)")
    profile_files = []
    
    for c_file in cluster_files:
        # e.g. clustered_nodes_louvain.json -> profiles_louvain.json
        p_file = SHARED_DATA / f"profiles_{c_file.stem.replace('clustered_nodes_', '')}.json"
        
        rc = run_skill("community-profiler", [
            "--clustered_nodes", str(c_file),
            "--raw_users",       str(RAW_USERS_FILE),
            "--out_file",        str(p_file),
        ])
        if rc != 0:
            log("STAGE 4/5", f"Profiler exited with errors for {c_file.name}.")
        check_output(p_file, p_file.name)
        profile_files.append(p_file)
        
    return profile_files


def stage_visualize(query: str, cluster_files: list, profile_files: list, compare: bool):
    """
    Skill E — Visualisation & Report
    Passes comma-separated paths to Skill E if compare mode is enabled.
    """
    log("STAGE 5/5", "Visualisation & report generation  (Skill E)")
    
    c_files_str = ",".join(str(f) for f in cluster_files)
    p_files_str = ",".join(str(f) for f in profile_files)
    
    args = [
        "--graph",             str(NETWORK_FILE),
        "--clustered_nodes",   c_files_str,
        "--community_profiles",p_files_str,
        "--query",             query,
        "--out_dir",           str(SHARED_DATA),
    ]
    if compare:
        args.append("--compare")
        
    rc = run_skill("community-visualization", args)
    if rc != 0:
        log("STAGE 5/5", "Visualisation exited with errors.")
    check_output(FINAL_REPORT, "final_report.md")

# ── Summary ────────────────────────────────────────────────────────────────────

def print_summary():
    print("\n" + "═" * 60)
    print("  MUSIC COMMUNITY AGENT — PIPELINE COMPLETE")
    print("═" * 60)
    
    # Just a quick check to see what was generated
    for path in SHARED_DATA.iterdir():
        if path.is_file() and path.stat().st_size > 0:
            print(f"  ✅  {path.name:<30}")

    if FINAL_REPORT.exists():
        print(f"\n  📄 Open the final report:  {FINAL_REPORT}")
    print("═" * 60 + "\n")

# ── Entry point ────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Music Community Analysis Agent — orchestrates Skills A–E."
    )
    parser.add_argument("--query", required=True, help='Natural-language analysis goal')
    parser.add_argument("--source", choices=["hetrec", "api"], default="hetrec", help="Data source for Skill A")
    parser.add_argument("--seed_artist", default="Radiohead", help="Offline HetRec artist seed")
    parser.add_argument("--seed_user", default=None, help="Online Last.fm seed username")
    parser.add_argument("--max_users", type=int, default=150, help="Maximum number of users to scrape")
    parser.add_argument("--algorithm", default="louvain", choices=["louvain", "girvan_newman"], help="Community detection algorithm")
    parser.add_argument("--compare", action="store_true", help="Compare Louvain and Girvan-Newman algorithms")
    parser.add_argument("--lastfm_api_key", default=os.environ.get("LASTFM_API_KEY", ""), help="Last.fm API key")
    parser.add_argument("--skip_scrape", action="store_true", help="Skip Stage 1")
    return parser.parse_args()


def main():
    args = parse_args()

    if not args.skip_scrape:
        if args.source == "api" and not args.lastfm_api_key:
            print("ERROR: --source api requires --lastfm_api_key or LASTFM_API_KEY.")
            sys.exit(1)
        if args.source == "api" and not args.seed_user:
            print("ERROR: --source api requires --seed_user.")
            sys.exit(1)

    print("\n" + "═" * 60)
    print("  MUSIC COMMUNITY ANALYSIS AGENT")
    print(f"  Query      : {args.query}")
    print(f"  Source     : {args.source}")
    print(f"  Compare    : {'ON (Louvain vs Girvan-Newman)' if args.compare else 'OFF'}")
    print("═" * 60 + "\n")

    ensure_shared_data()
    t0 = time.time()

    # Stage 1: Scrape
    if args.skip_scrape:
        log("STAGE 1/5", "Skipping scrape (--skip_scrape flag set)")
    else:
        stage_scrape(args.source, args.seed_artist, args.seed_user, args.max_users, args.lastfm_api_key)

    # Stage 2: Graph Linker
    if not RAW_USERS_FILE.exists():
        log("AGENT", "raw_users.json not found — cannot continue.")
        sys.exit(1)
    stage_build_graph()

    # Stage 3: Community Detection (Compare Support)
    if not NETWORK_FILE.exists():
        log("AGENT", "network.gml not found — cannot continue.")
        sys.exit(1)
    cluster_files = stage_cluster(algorithm=args.algorithm, compare=args.compare)

    # Stage 4: Profiling (LLM)
    profile_files = stage_profile(cluster_files)

    # Stage 5: Visualization
    stage_visualize(args.query, cluster_files, profile_files, compare=args.compare)

    elapsed = time.time() - t0
    log("AGENT", f"Total pipeline time: {elapsed:.1f}s")
    print_summary()


if __name__ == "__main__":
    main()