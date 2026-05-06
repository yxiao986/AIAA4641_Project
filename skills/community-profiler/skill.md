---
name: community-profiler
description: "Generate human-readable semantic profiles for detected music listener communities using LLM or heuristic fallback. Use when the user says 'profile communities', 'label communities', 'summarize music communities', or 'generate community_profiles.json'."
author: ZuriZHAO
version: 0.1.0
tags:
  - llm
  - semantic-profiling
  - music-community
  - social-network-analysis
metadata:
  openclaw:
    requires:
      env:
        - ANTHROPIC_API_KEY optional
        - OPENAI_API_KEY optional
      bins:
        - python
    primaryEnv: ""
---

# Community Profiler Skill

You are helping the user convert detected music listener communities into human-readable semantic profiles.

This skill reads clustered community assignments, optionally enriches each node with raw user music data, aggregates community-level artists, tags, tracks, and optional comments, then generates a natural language label and description for each community.

## When to trigger

Activate when the user asks to profile music communities, label detected communities, summarize listener groups, generate semantic community descriptions, or when the Agent orchestrator reaches the semantic profiling stage after community detection.

## Workflow

### Step 1: Gather input

Check whether the required clustered node file exists at `shared_data/clustered_nodes.json`.

Optionally check whether `shared_data/raw_users.json` exists. This file is used to enrich clustered nodes with music preference fields such as `top_artists`, `top_tags`, `top_tracks`, `recent_tracks`, and optional comment fields.

Expected input files:

- `shared_data/clustered_nodes.json` from the Community Detector skill
- `shared_data/raw_users.json` from the Data Scraper skill, if available

Expected output file:

- `shared_data/community_profiles.json`

### Step 2: Execute

Run the semantic profiler Python script from the `community_profiler` skill folder.

For a safe local test without API keys, execute:

`python skills/community_profiler/main.py --clustered_nodes shared_data/clustered_nodes.json --raw_users shared_data/raw_users.json --out_file shared_data/community_profiles.json --provider heuristic`

If the current working directory is already `skills/community_profiler/`, execute:

`python main.py --clustered_nodes ../../shared_data/clustered_nodes.json --raw_users ../../shared_data/raw_users.json --out_file ../../shared_data/community_profiles.json --provider heuristic`

For Anthropic Claude profiling, execute:

`python skills/community_profiler/main.py --clustered_nodes shared_data/clustered_nodes.json --raw_users shared_data/raw_users.json --out_file shared_data/community_profiles.json --provider anthropic`

For OpenAI profiling, execute:

`python skills/community_profiler/main.py --clustered_nodes shared_data/clustered_nodes.json --raw_users shared_data/raw_users.json --out_file shared_data/community_profiles.json --provider openai`

Use `--max_communities 2` when testing API-based runs to reduce cost and verify that the pipeline works before profiling all communities.

### Step 3: Present results

Read the terminal output to confirm how many communities were found and profiled.

Confirm that `shared_data/community_profiles.json` has been generated successfully. The output should contain one profile per community, including fields such as:

- `label`
- `description`
- `top_artists`
- `top_tags`
- `top_tracks`
- `top_comments`
- `size`

If the upstream raw user data does not contain comments, explain that the profiler still works by using aggregated artists, genre tags, and tracks. Optional comment fields are supported when available.

## Error handling

- If `shared_data/clustered_nodes.json` is missing, instruct the user to run the Graph Linker and Community Detector skills first.
- If `shared_data/raw_users.json` is missing, continue only if `clustered_nodes.json` already contains music fields such as `top_artists` and `top_tags`; otherwise, warn that the generated profiles may be generic.
- If API keys are missing, suggest running with `--provider heuristic` or setting `ANTHROPIC_API_KEY` / `OPENAI_API_KEY`.
- If an API call fails, fall back to the heuristic profiler so that the full Agent pipeline can still complete.
- If the LLM returns malformed JSON, extract the first valid JSON object from the response; if extraction fails, use the heuristic fallback.
- If no comments are present in the raw user data, do not treat it as a failure. Report that this version profiles communities using artists, tags, and tracks, while remaining compatible with future comment-enriched data.
