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
      "content": "complete file content as a string"
    }
  ],
  "commit_message": "short imperative message",
  "pr_title": "concise PR title under 70 chars",
  "pr_description": "what changed, why, and impact"
}

Rules:
- Follow existing code style in the snippets provided
- Minimal changes only — do not refactor unrelated code
- content must be the COMPLETE file content (not a diff), ready to write to disk
- Max 20 files
- No secrets or credentials in content
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

    with _client.messages.stream(
        model="claude-sonnet-4-6",
        max_tokens=32000,
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
    ) as stream:
        raw = stream.get_final_message().content[0].text
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
    if not text or not text.strip():
        raise ValueError("Sonnet returned an empty response")
    # Complete code fence
    match = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
    if match:
        text = match.group(1)
    else:
        # Truncated code fence — strip the opening fence line if present
        text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError as e:
        print(f"[SONNET] Parse error: {e}\nRaw response (first 500 chars):\n{text[:500]}")
        raise
