import json
import re
import anthropic
from agent.state import AgentState
from config import settings

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

SYSTEM_PROMPT = """You are a senior software engineer analyzing a ticket and producing a plan.

Output ONLY valid JSON in this exact shape:
{
  "problem": "one sentence summary of the problem",
  "files_to_modify": ["path/to/file.py"],
  "plan": ["step 1", "step 2"],
  "risks": ["risk 1"]
}

Rules:
- Do NOT generate code
- Keep plan steps concrete and minimal
- files_to_modify must be real paths from the code graph
- If requirements are unclear output: {"status": "NEED_CLARIFICATION", "reason": "..."}
"""


def analyze_plan(state: AgentState) -> AgentState:
    print("[OPUS] Analyzing ticket and producing plan...")

    graph_text = json.dumps(
        {k: v for k, v in state["code_graph"].items() if k not in ("snippets",)}, indent=2
    )
    memory_text = "\n\n".join(state["memory_notes"]) or "No relevant past decisions found."

    ticket_text = f"""
TICKET: {state['ticket_title']}
EPIC: {state['ticket_epic']}
PRIORITY: {state['ticket_priority']}
PHASE: {state['ticket_phase']}
ROLES: {', '.join(state['ticket_roles'])}
DEPENDS ON: {state['ticket_depends_on']}

DESCRIPTION:
{state['ticket_body']}
""".strip()

    response = _client.messages.create(
        model="claude-opus-4-7",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"CODE GRAPH:\n{graph_text}",
                        "cache_control": {"type": "ephemeral"},
                    },
                    {
                        "type": "text",
                        "text": f"PAST DECISIONS:\n{memory_text}",
                        "cache_control": {"type": "ephemeral"},
                    },
                    {
                        "type": "text",
                        "text": ticket_text,
                    },
                ],
            }
        ],
    )

    raw = response.content[0].text
    result = _parse_json(raw)

    if result.get("status") == "NEED_CLARIFICATION":
        print(f"[OPUS] Clarification needed: {result.get('reason')}")
        return {**state, "status": "stopped", "failure_message": result.get("reason")}

    branch_name = _make_branch(state["ticket_id"], state["ticket_title"])
    print(f"[OPUS] Plan ready — {len(result.get('plan', []))} steps, "
          f"{len(result.get('files_to_modify', []))} file(s)")

    return {
        **state,
        "problem": result.get("problem", ""),
        "plan": result.get("plan", []),
        "files_to_modify": result.get("files_to_modify", []),
        "risks": result.get("risks", []),
        "branch_name": branch_name,
    }


def _parse_json(text: str) -> dict:
    if not text or not text.strip():
        raise ValueError("Opus returned an empty response")
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
