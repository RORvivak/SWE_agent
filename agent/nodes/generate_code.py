import json
import re
import anthropic
from agent.state import AgentState
from config import settings

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

SYSTEM_PROMPT = """You are a senior software engineer implementing a plan.

Output ONLY valid JSON in this exact shape:
{
  "code_changes": [
    {
      "file": "path/to/file.py",
      "diff": "unified diff string"
    }
  ],
  "commit_message": "short imperative message",
  "pr_title": "concise PR title under 70 chars",
  "pr_description": "what changed, why, and impact"
}

Rules:
- Follow existing code style in the snippets provided
- Minimal changes only — do not refactor unrelated code
- diff must be a valid unified diff (--- a/file +++ b/file @@ ... @@)
- Max 20 files
- No secrets or credentials in diffs
"""


def generate_code(state: AgentState) -> AgentState:
    print("[SONNET] Generating code...")

    snippets_text = json.dumps(state["code_graph"].get("snippets", []), indent=2)

    plan_text = f"""
PROBLEM:
{state['problem']}

PLAN:
{chr(10).join(f'{i+1}. {step}' for i, step in enumerate(state['plan']))}

FILES TO MODIFY:
{chr(10).join(state['files_to_modify'])}

RISKS:
{chr(10).join(state['risks'])}
""".strip()

    response = _client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"RELEVANT CODE SNIPPETS:\n{snippets_text}",
                        "cache_control": {"type": "ephemeral"},
                    },
                    {
                        "type": "text",
                        "text": plan_text,
                    },
                ],
            }
        ],
    )

    raw = response.content[0].text
    result = _parse_json(raw)

    print(f"[SONNET] Generated {len(result.get('code_changes', []))} file change(s)")

    return {
        **state,
        "code_changes": result.get("code_changes", []),
        "commit_message": result.get("commit_message", ""),
        "pr_title": result.get("pr_title", state["ticket_title"]),
        "pr_description": result.get("pr_description", ""),
    }


def _parse_json(text: str) -> dict:
    match = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
    if match:
        text = match.group(1)
    return json.loads(text.strip())
