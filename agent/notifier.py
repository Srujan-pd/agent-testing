"""
notifier.py
───────────
This file sends emails in two scenarios:

  1. HIGH RISK alert  → send_high_risk_email()
     Called by main.py when risk_classifier returns 'HIGH'.
     Sends an urgent email with full alert details.
     Engineer must review and fix manually in GCP Console.

  2. LOW RISK resolved → send_resolution_email()
     Called by main.py after agent_core.py finishes.
     Sends a confirmation email describing what was fixed.
     Nothing happens silently — every action is communicated.

Uses Gmail SMTP on port 465 (SSL).
Requires a Gmail App Password (not your regular Gmail password).
How to get App Password:
  Google Account → Security → 2-Step Verification → App Passwords
  Create one named "SRE Agent" → copy the 16-digit password
"""

import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime


def send_high_risk_email(alert_summary: str, alert_details: dict, ticket_url: str = None):
    """
    Sends an urgent email when a HIGH RISK alert is detected.

    The engineer receives this email and must:
    1. Log into GCP Console
    2. Review the alert manually
    3. Take whatever action is appropriate
    4. The agent has done NOTHING to the resource

    Args:
        alert_summary (str): One-line description of the alert
        alert_details (dict): Full alert JSON for reference
    """
    sender   = os.environ["SENDER_EMAIL"]
    password = os.environ["SENDER_PASSWORD"]
    recipient = os.environ["ALERT_EMAIL"]

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    resource  = alert_details.get("incident", {}).get("resource_name", "Unknown")
    project   = alert_details.get("incident", {}).get("scoping_project_id", "Unknown")

    # Build the email
    msg = MIMEMultipart("alternative")
    ticket_line = f"\n🎫 Ticket: {ticket_url}" if ticket_url else ""
    msg["Subject"] = f"🚨 HIGH RISK GCP Alert — Manual Action Required — {resource}"
    msg["From"]    = sender
    msg["To"]      = recipient

    # Plain text fallback
    text_body = f"""
HIGH RISK GCP ALERT
===================
Time     : {timestamp}
Summary  : {alert_summary}
Resource : {resource}
Project  : {project}

Full Alert Details:
{str(alert_details)[:2000]}

⚠️  This alert was NOT auto-resolved.
The agent detected HIGH RISK signals and escalated to you.
Please review and take action manually in your GCP Console.

GCP Console: https://console.cloud.google.com/home/dashboard?project={project}
Cloud Run:   https://console.cloud.google.com/run?project={project}
Monitoring:  https://console.cloud.google.com/monitoring?project={project}
"""

    # HTML email (displayed in most email clients)
    html_body = f"""
<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto; padding: 20px; background: #f5f5f5;">

  <!-- Header -->
  <div style="background: #c0392b; padding: 20px; border-radius: 8px 8px 0 0;">
    <h1 style="color: white; margin: 0; font-size: 22px;">🚨 HIGH RISK GCP Alert</h1>
    <p style="color: #ffcccc; margin: 5px 0 0 0; font-size: 14px;">Manual action required — agent did NOT auto-resolve this</p>
  </div>

  <!-- Alert Details -->
  <div style="background: white; padding: 25px; border-left: 4px solid #c0392b;">
    <table style="width: 100%; border-collapse: collapse;">
      <tr>
        <td style="padding: 8px 0; color: #666; width: 120px;"><b>Time</b></td>
        <td style="padding: 8px 0; color: #333;">{timestamp}</td>
      </tr>
      <tr style="background: #fafafa;">
        <td style="padding: 8px 0; color: #666;"><b>Summary</b></td>
        <td style="padding: 8px 0; color: #333;">{alert_summary}</td>
      </tr>
      <tr>
        <td style="padding: 8px 0; color: #666;"><b>Resource</b></td>
        <td style="padding: 8px 0; color: #333;">{resource}</td>
      </tr>
      <tr style="background: #fafafa;">
        <td style="padding: 8px 0; color: #666;"><b>Project</b></td>
        <td style="padding: 8px 0; color: #333;">{project}</td>
      </tr>
    </table>
  </div>

  <!-- Full Details -->
  <div style="background: white; padding: 20px; margin-top: 2px;">
    <h3 style="color: #333; margin-top: 0;">Full Alert Payload</h3>
    <pre style="background: #1e1e1e; color: #d4d4d4; padding: 15px; border-radius: 6px;
                font-size: 12px; overflow-x: auto; white-space: pre-wrap;">
{str(alert_details)[:2000]}
    </pre>
  </div>

  <!-- Action Links -->
  <div style="background: #fff3cd; padding: 20px; margin-top: 2px; border-left: 4px solid #f39c12;">
    <h3 style="color: #856404; margin-top: 0;">⚠️ Action Required</h3>
    <p style="color: #856404;">This alert was NOT auto-resolved. Please investigate immediately.</p>
    <p>
      <a href="https://console.cloud.google.com/home/dashboard?project={project}"
         style="background: #1a56a0; color: white; padding: 10px 20px;
                text-decoration: none; border-radius: 5px; margin-right: 10px;">
        Open GCP Console
      </a>
      <a href="https://console.cloud.google.com/monitoring?project={project}"
         style="background: #27ae60; color: white; padding: 10px 20px;
                text-decoration: none; border-radius: 5px;">
        Open Monitoring
      </a>
    </p>
  </div>

  <!-- Footer -->
  <div style="background: #f5f5f5; padding: 15px; text-align: center; color: #999; font-size: 12px; margin-top: 2px;">
    GCP SRE Automation Agent — This email was sent automatically
  </div>

</body>
</html>
"""

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    _send_email(msg, sender, password, recipient, "HIGH RISK")


def send_resolution_email(resource_name: str, action_taken: str, ticket_url: str = None):
    """
    Sends a confirmation email after a LOW RISK alert is auto-resolved.

    Every auto-resolution sends this email so engineers are always
    aware of what the agent did. Nothing happens silently.

    Args:
        resource_name (str): The GCP resource that was affected
        action_taken (str): Description of what the agent did
    """
    sender    = os.environ["SENDER_EMAIL"]
    password  = os.environ["SENDER_PASSWORD"]
    recipient = os.environ["ALERT_EMAIL"]
    project   = os.environ.get("GCP_PROJECT_ID", "your-project")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    msg = MIMEMultipart("alternative")
    ticket_line = f"\n🎫 Ticket: {ticket_url}" if ticket_url else ""
    msg["Subject"] = f"✅ Auto-Resolved: GCP Alert on {resource_name}"
    msg["From"]    = sender
    msg["To"]      = recipient

    text_body = f"""
GCP ALERT AUTO-RESOLVED
=======================
Time      : {timestamp}
Resource  : {resource_name}
Project   : {project}

Action Taken:
{action_taken}

The issue was classified as LOW RISK and handled automatically.
No manual action is required.

To review: https://console.cloud.google.com/run?project={project}
"""

    html_body = f"""
<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto; padding: 20px; background: #f5f5f5;">

  <!-- Header -->
  <div style="background: #27ae60; padding: 20px; border-radius: 8px 8px 0 0;">
    <h1 style="color: white; margin: 0; font-size: 22px;">✅ Alert Auto-Resolved</h1>
    <p style="color: #d5f5e3; margin: 5px 0 0 0; font-size: 14px;">
      Low-risk issue handled automatically — no action required
    </p>
  </div>

  <!-- Resolution Details -->
  <div style="background: white; padding: 25px; border-left: 4px solid #27ae60;">
    <table style="width: 100%; border-collapse: collapse;">
      <tr>
        <td style="padding: 8px 0; color: #666; width: 120px;"><b>Time</b></td>
        <td style="padding: 8px 0; color: #333;">{timestamp}</td>
      </tr>
      <tr style="background: #fafafa;">
        <td style="padding: 8px 0; color: #666;"><b>Resource</b></td>
        <td style="padding: 8px 0; color: #333;">{resource_name}</td>
      </tr>
      <tr>
        <td style="padding: 8px 0; color: #666;"><b>Project</b></td>
        <td style="padding: 8px 0; color: #333;">{project}</td>
      </tr>
    </table>

    <h3 style="color: #333; margin-top: 20px;">Action Taken by Agent</h3>
    <div style="background: #f0fff4; border: 1px solid #27ae60; border-radius: 6px;
                padding: 15px; color: #333; font-size: 14px; white-space: pre-wrap;">
{action_taken[:1500]}
    </div>
  </div>

  <!-- Footer -->
  <div style="background: #f5f5f5; padding: 15px; text-align: center; color: #999;
              font-size: 12px; margin-top: 2px;">
    <a href="https://console.cloud.google.com/run?project={project}"
       style="color: #1a56a0;">Review in GCP Console</a>
    &nbsp;|&nbsp;
    GCP SRE Automation Agent
  </div>

</body>
</html>
"""

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    _send_email(msg, sender, password, recipient, "RESOLVED")


def _send_email(msg, sender: str, password: str, recipient: str, email_type: str):
    """Internal helper to send the email via Gmail SMTP."""
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.sendmail(sender, recipient, msg.as_string())
        print(f"[NOTIFIER] ✅ {email_type} email sent successfully to {recipient}")
    except smtplib.SMTPAuthenticationError:
        print(
            f"[NOTIFIER] ❌ Authentication failed. "
            f"Check SENDER_EMAIL and SENDER_PASSWORD in your .env file. "
            f"Make sure you are using a Gmail App Password, not your regular password."
        )
    except smtplib.SMTPException as e:
        print(f"[NOTIFIER] ❌ SMTP error sending {email_type} email: {str(e)}")
    except Exception as e:
        print(f"[NOTIFIER] ❌ Unexpected error sending {email_type} email: {str(e)}")
