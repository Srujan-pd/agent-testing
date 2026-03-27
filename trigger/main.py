import base64
import json
import os
import requests
import google.auth
import google.auth.transport.requests
from google.oauth2 import id_token

AGENT_URL = os.environ.get("AGENT_URL", "")


def handle_pubsub(event, context):
    """
    Entry point for the Cloud Function.
    Triggered automatically by every message on gcp-alerts-topic.

    Args:
        event (dict):   The Pub/Sub event data. Contains 'data' key
                        with base64-encoded message and 'attributes'.
        context (obj):  Metadata about the event (event_id, timestamp, etc.)
    """

    print(f"[TRIGGER] ── Cloud Function triggered ──")
    print(f"[TRIGGER] Event ID: {context.event_id}")
    print(f"[TRIGGER] Timestamp: {context.timestamp}")

    if not AGENT_URL:
        print("[TRIGGER] ❌ ERROR: AGENT_URL environment variable is not set!")
        print("[TRIGGER] Set it when deploying: --set-env-vars AGENT_URL=https://your-cloud-run-url")
        return

    # ── STEP 1: DECODE THE PUB/SUB MESSAGE ─────────────────────
    if "data" not in event:
        print("[TRIGGER] ⚠️  No data in Pub/Sub event — creating minimal alert")
        alert_data = {
            "incident": {
                "summary": "Empty Pub/Sub message received — possible test trigger",
                "condition_name": "unknown",
                "resource_name": "unknown",
                "state": "open"
            }
        }
    else:
        try:
            raw_message = base64.b64decode(event["data"]).decode("utf-8")
            print(f"[TRIGGER] Raw message (first 300 chars): {raw_message[:300]}")
        except Exception as e:
            print(f"[TRIGGER] ❌ Failed to decode base64 message: {str(e)}")
            return

        # ── STEP 2: PARSE AS JSON ────────────────────────────────
        try:
            alert_data = json.loads(raw_message)
            print(f"[TRIGGER] ✅ Successfully parsed JSON alert")
        except json.JSONDecodeError:
            # GCP sometimes sends plain text notifications
            print(f"[TRIGGER] ⚠️  Message is not JSON — wrapping as text alert")
            alert_data = {
                "incident": {
                    "summary": raw_message[:500],
                    "condition_name": "plain_text_alert",
                    "resource_name": "unknown",
                    "state": "open"
                }
            }

    # ── STEP 3: GET IDENTITY TOKEN FOR CLOUD RUN AUTH ──────────
    # Cloud Run requires authentication — it's not publicly accessible.
    # We use a Google identity token to prove the Cloud Function
    # is authorized to call the Cloud Run service.
    try:
        auth_req = google.auth.transport.requests.Request()
        token = id_token.fetch_id_token(auth_req, AGENT_URL)
        print(f"[TRIGGER] ✅ Got identity token for Cloud Run authentication")
    except Exception as e:
        print(f"[TRIGGER] ❌ Failed to get identity token: {str(e)}")
        print("[TRIGGER] Make sure the Cloud Function service account has 'roles/run.invoker' on the Cloud Run service")
        return

    # ── STEP 4: CALL THE CLOUD RUN AGENT ────────────────────────
    try:
        print(f"[TRIGGER] Calling agent at: {AGENT_URL}/handle-alert")
        response = requests.post(
            f"{AGENT_URL}/handle-alert",
            json=alert_data,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            timeout=120   # 2 minute timeout — agent may take time to think
        )

        print(f"[TRIGGER] ✅ Agent response status: {response.status_code}")
        print(f"[TRIGGER] Agent response body: {response.text[:500]}")

        if response.status_code != 200:
            print(f"[TRIGGER] ⚠️  Non-200 response from agent — check Cloud Run logs")

    except requests.Timeout:
        print(f"[TRIGGER] ❌ Timeout calling agent — the agent took longer than 120 seconds")
        print("[TRIGGER] Consider increasing Cloud Run timeout or reducing agent complexity")
    except requests.ConnectionError as e:
        print(f"[TRIGGER] ❌ Connection error calling agent: {str(e)}")
        print(f"[TRIGGER] Is the Cloud Run URL correct? AGENT_URL={AGENT_URL}")
    except Exception as e:
        print(f"[TRIGGER] ❌ Unexpected error: {str(e)}")

    print(f"[TRIGGER] ── Cloud Function complete ──\n")
