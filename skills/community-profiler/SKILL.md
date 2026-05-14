---
name: community-profiler
description: "Generate human-readable semantic and behavioral profiles for detected music listener communities using Anthropic, OpenAI, DeepSeek, or heuristic fallback. Use when the user says 'profile communities', 'label communities', 'analyze community behavior', 'summarize music communities', or 'generate community_profiles.json'."
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
        - DEEPSEEK_API_KEY optional
      bins:
        - python
    primaryEnv: ""
---

# Community Profiler Skill

You are helping the user convert detected music listener communities into human-readable semantic and behavioral profiles.

This skill reads clustered community assignments, optionally enriches each node with raw user music and behavior data, aggregates community-level artists, tags, tracks, comments, listening activity, social connectedness, demographics, and influence signals, then generates a natural language label, description, and behavior summary for each community.  

## When to trigger

Activate when the user asks to profile music communities, label detected communities, analyze community behavior, summarize listener groups, generate semantic community descriptions, or when the Agent orchestrator reaches the semantic profiling stage after community detection.  

## Workflow

### Step 1: Gather input

Check whether the required clustered node file exists at `shared_data/clustered_nodes.json`.

Optionally check whether `shared_data/raw_users.json` exists. This file is used to enrich clustered nodes with music preference fields such as `top_artists`, `top_tags`, `top_tracks`, `recent_tracks`, and optional comment fields. It can also provide behavior and metadata fields such as `friends`, `playcount`, `total_playcount`, `country`, `registered_year`, `age`, `gender`, `subscriber`, `artist_count`, `loved_tracks_count`, `recent_track_count`, `influence_score`, and `betweenness_score`.  

Expected input files:

- `shared_data/clustered_nodes.json` from the Community Detector skill
- `shared_data/raw_users.json` from the Data Scraper skill, if available

If the previous Community Detector skill generated results from two methods, this skill can be run twice without changing the code:

- `shared_data/clustered_nodes_louvain.json`
- `shared_data/clustered_nodes_girvan_newman.json`

Each run should use one clustered node file and produce one corresponding community profile file.   

Expected output file:

- `shared_data/community_profiles.json`

For two-method community detection, expected outputs can be:

- `shared_data/profiles_louvain.json`
- `shared_data/profiles_girvan_newman.json`

These two files can later be used by the visualization/reporting skill for comparison mode.  

The input JSON can be a list of node dictionaries, a dictionary containing `users`, `nodes`, `data`, or `items`, or a mapping from username to user record.

### Step 2: Execute(for windows)

Run the semantic profiler Python script from the `community-profiler` skill folder.

This skill profiles one clustered community file at a time. If the previous skill generated two community detection results, such as Louvain and Girvan-Newman, do not change the code. Run this skill twice with different `--clustered_nodes` and `--out_file` arguments.

#### API keys

For Windows PowerShell, set the provider key before running:

```powershell
$env:ANTHROPIC_API_KEY="your_key"
$env:OPENAI_API_KEY="your_key"
$env:DEEPSEEK_API_KEY="your_key"
```
For macOS/Linux:
```bash
export ANTHROPIC_API_KEY=your_key
export OPENAI_API_KEY=your_key
export DEEPSEEK_API_KEY=your_key
```
`shared_data/raw_users.json` is optional.

For a safe local test without API keys, execute:    

### Single-method profiling

For a safe local test without API keys:  
```powershell
python skills/community-profiler/main.py `
  --clustered_nodes shared_data/clustered_nodes.json `
  --raw_users shared_data/raw_users.json `
  --out_file shared_data/community_profiles.json `
  --provider heuristic
```
For Anthropic Claude profiling:  
```powershell
python skills/community-profiler/main.py `
  --clustered_nodes shared_data/clustered_nodes.json `
  --raw_users shared_data/raw_users.json `
  --out_file shared_data/community_profiles.json `
  --provider anthropic  
```
For OpenAI profiling:  
```powershell
python skills/community-profiler/main.py `
  --clustered_nodes shared_data/clustered_nodes.json `
  --raw_users shared_data/raw_users.json `
  --out_file shared_data/community_profiles.json `
  --provider openai
```
For Deepseek profiling:  
```powershell
python skills/community-profiler/main.py `
  --clustered_nodes shared_data/clustered_nodes.json `
  --raw_users shared_data/raw_users.json `
  --out_file shared_data/community_profiles.json `
  --provider deepseek
```  
Use `--max_communities 2` when testing API-based runs to reduce cost and verify that the pipeline works before profiling all communities.    

The script retries failed LLM calls before falling back to the heuristic profiler. The default setting is:

```powershell
--llm_retries 3 `
--retry_sleep 2 `
--retry_backoff 2
```

### Two-method profiling

If the previous Community Detector skill generated both Louvain and Girvan-Newman results, run this skill twice.    
Generate Louvain profiles:  
```powershell
python skills/community-profiler/main.py `
  --clustered_nodes shared_data/clustered_nodes_louvain.json `
  --raw_users shared_data/raw_users.json `
  --out_file shared_data/profiles_louvain.json `
  --provider deepseek
```
Generate Girvan-Newman profiles:  
```powershell
python skills/community-profiler/main.py `
  --clustered_nodes shared_data/clustered_nodes_girvan_newman.json `
  --raw_users shared_data/raw_users.json `
  --out_file shared_data/profiles_girvan_newman.json `
  --provider deepseek
```
For local testing without API keys, replace `--provider deepseek` with `--provider heuristic`.  
For cost-controlled testing, add:`--max_communities 2` .  

Example:  
```powershell
python skills/community-profiler/main.py `
  --clustered_nodes shared_data/clustered_nodes_louvain.json `
  --raw_users shared_data/raw_users.json `
  --out_file shared_data/profiles_louvain.json `
  --provider deepseek `
  --max_communities 2
```
Provider notes:

- For Anthropic Claude profiling, use `--provider anthropic`.
- For OpenAI profiling, use `--provider openai`.
- For DeepSeek profiling, use `--provider deepseek`.
- For no-API local fallback profiling, use `--provider heuristic`.

If `--model` is omitted, the script selects a default model based on the provider.

Default models used by the script:

- Anthropic: `claude-sonnet-4-20250514`
- OpenAI: `gpt-4o-mini`
- DeepSeek: `deepseek-v4-pro`
- Heuristic: no model is used

### Step 3: Present results

Read the terminal output to confirm how many communities were found and profiled.

Confirm that the expected output profile file has been generated successfully.

For single-method mode, check:

- `shared_data/community_profiles.json`

For two-method mode, check:

- `shared_data/profiles_louvain.json`
- `shared_data/profiles_girvan_newman.json`   

The output should contain one profile per community, including fields such as:

- `label`
- `description`
- `behavior_summary`
- `size`
- `top_artists`
- `top_tags`
- `top_tracks`
- `top_comments`
- `behavior_metrics`
- `relative_behavior`
- `top_countries`
- `gender_distribution`
- `registered_year_distribution`
- `top_influencers`
- `high_activity_users`
- `socially_connected_users`

`behavior_metrics` stores raw aggregated statistics such as average playcount, average friend count, subscriber rate, and influence scores.

`relative_behavior` converts these raw numbers into relative levels such as high, medium, or low by comparing each community against other communities. This helps the LLM generate more natural behavior summaries instead of mechanically listing raw metrics.

`behavior_summary` is the final natural-language interpretation of activity level, social connectedness, artist diversity, and influence pattern.

If the upstream raw user data does not contain comments, explain that the profiler still works by using aggregated artists, genre tags, and tracks. Optional comment fields are supported when available.

## Error handling

- If `shared_data/clustered_nodes.json` is missing, instruct the user to run the Graph Linker and Community Detector skills first.
- If `shared_data/raw_users.json` is missing, continue only if `clustered_nodes.json` already contains music fields such as `top_artists` and `top_tags`; otherwise, warn that the generated profiles may be generic.
- If API keys are missing, the script automatically falls back to `--provider heuristic`. Users can still set `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`,or `DEEPSEEK_API_KEY` to enable LLM-based profiling.
- If an API call fails, retry the LLM call according to `--llm_retries`, `--retry_sleep`, and `--retry_backoff`. If all attempts fail, fall back to the heuristic profiler so that the full Agent pipeline can still complete.   
- If the terminal prints `[TOKEN USAGE] input=..., output=..., total=...`, this means one LLM call has completed and the script is reporting token usage for that community. Since the skill profiles communities one by one, total token usage generally increases with the number of communities.
- If the LLM returns malformed JSON, extract the first valid JSON object from the response; if extraction fails, use the heuristic fallback.
- If no comments are present in the raw user data, do not treat it as a failure. Report that this version profiles communities using artists, tags, and tracks, while remaining compatible with future comment-enriched data.
