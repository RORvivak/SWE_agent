import re
import json
import subprocess
from agent.state import AgentState
from config import settings

PROMPT_TEMPLATE = """You are a senior software engineer analyzing a ticket and producing an implementation plan.

TICKET: {title}
EPIC: {epic}
PRIORITY: {priority}
PHASE: {phase}
ROLES: {roles}
DEPENDS ON: {depends_on}

DESCRIPTION:
{body}

RELEVANT CODE CONTEXT (from graphify query):
{graph_context}

PAST DECISIONS (from Obsidian vault):
{memory_notes}

Output ONLY valid JSON with no other text:
{{
  "problem": "one sentence summary",
  "files_to_modify": ["relative/path/to/file.py"],
  "plan": ["step 1", "step 2"],
  "risks": ["risk 1"]
}}

Rules:
- Do NOT generate code
- Keep plan steps concrete and minimal
- files_to_modify must be real paths that exist in this repo
- If requirements are unclear output: {{"status": "NEED_CLARIFICATION", "reason": "..."}}
"""


def analyze_plan(state: AgentState) -> AgentState:
    print("[OPUS] Analyzing ticket and producing plan...")

    memory_text = "\n\n".join(state["memory_notes"]) or "No relevant past decisions found."

    prompt = PROMPT_TEMPLATE.format(
        title=state["ticket_title"],
        epic=state["ticket_epic"],
        priority=state["ticket_priority"],
        phase=state["ticket_phase"],
        roles=", ".join(state["ticket_roles"]),
        depends_on=state["ticket_depends_on"],
        body=state["ticket_body"],
        graph_context=state["graph_context"] or "No graph context available.",
        memory_notes=memory_text,
    )

    result = subprocess.run(
        [settings.claude_bin, "-p", prompt, "--model", "claude-opus-4-7",
         "--dangerously-skip-permissions"],
        capture_output=True,
        text=True,
        cwd=settings.repo_path,
        timeout=300,
    )

    if result.returncode != 0:
        raise RuntimeError(f"claude subprocess failed:\n{result.stderr[:500]}")

    parsed = _parse_json(result.stdout)

    if parsed.get("status") == "NEED_CLARIFICATION":
        print(f"[OPUS] Clarification needed: {parsed.get('reason')}")
        return {**state, "status": "stopped", "failure_message": parsed.get("reason")}

    branch_name = _make_branch(state["ticket_id"], state["ticket_title"])
    print(f"[OPUS] Plan ready — {len(parsed.get('plan', []))} steps, "
          f"{len(parsed.get('files_to_modify', []))} file(s)")

    return {
        **state,
        "problem": parsed.get("problem", ""),
        "plan": parsed.get("plan", []),
        "files_to_modify": parsed.get("files_to_modify", []),
        "risks": parsed.get("risks", []),
        "branch_name": branch_name,
    }


def _parse_json(text: str) -> dict:
    if not text or not text.strip():
        raise ValueError("claude subprocess returned empty response")
    match = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
    if match:
        text = match.group(1)
    else:
        text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    return json.loads(text.strip())


def _make_branch(ticket_id: str, title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40]
    short_id = ticket_id.replace("-", "")[:8]
    return f"feature/{short_id}-{slug}"
