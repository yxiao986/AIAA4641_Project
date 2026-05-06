---
name: community-detector
version: 0.1.0
description: A modular skill that detects communities in a social network using Louvain or Girvan-Newman algorithms.
tags: [graph, community-detection, clustering, python]
---

# Community Detector Skill

This Skill is part of the Music Community Analysis Agent. 
It takes a network graph (.gml) as input, runs community detection algorithms, and outputs a JSON file mapping each user to a specific `community_id`.

## Inputs
- `shared_data/network.gml`

## Outputs
- `shared_data/clustered_nodes.json`