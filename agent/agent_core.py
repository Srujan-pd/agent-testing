import os
import json
from datetime import datetime
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate
from tools import ALL_TOOLS

with open("config.json") as f:
    CONFIG = json.load(f)

llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    google_api_key=os.environ["GEMINI_API_KEY"],
    temperature=0.1
)

AGENT_PROMPT = PromptTemplate.from_template("""
You are a careful GCP SRE agent. Resolve LOW RISK issues only.

RULES — NEVER VIOLATE:
1. NEVER delete any resource
2. NEVER modify IAM permissions
3. NEVER touch databases or Cloud SQL
4. NEVER scale beyond 10 instances
5. ALWAYS call get_recent_logs FIRST
6. Maximum 5 steps only

TOOLS: {tools}
Tool names: {tool_names}

ALERT: {input}

Thought: What is the issue and which resource is affected?
Action: [tool name]
Action Input: [input]
Observation: [result]
Thought: What should I do next based on the observation?
Final Answer: [Exactly what you did, which tools, what outcome]

{agent_scratchpad}
""")


def generate_gemini_diagnosis(alert_data: dict) -> str:
    """
    Generates root cause diagnosis for LOW RISK PR.
    Tells developer exactly what happened and why.
    """
    incident = alert_data.get("incident", {})
    prompt = f"""
You are a GCP SRE expert writing a diagnosis for a developer incident report.

Alert    : {incident.get('summary', 'Unknown')}
Condition: {incident.get('condition_name', 'Unknown')}
Resource : {incident.get('resource_name', 'Unknown')}
Project  : {incident.get('scoping_project_id', 'Unknown')}

Write a clear diagnosis (max 150 words) with these exact sections:

**Root Cause:**
What most likely caused this — be specific, not generic.

**What Happened:**
What was happening at the infrastructure level during the incident.

**User Impact:**
What the end user or calling service experienced.

**Prevention:**
3 specific, actionable steps to prevent recurrence.

Write for a developer who needs to understand quickly without searching.
"""
    try:
        return llm.invoke(prompt).content
    except Exception as e:
        return f"Diagnosis unavailable: {str(e)}"


def generate_gemini_solution(alert_data: dict) -> str:
    """
    Generates solution steps for HIGH RISK PR.
    Gives developer exact gcloud commands to fix the issue.
    """
    incident = alert_data.get("incident", {})
    project  = incident.get("scoping_project_id", "poc-genai-chatbot")
    resource = incident.get("resource_name", "unknown")

    prompt = f"""
You are a GCP SRE expert. A HIGH RISK alert was escalated to a human engineer.
The AI agent did NOT auto-fix this. Give the developer a complete solution.

Alert    : {incident.get('summary', 'Unknown')}
Condition: {incident.get('condition_name', 'Unknown')}
Resource : {resource}
Project  : {project}

Write a solution guide (max 250 words) with these sections:

**Immediate Actions (do these first):**
Numbered list — top 3 things to do RIGHT NOW to contain the issue.

**Investigation Commands:**
Actual gcloud commands to understand what happened.
Use the real values: project={project}, resource={resource}

**Fix Steps:**
Exact step-by-step commands to resolve this specific issue type.
Include real gcloud commands with the actual project and resource values.

**Verification:**
How to confirm the fix worked — include a gcloud command to verify.

Be specific. Use real gcloud commands. Do not be generic.
"""
    try:
        return llm.invoke(prompt).content
    except Exception as e:
        return f"Solution unavailable: {str(e)}"


def log_dry_run(alert_data: dict, plan: str):
    """Save dry run plan to log file."""
    log_file  = CONFIG.get("dry_run_log_file", "dry_run_logs.txt")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    summary   = alert_data.get("incident", {}).get("summary", "Unknown")
    resource  = alert_data.get("incident", {}).get("resource_name", "Unknown")

    with open(log_file, "a") as f:
        f.write(f"""
{'='*65}
TIMESTAMP : {timestamp}
MODE      : DRY RUN — No real GCP actions taken
ALERT     : {summary}
RESOURCE  : {resource}
{'='*65}
{plan}
{'='*65}

""")
    print(f"[AGENT CORE] ✅ Dry run plan written to {log_file}")


def run_agent(alert_data: dict) -> dict:
    """
    Main entry point for LOW RISK alerts.
    Returns dict with action_taken + gemini_diagnosis for PR creation.
    """
    is_dry_run = CONFIG.get("agent_dry_run", True)

    alert_text = f"""
Summary   : {alert_data.get('incident', {}).get('summary', 'Unknown')}
Condition : {alert_data.get('incident', {}).get('condition_name', 'Unknown')}
Resource  : {alert_data.get('incident', {}).get('resource_name', 'Unknown')}
Project   : {alert_data.get('incident', {}).get('scoping_project_id', 'Unknown')}
State     : {alert_data.get('incident', {}).get('state', 'Unknown')}
"""

    # Always generate diagnosis for PR regardless of mode
    print(f"[AGENT CORE] Generating Gemini diagnosis...")
    gemini_diagnosis = generate_gemini_diagnosis(alert_data)

    # ── DRY RUN ──────────────────────────────────────────────────
    if is_dry_run:
        print(f"[AGENT CORE] 🔍 DRY RUN MODE — planning only")
        prompt = f"""
GCP SRE DRY RUN — write a detailed action plan. No tools called.

Alert: {alert_text}

Write plan as:
1. DIAGNOSIS: What is broken and why
2. FIRST ACTION: Exact tool name + input + expected result
3. REMEDIATION: Exact tool + input + reasoning
4. VERIFICATION: How to confirm fix worked
5. FALLBACK: What to do if main fix fails

Available tools: {[t.name for t in ALL_TOOLS]}
"""
        try:
            plan         = llm.invoke(prompt).content
            action_taken = f"[DRY RUN — no real changes made]\n\n{plan}"
            log_dry_run(alert_data, plan)
        except Exception as e:
            action_taken = f"[DRY RUN] Error generating plan: {str(e)}"
            print(f"[AGENT CORE] ❌ {action_taken}")

    # ── LIVE MODE ────────────────────────────────────────────────
    else:
        print(f"[AGENT CORE] ⚡ LIVE MODE — taking real actions")
        try:
            agent    = create_react_agent(llm, ALL_TOOLS, AGENT_PROMPT)
            executor = AgentExecutor(
                agent=agent,
                tools=ALL_TOOLS,
                verbose=True,
                max_iterations=5,
                handle_parsing_errors=True
            )
            result       = executor.invoke({"input": alert_text})
            action_taken = result.get("output", "Agent completed")
            print(f"[AGENT CORE] ✅ {action_taken[:200]}")
        except Exception as e:
            action_taken = f"Agent error: {str(e)}"
            print(f"[AGENT CORE] ❌ {action_taken}")

    return {
        "action_taken":     action_taken,
        "gemini_diagnosis": gemini_diagnosis
    }
