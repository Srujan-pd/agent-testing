"""
pr_creator.py
─────────────
Creates GitHub Issues (tickets) for every alert.
No branches. No PRs. Just clean tickets.

LOW RISK  → Issue with what agent did + root cause + prevention
HIGH RISK → Issue with Gemini solution + GCP links + checklist
"""

import os
from datetime import datetime
from github import Github, GithubException


def _get_repo():
    token     = os.environ.get("GITHUB_TOKEN", "")
    repo_name = os.environ.get("GITHUB_REPO", "Srujan-pd/agent-testing")
    if not token:
        print("[TICKET] ⚠️  GITHUB_TOKEN not set")
        return None
    try:
        g    = Github(token)
        repo = g.get_repo(repo_name)
        print(f"[TICKET] ✅ Connected to: {repo_name}")
        return repo
    except GithubException as e:
        print(f"[TICKET] ❌ GitHub failed: {str(e)}")
        return None


def _ensure_labels(repo):
    needed = [
        ("auto-resolved",   "0075ca", "Agent automatically resolved this"),
        ("high-risk",       "d93f0b", "Requires immediate human attention"),
        ("action-required", "e4e669", "Engineer must take action"),
        ("sre-agent",       "1d76db", "Created by GCP SRE Agent"),
        ("low-risk",        "0e8a16", "Low risk — auto handled"),
        ("monday-report",   "f9d0c4", "Weekly Monday report"),
    ]
    try:
        existing = [l.name for l in repo.get_labels()]
        for name, color, desc in needed:
            if name not in existing:
                repo.create_label(name=name, color=color, description=desc)
    except GithubException:
        pass


def create_low_risk_pr(alert_data: dict, agent_action: str,
                        gemini_diagnosis: str, assignee: dict = None):
    """Creates a GitHub Issue for a LOW RISK auto-resolved alert."""
    repo = _get_repo()
    if repo is None:
        return None

    _ensure_labels(repo)

    incident   = alert_data.get("incident", {})
    summary    = incident.get("summary",            "Unknown alert")
    resource   = incident.get("resource_name",      "unknown")
    condition  = incident.get("condition_name",     "Unknown")
    project    = incident.get("scoping_project_id", "poc-genai-chatbot")
    started_at = incident.get("started_at",         "Unknown")
    timestamp  = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

    assignee_name   = assignee.get("name", "")           if assignee else ""
    assignee_github = assignee.get("github_username", "") if assignee else ""

    lines = [
        f"## ERROR",
        f"> **{summary}**",
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| **Resource** | `{resource}` |",
        f"| **Condition** | `{condition}` |",
        f"| **Project** | `{project}` |",
        f"| **Started** | `{started_at}` |",
        f"| **Resolved At** | `{timestamp}` |",
        f"| **Risk** | 🟢 LOW — auto-resolved |",
        f"| **Assignee** | {assignee_name} |",
        "",
        "---",
        "",
        "## ROOT CAUSE",
        "",
        gemini_diagnosis if gemini_diagnosis else "Not available.",
        "",
        "---",
        "",
        "## WHAT THE AGENT DID",
        "",
        "```",
        (agent_action or "No action recorded.")[:2000],
        "```",
        "",
        "---",
        "",
        "## VERIFY",
        "",
        f"- [Service Status](https://console.cloud.google.com/run/detail/us-central1/{resource}/revisions?project={project})",
        f"- [Metrics](https://console.cloud.google.com/run/detail/us-central1/{resource}/metrics?project={project})",
        f"- [Logs](https://console.cloud.google.com/logs/query;query=resource.labels.service_name%3D%22{resource}%22?project={project})",
        f"- [Monitoring](https://console.cloud.google.com/monitoring/alerting?project={project})",
        "",
        "---",
        "",
        "## PREVENTION",
        "",
        "**1. Review resource limits**",
        "```bash",
        f"gcloud run services describe {resource} --region=us-central1 --project={project}",
        "```",
        "",
        "**2. Set proactive alerts at 70%** in GCP Monitoring before it becomes critical.",
        "",
        "**3. Review recent deployments**",
        "```bash",
        f"gcloud run revisions list --service={resource} --region=us-central1 --project={project}",
        "```",
        "",
        "**4. Check logs for patterns**",
        "```bash",
        f'gcloud logging read \'resource.labels.service_name="{resource}" severity>=WARNING\' --project={project} --limit=50',
        "```",
        "",
        "---",
        "*🤖 GCP SRE Agent — auto-resolved, no human action needed*",
    ]

    try:
        issue = repo.create_issue(
            title=f"[AUTO-RESOLVED] {resource} — {summary[:80]}",
            body="\n".join(lines),
            labels=["auto-resolved", "sre-agent", "low-risk"]
        )
        if assignee_github:
            try:
                issue.add_to_assignees(assignee_github)
            except GithubException:
                pass
        print(f"[TICKET] ✅ LOW RISK ticket: {issue.html_url}")
        return issue.html_url
    except GithubException as e:
        print(f"[TICKET] ❌ Failed: {str(e)}")
        return None


def create_high_risk_pr(alert_data: dict, gemini_solution: str,
                         assignee: dict = None):
    """Creates a GitHub Issue for a HIGH RISK alert needing human action."""
    repo = _get_repo()
    if repo is None:
        return None

    _ensure_labels(repo)

    incident   = alert_data.get("incident", {})
    summary    = incident.get("summary",            "Unknown alert")
    resource   = incident.get("resource_name",      "unknown")
    condition  = incident.get("condition_name",     "Unknown")
    project    = incident.get("scoping_project_id", "poc-genai-chatbot")
    started_at = incident.get("started_at",         "Unknown")
    timestamp  = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

    assignee_name   = assignee.get("name", "")           if assignee else ""
    assignee_github = assignee.get("github_username", "") if assignee else ""

    lines = [
        "## ⚠️ IMMEDIATE ACTION REQUIRED",
        "",
        "## ERROR",
        f"> **{summary}**",
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| **Resource** | `{resource}` |",
        f"| **Condition** | `{condition}` |",
        f"| **Project** | `{project}` |",
        f"| **Started** | `{started_at}` |",
        f"| **Detected** | `{timestamp}` |",
        f"| **Risk** | 🔴 HIGH — manual action required |",
        f"| **Agent Changes** | ❌ None — nothing was touched |",
        f"| **Assignee** | {assignee_name} |",
        "",
        "---",
        "",
        "## WHY AGENT DID NOT AUTO-FIX",
        "",
        f"Alert `{condition}` on `{resource}` matched HIGH RISK rules.",
        "Agent never auto-handles: IAM changes, databases, firewalls, billing, secrets.",
        "",
        "---",
        "",
        "## GEMINI SOLUTION",
        "",
        gemini_solution if gemini_solution else "Solution not available — check GCP Console.",
        "",
        "---",
        "",
        "## GCP LINKS",
        "",
        f"| Check | Link |",
        f"|-------|------|",
        f"| Resource | https://console.cloud.google.com/run/detail/us-central1/{resource}?project={project} |",
        f"| Error Logs | https://console.cloud.google.com/logs/query;query=resource.labels.service_name%3D%22{resource}%22%20severity%3E%3DWARNING?project={project} |",
        f"| IAM | https://console.cloud.google.com/iam-admin/iam?project={project} |",
        f"| Audit Logs | https://console.cloud.google.com/logs/query;query=logName%3D%22projects%2F{project}%2Flogs%2Fcloudaudit.googleapis.com%2Factivity%22?project={project} |",
        f"| Billing | https://console.cloud.google.com/billing?project={project} |",
        f"| Monitoring | https://console.cloud.google.com/monitoring/alerting?project={project} |",
        "",
        "---",
        "",
        "## CHECKLIST",
        "",
        "### Step 1 — Investigate",
        "- [ ] Open Error Logs above",
        "- [ ] Open Audit Logs — find who triggered this",
        "- [ ] Correlate with recent deployments",
        "",
        "### Step 2 — Contain",
        "",
        "**IAM change:**",
        "```bash",
        f"gcloud projects get-iam-policy {project}",
        f"gcloud projects remove-iam-policy-binding {project} \\",
        f"  --member='SUSPICIOUS_MEMBER' --role='SUSPICIOUS_ROLE'",
        "```",
        "",
        "**Billing spike:**",
        "```bash",
        f"gcloud services list --enabled --project={project}",
        "```",
        "",
        "**Firewall change:**",
        "```bash",
        f"gcloud compute firewall-rules list --project={project}",
        "```",
        "",
        "**Cloud Run issue:**",
        "```bash",
        f"gcloud run services describe {resource} --region=us-central1 --project={project}",
        f"gcloud run services logs read {resource} --region=us-central1 --project={project} --limit=50",
        "```",
        "",
        "### Step 3 — Fix and Close",
        "- [ ] Apply Gemini solution above",
        "- [ ] Verify alert cleared in GCP Monitoring",
        "- [ ] Close this issue with a comment describing what you did",
        "",
        "---",
        "",
        "<details>",
        "<summary>Full Alert JSON</summary>",
        "",
        "```json",
        str(alert_data)[:1500],
        "```",
        "",
        "</details>",
        "",
        "---",
        "*🤖 GCP SRE Agent — escalated, zero GCP changes made*",
    ]

    try:
        issue = repo.create_issue(
            title=f"[HIGH RISK — ACTION REQUIRED] {resource} — {summary[:70]}",
            body="\n".join(lines),
            labels=["high-risk", "sre-agent", "action-required"]
        )
        if assignee_github:
            try:
                issue.add_to_assignees(assignee_github)
            except GithubException:
                pass
        print(f"[TICKET] ✅ HIGH RISK ticket: {issue.html_url}")
        return issue.html_url
    except GithubException as e:
        print(f"[TICKET] ❌ Failed: {str(e)}")
        return None
