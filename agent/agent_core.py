"""
agent_core.py — now returns diagnosis for ticket creation
"""

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

RULES:
1. NEVER delete any resource
2. NEVER modify IAM
3. NEVER touch databases
4. NEVER scale beyond 10 instances
5. ALWAYS call get_recent_logs FIRST
6. Maximum 5 steps

TOOLS: {tools}
Tool names: {tool_names}

ALERT: {input}

Thought: What is the issue?
Action: [tool]
Action Input: [input]
Observation: [result]
Thought: What next?
Final Answer: [Exactly what you did and outcome]

{agent_scratchpad}
""")


def generate_gemini_diagnosis(alert_data: dict) -> str:
    """Generate root cause diagnosis for LOW RISK ticket."""
    incident = alert_data.get("incident", {})
    prompt = f"""
You are a GCP SRE expert. Analyze this alert for a developer ticket.

Alert   : {incident.get('summary', 'Unknown')}
Condition: {incident.get('condition_name', 'Unknown')}
Resource : {incident.get('resource_name', 'Unknown')}

Write a concise diagnosis (max 150 words) with these sections:

**Root Cause:** What most likely caused this.
**What Happened:** What was happening at infrastructure level.
**User Impact:** What the user experienced.
**Prevention:** 3 specific steps to stop this happening again.
"""
    try:
        return llm.invoke(prompt).content
    except Exception as e:
        return f"Diagnosis unavailable: {str(e)}"


def generate_gemini_solution(alert_data: dict) -> str:
    """Generate solution steps for HIGH RISK ticket."""
    incident = alert_data.get("incident", {})
    project  = incident.get("scoping_project_id", "poc-genai-chatbot")
    resource = incident.get("resource_name", "unknown")

    prompt = f"""
You are a GCP SRE expert. A HIGH RISK alert was escalated to a human engineer.
The AI agent did NOT auto-fix this. Give the developer a solution guide.

Alert    : {incident.get('summary', 'Unknown')}
Condition: {incident.get('condition_name', 'Unknown')}
Resource : {resource}
Project  : {project}

Write a solution guide (max 250 words):

**Immediate Actions:**
Numbered list — first 3 things to do RIGHT NOW.

**Investigation Commands:**
Actual gcloud commands to find root cause.
Use project={project} and resource={resource} in the commands.

**Fix Steps:**
Exact steps to resolve this specific issue type.

**Verification:**
How to confirm the fix worked.

Use actual gcloud commands. Be specific and actionable.
"""
    try:
        return llm.invoke(prompt).content
    except Exception as e:
        return f"Solution unavailable: {str(e)}"


def log_dry_run(alert_data: dict, plan: str):
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
    Run agent for LOW RISK alerts.
    Returns dict with action_taken + gemini_diagnosis for ticket creation.
    """
    is_dry_run = CONFIG.get("agent_dry_run", True)

    alert_text = f"""
Summary   : {alert_data.get('incident', {}).get('summary', 'Unknown')}
Condition : {alert_data.get('incident', {}).get('condition_name', 'Unknown')}
Resource  : {alert_data.get('incident', {}).get('resource_name', 'Unknown')}
Project   : {alert_data.get('incident', {}).get('scoping_project_id', 'Unknown')}
State     : {alert_data.get('incident', {}).get('state', 'Unknown')}
"""

    # Always generate diagnosis for ticket
    print(f"[AGENT CORE] Generating Gemini diagnosis for ticket...")
    gemini_diagnosis = generate_gemini_diagnosis(alert_data)

    if is_dry_run:
        print(f"[AGENT CORE] 🔍 DRY RUN MODE")
        prompt = f"""
GCP SRE DRY RUN — write a detailed action plan.

Alert: {alert_text}

Format:
1. DIAGNOSIS: Root cause
2. FIRST ACTION: Tool + input + expected output
3. REMEDIATION: Tool + input + reasoning  
4. VERIFICATION: How to confirm fix
5. FALLBACK: If main fix fails

Available tools: {[t.name for t in ALL_TOOLS]}
"""
        try:
            plan         = llm.invoke(prompt).content
            action_taken = f"[DRY RUN]\n\n{plan}"
            log_dry_run(alert_data, plan)
        except Exception as e:
            action_taken = f"[DRY RUN] Error: {str(e)}"
            print(f"[AGENT CORE] ❌ {action_taken}")

    else:
        print(f"[AGENT CORE] ⚡ LIVE MODE")
        try:
            agent    = create_react_agent(llm, ALL_TOOLS, AGENT_PROMPT)
            executor = AgentExecutor(
                agent=agent, tools=ALL_TOOLS,
                verbose=True, max_iterations=5,
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
