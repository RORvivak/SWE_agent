import json
import uuid
import subprocess
from pathlib import Path
from agent.state import AgentState
from config import settings

PROMPT_TEMPLATE = """You are a senior software engineer implementing a plan on this codebase.

PROBLEM:
{problem}

PLAN:
{plan}

FILES TO MODIFY:
{files}

RISKS:
{risks}

Instructions:
1. Read each file listed above (use the Read tool)
2. Implement the plan by writing the updated files to disk (use the Write/Edit tools)
3. Write the following JSON to {result_file}:

{{
  "changed_files": ["relative/path/file.py"],
  "commit_message": "short imperative message",
  "pr_title": "concise PR title under 70 chars",
  "pr_description": "what changed, why, and impact"
}}

Rules:
- Match existing code style exactly
- Minimal changes only — do not refactor unrelated code
- No secrets or credentials
- You MUST write {result_file} as your last action
"""


def generate_code(state: AgentState) -> AgentState:
    print("[SONNET] Generating code...")

    result_file = f"/tmp/eng-agent-{uuid.uuid4().hex[:8]}.json"

    prompt = PROMPT_TEMPLATE.format(
        problem=state["problem"],
        plan="\n".join(f"{i+1}. {step}" for i, step in enumerate(state["plan"])),
        files="\n".join(state["files_to_modify"]),
        risks="\n".join(state["risks"]),
        result_file=result_file,
    )

    result = subprocess.run(
        [settings.claude_bin, "-p", prompt, "--model", "claude-sonnet-4-6",
         "--dangerously-skip-permissions"],
        capture_output=True,
        text=True,
        cwd=settings.repo_path,
        timeout=600,
    )

    if result.returncode != 0:
        raise RuntimeError(f"claude subprocess failed:\n{result.stderr[:500]}")

    result_path = Path(result_file)
    if not result_path.exists():
        raise RuntimeError(
            f"claude did not write result file {result_file}.\n"
            f"stdout (first 300):\n{result.stdout[:300]}"
        )

    parsed = json.loads(result_path.read_text())
    result_path.unlink(missing_ok=True)

    changed_files = parsed.get("changed_files", state["files_to_modify"])
    code_changes = [{"file": f} for f in changed_files]

    print(f"[SONNET] Wrote {len(code_changes)} file(s) to disk")

    return {
        **state,
        "code_changes": code_changes,
        "commit_message": parsed.get("commit_message", ""),
        "pr_title": parsed.get("pr_title", state["ticket_title"]),
        "pr_description": parsed.get("pr_description", ""),
    }
