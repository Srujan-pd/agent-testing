"""
incident_tracker.py
───────────────────
Tracks all incidents in a JSON file stored in the GitHub repo.
File: incidents/tracker.json

Structure:
{
  "incidents": {
    "INCIDENT_KEY": {
      "resource": "my-api",
      "condition": "cloud_run_5xx_errors",
      "summary": "...",
      "risk": "LOW" or "HIGH",
      "first_seen": "2026-03-27T09:00:00",
      "last_seen": "2026-03-27T09:00:00",
      "count": 3,
      "pr_url": "https://github.com/.../pull/1",
      "pr_number": 1,
      "branch": "resolved/20260327-...",
      "status": "open" or "closed",
      "resolved_at": null or "2026-03-27T10:00:00"
    }
  }
}

INCIDENT_KEY = resource:condition (e.g. "my-api:cloud_run_5xx_errors")
"""

import os
import json
from datetime import datetime, timedelta
from github import Github, GithubException


TRACKER_FILE = "incidents/tracker.json"


def _get_repo():
    token     = os.environ.get("GITHUB_TOKEN", "")
    repo_name = os.environ.get("GITHUB_REPO", "Srujan-pd/agent-testing")
    if not token:
        return None
    try:
        return Github(token).get_repo(repo_name)
    except GithubException as e:
        print(f"[TRACKER] ❌ GitHub connection failed: {str(e)}")
        return None


def _load_tracker(repo) -> dict:
    """Load tracker.json from GitHub repo."""
    try:
        file    = repo.get_contents(TRACKER_FILE, ref="main")
        content = file.decoded_content.decode("utf-8")
        data    = json.loads(content)
        print(f"[TRACKER] Loaded tracker — {len(data.get('incidents', {}))} incidents")
        return data
    except GithubException:
        # File does not exist yet — create empty tracker
        print(f"[TRACKER] tracker.json not found — creating new one")
        return {"incidents": {}, "last_updated": datetime.now().isoformat()}


def _save_tracker(repo, data: dict, message: str):
    """Save tracker.json back to GitHub repo on main branch."""
    content = json.dumps(data, indent=2, default=str)
    try:
        try:
            # Update existing file
            existing = repo.get_contents(TRACKER_FILE, ref="main")
            repo.update_file(
                path=TRACKER_FILE,
                message=message,
                content=content,
                sha=existing.sha,
                branch="main"
            )
        except GithubException:
            # Create new file
            repo.create_file(
                path=TRACKER_FILE,
                message=message,
                content=content,
                branch="main"
            )
        print(f"[TRACKER] ✅ tracker.json saved")
    except GithubException as e:
        print(f"[TRACKER] ❌ Failed to save tracker: {str(e)}")


def _make_key(alert_data: dict) -> str:
    """
    Create a unique key for this type of incident.
    Same resource + same condition = same key.
    """
    incident  = alert_data.get("incident", {})
    resource  = incident.get("resource_name",  "unknown")
    condition = incident.get("condition_name", "unknown")
    return f"{resource}:{condition}"


def check_duplicate(alert_data: dict) -> dict:
    """
    Check if this same error occurred in the last 7 days.

    Returns:
        {
          "is_duplicate": True/False,
          "existing_incident": {...} or None,
          "incident_key": "resource:condition",
          "occurrence_count": N
        }
    """
    repo = _get_repo()
    if repo is None:
        return {"is_duplicate": False, "existing_incident": None,
                "incident_key": "", "occurrence_count": 0}

    key     = _make_key(alert_data)
    tracker = _load_tracker(repo)
    incidents = tracker.get("incidents", {})

    if key not in incidents:
        return {"is_duplicate": False, "existing_incident": None,
                "incident_key": key, "occurrence_count": 0}

    existing  = incidents[key]
    last_seen = datetime.fromisoformat(existing["last_seen"])
    now       = datetime.now()
    days_ago  = (now - last_seen).days

    # Same error seen within 7 days AND PR still open
    if days_ago <= 7 and existing.get("status") == "open":
        print(f"[TRACKER] ⚠️  DUPLICATE — '{key}' seen {days_ago} days ago, count: {existing['count']}")
        return {
            "is_duplicate":      True,
            "existing_incident": existing,
            "incident_key":      key,
            "occurrence_count":  existing["count"],
            "days_ago":          days_ago
        }

    return {"is_duplicate": False, "existing_incident": None,
            "incident_key": key, "occurrence_count": existing.get("count", 0)}


def record_incident(alert_data: dict, risk: str, pr_url: str, pr_number: int, branch: str):
    """
    Record a new incident in tracker.json.
    Called after a new PR is created.
    """
    repo = _get_repo()
    if repo is None:
        return

    key      = _make_key(alert_data)
    incident = alert_data.get("incident", {})
    now      = datetime.now().isoformat()
    tracker  = _load_tracker(repo)

    tracker["incidents"][key] = {
        "resource":    incident.get("resource_name",     "unknown"),
        "condition":   incident.get("condition_name",    "unknown"),
        "summary":     incident.get("summary",           "Unknown"),
        "project":     incident.get("scoping_project_id","poc-genai-chatbot"),
        "risk":        risk,
        "first_seen":  now,
        "last_seen":   now,
        "count":       1,
        "pr_url":      pr_url,
        "pr_number":   pr_number,
        "branch":      branch,
        "status":      "open",
        "resolved_at": None
    }
    tracker["last_updated"] = now

    _save_tracker(repo, tracker, f"[TRACKER] New incident: {key}")
    print(f"[TRACKER] ✅ Recorded new incident: {key}")


def update_occurrence(alert_data: dict, incident_key: str):
    """
    Increment occurrence count for a duplicate incident.
    Add a comment to the existing PR saying error occurred again.
    Called when a duplicate is detected.
    """
    repo = _get_repo()
    if repo is None:
        return

    tracker   = _load_tracker(repo)
    incidents = tracker.get("incidents", {})

    if incident_key not in incidents:
        return

    existing          = incidents[incident_key]
    existing["count"] = existing.get("count", 1) + 1
    existing["last_seen"] = datetime.now().isoformat()
    tracker["last_updated"] = datetime.now().isoformat()

    # Add comment to existing PR
    pr_number = existing.get("pr_number")
    if pr_number:
        _add_pr_comment(repo, pr_number, alert_data, existing["count"])

    _save_tracker(repo, tracker, f"[TRACKER] Updated occurrence #{existing['count']}: {incident_key}")
    print(f"[TRACKER] ✅ Updated occurrence count to {existing['count']}")


def _add_pr_comment(repo, pr_number: int, alert_data: dict, count: int):
    """Add a comment to an existing PR saying the error occurred again."""
    incident  = alert_data.get("incident", {})
    summary   = incident.get("summary", "Unknown")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

    comment_lines = [
        f"## ⚠️ SAME ERROR OCCURRED AGAIN — Occurrence #{count}",
        "",
        f"**Time:** {timestamp}",
        "",
        f"**Alert:** {summary}",
        "",
        "---",
        "",
        f"This is the **{_ordinal(count)} time** this error has occurred.",
        "",
        "The PR is still open and the issue has NOT been resolved.",
        "",
        "**Please action this PR immediately to prevent further recurrence.**",
        "",
        "---",
        "*Auto-comment by GCP SRE Agent*",
    ]

    comment = "\n".join(comment_lines)

    try:
        pr = repo.get_pull(pr_number)
        pr.create_issue_comment(comment)
        print(f"[TRACKER] ✅ Added comment to PR #{pr_number}")
    except GithubException as e:
        print(f"[TRACKER] ❌ Failed to comment on PR: {str(e)}")


def _ordinal(n: int) -> str:
    """Convert number to ordinal string: 1 → 1st, 2 → 2nd etc."""
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10 if n % 100 not in [11,12,13] else 0, "th")
    return f"{n}{suffix}"


def get_all_open_incidents() -> list:
    """
    Returns all incidents that are still open.
    Used by Monday report.
    """
    repo = _get_repo()
    if repo is None:
        return []

    tracker   = _load_tracker(repo)
    incidents = tracker.get("incidents", {})
    open_list = []

    for key, inc in incidents.items():
        if inc.get("status") == "open":
            # Check if PR is actually still open on GitHub
            pr_number = inc.get("pr_number")
            if pr_number:
                try:
                    pr = repo.get_pull(pr_number)
                    if pr.state == "closed":
                        # PR was closed — update tracker
                        inc["status"]      = "closed"
                        inc["resolved_at"] = datetime.now().isoformat()
                        continue
                except GithubException:
                    pass
            open_list.append({"key": key, **inc})

    print(f"[TRACKER] Found {len(open_list)} open incidents")
    return open_list


def get_unresolved_high_risk(days: int = 7) -> list:
    """
    Returns HIGH RISK incidents that have been open for more than N days.
    Used to create escalation issues on GitHub.
    """
    open_incidents = get_all_open_incidents()
    cutoff         = datetime.now() - timedelta(days=days)
    unresolved     = []

    for inc in open_incidents:
        if inc.get("risk") == "HIGH":
            first_seen = datetime.fromisoformat(inc["first_seen"])
            if first_seen < cutoff:
                days_open = (datetime.now() - first_seen).days
                inc["days_open"] = days_open
                unresolved.append(inc)

    print(f"[TRACKER] Found {len(unresolved)} unresolved HIGH RISK incidents > {days} days old")
    return unresolved
