import json
import re
import anthropic
from pathlib import Path
from agent.state import AgentState
from agent.nodes.validate import _run_checks, _snapshot, _restore, _apply_diffs, _format_failure
from config import settings

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

SYSTEM_PROMPT = """You are a senior software engineer fixing failing tests or lint errors.

Output ONLY valid JSON in this exact shape:
{
  "code_changes": [
    {
      "file": "path/to/file.py",
      "diff": "unified diff string"
    }
  ]
}

Rules:
- Fix only what the error output describes
- Do not change unrelated code
- diff must be a valid unified diff
"""


def fix(state: AgentState) -> AgentState:
    print("[SONNET] Attempting fix...")

    snippets_text = json.dumps(state["code_graph"].get("snippets", []), indent=2)

    fix_prompt = f"""
VALIDATION ERRORS:
{state['failure_message']}

ORIGINAL CHANGES THAT FAILED:
{json.dumps(state['code_changes'], indent=2)}

Fix the errors above.
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
                        "text": fix_prompt,
                    },
                ],
            }
        ],
    )

    raw = response.content[0].text
    result = _parse_json(raw)
    new_changes = result.get("code_changes", [])

    repo = Path(settings.repo_path)
    originals = _snapshot(new_changes, repo)

    apply_error = _apply_diffs(new_changes, repo)
    if apply_error:
        _restore(originals, repo)
        return {
            **state,
            "validation_passed": False,
            "failure_message": f"Fix could not be applied:\n{apply_error}",
        }

    results = _run_checks(repo)
    passed = all(r["passed"] for r in results)

    if not passed:
        _restore(originals, repo)
        failure = _format_failure(results)
        print(f"[SONNET] Fix did not resolve the issue\n{failure}")
        return {
            **state,
            "validation_passed": False,
            "failure_message": failure,
            "code_changes": new_changes,
        }

    print("[SONNET] Fix successful — all checks passed")
    return {
        **state,
        "validation_passed": True,
        "failure_message": None,
        "code_changes": new_changes,
    }


def _parse_json(text: str) -> dict:
    match = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
    if match:
        text = match.group(1)
    return json.loads(text.strip())
