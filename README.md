# GCP SRE Agent — Incident Tracker

This repository tracks all GCP incidents detected by the SRE Agent.

## How It Works

| PR Label | Meaning |
|----------|---------|
| 🟢 `auto-resolved` | Agent fixed it — review and close |
| 🔴 `high-risk` | Needs your action — follow steps in PR |

## Folders
- `incidents/resolved/` — LOW RISK incidents auto-fixed by agent
- `incidents/high-risk/` — HIGH RISK incidents needing human action
