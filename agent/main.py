"""
main.py — v2.0 with ticket creation
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
from notifier import send_high_risk_email, send_resolution_email
from ticket_creator import create_low_risk_ticket, create_high_risk_ticket

app = FastAPI(
    title="GCP SRE Agent v2.0 — With Ticket Creation",
    description="Auto-resolves LOW RISK alerts and creates GitHub tickets for all incidents",
    version="2.0.0",
    docs_url="/docs"
)


class IncidentData(BaseModel):
    summary: str
    condition_name: Optional[str] = "Unknown"
    resource_name: Optional[str]  = "unknown-resource"
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
    agent_dry_run: Optional[bool]      = None
    log_all_decisions: Optional[bool]  = None


@app.get("/", tags=["Status"])
def root():
    return {
        "status":    "running",
        "version":   "2.0.0 — with ticket creation",
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
    Main endpoint — handles every alert.
    LOW RISK  → fixes it → creates GitHub ticket → sends resolution email
    HIGH RISK → creates GitHub ticket with AI solution → sends alert email
    """
    alert_data = alert.dict()
    summary    = alert.incident.summary
    resource   = alert.incident.resource_name

    print(f"\n{'='*55}")
    print(f"[MAIN] Alert   : {summary}")
    print(f"[MAIN] Resource: {resource}")
    print(f"{'='*55}")

    risk_level = classify_risk(alert_data)

    # ── HIGH RISK PATH ────────────────────────────────────────────
    if risk_level == "HIGH":
        print(f"[MAIN] 🚨 HIGH RISK — creating ticket + sending email")

        # Gemini generates solution for developer
        gemini_solution = generate_gemini_solution(alert_data)

        # Create GitHub ticket with full details + solution
        ticket_url = create_high_risk_ticket(alert_data, gemini_solution)

        # Send email with ticket link
        send_high_risk_email(summary, alert_data, ticket_url)

        return {
            "status":        "escalated_to_human",
            "risk":          "HIGH",
            "action":        "GitHub ticket created + email sent",
            "ticket_url":    ticket_url,
            "alert_summary": summary,
            "resource":      resource,
            "timestamp":     datetime.now().isoformat()
        }

    # ── LOW RISK PATH ─────────────────────────────────────────────
    else:
        print(f"[MAIN] ✅ LOW RISK — running agent")

        # Agent fixes + generates diagnosis
        result           = run_agent(alert_data)
        action_taken     = result["action_taken"]
        gemini_diagnosis = result["gemini_diagnosis"]

        # Create GitHub ticket showing what was done
        ticket_url = create_low_risk_ticket(
            alert_data,
            action_taken,
            gemini_diagnosis
        )

        # Send resolution email with ticket link
        send_resolution_email(resource, action_taken, ticket_url)

        return {
            "status":        "auto_resolved",
            "risk":          "LOW",
            "dry_run":       CONFIG.get("agent_dry_run", True),
            "action_taken":  action_taken,
            "ticket_url":    ticket_url,
            "alert_summary": summary,
            "resource":      resource,
            "timestamp":     datetime.now().isoformat()
        }


@app.post("/test/low-risk", tags=["Testing"])
async def test_low_risk():
    """Test LOW RISK — creates GitHub ticket + sends resolution email."""
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
    """Test HIGH RISK — creates GitHub ticket with AI solution + sends alert email."""
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
        return {"message": "No dry run logs yet — send a test alert first"}


@app.delete("/dry-run-logs/clear", tags=["Dry Run"])
def clear_dry_run_logs():
    log_file = CONFIG.get("dry_run_log_file", "dry_run_logs.txt")
    with open(log_file, "w") as f:
        f.write("")
    return {"message": "Logs cleared"}
