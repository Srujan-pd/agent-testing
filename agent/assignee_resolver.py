"""
assignee_resolver.py
────────────────────
Resolves who gets assigned to a ticket.

Rules:
  1. Check resource_owners first (most specific)
  2. Check owns_conditions next
  3. Fall back to default_assignee

Round-robin + no repeat:
  If the last ticket for this resource was assigned to Person A,
  assign the next one to Person B (if team has multiple members).
  Stored in assignment_history in tracker.json.
"""

import json
import os


def _load_config() -> dict:
    try:
        with open("config.json") as f:
            return json.load(f)
    except Exception:
        return {}


def _get_member(config: dict, github_username: str) -> dict:
    """Find a team member by github username."""
    for m in config.get("team", {}).get("members", []):
        if m.get("github_username") == github_username:
            return m
    return {}


def get_assignee(alert_data: dict, last_assignee: str = None) -> dict:
    """
    Returns the correct assignee for this alert.

    last_assignee: github_username of who was assigned last time
                   for this same resource+condition.
                   If provided and team has multiple members,
                   a different person is chosen.

    Returns:
        {
          "github_username": "Srujan-pd",
          "email": "srujan.sane@primisdigital.com",
          "name": "Srujan Sane",
          "reason": "Why chosen"
        }
    """
    config   = _load_config()
    team     = config.get("team", {})
    members  = team.get("members", [])
    incident = alert_data.get("incident", {})
    resource  = incident.get("resource_name",  "unknown")
    condition = incident.get("condition_name", "unknown")

    if not members:
        return {
            "github_username": team.get("default_assignee", ""),
            "email": "",
            "name": team.get("default_assignee", ""),
            "reason": "No members configured"
        }

    # ── STEP 1: Find candidates who own this resource ─────────
    resource_candidates = [
        m for m in members
        if resource in m.get("owns_resources", [])
    ]

    # ── STEP 2: Find candidates who own this condition ────────
    condition_candidates = [
        m for m in members
        if condition in m.get("owns_conditions", [])
    ]

    # Pick candidate pool — most specific first
    candidates = resource_candidates or condition_candidates or members

    # ── STEP 3: Avoid re-assigning to same person ─────────────
    if last_assignee and len(candidates) > 1:
        other_candidates = [
            c for c in candidates
            if c.get("github_username") != last_assignee
        ]
        if other_candidates:
            candidates = other_candidates
            print(f"[ASSIGNEE] Avoiding re-assign to '{last_assignee}' "
                  f"— switching to different team member")

    chosen = candidates[0]
    reason = (
        f"Resource owner of '{resource}'" if resource_candidates else
        f"Condition owner of '{condition}'" if condition_candidates else
        "Default team member"
    )

    print(f"[ASSIGNEE] Assigned to: {chosen.get('name')} — {reason}")
    return {**chosen, "reason": reason}


def get_cc_emails(alert_data: dict) -> list:
    """Returns CC list: assignee + global CCs + monday recipients."""
    config    = _load_config()
    team      = config.get("team", {})
    assignee  = get_assignee(alert_data)
    cc        = list(team.get("cc_emails", []))

    assignee_email = assignee.get("email", "")
    if assignee_email and assignee_email not in cc:
        cc.append(assignee_email)

    for email in team.get("monday_report_recipients", []):
        if email not in cc:
            cc.append(email)

    return list(set(cc))


def get_monday_recipients() -> list:
    config = _load_config()
    return config.get("team", {}).get("monday_report_recipients", [])


def get_all_assignee_emails(open_incidents: list) -> dict:
    """Groups open incidents by assignee for individual Monday emails."""
    grouped = {}
    for inc in open_incidents:
        email    = inc.get("assignee_email", "")
        name     = inc.get("assignee_name", "Team")
        username = inc.get("assignee_github", "")
        if not email:
            continue
        if email not in grouped:
            grouped[email] = {
                "name": name,
                "github_username": username,
                "incidents": []
            }
        grouped[email]["incidents"].append(inc)
    return grouped
