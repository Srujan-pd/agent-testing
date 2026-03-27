import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime


def send_high_risk_email(alert_summary: str, alert_details: dict, pr_url: str = None):
    """
    Sends urgent email for HIGH RISK alert.
    Includes PR link so engineer can go directly to the incident report.
    """
    sender    = os.environ.get("SENDER_EMAIL", "")
    password  = os.environ.get("SENDER_PASSWORD", "")
    recipient = os.environ.get("ALERT_EMAIL", "")

    if not sender or not password or not recipient:
        print("[NOTIFIER] ⚠️  Email env vars not set — skipping email")
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    resource  = alert_details.get("incident", {}).get("resource_name", "Unknown")
    project   = alert_details.get("incident", {}).get("scoping_project_id", "Unknown")
    condition = alert_details.get("incident", {}).get("condition_name", "Unknown")

    pr_section_text = f"\nGitHub PR    : {pr_url}" if pr_url else ""
    pr_section_html = f"""
      <tr style="background:#fef3cd;">
        <td style="padding:10px 0;color:#666;"><b>📋 GitHub PR</b></td>
        <td style="padding:10px 0;">
          <a href="{pr_url}" style="color:#1a56a0;font-weight:bold;">
            View Incident Report & Solution →
          </a>
        </td>
      </tr>
    """ if pr_url else ""

    msg            = MIMEMultipart("alternative")
    msg["Subject"] = f"🚨 HIGH RISK GCP Alert — Action Required — {resource}"
    msg["From"]    = sender
    msg["To"]      = recipient

    text_body = f"""
╔══════════════════════════════════════════════════════════╗
║  🚨 HIGH RISK GCP ALERT — IMMEDIATE ACTION REQUIRED     ║
╚══════════════════════════════════════════════════════════╝

Time         : {timestamp}
Resource     : {resource}
Project      : {project}
Condition    : {condition}
Summary      : {alert_summary}{pr_section_text}

⚠️  The SRE Agent detected HIGH RISK signals.
    NO automatic changes were made to GCP.
    You must review and act manually.

WHAT TO DO:
1. Open the GitHub PR link above
2. Read the full incident report
3. Follow the step-by-step checklist
4. Apply the Gemini suggested solution
5. Close the PR after resolving

GCP Console  : https://console.cloud.google.com/home?project={project}
Cloud Run    : https://console.cloud.google.com/run?project={project}
IAM          : https://console.cloud.google.com/iam-admin/iam?project={project}
Monitoring   : https://console.cloud.google.com/monitoring?project={project}

Full Alert Details:
{str(alert_details)[:1500]}
"""

    html_body = f"""
<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;max-width:700px;margin:0 auto;
             padding:20px;background:#f5f5f5;">

  <!-- Header -->
  <div style="background:#c0392b;padding:25px;border-radius:8px 8px 0 0;">
    <h1 style="color:white;margin:0;font-size:24px;">
      🚨 HIGH RISK GCP Alert
    </h1>
    <p style="color:#ffcccc;margin:8px 0 0 0;font-size:14px;">
      Immediate action required — agent made ZERO changes to GCP
    </p>
  </div>

  <!-- Alert Details -->
  <div style="background:white;padding:25px;border-left:5px solid #c0392b;">
    <table style="width:100%;border-collapse:collapse;">
      <tr>
        <td style="padding:10px 0;color:#666;width:130px;"><b>Time</b></td>
        <td style="padding:10px 0;color:#333;">{timestamp}</td>
      </tr>
      <tr style="background:#fafafa;">
        <td style="padding:10px 0;color:#666;"><b>Resource</b></td>
        <td style="padding:10px 0;color:#c0392b;font-weight:bold;">{resource}</td>
      </tr>
      <tr>
        <td style="padding:10px 0;color:#666;"><b>Project</b></td>
        <td style="padding:10px 0;color:#333;">{project}</td>
      </tr>
      <tr style="background:#fafafa;">
        <td style="padding:10px 0;color:#666;"><b>Condition</b></td>
        <td style="padding:10px 0;color:#333;">{condition}</td>
      </tr>
      <tr>
        <td style="padding:10px 0;color:#666;"><b>Summary</b></td>
        <td style="padding:10px 0;color:#333;">{alert_summary}</td>
      </tr>
      {pr_section_html}
    </table>
  </div>

  <!-- What To Do -->
  <div style="background:white;padding:25px;margin-top:3px;
              border-left:5px solid #f39c12;">
    <h3 style="color:#856404;margin-top:0;">⚠️ What You Need to Do</h3>
    <ol style="color:#333;line-height:1.8;">
      <li>Open the GitHub PR link above — full incident report is there</li>
      <li>Read the Gemini suggested solution in the PR</li>
      <li>Follow the step-by-step action checklist</li>
      <li>Apply the fix in GCP Console</li>
      <li>Close the PR after resolving</li>
    </ol>
  </div>

  <!-- Quick Links -->
  <div style="background:white;padding:25px;margin-top:3px;">
    <h3 style="color:#333;margin-top:0;">🔎 Quick Links</h3>
    <table style="width:100%;">
      <tr>
        <td style="padding:5px;">
          <a href="https://console.cloud.google.com/run?project={project}"
             style="background:#1a56a0;color:white;padding:8px 16px;
                    text-decoration:none;border-radius:4px;display:inline-block;">
            Cloud Run
          </a>
        </td>
        <td style="padding:5px;">
          <a href="https://console.cloud.google.com/iam-admin/iam?project={project}"
             style="background:#c0392b;color:white;padding:8px 16px;
                    text-decoration:none;border-radius:4px;display:inline-block;">
            IAM Console
          </a>
        </td>
        <td style="padding:5px;">
          <a href="https://console.cloud.google.com/monitoring?project={project}"
             style="background:#27ae60;color:white;padding:8px 16px;
                    text-decoration:none;border-radius:4px;display:inline-block;">
            Monitoring
          </a>
        </td>
        <td style="padding:5px;">
          <a href="https://console.cloud.google.com/logs?project={project}"
             style="background:#8e44ad;color:white;padding:8px 16px;
                    text-decoration:none;border-radius:4px;display:inline-block;">
            Logs
          </a>
        </td>
      </tr>
    </table>
  </div>

  <!-- Full Details -->
  <div style="background:white;padding:25px;margin-top:3px;">
    <h3 style="color:#333;margin-top:0;">📋 Full Alert Details</h3>
    <pre style="background:#1e1e1e;color:#d4d4d4;padding:15px;
                border-radius:6px;font-size:12px;overflow-x:auto;
                white-space:pre-wrap;">{str(alert_details)[:1500]}</pre>
  </div>

  <!-- Footer -->
  <div style="background:#f5f5f5;padding:15px;text-align:center;
              color:#999;font-size:12px;margin-top:3px;">
    🤖 GCP SRE Automation Agent — Zero changes made to your infrastructure
  </div>

</body>
</html>
"""

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))
    _send_email(msg, sender, password, recipient, "HIGH RISK")


def send_resolution_email(resource_name: str, action_taken: str, pr_url: str = None):
    """
    Sends confirmation email after LOW RISK alert is auto-resolved.
    Includes PR link so engineer can review what was done.
    """
    sender    = os.environ.get("SENDER_EMAIL", "")
    password  = os.environ.get("SENDER_PASSWORD", "")
    recipient = os.environ.get("ALERT_EMAIL", "")

    if not sender or not password or not recipient:
        print("[NOTIFIER] ⚠️  Email env vars not set — skipping email")
        return

    project   = os.environ.get("GCP_PROJECT_ID", "poc-genai-chatbot")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    pr_section_text = f"\nGitHub PR    : {pr_url}" if pr_url else ""
    pr_section_html = f"""
      <tr style="background:#d4edda;">
        <td style="padding:10px 0;color:#666;"><b>📋 GitHub PR</b></td>
        <td style="padding:10px 0;">
          <a href="{pr_url}" style="color:#1a56a0;font-weight:bold;">
            View Incident Report →
          </a>
        </td>
      </tr>
    """ if pr_url else ""

    msg            = MIMEMultipart("alternative")
    msg["Subject"] = f"✅ Auto-Resolved: GCP Alert on {resource_name}"
    msg["From"]    = sender
    msg["To"]      = recipient

    text_body = f"""
╔══════════════════════════════════════════════════════════╗
║  ✅ GCP ALERT AUTO-RESOLVED                              ║
╚══════════════════════════════════════════════════════════╝

Time         : {timestamp}
Resource     : {resource_name}
Project      : {project}{pr_section_text}

The SRE Agent automatically detected and resolved this issue.
No engineer was woken up. No manual action is needed.

WHAT THE AGENT DID:
{action_taken[:800]}

VERIFY THE FIX:
Cloud Run  : https://console.cloud.google.com/run?project={project}
Monitoring : https://console.cloud.google.com/monitoring?project={project}
"""

    html_body = f"""
<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;max-width:700px;margin:0 auto;
             padding:20px;background:#f5f5f5;">

  <!-- Header -->
  <div style="background:#27ae60;padding:25px;border-radius:8px 8px 0 0;">
    <h1 style="color:white;margin:0;font-size:24px;">
      ✅ Alert Auto-Resolved
    </h1>
    <p style="color:#d5f5e3;margin:8px 0 0 0;font-size:14px;">
      Handled automatically — no engineer intervention needed
    </p>
  </div>

  <!-- Resolution Details -->
  <div style="background:white;padding:25px;border-left:5px solid #27ae60;">
    <table style="width:100%;border-collapse:collapse;">
      <tr>
        <td style="padding:10px 0;color:#666;width:130px;"><b>Time</b></td>
        <td style="padding:10px 0;color:#333;">{timestamp}</td>
      </tr>
      <tr style="background:#fafafa;">
        <td style="padding:10px 0;color:#666;"><b>Resource</b></td>
        <td style="padding:10px 0;color:#27ae60;font-weight:bold;">{resource_name}</td>
      </tr>
      <tr>
        <td style="padding:10px 0;color:#666;"><b>Project</b></td>
        <td style="padding:10px 0;color:#333;">{project}</td>
      </tr>
      <tr style="background:#fafafa;">
        <td style="padding:10px 0;color:#666;"><b>Status</b></td>
        <td style="padding:10px 0;color:#27ae60;font-weight:bold;">
          ✅ Resolved automatically
        </td>
      </tr>
      {pr_section_html}
    </table>
  </div>

  <!-- What Agent Did -->
  <div style="background:white;padding:25px;margin-top:3px;">
    <h3 style="color:#333;margin-top:0;">✅ What the Agent Did</h3>
    <div style="background:#f0fff4;border:1px solid #27ae60;border-radius:6px;
                padding:15px;color:#333;font-size:13px;white-space:pre-wrap;">
{action_taken[:1000]}
    </div>
  </div>

  <!-- Verify Links -->
  <div style="background:white;padding:25px;margin-top:3px;">
    <h3 style="color:#333;margin-top:0;">🔎 Verify the Fix</h3>
    <table>
      <tr>
        <td style="padding:5px;">
          <a href="https://console.cloud.google.com/run?project={project}"
             style="background:#1a56a0;color:white;padding:8px 16px;
                    text-decoration:none;border-radius:4px;display:inline-block;">
            Cloud Run
          </a>
        </td>
        <td style="padding:5px;">
          <a href="https://console.cloud.google.com/monitoring?project={project}"
             style="background:#27ae60;color:white;padding:8px 16px;
                    text-decoration:none;border-radius:4px;display:inline-block;">
            Monitoring
          </a>
        </td>
        <td style="padding:5px;">
          <a href="https://console.cloud.google.com/logs?project={project}"
             style="background:#8e44ad;color:white;padding:8px 16px;
                    text-decoration:none;border-radius:4px;display:inline-block;">
            Logs
          </a>
        </td>
      </tr>
    </table>
  </div>

  <!-- Footer -->
  <div style="background:#f5f5f5;padding:15px;text-align:center;
              color:#999;font-size:12px;margin-top:3px;">
    🤖 GCP SRE Automation Agent — Issue resolved before you even noticed
  </div>

</body>
</html>
"""

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))
    _send_email(msg, sender, password, recipient, "RESOLVED")


def _send_email(msg, sender: str, password: str, recipient: str, email_type: str):
    """Internal helper — sends via Gmail SMTP SSL."""
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.sendmail(sender, recipient, msg.as_string())
        print(f"[NOTIFIER] ✅ {email_type} email sent to {recipient}")
    except smtplib.SMTPAuthenticationError:
        print("[NOTIFIER] ❌ Auth failed — check SENDER_EMAIL and SENDER_PASSWORD")
    except Exception as e:
        print(f"[NOTIFIER] ❌ Email error: {str(e)}")
