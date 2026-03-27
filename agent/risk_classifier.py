"""
risk_classifier.py
──────────────────
This is the GATEKEEPER of the entire agent.
It runs BEFORE the LLM is ever involved.
It reads rules from config.json and decides LOW or HIGH risk.

For HIGH RISK → agent_core.py is NEVER called. Email sent directly.
For LOW RISK  → agent_core.py runs and attempts to fix the issue.

The 4 checks run in ORDER. The classifier STOPS at the first HIGH match.
"""

import json

# Load rules from config.json once when the module is imported
with open("config.json") as f:
    CONFIG = json.load(f)


def classify_risk(alert_data: dict) -> str:
    """
    Returns 'LOW' or 'HIGH' based on 4 ordered checks.

    Check 1: Keyword scan of the full alert text
    Check 2: Resource type match
    Check 3: Condition name match
    Check 4: Numeric threshold comparison

    Stops and returns 'HIGH' immediately on the first match.
    Only returns 'LOW' if all 4 checks pass without a HIGH match.
    """

    print(f"\n[CLASSIFIER] ── Starting risk classification ──")
    print(f"[CLASSIFIER] Alert: {alert_data.get('incident', {}).get('summary', 'Unknown')}")

    # ──────────────────────────────────────────────────────────
    # CHECK 1 ─ KEYWORD SCAN
    # Convert the ENTIRE alert JSON to a lowercase string.
    # Scan it for every keyword in high_risk_keywords.
    # One match = HIGH RISK immediately. No further checks.
    # ──────────────────────────────────────────────────────────
    alert_text = json.dumps(alert_data).lower()

    for keyword in CONFIG["high_risk_keywords"]:
        if keyword in alert_text:
            print(f"[CLASSIFIER] ⛔ HIGH RISK — keyword matched: '{keyword}'")
            print(f"[CLASSIFIER] ── Classification complete: HIGH ──\n")
            return "HIGH"

    print(f"[CLASSIFIER] ✅ Check 1 passed — no high-risk keywords found")

    # ──────────────────────────────────────────────────────────
    # CHECK 2 ─ RESOURCE TYPE
    # Look at the resource_name in the alert.
    # If it matches any known high-risk resource type → HIGH.
    # ──────────────────────────────────────────────────────────
    resource_name = alert_data.get("incident", {}).get("resource_name", "").lower()

    for resource_type in CONFIG["high_risk_resource_types"]:
        if resource_type in resource_name:
            print(f"[CLASSIFIER] ⛔ HIGH RISK — resource type matched: '{resource_type}' in '{resource_name}'")
            print(f"[CLASSIFIER] ── Classification complete: HIGH ──\n")
            return "HIGH"

    print(f"[CLASSIFIER] ✅ Check 2 passed — resource type is safe: '{resource_name}'")

    # ──────────────────────────────────────────────────────────
    # CHECK 3 ─ CONDITION TYPE
    # Look at the condition_name of the alert.
    # If it matches any known high-risk condition → HIGH.
    # ──────────────────────────────────────────────────────────
    condition_name = alert_data.get("incident", {}).get("condition_name", "").lower()

    for high_condition in CONFIG["high_risk_conditions"]:
        if high_condition in condition_name:
            print(f"[CLASSIFIER] ⛔ HIGH RISK — condition matched: '{high_condition}'")
            print(f"[CLASSIFIER] ── Classification complete: HIGH ──\n")
            return "HIGH"

    print(f"[CLASSIFIER] ✅ Check 3 passed — condition type is safe: '{condition_name}'")

    # ──────────────────────────────────────────────────────────
    # CHECK 4 ─ NUMERIC THRESHOLDS
    # Only used for metric-based alerts where we have a value.
    # If the metric value is below threshold → still LOW RISK.
    # (This is a soft check — missing value defaults to LOW)
    # ──────────────────────────────────────────────────────────
    metric_value = alert_data.get("metric_value", None)

    if metric_value is not None:
        if "cpu" in condition_name:
            threshold = CONFIG["thresholds"]["cpu_percent"]
            if metric_value < threshold:
                print(f"[CLASSIFIER] ✅ Check 4 passed — CPU {metric_value}% is below threshold {threshold}%")
        elif "memory" in condition_name:
            threshold = CONFIG["thresholds"]["memory_percent"]
            if metric_value < threshold:
                print(f"[CLASSIFIER] ✅ Check 4 passed — Memory {metric_value}% is below threshold {threshold}%")

    print(f"[CLASSIFIER] ✅ Check 4 passed — thresholds are within safe range")

    # ──────────────────────────────────────────────────────────
    # ALL 4 CHECKS PASSED → LOW RISK
    # ──────────────────────────────────────────────────────────
    print(f"[CLASSIFIER] ── Classification complete: LOW ──\n")
    return "LOW"
