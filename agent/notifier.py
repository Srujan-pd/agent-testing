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


def send_monday_report_email(report_data: dict):
    """
    Sends Monday morning report email with all unresolved incidents.
    """
    sender    = os.environ.get("SENDER_EMAIL", "")
    password  = os.environ.get("SENDER_PASSWORD", "")
    recipient = os.environ.get("ALERT_EMAIL", "")

    if not sender or not password or not recipient:
        print("[NOTIFIER] ⚠️  Email vars not set — skipping Monday email")
        return

    week_date   = report_data.get("week_date", "This Week")
    total_open  = report_data.get("total_open", 0)
    high_count  = report_data.get("high_risk_open", 0)
    low_count   = report_data.get("low_risk_open", 0)
    critical    = report_data.get("critical_unresolved", 0)
    issue_url   = report_data.get("issue_url", "")
    high_list   = report_data.get("high_risk_list", [])
    low_list    = report_data.get("low_risk_list", [])
    critical_list = report_data.get("critical_list", [])
    timestamp   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    msg            = MIMEMultipart("alternative")
    msg["Subject"] = f"📊 Monday SRE Report — {week_date} — {total_open} Open Incidents"
    msg["From"]    = sender
    msg["To"]      = recipient

    # Build high risk rows for email
    high_rows = ""
    for inc in high_list:
        days_open = inc.get("days_open", "")
        days_str  = f" ({days_open} days)" if days_open else ""
        high_rows += f"""
        <tr style="background:#fff5f5;">
          <td style="padding:8px;color:#c0392b;font-weight:bold;">{inc['resource']}</td>
          <td style="padding:8px;">{inc['condition']}</td>
          <td style="padding:8px;">{inc.get('count',1)}x</td>
          <td style="padding:8px;color:#c0392b;">{inc.get('first_seen','')[:10]}{days_str}</td>
          <td style="padding:8px;">
            <a href="{inc.get('pr_url','')}" style="color:#1a56a0;">View PR</a>
          </td>
        </tr>"""

    # Build low risk rows for email
    low_rows = ""
    for inc in low_list:
        low_rows += f"""
        <tr>
          <td style="padding:8px;">{inc['resource']}</td>
          <td style="padding:8px;">{inc['condition']}</td>
          <td style="padding:8px;">{inc.get('count',1)}x</td>
          <td style="padding:8px;">{inc.get('first_seen','')[:10]}</td>
          <td style="padding:8px;">
            <a href="{inc.get('pr_url','')}" style="color:#1a56a0;">View PR</a>
          </td>
        </tr>"""

    critical_banner = ""
    if critical > 0:
        critical_banner = f"""
  <div style="background:#c0392b;color:white;padding:15px;margin-bottom:3px;
              border-radius:4px;text-align:center;">
    ⚠️ {critical} HIGH RISK INCIDENT(S) OPEN FOR MORE THAN 7 DAYS — IMMEDIATE ACTION REQUIRED
  </div>"""

    issue_button = f"""
    <a href="{issue_url}"
       style="background:#1a56a0;color:white;padding:12px 24px;
              text-decoration:none;border-radius:5px;display:inline-block;
              font-weight:bold;">
      View Full Monday Report on GitHub →
    </a>""" if issue_url else ""

    html_body = f"""
<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;max-width:750px;margin:0 auto;
             padding:20px;background:#f5f5f5;">

  <!-- Header -->
  <div style="background:#2c3e50;padding:25px;border-radius:8px 8px 0 0;">
    <h1 style="color:white;margin:0;font-size:24px;">
      📊 Monday Morning SRE Report
    </h1>
    <p style="color:#bdc3c7;margin:8px 0 0 0;">
      Week of {week_date} — Generated at {timestamp}
    </p>
  </div>

  {critical_banner}

  <!-- Summary Cards -->
  <div style="background:white;padding:25px;display:flex;gap:15px;">
    <div style="flex:1;background:#fef2f2;padding:15px;border-radius:8px;
                border-left:4px solid #c0392b;text-align:center;">
      <div style="font-size:32px;font-weight:bold;color:#c0392b;">{high_count}</div>
      <div style="color:#666;font-size:13px;">HIGH RISK Open</div>
    </div>
    <div style="flex:1;background:#f0fff4;padding:15px;border-radius:8px;
                border-left:4px solid #27ae60;text-align:center;">
      <div style="font-size:32px;font-weight:bold;color:#27ae60;">{low_count}</div>
      <div style="color:#666;font-size:13px;">LOW RISK Open</div>
    </div>
    <div style="flex:1;background:#fffbf0;padding:15px;border-radius:8px;
                border-left:4px solid #f39c12;text-align:center;">
      <div style="font-size:32px;font-weight:bold;color:#f39c12;">{total_open}</div>
      <div style="color:#666;font-size:13px;">Total Open</div>
    </div>
    <div style="flex:1;background:#fff5f5;padding:15px;border-radius:8px;
                border-left:4px solid #e74c3c;text-align:center;">
      <div style="font-size:32px;font-weight:bold;color:#e74c3c;">{critical}</div>
      <div style="color:#666;font-size:13px;">Critical (7+ days)</div>
    </div>
  </div>

  <!-- High Risk Table -->
  {'<div style="background:white;padding:25px;margin-top:3px;"><h3 style="color:#c0392b;margin-top:0;">🔴 HIGH RISK — Needs Your Action</h3><table style="width:100%;border-collapse:collapse;"><thead><tr style="background:#fef2f2;"><th style="padding:8px;text-align:left;">Resource</th><th style="padding:8px;text-align:left;">Condition</th><th style="padding:8px;text-align:left;">Count</th><th style="padding:8px;text-align:left;">First Seen</th><th style="padding:8px;text-align:left;">PR</th></tr></thead><tbody>' + high_rows + '</tbody></table></div>' if high_list else '<div style="background:white;padding:25px;margin-top:3px;"><h3 style="color:#27ae60;">✅ No HIGH RISK incidents open</h3></div>'}

  <!-- Low Risk Table -->
  {'<div style="background:white;padding:25px;margin-top:3px;"><h3 style="color:#f39c12;margin-top:0;">🟡 LOW RISK — Review and Close</h3><table style="width:100%;border-collapse:collapse;"><thead><tr style="background:#fafafa;"><th style="padding:8px;text-align:left;">Resource</th><th style="padding:8px;text-align:left;">Condition</th><th style="padding:8px;text-align:left;">Count</th><th style="padding:8px;text-align:left;">Date</th><th style="padding:8px;text-align:left;">PR</th></tr></thead><tbody>' + low_rows + '</tbody></table></div>' if low_list else ''}

  <!-- GitHub Button -->
  <div style="background:white;padding:25px;margin-top:3px;text-align:center;">
    {issue_button}
  </div>

  <!-- Footer -->
  <div style="background:#f5f5f5;padding:15px;text-align:center;
              color:#999;font-size:12px;margin-top:3px;">
    🤖 GCP SRE Agent — Monday Morning Report
  </div>

</body>
</html>
"""

    text_body = f"""
MONDAY MORNING SRE REPORT — {week_date}
{'='*50}

SUMMARY:
  HIGH RISK open    : {high_count}
  LOW RISK open     : {low_count}
  Total open        : {total_open}
  Critical (7+ days): {critical}

GitHub Report: {issue_url}

HIGH RISK INCIDENTS:
{chr(10).join([f"  - {i['resource']} ({i['condition']}) — {i.get('count',1)}x — {i.get('pr_url','')}" for i in high_list]) or '  None'}

LOW RISK INCIDENTS:
{chr(10).join([f"  - {i['resource']} ({i['condition']}) — {i.get('count',1)}x — {i.get('pr_url','')}" for i in low_list]) or '  None'}
"""

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))
    _send_email(msg, sender, password, recipient, "MONDAY REPORT")


def send_monday_report_email(report_data: dict):
    """
    Sends Monday morning report email with all unresolved incidents.
    """
    sender    = os.environ.get("SENDER_EMAIL", "")
    password  = os.environ.get("SENDER_PASSWORD", "")
    recipient = os.environ.get("ALERT_EMAIL", "")

    if not sender or not password or not recipient:
        print("[NOTIFIER] ⚠️  Email vars not set — skipping Monday email")
        return

    week_date   = report_data.get("week_date", "This Week")
    total_open  = report_data.get("total_open", 0)
    high_count  = report_data.get("high_risk_open", 0)
    low_count   = report_data.get("low_risk_open", 0)
    critical    = report_data.get("critical_unresolved", 0)
    issue_url   = report_data.get("issue_url", "")
    high_list   = report_data.get("high_risk_list", [])
    low_list    = report_data.get("low_risk_list", [])
    critical_list = report_data.get("critical_list", [])
    timestamp   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    msg            = MIMEMultipart("alternative")
    msg["Subject"] = f"📊 Monday SRE Report — {week_date} — {total_open} Open Incidents"
    msg["From"]    = sender
    msg["To"]      = recipient

    # Build high risk rows for email
    high_rows = ""
    for inc in high_list:
        days_open = inc.get("days_open", "")
        days_str  = f" ({days_open} days)" if days_open else ""
        high_rows += f"""
        <tr style="background:#fff5f5;">
          <td style="padding:8px;color:#c0392b;font-weight:bold;">{inc['resource']}</td>
          <td style="padding:8px;">{inc['condition']}</td>
          <td style="padding:8px;">{inc.get('count',1)}x</td>
          <td style="padding:8px;color:#c0392b;">{inc.get('first_seen','')[:10]}{days_str}</td>
          <td style="padding:8px;">
            <a href="{inc.get('pr_url','')}" style="color:#1a56a0;">View PR</a>
          </td>
        </tr>"""

    # Build low risk rows for email
    low_rows = ""
    for inc in low_list:
        low_rows += f"""
        <tr>
          <td style="padding:8px;">{inc['resource']}</td>
          <td style="padding:8px;">{inc['condition']}</td>
          <td style="padding:8px;">{inc.get('count',1)}x</td>
          <td style="padding:8px;">{inc.get('first_seen','')[:10]}</td>
          <td style="padding:8px;">
            <a href="{inc.get('pr_url','')}" style="color:#1a56a0;">View PR</a>
          </td>
        </tr>"""

    critical_banner = ""
    if critical > 0:
        critical_banner = f"""
  <div style="background:#c0392b;color:white;padding:15px;margin-bottom:3px;
              border-radius:4px;text-align:center;">
    ⚠️ {critical} HIGH RISK INCIDENT(S) OPEN FOR MORE THAN 7 DAYS — IMMEDIATE ACTION REQUIRED
  </div>"""

    issue_button = f"""
    <a href="{issue_url}"
       style="background:#1a56a0;color:white;padding:12px 24px;
              text-decoration:none;border-radius:5px;display:inline-block;
              font-weight:bold;">
      View Full Monday Report on GitHub →
    </a>""" if issue_url else ""

    html_body = f"""
<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;max-width:750px;margin:0 auto;
             padding:20px;background:#f5f5f5;">

  <!-- Header -->
  <div style="background:#2c3e50;padding:25px;border-radius:8px 8px 0 0;">
    <h1 style="color:white;margin:0;font-size:24px;">
      📊 Monday Morning SRE Report
    </h1>
    <p style="color:#bdc3c7;margin:8px 0 0 0;">
      Week of {week_date} — Generated at {timestamp}
    </p>
  </div>

  {critical_banner}

  <!-- Summary Cards -->
  <div style="background:white;padding:25px;display:flex;gap:15px;">
    <div style="flex:1;background:#fef2f2;padding:15px;border-radius:8px;
                border-left:4px solid #c0392b;text-align:center;">
      <div style="font-size:32px;font-weight:bold;color:#c0392b;">{high_count}</div>
      <div style="color:#666;font-size:13px;">HIGH RISK Open</div>
    </div>
    <div style="flex:1;background:#f0fff4;padding:15px;border-radius:8px;
                border-left:4px solid #27ae60;text-align:center;">
      <div style="font-size:32px;font-weight:bold;color:#27ae60;">{low_count}</div>
      <div style="color:#666;font-size:13px;">LOW RISK Open</div>
    </div>
    <div style="flex:1;background:#fffbf0;padding:15px;border-radius:8px;
                border-left:4px solid #f39c12;text-align:center;">
      <div style="font-size:32px;font-weight:bold;color:#f39c12;">{total_open}</div>
      <div style="color:#666;font-size:13px;">Total Open</div>
    </div>
    <div style="flex:1;background:#fff5f5;padding:15px;border-radius:8px;
                border-left:4px solid #e74c3c;text-align:center;">
      <div style="font-size:32px;font-weight:bold;color:#e74c3c;">{critical}</div>
      <div style="color:#666;font-size:13px;">Critical (7+ days)</div>
    </div>
  </div>

  <!-- High Risk Table -->
  {'<div style="background:white;padding:25px;margin-top:3px;"><h3 style="color:#c0392b;margin-top:0;">🔴 HIGH RISK — Needs Your Action</h3><table style="width:100%;border-collapse:collapse;"><thead><tr style="background:#fef2f2;"><th style="padding:8px;text-align:left;">Resource</th><th style="padding:8px;text-align:left;">Condition</th><th style="padding:8px;text-align:left;">Count</th><th style="padding:8px;text-align:left;">First Seen</th><th style="padding:8px;text-align:left;">PR</th></tr></thead><tbody>' + high_rows + '</tbody></table></div>' if high_list else '<div style="background:white;padding:25px;margin-top:3px;"><h3 style="color:#27ae60;">✅ No HIGH RISK incidents open</h3></div>'}

  <!-- Low Risk Table -->
  {'<div style="background:white;padding:25px;margin-top:3px;"><h3 style="color:#f39c12;margin-top:0;">🟡 LOW RISK — Review and Close</h3><table style="width:100%;border-collapse:collapse;"><thead><tr style="background:#fafafa;"><th style="padding:8px;text-align:left;">Resource</th><th style="padding:8px;text-align:left;">Condition</th><th style="padding:8px;text-align:left;">Count</th><th style="padding:8px;text-align:left;">Date</th><th style="padding:8px;text-align:left;">PR</th></tr></thead><tbody>' + low_rows + '</tbody></table></div>' if low_list else ''}

  <!-- GitHub Button -->
  <div style="background:white;padding:25px;margin-top:3px;text-align:center;">
    {issue_button}
  </div>

  <!-- Footer -->
  <div style="background:#f5f5f5;padding:15px;text-align:center;
              color:#999;font-size:12px;margin-top:3px;">
    🤖 GCP SRE Agent — Monday Morning Report
  </div>

</body>
</html>
"""

    text_body = f"""
MONDAY MORNING SRE REPORT — {week_date}
{'='*50}

SUMMARY:
  HIGH RISK open    : {high_count}
  LOW RISK open     : {low_count}
  Total open        : {total_open}
  Critical (7+ days): {critical}

GitHub Report: {issue_url}

HIGH RISK INCIDENTS:
{chr(10).join([f"  - {i['resource']} ({i['condition']}) — {i.get('count',1)}x — {i.get('pr_url','')}" for i in high_list]) or '  None'}

LOW RISK INCIDENTS:
{chr(10).join([f"  - {i['resource']} ({i['condition']}) — {i.get('count',1)}x — {i.get('pr_url','')}" for i in low_list]) or '  None'}
"""

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))
    _send_email(msg, sender, password, recipient, "MONDAY REPORT")


def send_monday_report_email(report_data: dict):
    """
    Sends Monday morning report email with all unresolved incidents.
    """
    sender    = os.environ.get("SENDER_EMAIL", "")
    password  = os.environ.get("SENDER_PASSWORD", "")
    recipient = os.environ.get("ALERT_EMAIL", "")

    if not sender or not password or not recipient:
        print("[NOTIFIER] ⚠️  Email vars not set — skipping Monday email")
        return

    week_date   = report_data.get("week_date", "This Week")
    total_open  = report_data.get("total_open", 0)
    high_count  = report_data.get("high_risk_open", 0)
    low_count   = report_data.get("low_risk_open", 0)
    critical    = report_data.get("critical_unresolved", 0)
    issue_url   = report_data.get("issue_url", "")
    high_list   = report_data.get("high_risk_list", [])
    low_list    = report_data.get("low_risk_list", [])
    critical_list = report_data.get("critical_list", [])
    timestamp   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    msg            = MIMEMultipart("alternative")
    msg["Subject"] = f"📊 Monday SRE Report — {week_date} — {total_open} Open Incidents"
    msg["From"]    = sender
    msg["To"]      = recipient

    # Build high risk rows for email
    high_rows = ""
    for inc in high_list:
        days_open = inc.get("days_open", "")
        days_str  = f" ({days_open} days)" if days_open else ""
        high_rows += f"""
        <tr style="background:#fff5f5;">
          <td style="padding:8px;color:#c0392b;font-weight:bold;">{inc['resource']}</td>
          <td style="padding:8px;">{inc['condition']}</td>
          <td style="padding:8px;">{inc.get('count',1)}x</td>
          <td style="padding:8px;color:#c0392b;">{inc.get('first_seen','')[:10]}{days_str}</td>
          <td style="padding:8px;">
            <a href="{inc.get('pr_url','')}" style="color:#1a56a0;">View PR</a>
          </td>
        </tr>"""

    # Build low risk rows for email
    low_rows = ""
    for inc in low_list:
        low_rows += f"""
        <tr>
          <td style="padding:8px;">{inc['resource']}</td>
          <td style="padding:8px;">{inc['condition']}</td>
          <td style="padding:8px;">{inc.get('count',1)}x</td>
          <td style="padding:8px;">{inc.get('first_seen','')[:10]}</td>
          <td style="padding:8px;">
            <a href="{inc.get('pr_url','')}" style="color:#1a56a0;">View PR</a>
          </td>
        </tr>"""

    critical_banner = ""
    if critical > 0:
        critical_banner = f"""
  <div style="background:#c0392b;color:white;padding:15px;margin-bottom:3px;
              border-radius:4px;text-align:center;">
    ⚠️ {critical} HIGH RISK INCIDENT(S) OPEN FOR MORE THAN 7 DAYS — IMMEDIATE ACTION REQUIRED
  </div>"""

    issue_button = f"""
    <a href="{issue_url}"
       style="background:#1a56a0;color:white;padding:12px 24px;
              text-decoration:none;border-radius:5px;display:inline-block;
              font-weight:bold;">
      View Full Monday Report on GitHub →
    </a>""" if issue_url else ""

    html_body = f"""
<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;max-width:750px;margin:0 auto;
             padding:20px;background:#f5f5f5;">

  <!-- Header -->
  <div style="background:#2c3e50;padding:25px;border-radius:8px 8px 0 0;">
    <h1 style="color:white;margin:0;font-size:24px;">
      📊 Monday Morning SRE Report
    </h1>
    <p style="color:#bdc3c7;margin:8px 0 0 0;">
      Week of {week_date} — Generated at {timestamp}
    </p>
  </div>

  {critical_banner}

  <!-- Summary Cards -->
  <div style="background:white;padding:25px;display:flex;gap:15px;">
    <div style="flex:1;background:#fef2f2;padding:15px;border-radius:8px;
                border-left:4px solid #c0392b;text-align:center;">
      <div style="font-size:32px;font-weight:bold;color:#c0392b;">{high_count}</div>
      <div style="color:#666;font-size:13px;">HIGH RISK Open</div>
    </div>
    <div style="flex:1;background:#f0fff4;padding:15px;border-radius:8px;
                border-left:4px solid #27ae60;text-align:center;">
      <div style="font-size:32px;font-weight:bold;color:#27ae60;">{low_count}</div>
      <div style="color:#666;font-size:13px;">LOW RISK Open</div>
    </div>
    <div style="flex:1;background:#fffbf0;padding:15px;border-radius:8px;
                border-left:4px solid #f39c12;text-align:center;">
      <div style="font-size:32px;font-weight:bold;color:#f39c12;">{total_open}</div>
      <div style="color:#666;font-size:13px;">Total Open</div>
    </div>
    <div style="flex:1;background:#fff5f5;padding:15px;border-radius:8px;
                border-left:4px solid #e74c3c;text-align:center;">
      <div style="font-size:32px;font-weight:bold;color:#e74c3c;">{critical}</div>
      <div style="color:#666;font-size:13px;">Critical (7+ days)</div>
    </div>
  </div>

  <!-- High Risk Table -->
  {'<div style="background:white;padding:25px;margin-top:3px;"><h3 style="color:#c0392b;margin-top:0;">🔴 HIGH RISK — Needs Your Action</h3><table style="width:100%;border-collapse:collapse;"><thead><tr style="background:#fef2f2;"><th style="padding:8px;text-align:left;">Resource</th><th style="padding:8px;text-align:left;">Condition</th><th style="padding:8px;text-align:left;">Count</th><th style="padding:8px;text-align:left;">First Seen</th><th style="padding:8px;text-align:left;">PR</th></tr></thead><tbody>' + high_rows + '</tbody></table></div>' if high_list else '<div style="background:white;padding:25px;margin-top:3px;"><h3 style="color:#27ae60;">✅ No HIGH RISK incidents open</h3></div>'}

  <!-- Low Risk Table -->
  {'<div style="background:white;padding:25px;margin-top:3px;"><h3 style="color:#f39c12;margin-top:0;">🟡 LOW RISK — Review and Close</h3><table style="width:100%;border-collapse:collapse;"><thead><tr style="background:#fafafa;"><th style="padding:8px;text-align:left;">Resource</th><th style="padding:8px;text-align:left;">Condition</th><th style="padding:8px;text-align:left;">Count</th><th style="padding:8px;text-align:left;">Date</th><th style="padding:8px;text-align:left;">PR</th></tr></thead><tbody>' + low_rows + '</tbody></table></div>' if low_list else ''}

  <!-- GitHub Button -->
  <div style="background:white;padding:25px;margin-top:3px;text-align:center;">
    {issue_button}
  </div>

  <!-- Footer -->
  <div style="background:#f5f5f5;padding:15px;text-align:center;
              color:#999;font-size:12px;margin-top:3px;">
    🤖 GCP SRE Agent — Monday Morning Report
  </div>

</body>
</html>
"""

    text_body = f"""
MONDAY MORNING SRE REPORT — {week_date}
{'='*50}

SUMMARY:
  HIGH RISK open    : {high_count}
  LOW RISK open     : {low_count}
  Total open        : {total_open}
  Critical (7+ days): {critical}

GitHub Report: {issue_url}

HIGH RISK INCIDENTS:
{chr(10).join([f"  - {i['resource']} ({i['condition']}) — {i.get('count',1)}x — {i.get('pr_url','')}" for i in high_list]) or '  None'}

LOW RISK INCIDENTS:
{chr(10).join([f"  - {i['resource']} ({i['condition']}) — {i.get('count',1)}x — {i.get('pr_url','')}" for i in low_list]) or '  None'}
"""

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))
    _send_email(msg, sender, password, recipient, "MONDAY REPORT")
