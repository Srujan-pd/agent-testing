"""
pr_creator.py
─────────────
Creates GitHub Pull Requests for every GCP alert.

LOW RISK PR:
  Branch : resolved/TIMESTAMP-RESOURCE
  File   : incidents/resolved/TIMESTAMP-RESOURCE.md
  Content: Error at top, what agent did, root cause, prevention
  Status : OPEN — never merged

HIGH RISK PR:
  Branch : high-risk/TIMESTAMP-RESOURCE
  File   : incidents/high-risk/TIMESTAMP-RESOURCE.md
  Content: Error at top, why not fixed, FULL Gemini solution, GCP links
  Status : OPEN — developer must review, act, then close
"""

import os
from datetime import datetime
from github import Github, GithubException


def _get_github_client():
    token     = os.environ.get("GITHUB_TOKEN", "")
    repo_name = os.environ.get("GITHUB_REPO", "Srujan-pd/agent-testing")

    if not token:
        print("[PR] ⚠️  GITHUB_TOKEN not set — skipping PR creation")
        return None, None

    try:
        g    = Github(token)
        repo = g.get_repo(repo_name)
        print(f"[PR] ✅ Connected to GitHub: {repo_name}")
        return g, repo
    except GithubException as e:
        print(f"[PR] ❌ GitHub connection failed: {str(e)}")
        return None, None


def _ensure_labels(repo):
    labels_needed = [
        ("auto-resolved",   "0075ca", "Agent automatically resolved this incident"),
        ("high-risk",       "d93f0b", "Requires immediate human attention"),
        ("action-required", "e4e669", "Engineer must take action before closing"),
        ("sre-agent",       "1d76db", "Created automatically by GCP SRE Agent"),
        ("low-risk",        "0e8a16", "Low risk — handled automatically"),
    ]
    try:
        existing = [label.name for label in repo.get_labels()]
        for name, color, description in labels_needed:
            if name not in existing:
                repo.create_label(name=name, color=color, description=description)
    except GithubException:
        pass


def _create_branch_and_file(repo, branch_name, file_path, content, commit_message):
    try:
        main_sha = repo.get_branch("main").commit.sha
        repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=main_sha)
        print(f"[PR] Created branch: {branch_name}")
        repo.create_file(
            path=file_path,
            message=commit_message,
            content=content,
            branch=branch_name
        )
        print(f"[PR] Created file: {file_path}")
        return True
    except GithubException as e:
        print(f"[PR] ❌ Failed to create branch/file: {str(e)}")
        return False


def create_low_risk_pr(alert_data: dict, agent_action: str, gemini_diagnosis: str):
    """
    Creates a GitHub PR for a LOW RISK alert that was auto-resolved.
    File added to incidents/resolved/ with full incident report.
    PR stays OPEN — developer reviews and closes without merging.
    """
    _, repo = _get_github_client()
    if repo is None:
        return None

    _ensure_labels(repo)

    incident   = alert_data.get("incident", {})
    summary    = incident.get("summary",           "Unknown alert")
    resource   = incident.get("resource_name",     "unknown")
    condition  = incident.get("condition_name",    "Unknown")
    project    = incident.get("scoping_project_id","poc-genai-chatbot")
    started_at = incident.get("started_at",        "Unknown")
    timestamp  = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    ts_short   = datetime.now().strftime("%Y%m%d-%H%M%S")

    clean_resource = resource.replace("/", "-").replace("_", "-").lower()
    branch_name    = f"resolved/{ts_short}-{clean_resource}"
    file_path      = f"incidents/resolved/{ts_short}-{clean_resource}.md"
    commit_message = f"[AUTO-RESOLVED] {resource}: {summary[:60]}"

    # Build diagnosis block safely — avoid f-string conflicts
    diagnosis_block = gemini_diagnosis if gemini_diagnosis else "Diagnosis not available."
    action_block    = agent_action[:3000] if agent_action else "No action recorded."

    lines = [
        f"# AUTO-RESOLVED — {resource}",
        "",
        f"> **{summary}**",
        "",
        "---",
        "",
        "## ERROR DETAILS",
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| **Resource** | `{resource}` |",
        f"| **Alert Condition** | `{condition}` |",
        f"| **GCP Project** | `{project}` |",
        f"| **Alert Started** | `{started_at}` |",
        f"| **Resolved At** | `{timestamp}` |",
        "| **Risk Level** | LOW — Auto-resolved by SRE Agent |",
        "| **Auto-Fixed** | Yes |",
        "| **Engineer Woken Up** | No — handled automatically |",
        "",
        "---",
        "",
        "## ROOT CAUSE DIAGNOSIS",
        "",
        diagnosis_block,
        "",
        "---",
        "",
        "## WHAT THE AGENT DID TO FIX IT",
        "",
        "```",
        action_block,
        "```",
        "",
        "---",
        "",
        "## VERIFY THE FIX",
        "",
        "| Check | Link |",
        "|-------|------|",
        f"| Service Status | https://console.cloud.google.com/run/detail/us-central1/{resource}/revisions?project={project} |",
        f"| Live Metrics | https://console.cloud.google.com/run/detail/us-central1/{resource}/metrics?project={project} |",
        f"| Recent Logs | https://console.cloud.google.com/logs/query;query=resource.labels.service_name%3D%22{resource}%22?project={project} |",
        f"| Alert Status | https://console.cloud.google.com/monitoring/alerting?project={project} |",
        "",
        "---",
        "",
        "## STEPS TO PREVENT THIS NEXT TIME",
        "",
        "**1. Review resource limits**",
        "",
        "Check if memory and CPU limits match actual traffic needs:",
        "",
        "```bash",
        f"gcloud run services describe {resource} --region=us-central1 --project={project}",
        "```",
        "",
        "**2. Set proactive alerts at 70%**",
        "",
        "Add a GCP Monitoring alert at 70% memory and CPU — before it becomes critical.",
        "",
        "**3. Review recent deployments**",
        "",
        "Check if a recent code push increased resource usage:",
        "",
        "```bash",
        f"gcloud run revisions list --service={resource} --region=us-central1 --project={project}",
        "```",
        "",
        "**4. Check application logs for patterns**",
        "",
        "Look for growing memory usage or repeated errors:",
        "",
        "```bash",
        f'gcloud logging read \'resource.labels.service_name="{resource}" severity>=WARNING\' --project={project} --limit=50',
        "```",
        "",
        "---",
        "",
        "## HOW TO CLOSE THIS PR",
        "",
        "1. Review the diagnosis and agent actions above",
        "2. Click the GCP Console links to confirm service is healthy",
        "3. Add a comment describing what you verified",
        "4. Close this PR without merging — this is an incident report not code",
        "",
        "---",
        "",
        "*Auto-created by GCP SRE Agent — no human intervention was needed*",
    ]

    file_content = "\n".join(lines)

    pr_body_lines = [
        "## AUTO-RESOLVED Incident Report",
        "",
        "> This PR was created automatically by the GCP SRE Agent.",
        "> **Do not merge** — review and close.",
        "",
        "---",
        "",
        "## What Broke",
        f"> **{summary}**",
        "",
        "| | |",
        "|---|---|",
        f"| **Resource** | `{resource}` |",
        f"| **Fixed At** | `{timestamp}` |",
        "| **Risk** | LOW — auto-resolved |",
        "",
        "---",
        "",
        "## What You Need to Do",
        "1. Read the full incident report in `incidents/resolved/`",
        "2. Verify service is healthy using the GCP Console links in the file",
        "3. **Close this PR without merging**",
        "",
        "---",
        "*GCP SRE Agent v2.0*",
    ]

    pr_body = "\n".join(pr_body_lines)

    success = _create_branch_and_file(repo, branch_name, file_path, file_content, commit_message)
    if not success:
        return None

    try:
        pr = repo.create_pull(
            title=f"[AUTO-RESOLVED] {resource} — {summary[:70]}",
            body=pr_body,
            head=branch_name,
            base="main"
        )
        pr.add_to_labels("auto-resolved", "sre-agent", "low-risk")
        print(f"[PR] ✅ LOW RISK PR created: {pr.html_url}")
        return pr.html_url
    except GithubException as e:
        print(f"[PR] ❌ Failed to create PR: {str(e)}")
        return None


def create_high_risk_pr(alert_data: dict, gemini_solution: str):
    """
    Creates a GitHub PR for a HIGH RISK alert.
    File added to incidents/high-risk/ with full solution.
    PR stays OPEN — developer must act then close without merging.
    """
    _, repo = _get_github_client()
    if repo is None:
        return None

    _ensure_labels(repo)

    incident   = alert_data.get("incident", {})
    summary    = incident.get("summary",           "Unknown alert")
    resource   = incident.get("resource_name",     "unknown")
    condition  = incident.get("condition_name",    "Unknown")
    project    = incident.get("scoping_project_id","poc-genai-chatbot")
    started_at = incident.get("started_at",        "Unknown")
    timestamp  = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    ts_short   = datetime.now().strftime("%Y%m%d-%H%M%S")

    clean_resource = resource.replace("/", "-").replace("_", "-").lower()
    branch_name    = f"high-risk/{ts_short}-{clean_resource}"
    file_path      = f"incidents/high-risk/{ts_short}-{clean_resource}.md"
    commit_message = f"[HIGH RISK] {resource}: {summary[:60]}"

    # Build solution block safely
    solution_block = gemini_solution if gemini_solution else "Solution not available — check GCP Console manually."

    lines = [
        f"# HIGH RISK INCIDENT — {resource}",
        "",
        "> **IMMEDIATE ACTION REQUIRED — Agent did NOT auto-fix this**",
        "",
        "---",
        "",
        "## ERROR DETAILS",
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| **Resource** | `{resource}` |",
        f"| **Alert Condition** | `{condition}` |",
        f"| **GCP Project** | `{project}` |",
        f"| **Alert Started** | `{started_at}` |",
        f"| **PR Created** | `{timestamp}` |",
        "| **Risk Level** | HIGH |",
        "| **Auto-Fixed** | NO — requires human judgement |",
        "| **GCP Changes Made by Agent** | ZERO — nothing was touched |",
        "",
        "---",
        "",
        "## WHAT BROKE",
        "",
        f"> **{summary}**",
        "",
        "---",
        "",
        "## WHY THE AGENT DID NOT AUTO-FIX THIS",
        "",
        "The agent never automatically handles HIGH RISK situations.",
        "The following categories are always escalated to a human:",
        "",
        "| Risk Category | Why It Is Dangerous |",
        "|--------------|---------------------|",
        "| IAM or permission changes | Could indicate unauthorized access or privilege escalation |",
        "| Production databases | Auto-actions risk data loss or corruption |",
        "| Firewall rule changes | Could expose your infrastructure to the internet |",
        "| Billing anomalies | Could indicate compromised account or runaway costs |",
        "| Credentials or secrets | Security-sensitive — needs human judgement only |",
        "",
        f"This alert matched: condition `{condition}` on resource `{resource}`",
        "",
        "---",
        "",
        "## GEMINI AI — EXACT SOLUTION",
        "",
        "> This solution was generated by Gemini AI specifically for this incident.",
        "> Follow these steps exactly to resolve the issue.",
        "",
        solution_block,
        "",
        "---",
        "",
        "## GCP CONSOLE LINKS — INVESTIGATE HERE",
        "",
        "Open these links directly — no searching required:",
        "",
        "| What to Check | Direct Link |",
        "|--------------|-------------|",
        f"| Resource Overview | https://console.cloud.google.com/run/detail/us-central1/{resource}?project={project} |",
        f"| Recent Error Logs | https://console.cloud.google.com/logs/query;query=resource.labels.service_name%3D%22{resource}%22%20severity%3E%3DWARNING?project={project} |",
        f"| IAM and Permissions | https://console.cloud.google.com/iam-admin/iam?project={project} |",
        f"| Audit Logs | https://console.cloud.google.com/logs/query;query=logName%3D%22projects%2F{project}%2Flogs%2Fcloudaudit.googleapis.com%2Factivity%22?project={project} |",
        f"| Billing Overview | https://console.cloud.google.com/billing?project={project} |",
        f"| All Active Alerts | https://console.cloud.google.com/monitoring/alerting?project={project} |",
        "",
        "---",
        "",
        "## STEP-BY-STEP ACTION CHECKLIST",
        "",
        "### Step 1 — Understand What Happened",
        "- [ ] Open the Recent Error Logs link above",
        "- [ ] Read the last 20 error lines",
        "- [ ] Open Audit Logs — identify who or what triggered this",
        "- [ ] Note the exact timestamp and correlate with recent deployments",
        "",
        "### Step 2 — Contain the Issue Based on Alert Type",
        "",
        "**If IAM change — find and revert the suspicious binding:**",
        "",
        "```bash",
        f"# See all current IAM bindings",
        f"gcloud projects get-iam-policy {project}",
        "",
        f"# Remove suspicious binding",
        f"gcloud projects remove-iam-policy-binding {project} \\",
        f"  --member='SUSPICIOUS_MEMBER' \\",
        f"  --role='SUSPICIOUS_ROLE'",
        "```",
        "",
        "**If billing spike — identify the resource causing cost:**",
        "",
        "```bash",
        f"gcloud services list --enabled --project={project}",
        f"gcloud run services list --region=us-central1 --project={project}",
        "```",
        "",
        "**If firewall change — review and revert suspicious rules:**",
        "",
        "```bash",
        f"gcloud compute firewall-rules list --project={project}",
        f"gcloud compute firewall-rules delete RULE_NAME --project={project}",
        "```",
        "",
        "**If database issue — check connections and disk:**",
        "",
        "```bash",
        f"gcloud sql instances list --project={project}",
        f"gcloud sql operations list --instance=INSTANCE_NAME --project={project}",
        "```",
        "",
        "**If Cloud Run service issue — check status and logs:**",
        "",
        "```bash",
        f"gcloud run services describe {resource} --region=us-central1 --project={project}",
        f"gcloud run services logs read {resource} --region=us-central1 --project={project} --limit=50",
        "```",
        "",
        "### Step 3 — Apply the Fix",
        "- [ ] Follow the Gemini solution section above",
        "- [ ] Verify the alert cleared in GCP Monitoring",
        "- [ ] Confirm service is healthy",
        "",
        "### Step 4 — Close This PR",
        "- [ ] Add a comment describing what you found and what you did",
        "- [ ] Close this PR without merging — this is an incident report",
        "",
        "---",
        "",
        "## FULL ALERT DATA",
        "",
        "<details>",
        "<summary>Expand to see raw alert JSON</summary>",
        "",
        "```json",
        str(alert_data)[:2000],
        "```",
        "",
        "</details>",
        "",
        "---",
        "",
        "*Auto-created by GCP SRE Agent — escalated because this is HIGH RISK*",
        "*Zero changes were made to your GCP infrastructure*",
    ]

    file_content = "\n".join(lines)

    pr_body_lines = [
        "## HIGH RISK Incident — Immediate Action Required",
        "",
        "> **The SRE Agent escalated this to you. Zero GCP changes were made.**",
        "",
        "---",
        "",
        "## What Broke",
        f"> **{summary}**",
        "",
        "| | |",
        "|---|---|",
        f"| **Resource** | `{resource}` |",
        f"| **Detected At** | `{timestamp}` |",
        "| **Risk** | HIGH — manual action required |",
        "| **Agent Touched GCP** | NO — nothing was changed |",
        "",
        "---",
        "",
        "## Gemini Solution Summary",
        "",
        solution_block[:800],
        "",
        "*(Full solution with all commands is in the incident file in `incidents/high-risk/`)*",
        "",
        "---",
        "",
        "## What You Need to Do",
        "1. Read the full incident file added by this PR in `incidents/high-risk/`",
        "2. Follow the step-by-step checklist in the file",
        "3. Use the GCP Console links in the file to investigate",
        "4. Apply the Gemini solution",
        "5. **Close this PR without merging** after resolving",
        "",
        "---",
        "*GCP SRE Agent v2.0*",
    ]

    pr_body = "\n".join(pr_body_lines)

    success = _create_branch_and_file(repo, branch_name, file_path, file_content, commit_message)
    if not success:
        return None

    try:
        pr = repo.create_pull(
            title=f"[HIGH RISK — ACTION REQUIRED] {resource} — {summary[:65]}",
            body=pr_body,
            head=branch_name,
            base="main"
        )
        pr.add_to_labels("high-risk", "sre-agent", "action-required")
        print(f"[PR] ✅ HIGH RISK PR created: {pr.html_url}")
        return pr.html_url
    except GithubException as e:
        print(f"[PR] ❌ Failed to create PR: {str(e)}")
        return None
