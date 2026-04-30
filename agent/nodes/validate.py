import subprocess
from pathlib import Path
from config import settings
from agent.state import AgentState


def validate(state: AgentState) -> AgentState:
    if settings.skip_validation:
        print("[VALIDATE] SKIP_VALIDATION=true — bypassing all checks")
        return {**state, "validation_passed": True, "failure_message": None}

    repo = Path(settings.repo_path)

    # Snapshot originals so we can rollback on failure without retry
    originals = _snapshot(state["code_changes"], repo)

    # Apply diffs to working tree
    apply_error = _apply_diffs(state["code_changes"], repo)
    if apply_error:
        _restore(originals, repo)
        return {
            **state,
            "validation_passed": False,
            "failure_message": f"Failed to apply diffs:\n{apply_error}",
        }

    # Run checks
    results = _run_checks(repo)
    passed = all(r["passed"] for r in results)

    if not passed:
        # If no retry, rollback immediately
        if not settings.retry:
            _restore(originals, repo)
        failure = _format_failure(results)
        print(f"[VALIDATE] Failed\n{failure}")
        return {
            **state,
            "validation_passed": False,
            "failure_message": failure,
            "status": "blocked",
            "_originals": originals,   # kept for fix node to rollback if needed
        }

    print("[VALIDATE] All checks passed")
    return {**state, "validation_passed": True, "failure_message": None}


def _apply_diffs(code_changes: list[dict], repo: Path) -> str | None:
    for change in code_changes:
        filepath = repo / change["file"]
        content = change.get("content")
        if content is None:
            continue
        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(content, encoding="utf-8")
        except Exception as e:
            return f"Failed to write {change['file']}: {e}"
    return None


def _run_checks(repo: Path) -> list[dict]:
    results = []

    # Detect and run tests
    if (repo / "pytest.ini").exists() or (repo / "pyproject.toml").exists():
        results.append(_run("Tests", ["python3", "-m", "pytest", "--tb=short", "-q"], repo))
    elif (repo / "package.json").exists():
        results.append(_run("Tests", ["npm", "test", "--", "--watchAll=false"], repo))

    # Lint
    if (repo / "pyproject.toml").exists() or list(repo.glob("*.py")):
        results.append(_run("Lint", ["python3", "-m", "ruff", "check", "."], repo))
    elif (repo / "package.json").exists():
        results.append(_run("Lint", ["npx", "eslint", "."], repo))

    return results if results else [{"name": "Checks", "passed": True, "output": "No checks configured"}]


def _run(name: str, cmd: list[str], cwd: Path) -> dict:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=120)
        passed = result.returncode == 0
        return {"name": name, "passed": passed, "output": result.stdout + result.stderr}
    except Exception as e:
        return {"name": name, "passed": False, "output": str(e)}


def _format_failure(results: list[dict]) -> str:
    lines = [""]
    for r in results:
        icon = "✓" if r["passed"] else "✗"
        lines.append(f"{icon} {r['name']}")
        if not r["passed"]:
            lines.append(r["output"].strip())
    return "\n".join(lines)


def _snapshot(code_changes: list[dict], repo: Path) -> dict[str, str | None]:
    originals = {}
    for change in code_changes:
        p = repo / change["file"]
        originals[change["file"]] = p.read_text(encoding="utf-8") if p.exists() else None
    return originals


def _restore(originals: dict[str, str | None], repo: Path) -> None:
    for filepath, content in originals.items():
        p = repo / filepath
        if content is None:
            p.unlink(missing_ok=True)
        else:
            p.write_text(content, encoding="utf-8")
