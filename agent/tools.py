import subprocess
import os
import json
from langchain.tools import tool
from google.cloud import logging_v2

PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "your-project-id")
REGION = os.environ.get("GCP_REGION", "us-central1")


# ──────────────────────────────────────────────────────────────────
# TOOL 1 ─ GET RECENT LOGS
# The agent should call this FIRST before taking any action.
# Understanding the root cause leads to a better fix.
# ──────────────────────────────────────────────────────────────────
@tool
def get_recent_logs(resource_name: str) -> str:
    """Fetch recent WARNING and ERROR logs for a Cloud Run service.
    
    This tool should be called first to understand what's wrong with the service.
    It helps diagnose issues like crashes, OOM errors, or 5xx responses.
    
    Args:
        resource_name: The name of the Cloud Run service to fetch logs for
    
    Returns:
        A formatted string containing up to 20 recent WARNING/ERROR log entries,
        or a message if no logs are found.
    """
    print(f"[TOOL] get_recent_logs called for: {resource_name}")
    try:
        client = logging_v2.Client(project=PROJECT_ID)
        logs = []

        filter_str = f"""
            resource.labels.service_name="{resource_name}"
            severity >= WARNING
        """

        entries = client.list_entries(filter_=filter_str, max_results=20)

        for entry in entries:
            logs.append(
                f"[{entry.severity}] {entry.timestamp}: {str(entry.payload)[:200]}"
            )

        if logs:
            result = "\n".join(logs)
            print(f"[TOOL] Found {len(logs)} log entries")
            return result
        else:
            return (
                f"No recent WARNING or ERROR logs found for '{resource_name}'. "
                f"The service may be healthy or the issue may have resolved itself."
            )

    except Exception as e:
        error_msg = f"Could not fetch logs for '{resource_name}': {str(e)}"
        print(f"[TOOL] ERROR: {error_msg}")
        return error_msg


# ──────────────────────────────────────────────────────────────────
# TOOL 2 ─ CHECK SERVICE STATUS
# Use this to confirm whether a service is up, degraded, or down
# before deciding on a remediation action.
# ──────────────────────────────────────────────────────────────────
@tool
def check_service_status(service_name: str) -> str:
    """Check the current status and conditions of a Cloud Run service.
    
    Retrieves the service's conditions (Ready, ConfigurationsReady, RoutesReady)
    to determine if the service is healthy, degraded, or failed.
    
    Args:
        service_name: The name of the Cloud Run service to check
    
    Returns:
        A formatted string showing the service's condition statuses,
        or an error message if the check fails.
    """
    print(f"[TOOL] check_service_status called for: {service_name}")
    try:
        result = subprocess.run(
            [
                "gcloud", "run", "services", "describe", service_name,
                "--region", REGION,
                "--project", PROJECT_ID,
                "--format", "json"
            ],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            data = json.loads(result.stdout)
            conditions = data.get("status", {}).get("conditions", [])
            status_lines = []
            for c in conditions:
                status_lines.append(
                    f"  {c.get('type', 'Unknown')}: {c.get('status', 'Unknown')} "
                    f"— {c.get('message', 'No message')}"
                )
            if status_lines:
                output = f"Service '{service_name}' status:\n" + "\n".join(status_lines)
            else:
                output = f"Service '{service_name}' appears healthy — no condition issues found."
            print(f"[TOOL] Status check complete")
            return output
        else:
            return f"Could not describe service '{service_name}': {result.stderr[:300]}"

    except subprocess.TimeoutExpired:
        return f"Timeout checking status of '{service_name}' — GCP may be slow to respond."
    except Exception as e:
        error_msg = f"Error checking service status for '{service_name}': {str(e)}"
        print(f"[TOOL] ERROR: {error_msg}")
        return error_msg


# ──────────────────────────────────────────────────────────────────
# TOOL 3 ─ RESTART CLOUD RUN SERVICE
# Use this when logs show the service is crashed, OOM-killed,
# or returning 5xx errors that a restart would resolve.
# ──────────────────────────────────────────────────────────────────
@tool
def restart_cloud_run_service(service_name: str) -> str:
    """Restart a Cloud Run service by updating it (creates a new revision).
    
    This tool forces a new revision to be deployed, which restarts all instances.
    It includes safety checks to prevent restarting production-critical services.
    
    Args:
        service_name: The name of the Cloud Run service to restart
    
    Returns:
        Success message if restart was triggered, or an error/refusal message
        if the service name contains blocked keywords (prod, production, database, etc.)
    """
    print(f"[TOOL] restart_cloud_run_service called for: {service_name}")

    # Safety check: refuse if service name contains high-risk words
    blocked = ["prod", "production", "database", "sql", "payment"]
    for word in blocked:
        if word in service_name.lower():
            return (
                f"REFUSED: Cannot restart '{service_name}' — "
                f"name contains '{word}' which is a protected resource. "
                f"Escalate to a human engineer."
            )

    try:
        result = subprocess.run(
            [
                "gcloud", "run", "services", "update", service_name,
                "--region", REGION,
                "--project", PROJECT_ID,
                "--format", "json"
            ],
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode == 0:
            success_msg = (
                f"✅ Successfully restarted Cloud Run service '{service_name}' "
                f"in region {REGION}. A new revision has been deployed."
            )
            print(f"[TOOL] {success_msg}")
            return success_msg
        else:
            fail_msg = (
                f"❌ Failed to restart '{service_name}'. "
                f"GCP error: {result.stderr[:300]}"
            )
            print(f"[TOOL] {fail_msg}")
            return fail_msg

    except subprocess.TimeoutExpired:
        return f"Timeout restarting '{service_name}' — operation may still be in progress in GCP."
    except Exception as e:
        error_msg = f"Unexpected error restarting '{service_name}': {str(e)}"
        print(f"[TOOL] ERROR: {error_msg}")
        return error_msg


# ──────────────────────────────────────────────────────────────────
# TOOL 4 ─ SCALE UP CLOUD RUN
# Use this when the service is overloaded with traffic, causing
# high latency or timeouts, but is NOT crashed.
# ──────────────────────────────────────────────────────────────────
@tool
def scale_up_cloud_run(service_name: str, max_instances: str) -> str:
    """Scale a Cloud Run service to handle more traffic.
    
    Increases the max-instances limit to allow more concurrent containers.
    Has a safety cap of 10 instances maximum regardless of input.
    
    Args:
        service_name: The name of the Cloud Run service to scale
        max_instances: The desired maximum number of instances (will be capped at 10)
    
    Returns:
        Success message if scaling was applied, or an error/refusal message
        if the service name contains blocked keywords or the operation fails.
    """
    print(f"[TOOL] scale_up_cloud_run called: {service_name} → {max_instances} instances")

    # Safety cap — never exceed 10 instances regardless of LLM input
    MAX_ALLOWED = 10
    try:
        requested = int(max_instances)
    except ValueError:
        return f"Invalid max_instances value: '{max_instances}'. Must be a number."

    actual_instances = min(requested, MAX_ALLOWED)

    if requested > MAX_ALLOWED:
        print(f"[TOOL] ⚠️  Requested {requested} instances — capped at {MAX_ALLOWED}")

    # Safety check: refuse if service name contains high-risk words
    blocked = ["prod", "production", "database", "sql", "payment"]
    for word in blocked:
        if word in service_name.lower():
            return (
                f"REFUSED: Cannot scale '{service_name}' — "
                f"name contains '{word}' which is a protected resource."
            )

    try:
        result = subprocess.run(
            [
                "gcloud", "run", "services", "update", service_name,
                "--max-instances", str(actual_instances),
                "--region", REGION,
                "--project", PROJECT_ID,
                "--format", "json"
            ],
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode == 0:
            success_msg = (
                f"✅ Successfully scaled '{service_name}' to "
                f"max {actual_instances} instances in region {REGION}."
            )
            if requested > MAX_ALLOWED:
                success_msg += f" (Note: requested {requested} was capped at safety limit of {MAX_ALLOWED})"
            print(f"[TOOL] {success_msg}")
            return success_msg
        else:
            fail_msg = (
                f"❌ Failed to scale '{service_name}'. "
                f"GCP error: {result.stderr[:300]}"
            )
            print(f"[TOOL] {fail_msg}")
            return fail_msg

    except subprocess.TimeoutExpired:
        return f"Timeout scaling '{service_name}' — operation may still be in progress in GCP."
    except Exception as e:
        error_msg = f"Unexpected error scaling '{service_name}': {str(e)}"
        print(f"[TOOL] ERROR: {error_msg}")
        return error_msg


# ──────────────────────────────────────────────────────────────────
# TOOLS LIST
# Import this list in agent_core.py to give all tools to the agent.
# To add a new tool: create a function above with @tool decorator,
# then add it to this list. The LLM will automatically learn to use it.
# ──────────────────────────────────────────────────────────────────
ALL_TOOLS = [
    get_recent_logs,
    check_service_status,
    restart_cloud_run_service,
    scale_up_cloud_run,
]
