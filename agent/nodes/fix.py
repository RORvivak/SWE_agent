import re
import json
import subprocess
from pathlib import Path
from agent.state import AgentState
from agent.nodes.validate import _run_checks, _snapshot, _restore, _apply_diffs, _format_failure
from config import settings

PROMPT_TEMPLATE = """You are a senior software engineer fixing failing tests or lint errors.

VALIDATION ERRORS:
{errors}

ORIGINAL FILES THAT FAILED (read them to understand the current state):
{files}

Fix only what the error output describes. Do not change unrelated code.

Output ONLY valid JSON with no other text:
{{
  "code_changes": [
    {{"file": "relative/path/file.py", "content": "complete fixed file content"}}
  ]
}}
"""


def fix(state: AgentState) -> AgentState:
    print("[SONNET] Attempting fix...")

    files_list = "\n".join(f["file"] for f in state["code_changes"])

    prompt = PROMPT_TEMPLATE.format(
        errors=state["failure_message"],
        files=files_list,
    )

    result = subprocess.run(
        [settings.claude_bin, "-p", prompt, "--model", "claude-sonnet-4-6",
         "--dangerously-skip-permissions"],
        capture_output=True,
        text=True,
        cwd=settings.repo_path,
        timeout=300,
    )

    if result.returncode != 0:
        raise RuntimeError(f"claude subprocess failed:\n{result.stderr[:500]}")

    parsed = _parse_json(result.stdout)
    new_changes = parsed.get("code_changes", [])

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
    if not text or not text.strip():
        raise ValueError("claude subprocess returned empty response")
    match = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
    if match:
        text = match.group(1)
    else:
        text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    return json.loads(text.strip())
