"""
monday_report.py
────────────────
Generates the Monday morning report of all unresolved incidents.

1. Gets all open PRs from incident tracker
2. Creates a GitHub Issue listing all unresolved incidents
3. Sends a formatted summary email
4. Triggered by Cloud Scheduler every Monday at 9am
"""

import os
from datetime import datetime
from github import Github, GithubException
from incident_tracker import get_all_open_incidents, get_unresolved_high_risk


def _get_repo():
    token     = os.environ.get("GITHUB_TOKEN", "")
    repo_name = os.environ.get("GITHUB_REPO", "Srujan-pd/agent-testing")
    if not token:
        return None
    try:
        return Github(token).get_repo(repo_name)
    except GithubException:
        return None


def generate_monday_report() -> dict:
    """
    Main function — called every Monday morning.

    1. Gets all open incidents from tracker
    2. Creates a GitHub Issue with full summary
    3. Returns data for email notification

    Returns:
        dict with report_data for notifier.py to send email
    """
    print(f"[MONDAY] Generating Monday morning report...")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    week_date = datetime.now().strftime("%B %d, %Y")

    open_incidents    = get_all_open_incidents()
    high_risk_open    = [i for i in open_incidents if i.get("risk") == "HIGH"]
    low_risk_open     = [i for i in open_incidents if i.get("risk") == "LOW"]
    critical_unresolved = get_unresolved_high_risk(days=7)

    print(f"[MONDAY] Open: {len(open_incidents)} total, "
          f"{len(high_risk_open)} HIGH, {len(low_risk_open)} LOW")
    print(f"[MONDAY] Critical (HIGH + 7 days): {len(critical_unresolved)}")

    # Create GitHub Issue with full report
    issue_url = _create_monday_issue(
        week_date, timestamp,
        open_incidents, high_risk_open,
        low_risk_open, critical_unresolved
    )

    return {
        "week_date":            week_date,
        "timestamp":            timestamp,
        "total_open":           len(open_incidents),
        "high_risk_open":       len(high_risk_open),
        "low_risk_open":        len(low_risk_open),
        "critical_unresolved":  len(critical_unresolved),
        "open_incidents":       open_incidents,
        "high_risk_list":       high_risk_open,
        "low_risk_list":        low_risk_open,
        "critical_list":        critical_unresolved,
        "issue_url":            issue_url
    }


def _create_monday_issue(week_date, timestamp, all_open,
                          high_risk, low_risk, critical) -> str:
    """Create a GitHub Issue with the full Monday report."""
    repo = _get_repo()
    if repo is None:
        return None

    # Ensure labels exist
    _ensure_monday_labels(repo)

    title = f"[MONDAY REPORT] {week_date} — {len(all_open)} Unresolved Incidents"

    # Build the issue body line by line
    lines = [
        f"# Monday Morning Incident Report",
        f"## Week of {week_date}",
        "",
        f"> Generated at {timestamp}",
        "",
        "---",
        "",
        "## SUMMARY",
        "",
        "| Category | Count |",
        "|----------|-------|",
        f"| Total Open Incidents | {len(all_open)} |",
        f"| HIGH RISK (needs action) | {len(high_risk)} |",
        f"| LOW RISK (auto-resolved, review pending) | {len(low_risk)} |",
        f"| CRITICAL (HIGH RISK open > 7 days) | {len(critical)} |",
        "",
        "---",
        "",
    ]

    # Critical section first
    if critical:
        lines += [
            "## CRITICAL — HIGH RISK OPEN MORE THAN 7 DAYS",
            "",
            "> These HIGH RISK incidents have been open for over 7 days.",
            "> They need IMMEDIATE attention.",
            "",
        ]
        for inc in critical:
            days_open = inc.get("days_open", "?")
            count     = inc.get("count", 1)
            pr_url    = inc.get("pr_url", "")
            lines += [
                f"### {inc['resource']} — {inc['condition']}",
                "",
                f"| | |",
                "|---|---|",
                f"| **Resource** | `{inc['resource']}` |",
                f"| **Condition** | `{inc['condition']}` |",
                f"| **Days Open** | {days_open} days |",
                f"| **Occurred** | {count} time(s) |",
                f"| **First Seen** | {inc.get('first_seen', 'Unknown')} |",
                f"| **PR** | {pr_url} |",
                f"| **Summary** | {inc.get('summary', 'Unknown')} |",
                "",
                f"**Action Required:** Open the PR above, follow the checklist, close when done.",
                "",
            ]
        lines += ["---", ""]

    # High risk open incidents
    if high_risk:
        lines += [
            "## HIGH RISK — OPEN INCIDENTS",
            "",
            "These HIGH RISK incidents are open and need your attention:",
            "",
        ]
        for inc in high_risk:
            count  = inc.get("count", 1)
            pr_url = inc.get("pr_url", "")
            lines += [
                f"- **{inc['resource']}** — `{inc['condition']}`",
                f"  - PR: {pr_url}",
                f"  - Occurred: {count} time(s)",
                f"  - First Seen: {inc.get('first_seen', 'Unknown')}",
                f"  - Summary: {inc.get('summary', 'Unknown')[:100]}",
                "",
            ]
        lines += ["---", ""]

    # Low risk open incidents
    if low_risk:
        lines += [
            "## LOW RISK — AUTO-RESOLVED, REVIEW PENDING",
            "",
            "These incidents were auto-resolved by the agent.",
            "Please review and close the PRs when satisfied:",
            "",
        ]
        for inc in low_risk:
            count  = inc.get("count", 1)
            pr_url = inc.get("pr_url", "")
            lines += [
                f"- **{inc['resource']}** — `{inc['condition']}`",
                f"  - PR: {pr_url}",
                f"  - Occurred: {count} time(s)",
                f"  - Summary: {inc.get('summary', 'Unknown')[:100]}",
                "",
            ]
        lines += ["---", ""]

    if not all_open:
        lines += [
            "## ALL CLEAR",
            "",
            "No open incidents this week. Everything is resolved.",
            "",
            "---",
        ]

    lines += [
        "",
        "## ACTION ITEMS",
        "",
        "- [ ] Review all HIGH RISK PRs above and close after resolving",
        "- [ ] Review all LOW RISK PRs above and close after verifying",
        "- [ ] Investigate any incident that has occurred more than 3 times",
        "",
        "---",
        "",
        "*Auto-generated by GCP SRE Agent — Monday Morning Report*",
    ]

    body = "\n".join(lines)

    try:
        issue = repo.create_issue(
            title=title,
            body=body,
            labels=["monday-report", "sre-agent"]
        )
        print(f"[MONDAY] ✅ Monday report issue created: {issue.html_url}")
        return issue.html_url
    except GithubException as e:
        print(f"[MONDAY] ❌ Failed to create issue: {str(e)}")
        return None


def _ensure_monday_labels(repo):
    needed = [
        ("monday-report", "f9d0c4", "Weekly Monday morning incident report"),
        ("sre-agent",     "1d76db", "Created by GCP SRE Agent"),
    ]
    try:
        existing = [l.name for l in repo.get_labels()]
        for name, color, desc in needed:
            if name not in existing:
                repo.create_label(name=name, color=color, description=desc)
    except GithubException:
        pass
