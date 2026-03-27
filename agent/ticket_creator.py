"""
ticket_creator.py
─────────────────
Creates GitHub Issues for every alert.

LOW RISK ticket  → Error on top, what agent did, root cause, prevention steps
HIGH RISK ticket → Error on top, why not auto-fixed, Gemini solution, GCP links
"""

import os
from datetime import datetime
from github import Github, GithubException


def _get_github_client():
    token     = os.environ.get("GITHUB_TOKEN", "")
    repo_name = os.environ.get("GITHUB_REPO", "")

    if not token or not repo_name:
        print("[TICKET] ⚠️  GITHUB_TOKEN or GITHUB_REPO not set — skipping ticket")
        return None, None

    try:
        g    = Github(token)
        repo = g.get_repo(repo_name)
        return g, repo
    except GithubException as e:
        print(f"[TICKET] ❌ GitHub auth failed: {str(e)}")
        return None, None


def _ensure_labels(repo):
    """Create labels if they don't exist yet in the repo."""
    needed = [
        ("auto-resolved",    "0075ca", "Agent automatically resolved this"),
        ("high-risk",        "d93f0b", "Requires immediate human attention"),
        ("action-required",  "e4e669", "Engineer must take action"),
        ("sre-agent",        "1d76db", "Created by GCP SRE Agent"),
        ("low-risk",         "0e8a16", "Low risk — auto handled"),
    ]
    existing = [l.name for l in repo.get_labels()]
    for name, color, desc in needed:
        if name not in existing:
            try:
                repo.create_label(name=name, color=color, description=desc)
            except GithubException:
                pass


def create_low_risk_ticket(alert_data: dict, agent_action: str, gemini_diagnosis: str):
    """
    Creates a GitHub Issue for a LOW RISK alert that was auto-resolved.

    TOP of ticket shows:
      - Exactly what broke (bold, clear)
      - Severity = LOW, auto-resolved

    Then shows:
      - Root cause diagnosis from Gemini
      - What the agent did step by step
      - How to verify the fix
      - Steps to prevent it next time
      - GCP Console links
    """
    _, repo = _get_github_client()
    if repo is None:
        return None

    _ensure_labels(repo)

    incident   = alert_data.get("incident", {})
    summary    = incident.get("summary",    "Unknown alert")
    resource   = incident.get("resource_name", "Unknown")
    condition  = incident.get("condition_name", "Unknown")
    project    = incident.get("scoping_project_id", "poc-genai-chatbot")
    started_at = incident.get("started_at", "Unknown")
    timestamp  = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

    title = f"[AUTO-RESOLVED] {resource} — {summary[:80]}"

    body = f"""## 🟢 AUTO-RESOLVED — Low Risk Incident

---

## ❗ What Broke
> ### {summary}

| | |
|---|---|
| **Affected Resource** | `{resource}` |
| **Alert Condition** | `{condition}` |
| **GCP Project** | `{project}` |
| **When it Started** | `{started_at}` |
| **When Resolved** | `{timestamp}` |
| **Risk Level** | 🟢 LOW — Auto-resolved by SRE Agent |
| **Engineer Woken Up** | ✅ No — handled automatically |

---

## 🔍 Root Cause Diagnosis

{gemini_diagnosis}

---

## ✅ What the Agent Did to Fix It
```
{agent_action[:2000]}
```

---

## 🔎 Verify the Fix Yourself

Click these links to confirm service is healthy:

| Check | Link |
|-------|------|
| Service Status | [Cloud Run — {resource}](https://console.cloud.google.com/run/detail/us-central1/{resource}/revisions?project={project}) |
| Live Metrics | [Metrics Dashboard](https://console.cloud.google.com/run/detail/us-central1/{resource}/metrics?project={project}) |
| Recent Logs | [Cloud Logging](https://console.cloud.google.com/logs/query;query=resource.labels.service_name%3D%22{resource}%22?project={project}) |
| Alert Status | [GCP Monitoring](https://console.cloud.google.com/monitoring/alerting?project={project}) |

---

## 🛡️ Steps to Prevent This Next Time

1. **Review resource limits** — Check if memory/CPU limits match actual traffic needs
```bash
   gcloud run services describe {resource} --region=us-central1 --project={project}
```

2. **Add proactive alerts** — Set alerts at 70% memory/CPU before it becomes critical

3. **Review recent deployments** — Check if a recent code push increased resource usage
```bash
   gcloud run revisions list --service={resource} --region=us-central1 --project={project}
```

4. **Check for memory leaks** — Review application logs for growing memory patterns
```bash
   gcloud logging read 'resource.labels.service_name="{resource}" severity>=WARNING' \\
     --project={project} --limit=50
```

---

## 📋 Full Alert Data
<details>
<summary>Expand to see raw alert JSON</summary>
```json
{str(alert_data)[:1500]}
```
</details>

---
*🤖 Automatically created by GCP SRE Agent — no human intervention was needed*
"""

    try:
        issue = repo.create_issue(
            title=title,
            body=body,
            labels=["auto-resolved", "sre-agent", "low-risk"]
        )
        print(f"[TICKET] ✅ LOW RISK ticket created: {issue.html_url}")
        return issue.html_url
    except GithubException as e:
        print(f"[TICKET] ❌ Failed to create ticket: {str(e)}")
        return None


def create_high_risk_ticket(alert_data: dict, gemini_solution: str):
    """
    Creates a GitHub Issue for a HIGH RISK alert.

    TOP of ticket shows:
      - Exactly what broke (bold, red heading)
      - Severity = HIGH, needs human action

    Then shows:
      - Why agent did NOT auto-fix it
      - Gemini's suggested solution steps with gcloud commands
      - Exact GCP Console links to investigate
      - Step by step checklist for developer
    """
    _, repo = _get_github_client()
    if repo is None:
        return None

    _ensure_labels(repo)

    incident   = alert_data.get("incident", {})
    summary    = incident.get("summary",    "Unknown alert")
    resource   = incident.get("resource_name", "Unknown")
    condition  = incident.get("condition_name", "Unknown")
    project    = incident.get("scoping_project_id", "poc-genai-chatbot")
    started_at = incident.get("started_at", "Unknown")
    timestamp  = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

    title = f"[HIGH RISK — ACTION REQUIRED] {resource} — {summary[:70]}"

    body = f"""## 🔴 HIGH RISK — Immediate Action Required

> ⚠️ **The SRE Agent escalated this to you. No automatic changes were made to GCP.**

---

## ❗ What Broke
> ### {summary}

| | |
|---|---|
| **Affected Resource** | `{resource}` |
| **Alert Condition** | `{condition}` |
| **GCP Project** | `{project}` |
| **When it Started** | `{started_at}` |
| **Ticket Created** | `{timestamp}` |
| **Risk Level** | 🔴 HIGH — Manual action required |
| **Agent Action Taken** | ❌ None — agent did not touch this resource |

---

## 🚫 Why the Agent Did NOT Auto-Fix This

The agent never automatically handles:

| Risk Type | Why It's Dangerous |
|-----------|-------------------|
| **IAM / Permission changes** | Could indicate unauthorized access or privilege escalation |
| **Production databases** | Auto-actions risk data loss or corruption |
| **Firewall rule changes** | Could expose infrastructure to the internet |
| **Billing anomalies** | Could indicate compromised account or runaway costs |
| **Credentials / Secrets** | Security-sensitive — needs human judgement |

**For this alert:** The classifier detected `{condition}` on `{resource}` which matched HIGH RISK rules.

---

## 💡 Suggested Solution (Generated by Gemini AI)

{gemini_solution}

---

## 🔎 Investigate Here — GCP Console Links

| What to Check | Link |
|---------------|------|
| Resource Overview | [Cloud Run — {resource}](https://console.cloud.google.com/run/detail/us-central1/{resource}?project={project}) |
| Recent Error Logs | [Cloud Logging](https://console.cloud.google.com/logs/query;query=resource.labels.service_name%3D%22{resource}%22%20severity%3E%3DWARNING?project={project}) |
| IAM & Permissions | [IAM Console](https://console.cloud.google.com/iam-admin/iam?project={project}) |
| Audit Logs | [Audit Logs](https://console.cloud.google.com/logs/query;query=logName%3D%22projects%2F{project}%2Flogs%2Fcloudaudit.googleapis.com%2Factivity%22?project={project}) |
| Billing Overview | [Billing](https://console.cloud.google.com/billing?project={project}) |
| All Alerts | [GCP Monitoring](https://console.cloud.google.com/monitoring/alerting?project={project}) |

---

## 📋 Action Checklist for Developer

**Step 1 — Understand what happened**
- [ ] Open Cloud Logging link above — read the last 20 error lines
- [ ] Check Audit Logs — identify who or what triggered this alert
- [ ] Note the exact timestamp and correlate with any recent deployments

**Step 2 — Contain the issue**
- [ ] If IAM change → identify the suspicious binding and revert:
```bash
  gcloud projects get-iam-policy {project}
  gcloud projects remove-iam-policy-binding {project} \\
    --member="SUSPICIOUS_MEMBER" --role="ROLE"
```
- [ ] If billing spike → identify the resource causing cost:
```bash
  gcloud billing budgets list --billing-account=YOUR_BILLING_ACCOUNT
```
- [ ] If firewall change → review and revert suspicious rules:
```bash
  gcloud compute firewall-rules list --project={project}
```

**Step 3 — Apply the fix**
- [ ] Follow the Suggested Solution steps above
- [ ] Verify alert cleared in GCP Monitoring

**Step 4 — Close this ticket**
- [ ] Add a comment: what you found + what you did
- [ ] Close issue with label `resolved`

---

## 📋 Full Alert Data
<details>
<summary>Expand to see raw alert JSON</summary>
```json
{str(alert_data)[:1500]}
```
</details>

---
*🤖 Automatically created by GCP SRE Agent — escalated because this is HIGH RISK*
*The agent made zero changes to your GCP infrastructure*
"""

    try:
        issue = repo.create_issue(
            title=title,
            body=body,
            labels=["high-risk", "sre-agent", "action-required"]
        )
        print(f"[TICKET] ✅ HIGH RISK ticket created: {issue.html_url}")
        return issue.html_url
    except GithubException as e:
        print(f"[TICKET] ❌ Failed to create ticket: {str(e)}")
        return None
