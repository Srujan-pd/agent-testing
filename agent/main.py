"""
main.py v3.0
────────────
- Duplicate detection (7 days)
- GitHub PR creation
- Monday morning report endpoint
- Email for all events
"""

import os
import json
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

from risk_classifier import classify_risk
from agent_core import run_agent, generate_gemini_solution, CONFIG
from notifier import send_high_risk_email, send_resolution_email, send_monday_report_email
from pr_creator import create_low_risk_pr, create_high_risk_pr
from incident_tracker import (
    check_duplicate, record_incident,
    update_occurrence, get_unresolved_high_risk
)
from monday_report import generate_monday_report

app = FastAPI(
    title="GCP SRE Agent v3.0",
    description="""
## GCP SRE Agent v3.0

### Features:
- AUTO-RESOLVES low risk GCP errors
- Creates GitHub PRs for every incident
- Detects duplicate errors within 7 days
- Adds comments to existing PRs on recurrence
- Monday morning report of all unresolved incidents
- Email alerts for everything
    """,
    version="3.0.0",
    docs_url="/docs"
)


class IncidentData(BaseModel):
    summary: str
    condition_name: Optional[str]     = "Unknown"
    resource_name: Optional[str]      = "unknown-resource"
    scoping_project_id: Optional[str] = "poc-genai-chatbot"
    state: Optional[str]              = "open"
    started_at: Optional[str]         = "2024-01-01T00:00:00Z"

class AlertRequest(BaseModel):
    incident: IncidentData
    metric_value: Optional[float] = None

    class Config:
        json_schema_extra = {"example": {"incident": {
            "summary": "Cloud Run service my-api returning 503 errors",
            "condition_name": "cloud_run_5xx_errors",
            "resource_name": "my-api",
            "scoping_project_id": "poc-genai-chatbot",
            "state": "open"
        }}}

class ConfigUpdate(BaseModel):
    agent_dry_run: Optional[bool]     = None
    log_all_decisions: Optional[bool] = None


@app.get("/", tags=["Status"])
def root():
    return {
        "status":    "running",
        "version":   "3.0.0",
        "features":  [
            "auto-resolve",
            "github-pr",
            "duplicate-detection",
            "monday-report",
            "email-alerts"
        ],
        "dry_run":   CONFIG.get("agent_dry_run", True),
        "timestamp": datetime.now().isoformat()
    }


@app.get("/health", tags=["Status"])
def health():
    return {"status": "healthy"}


@app.get("/config", tags=["Configuration"])
def get_config():
    return {"current_config": CONFIG}


@app.patch("/config", tags=["Configuration"])
def update_config(update: ConfigUpdate):
    changes = {}
    if update.agent_dry_run is not None:
        CONFIG["agent_dry_run"] = update.agent_dry_run
        changes["agent_dry_run"] = update.agent_dry_run
    if update.log_all_decisions is not None:
        CONFIG["log_all_decisions"] = update.log_all_decisions
        changes["log_all_decisions"] = update.log_all_decisions
    with open("config.json", "w") as f:
        json.dump(CONFIG, f, indent=2)
    return {"message": "Config updated", "changes": changes}


@app.post("/handle-alert", tags=["Agent"])
async def handle_alert(alert: AlertRequest):
    """
    Handles every GCP alert with full pipeline:

    1. Check if same error occurred in last 7 days
       YES → Add comment to existing PR, update count, send email
       NO  → Continue to step 2

    2. Classify risk (LOW or HIGH)

    3. LOW RISK → Fix GCP → Create PR → Record in tracker → Email
       HIGH RISK → Create PR with solution → Record in tracker → Email
    """
    alert_data = alert.dict()
    summary    = alert.incident.summary
    resource   = alert.incident.resource_name

    print(f"\n{'='*55}")
    print(f"[MAIN] Alert   : {summary}")
    print(f"[MAIN] Resource: {resource}")
    print(f"{'='*55}")

    # ── STEP 1: DUPLICATE CHECK ───────────────────────────────────
    dup_check = check_duplicate(alert_data)

    if dup_check["is_duplicate"]:
        existing    = dup_check["existing_incident"]
        count       = dup_check["occurrence_count"] + 1
        days_ago    = dup_check.get("days_ago", 0)
        pr_url      = existing.get("pr_url", "")
        incident_key = dup_check["incident_key"]

        print(f"[MAIN] ⚠️  DUPLICATE — same error {days_ago} days ago, "
              f"occurrence #{count}")

        # Update occurrence count + add comment to PR
        update_occurrence(alert_data, incident_key)

        # Send email about recurrence
        _send_recurrence_email(
            summary, resource, count, days_ago,
            pr_url, existing.get("risk", "LOW")
        )

        return {
            "status":           "duplicate_detected",
            "message":          f"Same error occurred {count} times. Comment added to existing PR.",
            "occurrence_count": count,
            "days_since_last":  days_ago,
            "existing_pr":      pr_url,
            "resource":         resource,
            "timestamp":        datetime.now().isoformat()
        }

    # ── STEP 2: CLASSIFY RISK ─────────────────────────────────────
    risk_level = classify_risk(alert_data)

    # ── STEP 3A: HIGH RISK ────────────────────────────────────────
    if risk_level == "HIGH":
        print(f"[MAIN] 🚨 HIGH RISK — creating PR + sending email")

        gemini_solution = generate_gemini_solution(alert_data)
        pr_url          = create_high_risk_pr(alert_data, gemini_solution)

        # Record in tracker
        if pr_url:
            pr_number = _extract_pr_number(pr_url)
            branch    = f"high-risk/{datetime.now().strftime('%Y%m%d-%H%M%S')}-{resource}"
            record_incident(alert_data, "HIGH", pr_url, pr_number, branch)

        send_high_risk_email(summary, alert_data, pr_url)

        return {
            "status":        "escalated_to_human",
            "risk":          "HIGH",
            "action":        "PR created with Gemini solution + email sent",
            "pr_url":        pr_url,
            "alert_summary": summary,
            "resource":      resource,
            "timestamp":     datetime.now().isoformat()
        }

    # ── STEP 3B: LOW RISK ─────────────────────────────────────────
    else:
        print(f"[MAIN] ✅ LOW RISK — running agent")

        result           = run_agent(alert_data)
        action_taken     = result["action_taken"]
        gemini_diagnosis = result["gemini_diagnosis"]

        pr_url = create_low_risk_pr(alert_data, action_taken, gemini_diagnosis)

        # Record in tracker
        if pr_url:
            pr_number = _extract_pr_number(pr_url)
            branch    = f"resolved/{datetime.now().strftime('%Y%m%d-%H%M%S')}-{resource}"
            record_incident(alert_data, "LOW", pr_url, pr_number, branch)

        send_resolution_email(resource, action_taken, pr_url)

        return {
            "status":        "auto_resolved",
            "risk":          "LOW",
            "dry_run":       CONFIG.get("agent_dry_run", True),
            "action_taken":  action_taken,
            "pr_url":        pr_url,
            "alert_summary": summary,
            "resource":      resource,
            "timestamp":     datetime.now().isoformat()
        }


@app.post("/monday-report", tags=["Reports"])
async def monday_report():
    """
    Generates Monday morning report.
    Called automatically by Cloud Scheduler every Monday at 9am IST.
    Can also be triggered manually from Swagger or curl.

    1. Gets all open incidents from tracker
    2. Creates a GitHub Issue with full summary
    3. Sends report email
    """
    print(f"\n[MAIN] 📊 Monday report triggered")

    report_data = generate_monday_report()
    send_monday_report_email(report_data)

    return {
        "status":              "monday_report_generated",
        "week":                report_data["week_date"],
        "total_open":          report_data["total_open"],
        "high_risk_open":      report_data["high_risk_open"],
        "low_risk_open":       report_data["low_risk_open"],
        "critical_unresolved": report_data["critical_unresolved"],
        "github_issue":        report_data["issue_url"],
        "timestamp":           datetime.now().isoformat()
    }


@app.get("/incidents/open", tags=["Reports"])
async def get_open_incidents():
    """View all currently open incidents from the tracker."""
    from incident_tracker import get_all_open_incidents
    open_incidents = get_all_open_incidents()
    return {
        "total_open": len(open_incidents),
        "incidents":  open_incidents
    }


@app.get("/incidents/unresolved-high-risk", tags=["Reports"])
async def get_unresolved():
    """View HIGH RISK incidents open more than 7 days."""
    unresolved = get_unresolved_high_risk(days=7)
    return {
        "count":      len(unresolved),
        "incidents":  unresolved
    }


@app.post("/test/low-risk", tags=["Testing"])
async def test_low_risk():
    return await handle_alert(AlertRequest(incident=IncidentData(
        summary="Cloud Run service my-api returning 503 errors and may be crashed",
        condition_name="cloud_run_5xx_errors",
        resource_name="my-api",
        scoping_project_id=os.environ.get("GCP_PROJECT_ID", "poc-genai-chatbot"),
        state="open",
        started_at=datetime.now().isoformat()
    )))


@app.post("/test/high-risk", tags=["Testing"])
async def test_high_risk():
    return await handle_alert(AlertRequest(incident=IncidentData(
        summary="Unusual IAM permission change — owner role granted on production database",
        condition_name="iam_policy_change",
        resource_name="prod-database",
        scoping_project_id=os.environ.get("GCP_PROJECT_ID", "poc-genai-chatbot"),
        state="open",
        started_at=datetime.now().isoformat()
    )))


@app.get("/dry-run-logs", tags=["Dry Run"])
def get_dry_run_logs(last_n_lines: int = 80):
    log_file = CONFIG.get("dry_run_log_file", "dry_run_logs.txt")
    try:
        with open(log_file, "r") as f:
            lines = f.readlines()
        return {"total_lines": len(lines), "logs": "".join(lines[-last_n_lines:])}
    except FileNotFoundError:
        return {"message": "No dry run logs yet"}


@app.delete("/dry-run-logs/clear", tags=["Dry Run"])
def clear_dry_run_logs():
    log_file = CONFIG.get("dry_run_log_file", "dry_run_logs.txt")
    with open(log_file, "w") as f:
        f.write("")
    return {"message": "Logs cleared"}


# ── HELPERS ───────────────────────────────────────────────────────

def _extract_pr_number(pr_url: str) -> int:
    """Extract PR number from GitHub URL."""
    try:
        return int(pr_url.rstrip("/").split("/")[-1])
    except (ValueError, IndexError):
        return 0


def _send_recurrence_email(summary, resource, count, days_ago, pr_url, risk):
    """Send email when same error occurs again within 7 days."""
    from notifier import _send_email
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    sender    = os.environ.get("SENDER_EMAIL", "")
    password  = os.environ.get("SENDER_PASSWORD", "")
    recipient = os.environ.get("ALERT_EMAIL", "")

    if not sender or not password or not recipient:
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    color     = "#c0392b" if risk == "HIGH" else "#f39c12"
    icon      = "🚨" if risk == "HIGH" else "⚠️"

    msg            = MIMEMultipart("alternative")
    msg["Subject"] = f"{icon} RECURRING ERROR — {resource} — Occurrence #{count}"
    msg["From"]    = sender
    msg["To"]      = recipient

    html_body = f"""
<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;max-width:700px;margin:0 auto;padding:20px;">
  <div style="background:{color};padding:25px;border-radius:8px 8px 0 0;">
    <h1 style="color:white;margin:0;">{icon} Recurring Error — Occurrence #{count}</h1>
    <p style="color:#ffcccc;margin:8px 0 0 0;">
      Same error seen {days_ago} days ago — PR is still open and unresolved
    </p>
  </div>
  <div style="background:white;padding:25px;border-left:5px solid {color};">
    <table style="width:100%;border-collapse:collapse;">
      <tr><td style="padding:8px;color:#666;width:130px;"><b>Time</b></td>
          <td style="padding:8px;">{timestamp}</td></tr>
      <tr style="background:#fafafa;">
          <td style="padding:8px;color:#666;"><b>Resource</b></td>
          <td style="padding:8px;font-weight:bold;">{resource}</td></tr>
      <tr><td style="padding:8px;color:#666;"><b>Occurrence</b></td>
          <td style="padding:8px;color:{color};font-weight:bold;">#{count} times</td></tr>
      <tr style="background:#fafafa;">
          <td style="padding:8px;color:#666;"><b>Last Seen</b></td>
          <td style="padding:8px;">{days_ago} day(s) ago</td></tr>
      <tr><td style="padding:8px;color:#666;"><b>Summary</b></td>
          <td style="padding:8px;">{summary}</td></tr>
      <tr style="background:#fef3cd;">
          <td style="padding:8px;color:#666;"><b>GitHub PR</b></td>
          <td style="padding:8px;">
            <a href="{pr_url}" style="color:#1a56a0;font-weight:bold;">
              View Existing PR (comment added) →
            </a>
          </td></tr>
    </table>
  </div>
  <div style="background:#fff3cd;padding:20px;margin-top:3px;border-left:5px solid #f39c12;">
    <h3 style="color:#856404;margin:0 0 10px 0;">⚠️ This error keeps recurring</h3>
    <p style="color:#333;margin:0;">
      The same error has occurred {count} times. The existing PR has been updated
      with a new comment. Please review and resolve the root cause to prevent
      further recurrence.
    </p>
  </div>
  <div style="padding:15px;text-align:center;color:#999;font-size:12px;margin-top:3px;">
    🤖 GCP SRE Agent v3.0
  </div>
</body>
</html>
"""

    msg.attach(MIMEText(html_body, "html"))
    _send_email(msg, sender, password, recipient, "RECURRING")
